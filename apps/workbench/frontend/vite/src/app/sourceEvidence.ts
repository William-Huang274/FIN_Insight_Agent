// Prefer the published chunk readback; retain original passage IDs for old releases.
export function evidencePassage(value: Record<string, unknown>): string | undefined {
  const readback = value.readback as {node_id?: string} | undefined;
  if (readback?.node_id) return readback.node_id;
  const chunks = value.chunk_evidence as {id?: string; readback?: {node_id?: string}}[] | undefined;
  if (chunks?.[0]) return chunks[0].readback?.node_id || chunks[0].id;
  const evidence = value.evidence as {id?: string; passage_id?: string}[] | undefined;
  return evidence?.[0]?.id || evidence?.[0]?.passage_id;
}
