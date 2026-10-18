export const POLL_INTERVAL_MS = 15000;

export function localDate(now, timezone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date(now));
  const part = name => parts.find(value => value.type === name).value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function addDays(value, days) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function briefingWindow(now, timezone) {
  const hour = Number(new Intl.DateTimeFormat('en-US', {
    timeZone: timezone, hour: '2-digit', hourCycle: 'h23',
  }).format(new Date(now)));
  const deliveryDate = addDays(localDate(now, timezone), hour >= 18 ? 1 : 0);
  return { deliveryDate, targetDate: addDays(deliveryDate, 1) };
}

export function formatTime(value, timezone = 'America/New_York') {
  if (value == null || !Number.isFinite(new Date(value).getTime())) return 'Unavailable';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: timezone, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  }).format(new Date(value));
}

export function formatDate(value) {
  if (!value) return 'Unavailable';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric',
  }).format(new Date(`${value}T12:00:00Z`));
}

export function formatScore(value) {
  return Number.isFinite(value) && value >= 0 && value <= 10 ? value.toFixed(2) : 'Unavailable';
}

export function siteSummary(row, now) {
  if (activeHold(row, now)) return 'Lightning recorded nearby. Stop work until the timer ends.';
  const alerts = activeAlerts(row, now);
  if (alerts.length) return alerts.map(alert => alert.event).join(' · ');
  if (row.unresolved_reports?.length) return `${row.unresolved_reports.length} crew reports need review.`;
  if (row.flood_advisory?.active) return 'Rain and a nearby stream may affect site access.';
  if (feedState(row, 'official', now) !== 'COMPLETE') return 'Weather warnings need an update.';
  return 'No active official alerts in the available reports.';
}

// Presentation-only exclusions for feeds that have no implemented integration.
// Keep all stored evidence and temporary failures in working integrations intact.
export function isUnimplementedFeed(value) {
  return /^(lightning|lightning feed|automatic lightning detection|wildfire|fire|fire detection|fire detections)$/i.test(String(value).replaceAll('_', ' ').trim());
}

export function displayedMissingLayers(row) {
  return (row.unavailable_layers ?? []).filter(value => !isUnimplementedFeed(value));
}

export function briefingTextForDisplay(text = '') {
  return text.split('\n').filter(line => {
    if (/^Lightning monitoring coverage:/.test(line)) return false;
    const missing = line.match(/^Missing: (.+)\.$/);
    return !missing || !isUnimplementedFeed(missing[1]);
  }).join('\n');
}

export function monitoringSummary(row, now, disconnected = false) {
  const gaps = [];
  if (feedState(row, 'weather', now, disconnected) !== 'COMPLETE') gaps.push('weather needs an update');
  if (feedState(row, 'official', now, disconnected) !== 'COMPLETE') gaps.push('warnings need an update');
  const other = displayedMissingLayers(row).filter(layer => !/weather|official|model|prediction/i.test(layer));
  if (other.length) gaps.push('other monitoring missing');
  return gaps.length ? gaps.join(' · ') : 'Configured checks are up to date';
}

export function activeHold(row, now) {
  const hold = row.lightning_hold;
  return hold && Date.parse(hold.hold_until) > now ? hold : null;
}

export function activeAlerts(row, now) {
  return (row.alerts ?? []).filter(alert => {
    const end = Math.min(Date.parse(alert.expires), alert.ends ? Date.parse(alert.ends) : Infinity);
    return Date.parse(alert.effective) <= now && now < end;
  });
}

export function feedState(row, feed, now, disconnected = false) {
  const monitoring = feed === 'weather' ? row.weather_monitoring : row.official_alerts_monitoring;
  if (!monitoring || monitoring.state === 'UNAVAILABLE') return 'UNAVAILABLE';
  const fetched = feed === 'weather' ? row.weather?.fetched_at : monitoring.fetched_at;
  const age = now - Date.parse(fetched);
  const limit = feed === 'weather' ? 1800000 : 600000;
  if (disconnected || !Number.isFinite(age) || age < 0 || age > limit || monitoring.state === 'STALE') return 'STALE';
  if (feed === 'weather') {
    const valid = row.weather?.current?.time;
    const validAge = now - valid * 1000;
    if (!Number.isFinite(valid) || validAge > limit || validAge < -900000) return 'STALE';
  }
  return monitoring.state;
}

