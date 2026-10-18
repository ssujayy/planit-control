import test from 'node:test';
import assert from 'node:assert/strict';
import { activeAlerts, activeHold, attentionReasons, briefingWindow, countdown, coverageState, feedState, formatScore, hazardState, monitoringSummary, predictionFor, predictionReason, rankRows } from '../src/outlook.js';
import { floodAlert, siteRow } from './fixtures.mjs';

const now = Date.parse('2026-10-17T21:59:50Z');
const hold = expiration => ({ hold_until: new Date(expiration).toISOString(), last_strike_at: new Date(expiration - 1800000).toISOString(), source: 'TEST FIXTURE' });

test('different small model scores remain distinguishable and unavailable is never zero', () => {
  assert.deepEqual([.064, .094, .146, 1.25, 0, 10].map(formatScore), ['0.06', '0.09', '0.15', '1.25', '0.00', '10.00']);
  for (const value of [null, undefined, NaN, -1, 11]) assert.equal(formatScore(value), 'Unavailable');
});

test('plain-language monitoring keeps missing lightning visible', () => {
  const row = siteRow(1, now);
  assert.match(monitoringSummary(row, now), /lightning unavailable/);
  assert.match(monitoringSummary(row, now, true), /weather needs an update/);
});

test('an active hold stays STOP_WORK even with unavailable feeds', () => {
  const row = siteRow(1, now, { lightning_hold: hold(now + 1800000), weather: null, weather_monitoring: { state: 'UNAVAILABLE' }, official_alerts_monitoring: { state: 'UNAVAILABLE' } });
  assert.equal(hazardState(row, now, true), 'STOP_WORK');
  assert.equal(countdown(row.lightning_hold, now), '30:00');
});

test('a new persisted expiration extends the visible countdown', () => {
  const row = siteRow(1, now, { lightning_hold: hold(now + 1800000) });
  assert.equal(countdown(row.lightning_hold, now + 600000), '20:00');
  row.lightning_hold = hold(now + 2400000);
  assert.equal(countdown(row.lightning_hold, now + 600000), '30:00');
});

test('expiry clears only the hold and preserves an official flood warning', () => {
  const row = siteRow(1, now, { lightning_hold: hold(now + 1000), alerts: [floodAlert(now)] });
  assert.equal(hazardState(row, now), 'STOP_WORK');
  assert.equal(activeHold(row, now + 1000), null);
  assert.equal(hazardState(row, now + 1000), 'ALERT');
  assert.equal(countdown(row.lightning_hold, now + 5000), '00:00');
});

test('expiry preserves crew evidence and does not hide unavailable monitoring', () => {
  const row = siteRow(1, now, { lightning_hold: hold(now), official_alerts_monitoring: { state: 'UNAVAILABLE' }, unresolved_reports: [{ id: 'fixture', category: 'water' }] });
  assert.equal(hazardState(row, now), 'ELEVATED');
  row.unresolved_reports = [];
  assert.equal(hazardState(row, now), 'UNKNOWN');
  assert.equal(feedState(row, 'official', now), 'UNAVAILABLE');
});

test('an alert ends at the earlier of ends or expires', () => {
  const row = siteRow(1, now, { alerts: [floodAlert(now, { ends: new Date(now + 1000).toISOString() })] });
  assert.equal(activeAlerts(row, now).length, 1);
  assert.equal(activeAlerts(row, now + 1000).length, 0);
});

test('model scores never outrank holds, warnings, or crew evidence', () => {
  const model = siteRow(4, now, { model_index: 10 });
  const report = siteRow(3, now, { unresolved_reports: [{ id: 'report' }] });
  const warning = siteRow(2, now, { alerts: [floodAlert(now)] });
  const lightning = siteRow(1, now, { lightning_hold: hold(now + 1800000) });
  const input = [model, report, warning, lightning];
  assert.deepEqual(rankRows(input, now).map(row => row.site.id), [1, 2, 3, 4]);
  assert.deepEqual(input.map(row => row.site.id), [4, 3, 2, 1]);
});

test('elapsed holds drop below active warnings without stale hold reasons', () => {
  const expired = siteRow(1, now, { lightning_hold: hold(now), reasons: ['Active lightning hold until expired.', 'Missing strike feed.'] });
  const warning = siteRow(2, now, { alerts: [floodAlert(now)] });
  assert.deepEqual(rankRows([expired, warning], now).map(row => row.site.id), [2, 1]);
  assert.deepEqual(attentionReasons(expired, now), ['Missing strike feed.']);
});

