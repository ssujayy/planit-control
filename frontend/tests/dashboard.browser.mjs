// Dependency-free Chromium smoke check. Serves synthetic fixtures only unless --live URL is supplied.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync } from 'node:fs';
import { mkdtemp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { floodAlert, siteRow } from './fixtures.mjs';

const frontend = fileURLToPath(new URL('../', import.meta.url));
const inventory = process.argv[2] === '--inventory';
const live = ['--live', '--inventory'].includes(process.argv[2]) ? process.argv[3] : null;
const browser = process.env.PLANIT_BROWSER || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
assert.ok(browser, 'Set PLANIT_BROWSER to an installed Chromium executable.');
const started = Date.now();
const hold = expiration => ({ site_id: 1, hold_until: new Date(expiration).toISOString(), last_strike_at: new Date(expiration - 1800000).toISOString(), source: 'TEST FIXTURE', seconds_remaining: 60 });
const model = siteRow(3, started);
model.prediction = { site_id: 3, valid_date: model.planning_weather.target_date, model_version: 'TEST-MODEL', feature_version: 'TEST-FEATURES', score: 9, computed_at: new Date(started).toISOString(), provenance: { model_artifact: 'TEST-ARTIFACT' }, evidence_type: 'experimental_prediction', label: 'experimental model index' };
model.model_index = 9;
model.current_prediction = { ...model.prediction, score: 4.25,
  valid_date: new Intl.DateTimeFormat('en-CA', { timeZone: model.site.timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(started)) };
model.current_model_index = 4.25;
model.unavailable_layers = model.unavailable_layers.filter(layer => layer !== 'model');
const rows = [siteRow(1, started, { lightning_hold: hold(started + 60000) }), siteRow(2, started, { alerts: [floodAlert(started)] }), model];
rows[1].planning_weather = { ...rows[1].planning_weather, heat_index_max_f: 105.9, precipitation_sum_mm: 29, soil_moisture_max_m3_m3: .55 };
let fail = false;
const reports = [];
const photo = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jG2QAAAAASUVORK5CYII=', 'base64');
const requests = [];
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    if (url.pathname.startsWith('/api/')) {
      requests.push(url.pathname);
      response.setHeader('Content-Type', 'application/json');
      if (live) {
        const upstream = await fetch(live + request.url);
        response.writeHead(upstream.status); response.end(await upstream.text()); return;
      }
      if (url.pathname === '/api/reports' && request.method === 'POST') {
        const chunks = []; for await (const chunk of request) chunks.push(chunk);
        const form = await new Request('http://localhost', { method: 'POST', headers: request.headers, body: Buffer.concat(chunks) }).formData();
        assert.ok(form.get('photo').size > 0);
        const siteId = Number(form.get('site_id'));
        const report = { id: 'test-report-' + reports.length, site_id: siteId, category: form.get('category'), note: form.get('note'),
          latitude: Number(form.get('latitude')), longitude: Number(form.get('longitude')), status: 'unresolved',
          observed_at: new Date().toISOString(), photo_url: '/api/reports/fixture/photo' };
        reports.unshift(report); rows.find(row => row.site.id === siteId).unresolved_reports.push(report);
        response.writeHead(201); response.end(JSON.stringify({ report })); return;
      }
      if (url.pathname === '/api/reports') {
        const history = reports.filter(report => report.site_id === Number(url.searchParams.get('site_id'))
          && (!url.searchParams.get('status') || report.status === url.searchParams.get('status'))
          && (!url.searchParams.get('category') || report.category === url.searchParams.get('category'))
          && report.note.includes(url.searchParams.get('q') || ''));
        response.end(JSON.stringify({ history, counts: { total: history.length } })); return;
      }
      if (/^\/api\/reports\/.+\/resolve$/.test(url.pathname)) {
        const report = reports.find(report => report.id === url.pathname.split('/')[3]);
        report.status = 'resolved';
        rows.find(row => row.site.id === report.site_id).unresolved_reports = [];
        response.end(JSON.stringify({ report })); return;
      }
      if (/^\/api\/reports\/.+\/photo$/.test(url.pathname)) { response.setHeader('Content-Type', 'image/png'); response.end(photo); return; }
      if (url.pathname === '/api/briefings') { response.end(JSON.stringify({ briefings: [], count: 0 })); return; }
      if (url.pathname === '/api/briefings/preview') { response.end(JSON.stringify({ preview: true, delivered: false,
        briefing: { body_text: 'TEST FIXTURE preview. No delivery.', forecast_target_date: model.planning_weather.target_date } })); return; }
      const demo = url.searchParams.get('mode') === 'demo';
      if (fail && !demo && url.pathname === '/api/outlook') {
        response.writeHead(503); response.end(JSON.stringify({ error: 'TEST FIXTURE database interruption', code: 'database_unavailable' })); return;
      }
      if (url.pathname === '/api/health') { response.end(JSON.stringify({ application: 'ready', database: 'connected', as_of: new Date().toISOString() })); return; }
      if (url.pathname === '/api/readiness') {
        response.end(JSON.stringify({ storage_mode: demo ? 'demo' : 'live', event_mode: 'live', plant_count: 3,
          lightning: { storage_ready: true, live_feed_connected: false }, reports: { storage_ready: true, upload_api_implemented: false },
          briefings: { storage_ready: true, scheduled_delivery_implemented: false }, model: { storage_ready: true, saved_next_day_predictions: 1 } })); return;
      }
      if (url.pathname === '/api/outlook') {
        const sites = demo ? rows.map(row => ({ ...row, rank: null, weather: null, weather_monitoring: { state: 'UNAVAILABLE' }, official_alerts_monitoring: { state: 'UNAVAILABLE', fetched_at: null }, alerts: null, lightning_hold: null, model_index: null, prediction: null, current_prediction: null, current_model_index: null, planning_weather: null, coverage: 'UNAVAILABLE', hazard_state: null })) : rows;
        response.end(JSON.stringify({ storage_mode: demo ? 'demo' : 'live', event_mode: 'live', as_of: new Date().toISOString(), count: sites.length, ranking_status: demo ? 'not_implemented' : 'evidence_based', weather_freshness_seconds: 1800, sites })); return;
      }
      response.writeHead(404); response.end(JSON.stringify({ error: 'Endpoint not implemented' })); return;
    }
    const file = resolve(frontend, 'dist', url.pathname === '/' ? 'index.html' : '.' + url.pathname);
    assert.ok(file.startsWith(resolve(frontend, 'dist') + '/') || file.startsWith(resolve(frontend, 'dist') + '\\'));
    const extension = file.split('.').at(-1);
    response.setHeader('Content-Type', ({ html: 'text/html', js: 'text/javascript', css: 'text/css', jpg: 'image/jpeg', png: 'image/png' })[extension] || 'application/octet-stream');
    response.end(await readFile(file));
  } catch { response.writeHead(500); response.end('Smoke server failed.'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const profile = await mkdtemp(join(tmpdir(), 'planit-browser-'));
const chrome = spawn(browser, ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'], { windowsHide: true, stdio: 'ignore' });
chrome.on('error', error => { console.error('Browser launch failed:', error.code); });
let socket;
const errors = [];
try {
  let port;
  for (let attempt = 0; attempt < 80; attempt++) {
    try { port = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; break; } catch { await new Promise(resolve => setTimeout(resolve, 100)); }
  }
  assert.ok(port, 'Browser did not expose its debugging port.');
  const tabs = await (await fetch('http://127.0.0.1:' + port + '/json')).json();
  socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  let id = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text + ': ' + (message.params.exceptionDetails.exception?.description || ''));
    if (message.id && pending.has(message.id)) {
      const { resolve, reject, timer } = pending.get(message.id); clearTimeout(timer); pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    }
  });
  function command(method, params = {}) {
    const callId = ++id;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(callId); reject(new Error('CDP timeout: ' + method)); }, 15000);
      pending.set(callId, { resolve, reject, timer }); socket.send(JSON.stringify({ id: callId, method, params }));
    });
  }
  async function evaluate(expression) {
    const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  }
  async function waitFor(expression, timeout = 12000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      if (await evaluate(expression)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('Condition timed out: ' + expression);
  }
  const screenshots = join(frontend, 'dist', 'checks'); await mkdir(screenshots, { recursive: true });
  async function screenshot(name) {
    const result = await command('Page.captureScreenshot', { format: 'png' });
    const path = join(screenshots, name + '.png'); await writeFile(path, Buffer.from(result.data, 'base64')); console.log('Screenshot:', path);
  }
  await command('Runtime.enable'); await command('Page.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://127.0.0.1:' + server.address().port });
  async function selectInventory() {
    await waitFor("!!document.querySelector('.mode select')");
    await evaluate("const choice = document.querySelector('.mode select'); choice.value = 'demo'; choice.dispatchEvent(new Event('change', { bubbles: true }));");
  }
  if (inventory) await selectInventory();
  await waitFor("document.querySelectorAll('.sites button').length === " + (live ? 55 : 3), live ? 25000 : 12000);
  assert.equal(await evaluate("document.querySelector('.mode select').value"), inventory ? 'demo' : 'live');
  assert.equal(await evaluate("!!document.querySelector('.leaflet-marker-icon')"), true);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true);
  assert.equal(await evaluate("document.body.innerText.includes('Foundation build') || document.body.innerText.includes('Fetch current weather')"), false);
  if (inventory) {
    assert.equal(await evaluate("document.querySelector('#reports').textContent.includes('File inventory has no report storage')"), true);
    assert.equal(await evaluate("!!document.querySelector('#reports form')"), false);
    console.log('Actual Flask app: 55 real inventory sites, unavailable monitoring and disabled shared writes verified.');
  } else if (live) {
    await waitFor("!!document.querySelector('#reports form') && !!document.querySelector('#briefings button')");
    assert.equal(await evaluate("[...document.querySelectorAll('.sites button .today-model')].filter(node => !node.textContent.includes('Unavailable')).length"), 55);
    assert.equal(await evaluate("[...document.querySelectorAll('.sites button .tomorrow-model')].filter(node => !node.textContent.includes('Unavailable')).length"), 55);
    for (const position of [0, 1]) {
      const expectedName = await evaluate(`document.querySelectorAll('.sites button')[${position}].querySelector('.queue-name strong').textContent`);
      await evaluate(`document.querySelectorAll('.sites button')[${position}].click()`);
      await waitFor("document.querySelector('#selected-site-title')?.textContent === " + JSON.stringify(expectedName) + " && !document.querySelector('.today-index').textContent.includes('Unavailable')");
      assert.equal(await evaluate("[...document.querySelectorAll('.weather-grid > div')].filter(node => node.querySelector('small')?.textContent.startsWith('Tomorrow')).every(node => !node.querySelector('strong').textContent.includes('Unavailable'))"), true);
    }
    console.log('Live Tiger Data: all 55 today/tomorrow indices, three complete tomorrow metrics, site switching, map, reports and inbox verified.');
  } else {
    await waitFor("!!document.querySelector('#reports form') && !!document.querySelector('#reports .leaflet-marker-icon')");
    await evaluate(`(() => {
      const form = document.querySelector('#reports form');
      form.querySelector('textarea').value = 'TEST FIXTURE pinned wildlife sighting';
      const transfer = new DataTransfer(); transfer.items.add(new File([Uint8Array.from(atob(${JSON.stringify(photo.toString('base64'))}), char => char.charCodeAt(0))], 'test.png', { type: 'image/png' }));
      form.querySelector('[name=photo]').files = transfer.files;
      form.requestSubmit();
    })()`);
    await waitFor("document.querySelector('.history-report')?.textContent.includes('pinned wildlife sighting')");
    assert.equal(reports.length, 1); assert.equal(reports[0].latitude, rows[0].site.latitude);
    await evaluate("document.querySelector('.history-report button').click()");
    await waitFor("document.querySelector('.history-report')?.textContent.includes('Resolved')");
    await evaluate("document.querySelector('#briefings button').click()");
    await waitFor("document.querySelector('.briefing-record')?.textContent.includes('not delivered')");
    console.log('Report form submission, map pin, shared history, resolution and unpersisted briefing preview passed with isolated HTTP fixtures.');
    assert.equal(await evaluate("document.querySelector('.sites button strong').textContent"), 'Fixture plant 1');
    const initialCountdown = await evaluate("document.querySelector('.countdown').textContent");
    assert.match(initialCountdown, /^0[01]:\d{2}$/);
    await waitFor("document.querySelector('.countdown').textContent !== " + JSON.stringify(initialCountdown));
    assert.equal(await evaluate("document.querySelector('.alert-toast').innerText.includes('Stop work')"), true);
    await evaluate("document.querySelector('.alert-toast button').click()");
    await evaluate("[...document.querySelectorAll('.sites button')].find(button => button.innerText.includes('Fixture plant 2')).click()");
    await waitFor("document.querySelector('#selected-site-title').textContent === 'Fixture plant 2'");
    assert.equal(await evaluate("document.querySelector('.official-alert').innerText.includes('Flood Warning')"), true);
    assert.equal(await evaluate("[...document.querySelectorAll('.weather-grid > div')].find(node => node.querySelector('small')?.textContent.includes('forecast rainfall')).querySelector('strong').textContent"), '29 mm');
    assert.equal(await evaluate("[...document.querySelectorAll('.weather-grid > div')].find(node => node.querySelector('small')?.textContent.includes('shallow soil moisture')).querySelector('strong').textContent"), '0.55 m³/m³');
    await evaluate("[...document.querySelectorAll('.sites button')].find(button => button.innerText.includes('Fixture plant 3')).click()");
    await waitFor("document.querySelector('.model-score').textContent.includes('9.0')");
    assert.equal(await evaluate("[...document.querySelectorAll('.sites button')].find(button => button.innerText.includes('Fixture plant 3')).querySelector('.today-model').textContent.includes('4.25')"), true);
    assert.equal(await evaluate("document.querySelector('.today-index').textContent.includes('4.25')"), true);
    rows[0].lightning_hold = hold(Date.now() + 1800000); rows[2].prediction.score = 0; rows[2].model_index = 0;
    console.log('Checking the next automatic poll for hold extension and a saved zero score…');
    await waitFor("document.querySelector('.model-score').textContent.includes('0.0')", 20000);
    assert.equal(await evaluate("document.querySelector('.alert-toast').innerText.includes('Stop work')"), true);
    assert.equal(await evaluate("document.querySelector('#selected-site-title').textContent"), 'Fixture plant 3');
    await evaluate("document.querySelector('.sites button').click()");
    await waitFor("document.querySelector('.countdown')?.textContent.startsWith('29:')");
    await screenshot('fixture-desktop');
    fail = true;
    console.log('Checking a failed poll retains the hold and marks coverage stale…');
    await waitFor("document.querySelector('.error')?.innerText.includes('Updates interrupted')", 20000);
    assert.equal(await evaluate("!!document.querySelector('.countdown')"), true);
    assert.equal(await evaluate("document.querySelector('.reasons-panel .badge').textContent"), 'stale coverage');
    assert.equal(await evaluate("(async () => { document.querySelector('.error button').click(); await new Promise(resolve => setTimeout(resolve, 400)); return !!document.querySelector('.countdown'); })()"), true, 'Retrying must preserve an active hold.');
    await evaluate("const select = document.querySelector('.mode select'); select.value = 'demo'; select.dispatchEvent(new Event('change', { bubbles: true }));");
    await waitFor("document.querySelector('.mode select').value === 'demo' && document.querySelectorAll('.sites button').length === 3");
    assert.equal(await evaluate("!!document.querySelector('.countdown')"), false);
    assert.equal(await evaluate("document.querySelector('.model-score').textContent.includes('—')"), true);
    fail = false;
    console.log('Fixture checks passed: selection, flood evidence, polling, hold extension, zero score, error retention, and file-mode isolation.');
  }
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await command('Page.reload');
  if (inventory) await selectInventory();
  await waitFor("document.querySelectorAll('.sites button').length === " + (live ? 55 : 3), live ? 25000 : 12000);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), true, 'Mobile layout overflows horizontally.');
  await screenshot(live ? 'live-mobile' : 'fixture-mobile');
  await evaluate("document.querySelector('#site-details').scrollIntoView({ behavior: 'instant' })");
  await screenshot(live ? 'live-mobile-details' : 'fixture-mobile-details');
  if (live) {
    await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
    await screenshot('live-desktop');
  }
  assert.equal(requests.some(path => /\/api\/sites\/\d+\/weather/.test(path)), false, 'The dashboard must not trigger provider fetches.');
  assert.deepEqual(errors, [], 'Browser raised JavaScript errors.');
  console.log('Desktop/mobile layout, map rendering, stored-only API requests, and JavaScript checks passed.');
} finally {
  socket?.close(); chrome.kill(); server.close(); server.closeAllConnections();
}
