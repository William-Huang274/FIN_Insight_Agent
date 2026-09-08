import type { Source } from "../api/reportSessions";

/** Legacy saved CALCs expose the same calculation JSON in a source text window. */
export function sourceCalculation(source: Source | null): Source["calculation"] {
  if (!source) return undefined;
  if (source.calculation) return source.calculation;
  if (source.result_state !== "non_authoritative_metric" || !source.text) return undefined;
  try {
    const value = JSON.parse(source.text);
    if (!value || typeof value.expression !== "string" || !value.operands || Array.isArray(value.operands)
      || typeof value.operands !== "object" || !Object.values(value.operands).every(operand =>
        operand && typeof operand === "object" && !Array.isArray(operand))) return undefined;
    return { ...value, value_decimal: source.value_decimal, result_unit: source.unit,
      arithmetic_verified: source.arithmetic_verified, financial_semantics_verified: source.financial_semantics_verified };
  } catch { return undefined; } // Partial/non-JSON windows remain readable as original text.
}
