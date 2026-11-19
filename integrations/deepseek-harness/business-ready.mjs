/** Wait for maintained MCP registration before a native agent is published.
 * The profile's global MCP plugin activates asynchronously; ACP initialization
 * alone does not await that sibling plugin. Do not patch a persisted request
 * header after assembly, or forward an inference with missing capabilities.
 */
import { setTimeout as delay } from 'node:timers/promises'

export async function awaitBusinessTools(tools, agent, signal, timeoutMs = 30_000) {
  const deadline = AbortSignal.timeout(timeoutMs)
  const cancellation = signal ? AbortSignal.any([signal, deadline]) : deadline
  while (true) {
    cancellation.throwIfAborted()
    const schemas = tools.wireSchemas(agent).schemas
    if (schemas.some(tool => tool.name?.startsWith('mcp__financial__'))) return
    try {
      await delay(50, undefined, { signal: cancellation })
    } catch (error) {
      if (signal?.aborted) throw error
      throw new Error('FIN business MCP registration did not become ready before agent publication', { cause: error })
    }
  }
}

export function installBusinessReadiness(ctx) {
  ctx.inject(['tools'], child => {
    child.on('agent/created', ({ agent, signal }) => awaitBusinessTools(child.tools, agent, signal))
  })
}
