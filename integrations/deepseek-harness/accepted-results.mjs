/** Retire accepted child results through native logged surface replacements.
 * Full events and FIN receipts remain immutable. No provider request rewriting.
 */

function receiptOf(event) {
  if (event.type !== 'tool/result' || event.data.message.isError) return null
  const blocks = event.data.message.content ?? []
  if (blocks.length !== 1 || blocks[0].type !== 'text') return null
  try {
    const receipt = JSON.parse(blocks[0].text)
    return receipt.status === 'success' && receipt.receipt_id && receipt.result?.result_digest ? receipt : null
  } catch { return null }
}

export function installAcceptedResults(ctx, post) {
  const states = new WeakMap()
  const track = (state, event) => {
    if (event.type === 'assistant/message') {
      for (const block of event.data.message.content ?? []) {
        if (block.type === 'tool-call') state.calls.set(block.id, block.name)
      }
    }
    if (event.type === 'tool/result') state.results.set(event.seq, event)
  }
  ctx.on('session/event', (session, event) => {
    const state = states.get(session)
    if (state) track(state, event)
  })
  ctx.on('agent/pre-step', async ({agent, signal}, next) => {
    signal.throwIfAborted()
    const session = agent.session
    let state = states.get(session)
    if (!state) {
      state = {calls: new Map(), results: new Map()}
      // Public query API supports restored sessions as well as live sessions.
      // Do not reread/copy the complete native log on every model turn.
      const snapshot = await ctx.sessionQuery.readSurface(session.id)
      for (const event of snapshot.events) track(state, event)
      states.set(session, state)
    }
    const active = new Set(session.surface.nodes)
    const candidates = []
    for (const [seq, event] of state.results) {
      if (!active.has(seq)) { state.results.delete(seq); continue }
      const message = event.data.message
      if (!['mcp__financial__read_research_agent_result', 'mcp__financial__read_next_research_result',
        'mcp__financial__read_research_workpaper', 'mcp__financial__read_workpaper_evidence']
        .includes(state.calls.get(message.toolCallId))) continue
      const receipt = receiptOf(event)
      if (receipt) candidates.push({event, receipt})
    }
    if (candidates.length) {
      const response = await post('/context/accepted-results', {candidates: candidates.map(({receipt}) => ({
        receipt_id: receipt.receipt_id, retired: receipt.result.context_state === 'accepted_result_summary',
      }))}, signal)
      const replacements = new Map(response.replacements.map(r => [r.receipt_id, r]))
      for (const {event, receipt} of candidates) {
        const replacement = replacements.get(receipt.receipt_id)
        if (!replacement || replacement.result_digest !== receipt.result.result_digest) continue
        const text = JSON.stringify(replacement.receipt)
        if (JSON.stringify(receipt) === text) continue
        // A short original may be cheaper than its acceptance envelope. Never
        // discard information merely to increase input; updated/revoked summaries
        // must still be refreshed regardless of their new size.
        if (receipt.result.context_state !== 'accepted_result_summary' &&
            replacement.receipt.result.context_state === 'accepted_result_summary' &&
            text.length >= JSON.stringify(receipt).length) continue
        signal.throwIfAborted()
        if (!session.surface.nodes.includes(event.seq)) throw new Error('FIN acceptance surface changed during projection')
        const message = {...event.data.message, content: [{type:'text', text}]}
        session.append('tool/result', {...event.data, message}, {
          surfaceOp: {op:'replace', startSeq:event.seq, endSeq:event.seq}, sourceEventSeqs:[event.seq],
        })
        state.results.delete(event.seq)
      }
    }
    return next()
  }, {prepend: true}) // Before native pressure measurement/compaction, not after billing.
}
