"""Period-label arithmetic plus a conservative, advisory-only prose adapter.

The arithmetic never interprets an issuer's calendar. The adapter exposes its
bindings and assumptions, not a semantic verdict. No company/date exceptions,
provider calls, manuscript edits, or model-authored checklist fields.
"""
from dataclasses import dataclass
import re

from .research_graph_contracts import canonical_sha256


@dataclass(frozen=True)
class Period:
    year: int
    part: int
    frequency: int
    basis: str = "unspecified"

    def __post_init__(self):
        if self.frequency not in (1, 2, 4) or not 1 <= self.part <= self.frequency:
            raise ValueError("invalid_period_label")

    @property
    def label(self):
        suffix = {1: "", 2: f"H{self.part}", 4: f"Q{self.part}"}[self.frequency]
        return ("FY" if self.basis == "fiscal" else "") + str(self.year) + suffix

    def shift(self, steps):
        year, part = divmod(self.year * self.frequency + self.part - 1 + steps, self.frequency)
        return Period(year, part + 1, self.frequency, self.basis)


def compare_periods(reference, comparison, relation):
    """Pure label comparison; callers must establish the shared reporting scope."""
    if relation not in {"previous_period", "same_period_prior_year"}:
        raise ValueError("unsupported_period_relation")
    if reference.frequency != comparison.frequency or reference.basis != comparison.basis:
        return {"status": "not_comparable", "expected_label": None}
    expected = reference.shift(-1 if relation == "previous_period" else -reference.frequency)
    return {"status": "consistent" if comparison == expected else "inconsistent",
            "expected_label": expected.label}


_PERIOD = re.compile(
    r"(?<![A-Za-z0-9])(?:(?P<fy>FY)\s*)?(?P<year>\d{4})\s*(?:年\s*)?"
    r"(?P<unit>[QH])\s*(?P<part>[1-4])(?!\d)"
    r"|(?<![A-Za-z0-9])(?P<revunit>[QH])\s*(?P<revpart>[1-4])\s+"
    r"(?:(?P<revfy>FY)\s*)?(?P<revyear>\d{4})(?!\d)"
    r"|(?P<zhyear>\d{4})\s*年\s*第\s*(?P<zhpart>[一二三四1-4])\s*季度", re.I)
# These are surface forms, not financial rules. Unsupported syntax is not
# silently treated as verified. The arithmetic above is independent of language.
_RELATIONS = {
    "上一季度": ("previous_period", 4), "上季度": ("previous_period", 4),
    "上季": ("previous_period", 4), "previous quarter": ("previous_period", 4),
    "prior quarter": ("previous_period", 4),
    "上一半年度": ("previous_period", 2), "previous half-year": ("previous_period", 2),
    "上年同期": ("same_period_prior_year", None), "去年同期": ("same_period_prior_year", None),
    "same period last year": ("same_period_prior_year", None),
    "year-earlier period": ("same_period_prior_year", None),
}
_RELATION = re.compile("|".join(re.escape(x) for x in sorted(_RELATIONS, key=len, reverse=True)), re.I)
_ANCHOR = re.compile(
    r"本(?:期|季|节|段|报告)|当前(?:季度|期间)|研究期间|报告期间|"
    r"\bcurrent (?:quarter|period|half-year)\b|\breporting period\b", re.I)
_COPULA = re.compile(r"分别(?:为|是)|(?:为|是)|\b(?:is|are|represents?)\b", re.I)
_NEGATION = re.compile(r"不是|并非|亦非|均非|非|不应|不能称|不可称|"
                       r"\b(?:not|isn't|aren't)\b", re.I)
_LIST_SEPARATOR = re.compile(r"、|，|,|与|和|以及|及|\band\b", re.I)


def _periods(text):
    result = []
    for match in _PERIOD.finditer(text):
        if match["zhyear"]:
            part = match["zhpart"]
            result.append((match, Period(int(match["zhyear"]),
                int(part) if part.isdigit() else "一二三四".index(part) + 1, 4)))
            continue
        unit = (match["unit"] or match["revunit"]).upper()
        part = int(match["part"] or match["revpart"])
        frequency = 4 if unit == "Q" else 2
        if part > frequency:
            continue
        result.append((match, Period(int(match["year"] or match["revyear"]), part, frequency,
                                     "fiscal" if match["fy"] or match["revfy"] else "unspecified")))
    return result


def _anchors(text):
    """Only explicitly labelled current periods, never the latest number/year."""
    found = []
    for anchor in _ANCHOR.finditer(text):
        tail = text[anchor.end():]
        boundary = re.search(r"[。；;.\n]", tail)
        tail = tail[:boundary.start()] if boundary else tail
        periods = _periods(tail)
        if periods and periods[0][0].start() <= 36:
            match, period = periods[0]
            prefix = tail[:match.start()]
            if not _NEGATION.search(prefix):
                found.append((period, text[anchor.start():anchor.end() + match.end()]))
    return list(dict.fromkeys(found))


