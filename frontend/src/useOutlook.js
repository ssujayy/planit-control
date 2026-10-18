import { useEffect, useState } from 'react';
import { getJson } from './api';
import { POLL_INTERVAL_MS } from './outlook';

export default function useOutlook(mode, retry) {
  const [state, setState] = useState({ outlook: null, readiness: null, health: null, loading: true, error: '', readinessError: '', offset: 0 });
  useEffect(() => {
    const controller = new AbortController();
    let timer, cycle = 0;
    setState(previous => previous.outlook?.storage_mode === mode
      ? { ...previous, loading: false }
      : { outlook: null, readiness: null, health: null, loading: true, error: '', readinessError: '', offset: 0 });
    async function refresh() {
      const checkCapabilities = cycle++ % 4 === 0;
      const results = await Promise.allSettled([
        getJson(`/api/outlook?mode=${mode}`, controller.signal).then(data => {
          if (!Array.isArray(data.sites) || data.storage_mode !== mode || data.event_mode !== 'live') {
            throw new Error('The server returned an unsupported Outlook response.');
          }
          return data;
        }),
        ...(checkCapabilities ? [
          getJson(`/api/readiness?mode=${mode}`, controller.signal),
          getJson('/api/health', controller.signal),
        ] : []),
      ]);
      if (controller.signal.aborted) return;
      setState(previous => {
        const next = { ...previous, loading: false };
        const [outlook, readiness, health] = results;
        if (outlook.status === 'fulfilled') {
          next.outlook = outlook.value;
          next.error = '';
          const serverTime = Date.parse(outlook.value.as_of);
          next.offset = Number.isFinite(serverTime) ? serverTime - Date.now() : 0;
        } else next.error = outlook.reason.message || 'Stored site evidence could not be loaded.';
        if (readiness) {
          next.readiness = readiness.status === 'fulfilled' ? readiness.value : null;
          next.readinessError = readiness.status === 'rejected' ? 'Integration status could not be checked.' : '';
        }
        if (health) next.health = health.status === 'fulfilled' ? health.value : { database: 'unavailable' };
        return next;
      });
      timer = setTimeout(refresh, POLL_INTERVAL_MS);
    }
    refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [mode, retry]);
  return state;
}
