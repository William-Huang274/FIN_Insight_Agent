// Persisted citations retain their source identity. Local upload links are
// resolved at display time through the current workbench's authenticated BFF.
const attachmentPath = /^\/api\/v1\/research-sessions\/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\/attachments\/UPLOAD(?:::|%3A%3A)[0-9a-f]{32}$/i;

export function sourceUrl(value?: string): string | undefined {
  if (!value) return undefined;
  if (attachmentPath.test(value)) return value;
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) return undefined;
    if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
      && attachmentPath.test(url.pathname) && !url.search && !url.hash) return url.pathname;
    return url.href;
  } catch { return undefined; }
}