def _scopes(text, start=0):
    """Separate parenthetical assertions without inheriting an outer subject.

    Spaces preserve original offsets. A bracket's own explicit proposition can
    still be checked; a subjectless aside cannot borrow an outer list item.
    """
    masked = list(text)
    stack, children = [], []
    for index, char in enumerate(text):
        if char in "(（":
            stack.append(index)
        elif char in ")）" and stack:
            opening = stack.pop()
            if not stack:
                children.extend(_scopes(text[opening + 1:index], start + opening + 1))
                masked[opening:index + 1] = " " * (index + 1 - opening)
    # An unclosed aside is unsupported, not an assertion of the outer subject.
    if stack:
        masked[stack[0]:] = " " * (len(text) - stack[0])
    return [(start, "".join(masked)), *children]


def text_period_analysis(text, *, path, reference_text=None):
    """Return bound affirmative contradictions separately from parser diagnostics.

    Diagnostics never require an author response or a manuscript rewrite.
    Reference text is the same paper only. Explicit ordered complements may
    contain both relative labels and literal periods; neither is a missing slot.
    """
    checks, diagnostics = [], []
    if not isinstance(text, str):
        return {"checks": checks, "diagnostics": diagnostics}
    # Preserve offsets in original text while tolerating Markdown emphasis.
    plain = text.replace("*", " ").replace("`", " ")
    external = _anchors((reference_text or "").replace("*", " "))
    for paragraph in re.finditer(r"[^\n]+", plain):
        paragraph_text = paragraph.group()
        local = _anchors(paragraph_text)
        anchors = local or external
        distinct = {period for period, _ in anchors}
        reference = next(iter(distinct)) if len(distinct) == 1 else None
        scopes = [(base + clause.start(), clause.group())
                  for base, scope in _scopes(paragraph_text)
                  for clause in re.finditer(r"[^。；;.]+", scope)]
        for clause_start, sentence in scopes:
            relations = list(_RELATION.finditer(sentence))
            if not relations:
                continue
            prefix = sentence[:relations[0].start()]
            copulas = list(_COPULA.finditer(prefix))
            if not copulas:
                continue  # mentions of comparisons are not assertions of identity
            copula = copulas[-1]
            subject = prefix[:copula.start()]
            subjects = _periods(subject)
            # Explicit "A is the previous quarter of B" / "A 是 B 的上一季度".
            direct = _periods(prefix[copula.end():])
            ref, binding = reference, "current_period_anchor"
            if len(subjects) == len(relations) == 1:
                after = _periods(sentence[relations[-1].end():])
                if len(direct) == 1 and prefix.rstrip().endswith("的"):
                    ref, binding = direct[0][1], "explicit_relation_reference"
                elif len(after) == 1 and re.match(r"\s+of\b", sentence[relations[-1].end():], re.I):
                    ref, binding = after[0][1], "explicit_relation_reference"
            if not subjects:
                continue
            offset = paragraph.start() + clause_start
            quote = text[offset:offset + len(sentence)]
            predicate_start = copula.end()
            # A direct reference date belongs to the relation, not a list slot.
            direct_binding = binding == "explicit_relation_reference"
            slots = []
            cuts = [predicate_start, *[m.end() for m in
                    _LIST_SEPARATOR.finditer(sentence, predicate_start)], len(sentence)]
            for begin, end in zip(cuts, cuts[1:]):
                slot = sentence[begin:end]
                tokens = [*[(m.start(), m.end(), "relation") for m in _RELATION.finditer(slot)],
                          *[(m.start(), m.end(), "period") for m, _ in _periods(slot)]]
                if _LIST_SEPARATOR.sub("", slot).strip():
                    slots.append((begin, end, len(tokens)))
            # Unknown list items must not disappear and shift later bindings.
            # Token-free trailing commentary is not another period complement.
            paired = (direct_binding or (len(slots) >= len(subjects)
                       and all(count == 1 for _, _, count in slots[:len(subjects)])
                       and all(count == 0 for _, _, count in slots[len(subjects):])))
            for relation_match in relations:
                relation, frequency = _RELATIONS[relation_match.group().lower()]
                slot_index = next((i for i, (a, b, _) in enumerate(slots)
                                   if a <= relation_match.start() < b), None)
                comparison = (subjects[0][1] if direct_binding else
                              subjects[slot_index][1] if paired and slot_index is not None else None)
                # Negation is local to this predicate/complement. Do not invert
                # it into an affirmative error or demand changes to negative prose.
                slot_start = slots[slot_index][0] if slot_index is not None else predicate_start
                negated = bool(_NEGATION.search(sentence[copula.start():predicate_start])
                               or _NEGATION.search(subject[subjects[-1][0].end():])
                               or re.search(r"不\s*$", subject)
                               or _NEGATION.search(sentence[slot_start:relation_match.start()]))
                result = {"status": "binding_unresolved", "expected_label": None}
                if ref and comparison:
                    result = (compare_periods(ref, comparison, relation)
                              if frequency in (None, ref.frequency)
                              else {"status": "not_comparable", "expected_label": None})
                if negated:
                    result = {"status": "negative_or_qualified_proposition", "expected_label": None}
                if result["status"] == "consistent":
                    continue
                item = {
                    "code": "period_relation_requires_check", "path": path,
                    "span": {"start": offset, "end": offset + len(sentence)}, "quote": quote,
                    "relation": relation, "relation_text": relation_match.group(),
                    "reference_label": ref.label if ref else None,
                    "comparison_label": comparison.label if comparison else None,
                    "comparison_candidates": [p.label for _, p in subjects],
                    "reference_candidates": sorted(p.label for p in distinct),
                    "reference_evidence": [evidence for _, evidence in anchors],
                    "binding_basis": binding if paired else "ambiguous_ordered_list",
                    "label_check": result, "blocking": False,
                    "financial_semantics_verified": False,
                    "assumptions": ["Same issuer/reporting calendar; no fiscal-calendar change.",
                                    "Prose parsing does not independently establish financial meaning."],
                }
                item["check_id"] = canonical_sha256({k: item[k] for k in
                    ("path", "quote", "relation", "reference_label", "comparison_label")})
                if result["status"] == "inconsistent":
                    item["instruction"] = (
                        "Check this explicitly bound period relation against its source/calendar. "
                        "The label arithmetic is advisory, not a financial verdict. "
                        "Do not change dates merely to satisfy the check. Saved edits remain intact.")
                    checks.append(item)
                else:
                    item.update(code="period_relation_parse_diagnostic", author_action_required=False)
                    diagnostics.append(item)
    return {"checks": checks, "diagnostics": diagnostics}


