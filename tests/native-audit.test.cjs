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
const response = (text, { status = 200, length = null, mime = 'text/html; charset=utf-8' } = {}) => ({
  ok: status >= 200 && status < 300, status, headers: { get: name => name === 'Content-Length' ? length : mime }, text: () => Promise.resolve(text),
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
  assert.deepEqual(p.report().public_vendor_assets, ['https://assets.vizio.com/home.js']);
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

test('follows inert local frame, refresh and inline redirect references within depth and request limits', async () => {
  const pages = {
    [entry]: '<html><iframe src="/scfs/sctv/frame.html?token=PRIVATE"></iframe></html>',
    [base + '/scfs/sctv/frame.html']: '<meta http-equiv=refresh content="0;url=next.html?token=PRIVATE">',
    [base + '/scfs/sctv/next.html']: '<script>window.location.replace("/scfs/sctv/final.html");globalThis.vendorRan=true;</script>',
  };
  const p = page(url => Promise.resolve(response(pages[url] || 'PRIVATE'))); await flush();
  // A depth-two target is inspected but its own references are not followed.
  assert.deepEqual(p.calls.map(c => c.url), [entry, base + '/scfs/sctv/frame.html', base + '/scfs/sctv/next.html']);
  assert.equal(p.report().assets[0].wrapper_signals.iframe_tags, 1);
  assert.equal(p.report().assets[1].wrapper_signals.meta_refresh_tags, 1);
  assert.equal(p.report().assets[2].wrapper_signals.inline_script_tags, 1);
  assert.equal(p.report().assets[2].wrapper_signals.has_location_code, true);
  assert.equal(p.context.vendorRan, undefined);
  assert.ok(!p.output.textContent.includes('PRIVATE'));
});

test('finds unquoted script attributes and resolves relative paths against an inert base tag', async () => {
  const p = page(url => Promise.resolve(response(url === entry ?
    '<html><base href="/scfs/sctv/assets/"><script src=bootstrap.js?secret=PRIVATE></script></html>' : 'var version=1;')));
  await flush();
  assert.deepEqual(p.calls.map(c => c.url), [entry, base + '/scfs/sctv/assets/bootstrap.js']);
  assert.equal(p.report().assets[0].wrapper_signals.has_base_tag, true);
  assert.ok(!p.output.textContent.includes('PRIVATE'));
});

test('reports public redirect assets and escaped URL literals without fetching remote pages or evaluating expressions', async () => {
  const source = '<script>location.href="https://assets.vizio.com/home.html?token=PRIVATE";' +
    'location.replace("/scfs/sctv/partial.html"+userData);' +
    'var asset="https:\\/\\/assets.vizio.com\\/home.js?token=PRIVATE";globalThis.vendorRan=true;</script>';
  const p = page(() => Promise.resolve(response(source))); await flush();
  assert.equal(p.calls.length, 1);
  assert.ok(p.report().public_vendor_assets.includes('https://assets.vizio.com/home.html'));
  assert.ok(p.report().public_vendor_assets.includes('https://assets.vizio.com/home.js'));
  assert.ok(p.report().assets[0].other_references.includes('location: dynamic expression (not evaluated)'));
  assert.ok(!p.output.textContent.includes('PRIVATE'));
  assert.equal(p.context.vendorRan, undefined);
});

test('wrapper references cannot request CGI, another port or service, credentials, or files outside scfs', async () => {
  const source = '<iframe src="http://127.0.0.1:12345/usbparts/sda1/run.cgi"></iframe>' +
    '<meta http-equiv=refresh content="0;url=http://127.0.0.1:7346/app/launch">' +
    '<script>location="http://user:PRIVATE@127.0.0.1:12345/scfs/secret.html";</script>' +
    '<iframe src="/scfs/../../private.html"></iframe>';
  const p = page(() => Promise.resolve(response(source, { mime: 'PRIVATE' }))); await flush();
  assert.equal(p.calls.length, 1);
  assert.ok(!p.output.textContent.includes('PRIVATE'));
  assert.equal(p.report().assets[0].content_type, 'unreported or other');
});

test('cyclic wrappers do not cause repeated requests', async () => {
  const p = page(() => Promise.resolve(response('<iframe src="/scfs/sctv/main.html"></iframe>'))); await flush();
  assert.equal(p.calls.length, 1);
  assert.equal(p.report().audit_version, 2);
  assert.equal(p.report().complete, true);
});
