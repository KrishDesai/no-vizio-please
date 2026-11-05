// Contract tests for the actual inline TV script. No network or TV commands.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, '../index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const inputPath = '/menu_native/dynamic/tv_settings/devices/current_input';
const secret = 'FAKE-test-only-session-secret';
const ok = (extra = {}) => ({ STATUS: { RESULT: 'SUCCESS' }, ...extra });
const reply = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, text: () => Promise.resolve(JSON.stringify(data)) });
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); };

function page(handler, { abort = true, fetchAvailable = true } = {}) {
  const events = {}, requests = [], timers = new Map(), stored = [];
  let timerId = 0, document;
  function element(dataset = {}, classes = []) {
    const listeners = {}, names = new Set(classes);
    return {
      dataset, textContent: '', style: { display: 'none' },
      classList: {
        add: x => names.add(x), remove: x => names.delete(x), contains: x => names.has(x),
        toggle: (x, on) => on ? names.add(x) : names.delete(x),
      },
      addEventListener: (name, fn) => { listeners[name] = fn; },
      focus() { document.activeElement = this; if (listeners.focus) listeners.focus(); },
      click() { if (listeners.click) listeners.click(); },
    };
  }
  const tiles = [...html.matchAll(/<button class="tile [^"]+" data-name="([^"]+)"(?: data-action="([^"]+)")?/g)]
    .map(m => element({ name: m[1], action: m[2] }, ['tile']));
  const swatches = ['sunset', 'night', 'forest'].map(theme => element({ theme }, ['swatch']));
  const ids = Object.fromEntries(['overlay', 'modalTitle', 'modalDescription', 'swatches', 'time', 'ampm', 'date', 'tvDirectStatus'].map(id => [id, element()]));
  document = {
    body: { dataset: { theme: 'sunset' } }, activeElement: null,
    querySelectorAll: selector => selector === '.tile' ? tiles : swatches,
    getElementById: id => ids[id], addEventListener: (event, fn) => { events[event] = fn; },
  };
  const context = {
    document, location: { protocol: 'https:' }, window: { isSecureContext: true }, navigator: { userAgent: 'Mock TV' },
    localStorage: { getItem: () => null, setItem: (key, value) => stored.push([key, value]) },
    setInterval() {}, setTimeout: (fn, ms) => { const id = ++timerId; timers.set(id, { fn, ms }); return id; },
    clearTimeout: id => timers.delete(id),
  };
  if (abort) context.AbortController = AbortController;
  if (fetchAvailable) context.fetch = (url, options) => {
    requests.push({ url, options });
    return handler(url.replace('http://127.0.0.1:7346', ''), options, requests);
  };
  vm.runInNewContext(script, context);
  function key(key = '', keyCode = 0) { events.keydown({ key, keyCode, preventDefault() {} }); }
  function tick(ms) { for (const [id, timer] of [...timers]) if (timer.ms === ms) { timers.delete(id); timer.fn(); } }
  const visible = () => Object.values(ids).map(el => el.textContent).join('\n');
  return { tiles, ids, requests, stored, key, tick, visible, document, timers };
}

function usual(path) {
  if (path === '/app/get_auth_token') return Promise.resolve(reply(ok({ ITEM: { VALUE: secret } })));
  if (path === inputPath) return Promise.resolve(reply(ok({ ITEMS: [{ CNAME: 'current_input', VALUE: 'HDMI-1', HASHVAL: 42 }] })));
  return Promise.resolve(reply(ok()));
}

test('PS4 stays first and focused; arrows, legacy key codes, OK, Back and Appearance work', async () => {
  const p = page(usual);
  await flush(); p.tick(400);
  assert.deepEqual(p.tiles.map(t => t.dataset.name), ['PS4 (HDMI 3)', 'HDMI 1', 'HDMI 2', 'YouTube', 'Netflix', 'Prime Video', 'Appearance']);
  assert.equal(p.document.activeElement, p.tiles[0]);
  p.key('ArrowLeft'); assert.equal(p.document.activeElement, p.tiles[6]);
  p.key('', 13); assert.equal(p.ids.swatches.style.display, 'flex');
  p.key('', 39); p.key('Enter');
  assert.deepEqual(p.stored, [['quietframe.theme', 'night']]);
  p.key('Backspace'); assert.equal(p.document.activeElement, p.tiles[6]);
  p.key('', 39); assert.equal(p.document.activeElement, p.tiles[0]);
  assert.equal(p.requests.length, 1);
});

test('power probe is read-only and does not claim controls were tested', async () => {
  const p = page(usual); await flush();
  assert.equal(p.requests.length, 1);
  assert.match(p.ids.tvDirectStatus.textContent, /Power read OK/);
  p.key('i'); assert.match(p.visible(), /v8.1-hosted-test/);
  assert.match(p.visible(), /power read only/);
  assert.match(p.visible(), /https:/);
  assert.match(p.visible(), /Mock TV/);
});

for (const [action, namespace, appId] of [['youtube', 5, '1'], ['netflix', 3, '1'], ['prime', 3, '3']]) {
  test(`${action} preserves its verified native mapping and keeps token in loopback requests`, async () => {
    const p = page(usual); await flush();
    p.tiles.find(t => t.dataset.action === action).click(); await flush();
    const writes = p.requests.filter(r => r.options.method === 'PUT');
    assert.equal(writes.length, 1);
    assert.equal(writes[0].url, 'http://127.0.0.1:7346/app/launch');
    assert.deepEqual(JSON.parse(writes[0].options.body), { VALUE: { NAME_SPACE: namespace, APP_ID: appId, MESSAGE: '' } });
    assert.equal(writes[0].options.headers.AUTH, secret);
    for (const { url, options } of p.requests) {
      assert.ok(url.startsWith('http://127.0.0.1:7346/'));
      assert.equal(options.redirect, 'error'); assert.equal(options.mode, 'cors');
      assert.equal(options.credentials, 'omit'); assert.equal(options.cache, 'no-store');
    }
    p.key('Info'); assert.ok(!p.visible().includes(secret)); assert.deepEqual(p.stored, []);
  });
}

for (const [action, target] of [['ps4', 'hdmi3'], ['hdmi1', 'hdmi1'], ['hdmi2', 'hdmi2']]) {
  test(`${action} reads a fresh HASHVAL and sends lowercase ${target}`, async () => {
    let hash = 40;
    const p = page((path, options) => path === inputPath && options.method !== 'PUT'
      ? Promise.resolve(reply(ok({ ITEMS: [{ CNAME: 'current_input', VALUE: 'CAST', HASHVAL: ++hash }] }))) : usual(path));
    await flush();
    for (const expectedHash of [41, 42]) {
      p.tiles.find(t => t.dataset.action === action).click(); await flush();
      const write = p.requests.filter(r => r.options.method === 'PUT').at(-1);
      assert.deepEqual(JSON.parse(write.options.body), { REQUEST: 'MODIFY', VALUE: target, HASHVAL: expectedHash });
      assert.equal(write.options.headers.AUTH, secret);
      p.key('Escape');
    }
  });
}

test('already-selected HDMI is a no-op; invalid HASHVAL never produces a write', async () => {
  for (const state of [
    { ITEMS: [{ VALUE: 'HDMI-3', HASHVAL: 42 }] },
    { ITEMS: [{ VALUE: 'CAST', HASHVAL: '42' }] },
    { ITEMS: {} },
  ]) {
    const p = page(path => path === inputPath ? Promise.resolve(reply(ok(state))) : usual(path));
    await flush(); p.tiles[0].click(); await flush();
    assert.equal(p.requests.filter(r => r.options.method === 'PUT').length, 0);
  }
});

test('network and HTTP errors are distinguished without echoing bodies or raw error details', async () => {
  for (const [handler, expected] of [
    [() => Promise.reject(new TypeError(secret)), /No readable response/],
    [() => Promise.resolve(reply({ secret }, 403)), /HTTP 403/],
    [() => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(secret) }), /Non-JSON/],
    [() => Promise.resolve(reply({ STATUS: { RESULT: secret, DETAIL: secret } })), /did not report SUCCESS/],
    [() => Promise.resolve(reply(null)), /did not report SUCCESS/],
  ]) {
    const p = page(handler); await flush(); p.key('i');
    assert.match(p.visible(), expected); assert.ok(!p.visible().includes(secret));
    assert.ok(!p.ids.tvDirectStatus.textContent.includes('Blocked by browser'));
  }
});

