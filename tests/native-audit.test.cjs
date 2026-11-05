// Runs our audit script with mock fetch; never connects to a TV or executes vendor JS.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../native-audit.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const base = 'http://127.0.0.1:12345';
const entry = base + '/scfs/sctv/main.html';
const flush = async () => { for (let i = 0; i < 100; i++) await Promise.resolve(); };
const response = (text, { status = 200, length = null } = {}) => ({
  ok: status >= 200 && status < 300, status, headers: { get: () => length }, text: () => Promise.resolve(text),
});

function page(handler, { abort = true } = {}) {
  const calls = [], timers = new Map(); let id = 0;
  const output = { textContent: '', scrollTop: 0, focus() {} };
  const context = {
    URL, document: { getElementById: () => output, addEventListener() {} },
    fetch: (url, options) => { calls.push({ url, options }); return handler(url, options); },
    setTimeout: fn => { const next = ++id; timers.set(next, fn); return next; }, clearTimeout: n => timers.delete(n),
  };
  if (abort) context.AbortController = AbortController;
  vm.runInNewContext(script, context);
  return { calls, context, output, report: () => JSON.parse(output.textContent), expire: () => { for (const fn of [...timers.values()]) fn(); } };
}

test('reads only entry HTML and three local scripts, without executing or uploading source', async () => {
  const source = '<script src="/scfs/sctv/one.js?token=PRIVATE"></script>' +
    '<script src="two.js"></script><script src="three.js"></script><script src="four.js"></script>' +
    '<script src="http://127.0.0.1:7346/app/store/set"></script>' +
    '<script src="http://127.0.0.1:12345/private.js"></script>' +
    '<script src="https://assets.vizio.com/home.js?token=PRIVATE#PRIVATE"></script>' +
    '<script src="https://other.invalid/PRIVATE.js"></script>';
  const p = page(url => Promise.resolve(response(url === entry ? source :
    'globalThis.vendorRan=true; var key="ApplicationFramework:Home:URL"; var token="PRIVATE";')));
  await flush();
  assert.deepEqual(p.calls.map(c => c.url), [entry, base + '/scfs/sctv/one.js', base + '/scfs/sctv/two.js', base + '/scfs/sctv/three.js']);
  for (const { options } of p.calls) {
    assert.equal(options.method, 'GET'); assert.equal(options.credentials, 'omit');
    assert.equal(options.redirect, 'error'); assert.equal(options.headers, undefined); assert.equal(options.body, undefined);
  }
  assert.equal(p.context.vendorRan, undefined);
  assert.ok(!p.output.textContent.includes('PRIVATE'));
  assert.ok(!p.output.textContent.includes('globalThis.vendorRan'));
  assert.deepEqual(p.report().linked_public_vendor_scripts, ['https://assets.vizio.com/home.js']);
  assert.equal(p.report().complete, true);
  assert.match(p.report().coverage, /no native bundle/);
});

test('reports a readable HTTP failure without attempting more assets', async () => {
  const p = page(() => Promise.resolve(response('PRIVATE', { status: 403 })));
  await flush();
  assert.equal(p.calls.length, 1);
  assert.equal(p.report().assets[0].result, 'HTTP 403');
  assert.ok(!p.output.textContent.includes('PRIVATE'));
});

test('network error details are withheld and not misdiagnosed as a definite browser block', async () => {
  const p = page(() => Promise.reject(new Error('PRIVATE'))); await flush();
  assert.match(p.report().assets[0].result, /No readable response/);
  assert.ok(!p.output.textContent.includes('PRIVATE'));
});

test('timeout includes body reads; a late response cannot start follow-up reads', async () => {
  for (const abort of [true, false]) {
    let deliver;
    const p = page(() => Promise.resolve({ ok: true, status: 200, headers: { get: () => null },
      text: () => new Promise(resolve => { deliver = resolve; }) }), { abort });
    await flush(); p.expire(); await flush();
    deliver('<script src="/scfs/sctv/late.js"></script>'); await flush();
    assert.equal(p.calls.length, 1);
    assert.match(p.report().assets[0].result, /Timed out/);
    assert.equal(p.report().complete, true);
  }
});

test('declared oversized assets are rejected without reading the body', async () => {
  let bodyRead = false;
  const p = page(() => Promise.resolve({ ok: true, status: 200, headers: { get: () => 3 * 1024 * 1024 },
    text: () => { bodyRead = true; return Promise.resolve('PRIVATE'); } }));
  await flush();
  assert.equal(bodyRead, false);
  assert.match(p.report().assets[0].result, /exceeds/);
  assert.match(html, /connect-src http:\/\/127\.0\.0\.1:12345/);
});
