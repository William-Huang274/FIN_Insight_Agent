import {randomUUID} from 'node:crypto'
/** Retire accepted child results through native logged surface replacements.
 * Full events and FIN receipts remain immutable. No provider request rewriting.
 */

const sourceTools = ['read_public_source','read_source_document','read_research_source','read_company_library','read_legislation']
const journalTools = new Set(['read_saved_result','assess_research_result','publish_research_workpaper', ...sourceTools])
const fingerprint = receipt => receipt.result?.result_digest || receipt.result?.source_snapshot_sha256 || receipt.receipt_id

function receiptOf(event, tool) {
  if (event.type !== 'tool/result' || event.data.message.isError) return null
  const blocks = event.data.message.content ?? []
  if (blocks.length !== 1 || blocks[0].type !== 'text') return null
  try {
    const receipt = JSON.parse(blocks[0].text)
    return receipt.receipt_id && (journalTools.has(tool) ||
      (receipt.status === 'success' && (receipt.result?.result_digest || receipt.result?.source_snapshot_sha256))) ? receipt : null
  } catch { return null }
}

const isRetired = receipt => ['inspected_research_window','resolved_research_feedback','accepted_result_summary', 'superseded_authoring_view', 'duplicate_material_window', 'deduplicated_search_navigation', 'saved_chapter_material', 'unused_authoring_material', 'chapter_argument_view'].includes(receipt.result?.context_state)

export function installAcceptedResults(ctx, post) {
  const states = new WeakMap()
  const track = (state, event) => {
    if (event.type === 'user/message' && event.data.source?.kind === 'fin-research-control') state.control = event
    if (event.type === 'assistant/message') {
      if (event.data.message.content?.some(block => block.type === 'tool-call')) {
        state.previousBatch = state.latestBatch
        state.latestBatch = event.seq
      }
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
        'mcp__financial__reuse_adopted_judgment', 'mcp__financial__read_research_workpaper', 'mcp__financial__read_workpaper_evidence',
        'mcp__financial__read_authoring_context', 'mcp__financial__read_synthesis_material', 'mcp__financial__read_public_source',
        'mcp__financial__read_saved_result', 'mcp__financial__calculate_research_metric',
        'mcp__financial__assess_research_result','mcp__financial__publish_research_workpaper',
        ...sourceTools.map(name => 'mcp__financial__'+name)]
        .includes(state.calls.get(message.toolCallId))) continue
      const receipt = receiptOf(event, state.calls.get(message.toolCallId).split('__').at(-1))
      if (receipt) candidates.push({event, receipt})
    }
    let control
    {
      const response = await post('/context/accepted-results', {candidates: candidates.map(({receipt,event}) => ({
        receipt_id: receipt.receipt_id, retired: isRetired(receipt), context_state: receipt.result?.context_state,
        inspected: (event.sourceEventSeqs?.[0] ?? event.seq) < state.previousBatch,
      }))}, signal, 120_000)
      control = response.control_state
      const replacements = new Map(response.replacements.map(r => [r.receipt_id, r]))
      const visible = new Map(candidates.map(({event,receipt}) => [receipt.receipt_id,event.seq]))
      for (const {event, receipt} of candidates) {
        const replacement = replacements.get(receipt.receipt_id)
        if (!replacement || replacement.result_digest !== fingerprint(receipt)) continue
        const projected = replacement.receipt.result ?? {}
        const dependencies = projected.active_window_receipts ?? (projected.current_view_receipt_id ? [projected.current_view_receipt_id] : [])
        if (dependencies.some(id => !session.surface.nodes.includes(visible.get(id)))) continue
        const text = JSON.stringify(replacement.receipt)
        if (JSON.stringify(receipt) === text) continue
        // A short original may be cheaper than its acceptance envelope. Never
        // discard information merely to increase input; updated/revoked summaries
        // must still be refreshed regardless of their new size.
        if (!isRetired(receipt) && isRetired(replacement.receipt) &&
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
    const prior = state.control
    const visible = prior && session.surface.nodes.includes(prior.seq)
    const same = visible && prior.data.source.generation === control?.generation
    const message = control ? {
      id:randomUUID(), role:'user', source:{kind:'fin-research-control',generation:control.generation},
      content:[{type:'text',text:'[Runtime research state; not a new user instruction]\n'+JSON.stringify(control.state)}],
    } : null
    if (message && visible && !same) {
      session.append('user/message', message, {
        surfaceOp:{op:'replace',startSeq:prior.seq,endSeq:prior.seq},sourceEventSeqs:[prior.seq],
      })
    }
    const decision = await next()
    const current = state.control
    const retained = current && session.surface.nodes.includes(current.seq) && current.data.source.generation === control?.generation
    if (!message || retained || !decision || decision.kind === 'reject') return decision
    // Use the native pre-step message admission contract, as native context
    // notices do. Compacted-away state is rebuilt from SQLite, not the summary.
    return {...decision,messages:[...decision.messages,message]}
  }, {prepend: true}) // Before native pressure measurement/compaction, not after billing.
}
