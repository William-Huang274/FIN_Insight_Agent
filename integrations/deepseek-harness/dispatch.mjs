/** FIN request accounting seam, using upstream llm/stream (no agent loop fork).
 *
 * One process belongs to one admitted host execution. The host owns the opaque
 * run grant, TokenBudgetBasis, price snapshot, durable reservations and resume
 * admission. This plugin cannot authorize research or increase its budget.
 * The bridge is opt-in until that host endpoint is qualified and deployed.
 */
import { randomUUID } from 'node:crypto'

export function apply(ctx, config) {
  const base = new URL(config.endpoint)
  if (base.protocol !== 'http:' || !['127.0.0.1', '[::1]'].includes(base.hostname)) {
    throw new Error('FIN dispatch endpoint must be an explicit loopback sidecar')
  }
  const token = process.env[config.tokenEnv]
  if (!token) throw new Error('FIN dispatch credential unavailable')
  let stopped = false
  const post = async (path, body) => {
    const response = await fetch(new URL(path, base), {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(body), signal: AbortSignal.timeout(30_000),
    })
    if (!response.ok) throw new Error(`FIN dispatch host refused ${path}: ${response.status}`)
    return response.json()
  }
  ctx.on('llm/stream', async function* (options, next) {
    if (stopped) throw new Error('FIN execution stopped after a failed or unresolved request')
    const requestId = randomUUID()
    // Signals and extension callbacks are process-local, not durable payloads.
    const { signal, ...request } = options
    const chunks = []
    let reserved = false, settled = false
    try {
      const admission = await post('/calls/reserve', { requestId, request })
      if (admission.status !== 'reserved') throw new Error('FIN request not admitted')
      reserved = true
      for await (const chunk of next()) {
        chunks.push(chunk)
        if (chunk.type !== 'finish') {
          yield chunk
          continue
        }
        const reason = chunk.reason?.kind
        const success = ['stop', 'tool-calls'].includes(reason)
        if (!success) stopped = true
        // Preserve the original terminal, including max-tokens, without turning
        // a saved response into successful research. Host persists before yield.
        await post('/calls/settle', { requestId, chunks, terminal: reason, stopRequired: !success })
        settled = true
        yield chunk
      }
      if (!settled) throw new Error('FIN provider stream ended without a terminal result')
    } catch (error) {
      stopped = true
      throw error
    } finally {
      if (reserved && !settled) {
        stopped = true
        // No request abort signal here: cancellation must still leave a receipt.
        // A failed settlement leaves the durable pre-dispatch reservation open.
        try { await post('/calls/unknown', { requestId, chunks }) } catch { /* reservation remains */ }
      }
    }
  })
}
