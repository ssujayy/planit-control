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
  if (row.unresolved_reports?.length) return 'ELEVATED';
  return feedState(row, 'official', now, disconnected) === 'COMPLETE' ? 'NO_ACTIVE_ALERTS' : 'UNKNOWN';
}

export function coverageState(row, now, disconnected = false) {
  if (['weather', 'official'].some(feed => feedState(row, feed, now, disconnected) === 'STALE')) return 'STALE';
  return row.coverage ?? 'UNAVAILABLE';
}

export const HAZARD_LABELS = {
  STOP_WORK: 'Stop work', ALERT: 'Official alert', ELEVATED: 'Crew report',
  NO_ACTIVE_ALERTS: 'No active alerts', UNKNOWN: 'Status unknown',
};

export function countdown(hold, now) {
  const seconds = Math.max(0, Math.ceil((Date.parse(hold.hold_until) - now) / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

export function predictionFor(row, now) {
  const prediction = row.prediction;
  if (!prediction || !Number.isFinite(prediction.score) || prediction.score < 0 || prediction.score > 10) return null;
  return prediction.valid_date === addDays(localDate(now, row.site.timezone), 1) ? prediction : null;
}

export function rankRows(rows, now) {
  const priority = row => {
    if (activeHold(row, now)) return 0;
    const alerts = activeAlerts(row, now);
    if (alerts.some(alert => ['Extreme', 'Severe'].includes(alert.severity)
      && (/warning/i.test(alert.event) || alert.urgency === 'Immediate'))) return 1;
    if (alerts.length) return 2;
    if (row.unresolved_reports?.length) return 3;
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
  reasons.push(...(row.reasons ?? []).filter(reason =>
    !/^(Active lightning hold|Official alerts:|\d+ unresolved crew report)/.test(reason)));
  return [...new Set(reasons)];
}