def text_period_checks(text, *, path, reference_text=None):
    """Only affirmative, comparable, uniquely bound label contradictions."""
    return text_period_analysis(text, path=path, reference_text=reference_text)["checks"]


def project_period_receipt(receipt):
    """Request-only view: historical advisories are not current task findings.

    Saved receipts remain immutable/readable. The caller supplies fresh checks
    beside the current candidate; no manuscript or financial finding is changed.
    """
    from copy import deepcopy
    projected = deepcopy(receipt)
    # Only traverse native receipt envelopes, never manuscript/source fields.
    # A failed or unacknowledged proposal is still actionable feedback.
    node = projected
    while isinstance(node, dict):
        if node.get("saved") is True and "period_relation_checks" in node:
            node.pop("period_relation_checks")
            if node.get("semantic_check_status") == "period_relations_require_author_check_not_schema_errors":
                node.pop("semantic_check_status")
            node["period_check_view"] = {
                "current_checks_at": "/current_context/submission_to_repair/period_relation_checks",
                "historical_checks": "Available in the original operation receipt; not current findings.",
            }
        if isinstance(node.get("draft_result"), dict):
            node = node["draft_result"]
        elif isinstance(node.get("result"), dict):
            node = node["result"]
        else:
            break
    return projected


def workpaper_period_checks(candidate):
    """Current author assertions only; citations, history and task notes excluded."""
    reference_text = candidate.get("narrative_markdown") or ""
    checks = []
    for key in ("thesis", "mechanism", "narrative_markdown"):
        checks.extend(text_period_checks(candidate.get(key), path="/" + key,
                                         reference_text=reference_text))
    for index, claim in enumerate(candidate.get("claims") or []):
        for key in ("statement", "reasoning_summary"):
            for item in text_period_checks(claim.get(key), path=f"/claims/{index}/{key}",
                                           reference_text=reference_text):
                checks.append({**item, "claim_id": claim.get("claim_id")})
    return checks


def remedy_period_checks(findings, read_paper):
    """Same adapter for proposed Lead remedies, without altering their content."""
    checks = []
    for finding in findings:
        pid = finding.get("paper_id")
        fields = [k for k in ("requested_change", "lead_requested_change") if finding.get(k)]
        if not pid or not fields:
            continue
        paper = read_paper(pid)
        for field in fields:
            for item in text_period_checks(finding[field], path="/" + field,
                                          reference_text=paper.get("narrative_markdown") or ""):
                checks.append({**item, "paper_id": pid, "finding_id": finding.get("finding_id")})
    return checks