test('zero is a real saved score; null, invalid, or bare model_index is unavailable', () => {
  const row = siteRow(1, now, { model_index: 9 });
  assert.equal(predictionFor(row, now), null);
  row.prediction = { valid_date: '2026-10-18', score: 0, computed_at: new Date(now).toISOString() };
  assert.equal(predictionFor(row, now).score, 0);
  for (const score of [null, NaN, Infinity, -1, 11]) {
    row.prediction.score = score;
    assert.equal(predictionFor(row, now), null);
  }
});

test('prediction target follows each site local date and expires at local midnight', () => {
  const at = Date.parse('2026-10-18T04:30:00Z');
  const eastern = siteRow(1, at, { prediction: { valid_date: '2026-10-18', score: 2, computed_at: new Date(at).toISOString() } });
  assert.equal(predictionFor(eastern, at), null);
  const central = { ...eastern, site: { ...eastern.site, timezone: 'America/Chicago' } };
  assert.equal(predictionFor(central, at).score, 2);
});

test('stale, unavailable and undated model outputs cannot masquerade as current scores', () => {
  const row = siteRow(1, now);
  const prediction = { valid_date: '2026-10-18', score: 0, computed_at: new Date(now).toISOString() };
  for (const override of [{ stale: true }, { status: 'unavailable' }, { computed_at: null }, { computed_at: new Date(now - 1800001).toISOString() }]) {
    row.prediction = { ...prediction, ...override };
    assert.equal(predictionFor(row, now), null);
  }
  row.current_prediction = { ...prediction, valid_date: '2026-10-17' };
  assert.equal(predictionFor(row, now, 0).score, 0);
});

test('today and tomorrow indices stay separate and unavailable scores explain the cause', () => {
  const row = siteRow(1, now, {
    current_prediction: { valid_date: '2026-10-17', score: 4.25, computed_at: new Date(now).toISOString() },
    prediction: { valid_date: '2026-10-18', score: 1.75, computed_at: new Date(now).toISOString() },
  });
  assert.equal(predictionFor(row, now, 0).score, 4.25);
  assert.equal(predictionFor(row, now).score, 1.75);
  row.current_prediction = null;
  row.current_prediction_monitoring = { state: 'UNAVAILABLE', reason: 'Missing full daily forecast inputs.' };
  assert.match(predictionReason(row, now, 0), /Missing full daily/);
  assert.equal(predictionReason(row, now), '');
});

test('6 PM delivery dates respect site timezone and distinguish forecast date', () => {
  const at = Date.parse('2026-10-17T22:00:00Z');
  assert.deepEqual(briefingWindow(at, 'America/New_York'), { deliveryDate: '2026-10-18', targetDate: '2026-10-19' });
  assert.deepEqual(briefingWindow(at, 'America/Chicago'), { deliveryDate: '2026-10-17', targetDate: '2026-10-18' });
  assert.deepEqual(briefingWindow(at - 1, 'America/New_York'), { deliveryDate: '2026-10-17', targetDate: '2026-10-18' });
});

test('6 PM local windows remain correct after the fall daylight-saving change', () => {
  assert.deepEqual(briefingWindow(Date.parse('2026-11-01T22:59:59Z'), 'America/New_York'), { deliveryDate: '2026-11-01', targetDate: '2026-11-02' });
  assert.deepEqual(briefingWindow(Date.parse('2026-11-01T23:00:00Z'), 'America/New_York'), { deliveryDate: '2026-11-02', targetDate: '2026-11-03' });
});

test('stale and disconnected monitoring cannot produce a no-active-alerts status', () => {
  const row = siteRow(1, now);
  assert.equal(hazardState(row, now), 'NO_ACTIVE_ALERTS');
  assert.equal(feedState(row, 'official', now + 600001), 'STALE');
  assert.equal(hazardState(row, now + 600001), 'UNKNOWN');
  assert.equal(hazardState(row, now, true), 'UNKNOWN');
  assert.equal(coverageState(row, now, true), 'STALE');
});

test('fresh retrieval cannot conceal an old weather valid time', () => {
  const row = siteRow(1, now);
  row.weather.current.time = Math.floor(now / 1000) - 1801;
  assert.equal(feedState(row, 'weather', now), 'STALE');
});
