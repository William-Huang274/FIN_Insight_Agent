import { browserOwner } from '../app/IdentityBoundary';

/** Persist the same intent through a lost response/reload. Never retry transport. */
export async function submissionFetch(url: string, init: RequestInit): Promise<Response> {
  if (!['POST', 'PUT', 'PATCH'].includes(init.method || '') || typeof init.body !== 'string') return fetch(url, init);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify([url, init.method, init.body])));
  const fingerprint = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
  const slot = `finsight:submission:${browserOwner}:${fingerprint}`;
  // Refuse a paid dispatch if the browser cannot preserve its receipt key.
  const key = sessionStorage.getItem(slot) || crypto.randomUUID();
  sessionStorage.setItem(slot, key);
  const headers = new Headers(init.headers);
  headers.set('Idempotency-Key', key);
  const response = await fetch(url, {...init, headers});
  // Consume a clone before clearing the key: truncated JSON is also uncertain.
  if (response.ok) {
    await response.clone().json();
    sessionStorage.removeItem(slot);
  }
  return response;
}