test('token shape failure stops before any authenticated request', async () => {
  const p = page(path => path === '/app/get_auth_token' ? Promise.resolve(reply(ok({ ITEM: { VALUE: { secret } } }))) : usual(path));
  await flush(); p.tiles[3].click(); await flush();
  assert.match(p.visible(), /Token response shape/);
  assert.ok(!p.visible().includes(secret));
  assert.equal(p.requests.filter(r => r.options.headers).length, 0);
});

test('timeout includes body reads; late token arrival never causes a command, with or without AbortController', async () => {
  for (const abort of [true, false]) {
    let deliver;
    const p = page(path => path === '/app/get_auth_token'
      ? Promise.resolve({ ok: true, status: 200, text: () => new Promise(resolve => { deliver = resolve; }) }) : usual(path), { abort });
    await flush(); p.tiles[3].click(); await flush(); p.tick(10000); await flush();
    assert.match(p.visible(), /GET \/app\/get_auth_token: Timed out/);
    deliver(JSON.stringify(ok({ ITEM: { VALUE: secret } }))); await flush();
    assert.equal(p.requests.filter(r => r.options.method === 'PUT').length, 0);
    assert.equal(p.timers.size, 1); // Initial focus timer only.
  }
});

test('pending write blocks duplicate commands and a timeout is treated as uncertain, without retry', async () => {
  const p = page((path, options) => options.method === 'PUT' ? new Promise(() => {}) : usual(path));
  await flush(); p.tiles[3].click(); await flush(); p.key('Escape'); p.tiles[3].click(); await flush();
  assert.equal(p.requests.filter(r => r.options.method === 'PUT').length, 1);
  p.tick(10000); await flush(); p.key('i');
  assert.match(p.visible(), /outcome is unknown/);
  assert.equal(p.requests.filter(r => r.options.method === 'PUT').length, 1);
});

test('late action completion does not overwrite an Appearance dialog opened after Back', async () => {
  let accept;
  const p = page((path, options) => options.method === 'PUT' ? new Promise(resolve => { accept = resolve; }) : usual(path));
  await flush(); p.tiles[3].click(); await flush(); p.key('Escape'); p.tiles[6].click();
  accept(reply(ok())); await flush();
  assert.equal(p.ids.modalTitle.textContent, 'Appearance');
  assert.match(p.ids.modalDescription.textContent, /Choose a background/);
});

test('missing fetch produces a readable unsupported-browser diagnosis', async () => {
  const p = page(usual, { fetchAvailable: false }); await flush(); p.key('', 457);
  assert.match(p.visible(), /no Fetch API/);
});

test('a slow initial probe does not overwrite a successful action status', async () => {
  let finishProbe;
  const p = page(path => path === '/state/device/power_mode'
    ? new Promise(resolve => { finishProbe = resolve; }) : usual(path));
  await flush(); p.tiles[3].click(); await flush();
  finishProbe(reply(ok())); await flush();
  assert.equal(p.ids.tvDirectStatus.textContent, 'TV controls · Command accepted');
});
