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
    r"(?:(?P<revfy>FY)\s*)?(?P<revyear>\d{4})(?!\d)", re.I)
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
_NEGATION = re.compile(r"不是|并非|不应|不能称|不可称|\b(?:not|isn't|aren't)\b", re.I)


def _periods(text):
    result = []
    for match in _PERIOD.finditer(text):
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


def text_period_checks(text, *, path, reference_text=None):
    """Locate explicit assertions; ambiguous bindings remain nonblocking checks.

    Reference text is the same paper only (e.g. Lead's requested remedy against
    that paper). No reference period is selected across papers, or from as-of /
    publication dates. Ordered lists need equally many periods and relations.
    """
    if not isinstance(text, str):
        return []
    # Preserve offsets in original text while tolerating Markdown emphasis.
    plain = text.replace("*", " ").replace("`", " ")
    external = _anchors((reference_text or "").replace("*", " "))
    checks = []
    for paragraph in re.finditer(r"[^\n]+", plain):
        paragraph_text = paragraph.group()
        local = _anchors(paragraph_text)
        anchors = local or external
        distinct = {period for period, _ in anchors}
        reference = next(iter(distinct)) if len(distinct) == 1 else None
        for clause in re.finditer(r"[^。；;.]+", paragraph_text):
            sentence = clause.group()
            relations = list(_RELATION.finditer(sentence))
            if not relations:
                continue
            prefix = sentence[:relations[0].start()]
            if _NEGATION.search(prefix):
                continue
            copulas = list(_COPULA.finditer(prefix))
            if not copulas:
                continue  # mentions of comparisons are not assertions of identity
            subject = prefix[:copulas[-1].start()]
            subjects = _periods(subject)
            # Explicit "A is the previous quarter of B" / "A 是 B 的上一季度".
            direct = _periods(prefix[copulas[-1].end():])
            ref, binding = reference, "current_period_anchor"
            if len(subjects) == len(relations) == 1:
                after = _periods(sentence[relations[-1].end():])
                if len(direct) == 1 and prefix.rstrip().endswith("的"):
                    ref, binding = direct[0][1], "explicit_relation_reference"
                elif len(after) == 1 and re.match(r"\s+of\b", sentence[relations[-1].end():], re.I):
                    ref, binding = after[0][1], "explicit_relation_reference"
            if not subjects:
                continue
            offset = paragraph.start() + clause.start()
            quote = text[offset:offset + len(sentence)]
            paired = len(subjects) == len(relations)
            for index, relation_match in enumerate(relations):
                relation, frequency = _RELATIONS[relation_match.group().lower()]
                comparison = subjects[index][1] if paired else None
                result = {"status": "binding_unresolved", "expected_label": None}
                if ref and comparison:
                    result = (compare_periods(ref, comparison, relation)
                              if frequency in (None, ref.frequency)
                              else {"status": "not_comparable", "expected_label": None})
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
                                    "Prose parsing and reference binding require author confirmation."],
                    "instruction": "Check the quoted period relation and its reference against the table/source. "
                        "If this binding is wrong, explain the actual reference/calendar in the manuscript. "
                        "Do not substitute another date merely to satisfy this check. Saved edits remain intact.",
                }
                item["check_id"] = canonical_sha256({k: item[k] for k in
                    ("path", "quote", "relation", "reference_label", "comparison_label")})
                checks.append(item)
    return checks


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
