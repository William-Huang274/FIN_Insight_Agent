/** Browser UI memory only. Runtime authority and saved reports remain on the server. */
export function readMemory<T>(key: string, fallback: T): T {
  try { return JSON.parse(sessionStorage.getItem(`finsight:${key}`) || "null") ?? fallback; } catch { return fallback; }
}
export function writeMemory(key: string, value: unknown) {
  try { sessionStorage.setItem(`finsight:${key}`, JSON.stringify(value)); } catch { /* UI still works with tab-local React state when storage is unavailable. */ }
}
