/** Complete a durable artifact via the upstream tool conclusion contract. */
export function installDeliveryConclusion(ctx) {
  ctx.on('tools/execute', async (exec, next) => {
    const result = await next()
    const kind = {mcp__financial__deliver_current_report: 'report',
      mcp__financial__deliver_working_note: 'workpaper'}[exec.name]
    if (!kind || result.isError || exec.signal?.aborted) return result
    // Only the named business tool can provide this receipt. Never infer
    // delivery from arbitrary web text, a save result, or an assistant claim.
    const receipts = (result.content ?? []).flatMap(block => {
      if (block.type !== 'text') return []
      try { return [JSON.parse(block.text)] } catch { return [] }
    })
    const confirmed = receipts.some(receipt => receipt.status === 'success' && receipt.receipt_id &&
      receipt.result?.execution_status === 'submitted' && receipt.result.artifact_kind === kind &&
      receipt.result.artifact_digest && (kind !== 'report' || receipt.result.artifact_version === exec.arguments.version))
    if (!confirmed) return result
    exec.concludeTurn()
    // A new wrapper result asks the registry to normalize against its existing
    // output contract; it then observes concludeTurn on this execution.
    return {...result}
  })
}
