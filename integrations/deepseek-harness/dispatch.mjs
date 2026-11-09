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
  let toolsVerified = false
  const post = async (path, body, signal, timeoutMs = 30_000) => {
    let response
    try {
      response = await fetch(new URL(path, base), {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body), signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
      })
    } catch (error) {
      throw new Error(`FIN dispatch host transport ${path}: ${error.name}`, { cause: error })
    }
    if (!response.ok) throw new Error(`FIN dispatch host refused ${path}: ${response.status}`)
    return response.json()
  }
  ctx.on('llm/stream', async function* (options, next) {
    if (stopped) throw new Error('FIN execution stopped after a failed or unresolved request')
    if (!toolsVerified && config.requireBusinessTools) {
      // Historical schemas alone do not prove a restored plugin is active.
      const schemas = options.tools ?? []
      if (!schemas.some(tool => tool.name?.startsWith('mcp__financial__'))) {
        stopped = true
        throw new Error('FIN business MCP tools unavailable before first model dispatch')
      }
      toolsVerified = true
    }
    const requestId = randomUUID()
    // Signals and extension callbacks are process-local, not durable payloads.
    const { signal, ...request } = options
    const chunks = []
    let reserved = false, settled = false
    try {
      if (config.waitForConsultations) {
        // Host long-polls completion. No model request, large payload or budget
        // reservation is sent while waiting. Cancellation remains responsive.
        let readiness
        // Readiness includes durable checkpoint/authority reads as well as a
        // 20s wait. It is not a provider request and needs its own bounded
        // transport allowance; the former 30s envelope cancelled live children.
        do { readiness = await post('/calls/ready', {}, signal, 120_000) } while (readiness.status === 'waiting')
        if (readiness.status !== 'ready') throw new Error('FIN consultation admission failed')
      }
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
        const text = chunks.filter(c => c.type === 'text-delta').map(c => c.text ?? '').join('')
        const leakedTools = /<[｜|]{1,2}DSML[｜|]{1,2}\s+(?:calls|function_calls|invoke)\b/u.test(text)
        const success = ['stop', 'tool-calls'].includes(reason) && !leakedTools
        if (!success) stopped = true
        // Preserve the original terminal, including max-tokens, without turning
        // a saved response into successful research. Host persists before yield.
        const receipt = await post('/calls/settle', { requestId, chunks, terminal: reason, stopRequired: !success })
        if (receipt.stopRequired) stopped = true
        settled = true
        if (leakedTools) throw new Error('FIN provider returned textual tool protocol; response retained, no tool executed')
        if (receipt.stopRequired && success) {
          throw new Error('FIN host saved the response but stopped execution; inspect its durable receipt')
        }
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
