export async function getJson(path, signal) {
  const response = await fetch(path, { signal });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