export function hazardState(row, now, disconnected = false) {
  if (activeHold(row, now)) return 'STOP_WORK';
  if (activeAlerts(row, now).length) return 'ALERT';
  if (row.unresolved_reports?.length || row.flood_advisory?.active === true) return 'ELEVATED';
  return feedState(row, 'official', now, disconnected) === 'COMPLETE' ? 'NO_ACTIVE_ALERTS' : 'UNKNOWN';
}

export function coverageState(row, now, disconnected = false) {
  if (['weather', 'official'].some(feed => feedState(row, feed, now, disconnected) === 'STALE')) return 'STALE';
  return row.coverage ?? 'UNAVAILABLE';
}

export const HAZARD_LABELS = {
  STOP_WORK: 'Stop work', ALERT: 'Official alert', ELEVATED: 'Crew report / advisory',
  NO_ACTIVE_ALERTS: 'No active alerts', UNKNOWN: 'Status unknown',
};

export function countdown(hold, now) {
  const seconds = Math.max(0, Math.ceil((Date.parse(hold.hold_until) - now) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function predictionFor(row, now, dayOffset = 1) {
  const prediction = dayOffset === 0 ? row.current_prediction : row.prediction;
  if (!prediction || !Number.isFinite(prediction.score) || prediction.score < 0 || prediction.score > 10) return null;
  if (prediction.stale || prediction.status === 'unavailable') return null;
  const age = now - Date.parse(prediction.computed_at);
  if (!Number.isFinite(age) || age < -1000 || age > 1800000) return null;
  return prediction.valid_date === addDays(localDate(now, row.site.timezone), dayOffset) ? prediction : null;
}

export function predictionReason(row, now, dayOffset = 1) {
  if (predictionFor(row, now, dayOffset)) return '';
  const prediction = dayOffset === 0 ? row.current_prediction : row.prediction;
  if (prediction?.reason) return prediction.reason;
  if (prediction && prediction.valid_date !== addDays(localDate(now, row.site.timezone), dayOffset)) return 'No prediction saved for this local date.';
  if (prediction?.stale || prediction && now - Date.parse(prediction.computed_at) > 1800000) return 'Stored model output is stale; refresh the site forecast.';
  const monitoring = dayOffset === 0 ? row.current_prediction_monitoring : row.prediction_monitoring;
  return monitoring?.reason || prediction?.provenance?.reason || 'No saved model output. The background worker must collect a full daily forecast and calculate this index.';
}

export function rankRows(rows, now) {
  const priority = row => {
    if (activeHold(row, now)) return 0;
    const alerts = activeAlerts(row, now);
    if (alerts.some(alert => ['Extreme', 'Severe'].includes(alert.severity)
      && (/warning/i.test(alert.event) || alert.urgency === 'Immediate'))) return 1;
    if (alerts.length) return 2;
    if (row.unresolved_reports?.length || row.flood_advisory?.active === true) return 3;
    return row.unavailable_layers?.includes('lightning') ? 4 : 5;
  };
  // Preserve the server's order within each priority; only elapsed holds/alerts change groups locally.
  return rows.map((row, order) => ({ row, order }))
    .sort((a, b) => priority(a.row) - priority(b.row) || a.order - b.order)
    .map(({ row }) => row);
}

export function attentionReasons(row, now) {
  const hold = activeHold(row, now);
  const alerts = activeAlerts(row, now);
  const reasons = [];
  if (hold) reasons.push(`Lightning hold · ${countdown(hold, now)} remaining`);
  if (alerts.length) reasons.push(alerts.map(alert => alert.event).join(', '));
  if (row.unresolved_reports?.length) reasons.push(`${row.unresolved_reports.length} unresolved crew report(s)`);
  reasons.push(...(row.reasons ?? []).map(reason => {
    if (/^Incomplete monitoring: /.test(reason)) {
      const layers = reason.slice('Incomplete monitoring: '.length).replace(/\.$/, '').split(', ').filter(value => !isUnimplementedFeed(value));
      return layers.length ? 'Incomplete monitoring: ' + layers.join(', ') + '.' : '';
    }
    return /^(Live strike monitoring is unavailable|Missing strike feed)/.test(reason) ? '' : reason;
  }).filter(Boolean).filter(reason =>
    !/^(Active lightning hold|Official alerts:|\d+ unresolved crew report)/.test(reason)));
  return [...new Set(reasons)];
}
