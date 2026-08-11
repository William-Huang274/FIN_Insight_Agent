"""One exact, approval-gated SEC Archives document retrieval and table parse.

The module intentionally stores only digests, selectors and parsed lineage.
The raw HTML exists only in process memory for the single bounded operation and
is never written to Git, the object store, or the canonical SQLite payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import hashlib
import re
from typing import Any, Callable, Literal, Protocol
from urllib.parse import urlparse

import requests
from pydantic import Field, model_validator

from .bounded_sec_metadata_execution import SingleCallSecSubmissionsClient
from .budget_control import BudgetControlService, BudgetReservationRequest
from .capability_security import CapabilitySecurityError, CapabilitySecurityService, SandboxAdmissionRequest, SecurityAdmissionDecision
from .evidence_request import EvidenceRequest
from .facade import RuntimeFacade
from .m6_pilot_global_approval import M6GlobalOneShotApprovalReceipt, M6GlobalOneShotApprovalService, build_m6_pilot_scope
from .m6_pilot_package import M6PilotPackageDigest
from .models import CommandEnvelope, ScopedVersion, StrictModel, canonical_digest, utc_now
from .tool_planner import ToolSelectionPlan


class BoundedSecDocumentExecutionError(RuntimeError):
    """Typed fail-closed error for the positive single-document pilot."""


class SecDocumentTransportError(BoundedSecDocumentExecutionError):
    """The exact send may have reached SEC; retry is forbidden."""


class SecDocumentParseError(BoundedSecDocumentExecutionError):
    """The fetched source cannot form the approved candidate/parser chain."""


class HttpSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> requests.Response: ...


class _FailClosedHttpSession:
    """Default transport for importable code and tests; never opens a socket."""

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        raise SecDocumentTransportError("sec_document_network_transport_must_be_explicitly_injected")


class SecDocumentTableSelector(StrictModel):
    table_heading_normalized: str = Field(min_length=1)
    unit_caption_normalized: str = Field(min_length=1)
    row_label_normalized: str = Field(min_length=1)
    column_period_normalized: str = Field(min_length=1)
    xbrl_concept_hint: str = Field(min_length=1)
    financial_statement_role: Literal["consolidated_primary_financial_statement"] = "consolidated_primary_financial_statement"


class BoundedSecDocumentExecutionPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    approval_ref: Literal["approve_m6_3_5_single_sec_document_positive_retrieval_parser_pilot_only"]
    approved_execution_scope: Literal["single_sec_document_positive_retrieval_parser_pilot_only"]
    tool_id: Literal["issuer_filing_document_table_tool"]
    route_id: Literal["issuer_filing_document_table_route"]
    capability: Literal["evidence.document.read"]
    required_registry_snapshot_id: str = Field(min_length=1)
    allowed_network_host: Literal["www.sec.gov"]
    exact_path: str = Field(min_length=1)
    allowed_cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    form_type: Literal["10-K"]
    report_period: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    target_table_selector: SecDocumentTableSelector
    source_authority_rank: Literal[4] = 4
    max_external_calls: Literal[1] = 1
    max_fallback_calls: Literal[0] = 0
    max_retry_calls: Literal[0] = 0
    timeout_seconds: int = Field(ge=1, le=30)
    user_agent_environment_variable: str = Field(min_length=1)
    user_agent_scope_confirmation_environment_variable: str = Field(min_length=1)
    user_agent_min_length: int = Field(ge=20, le=256)
    forbidden_user_agent_values: tuple[str, ...] = Field(min_length=1)

    @property
    def exact_url(self) -> str:
        return f"https://{self.allowed_network_host}{self.exact_path}"


class SecDocumentFetchResult(StrictModel):
    source_url: str
    source_host: Literal["www.sec.gov"]
    response_status_code: int = Field(ge=200, lt=300)
    document_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_byte_length: int = Field(ge=1)
    raw_document_persisted: Literal[False] = False


class ExtractedTableValue(StrictModel):
    table_index: int = Field(ge=0)
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    table_coordinate: str = Field(min_length=1)
    table_heading_normalized: str = Field(min_length=1)
    unit_caption_normalized: str = Field(min_length=1)
    row_label_normalized: str = Field(min_length=1)
    column_period_normalized: str = Field(min_length=1)
    normalized_period: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    unit: Literal["USD_millions"] = "USD_millions"
    financial_statement_role: Literal["consolidated_primary_financial_statement"]
    raw_value: str = Field(min_length=1)
    parsed_value: str = Field(min_length=1)


class SecDocumentInvocationReceiptVersion(ScopedVersion):
    case_id: str
    invocation_id: str = Field(min_length=1)
    invocation_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    invocation_state: Literal["prepared", "blocked_before_send", "send_authorized", "send_started", "succeeded", "outcome_unknown", "aborted_before_send_reconciled"]
    downstream_status: Literal["not_started", "source_received", "positive_chain_persisted", "typed_terminal_stop", "not_available"]
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(min_length=1)
    registry_snapshot_id: str = Field(min_length=1)
    registry_snapshot_digest: str = Field(min_length=1)
    policy_ref: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_ref: str = Field(min_length=1)
    global_approval_id: str = Field(min_length=1)
    global_approval_nonce_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    global_approval_activation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    global_approval_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    global_approval_store_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_execution_scope: Literal["single_sec_document_positive_retrieval_parser_pilot_only"]
    target_cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str = Field(min_length=1)
    endpoint_host: Literal["www.sec.gov"]
    endpoint_path: str = Field(min_length=1)
    capability_grant_id: str = Field(min_length=1)
    admission_decision_id: str = Field(min_length=1)
    admission_decision_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    budget_reservation_id: str = Field(min_length=1)
    external_call_count: int = Field(ge=0, le=1)
    fallback_call_count: Literal[0] = 0
    retry_call_count: Literal[0] = 0
    request_sent_at: datetime | None = None
    send_authorized_at: datetime | None = None
    send_started_at: datetime | None = None
    user_agent_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_at: datetime | None = None
    source_document: SecDocumentFetchResult | None = None
    source_document_digest: str | None = None
    error_code: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_raw_nonce_from_new_receipts(cls, value: Any) -> Any:
        """Convert historic raw nonce rows only for read-only quarantine paths.

        New records must be constructed with `global_approval_nonce_sha256`.
        Keeping this conversion permits deterministic inspection of historic
        evidence without rewriting it, while its old content digest prevents
        it from being reused as valid v5 authority.
        """
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        raw_nonce = payload.pop("global_approval_nonce", None)
        if raw_nonce is not None:
            digest = hashlib.sha256(str(raw_nonce).encode("utf-8")).hexdigest()
            existing = payload.get("global_approval_nonce_sha256")
            if existing is not None and existing != digest:
                raise ValueError("global_approval_nonce_digest_mismatch")
            payload["global_approval_nonce_sha256"] = digest
        return payload

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentInvocationReceiptVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class SecDocumentCandidateVersion(ScopedVersion):
    case_id: str
    execution_instance_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    candidate_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_document_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_authority_rank: Literal[4] = 4
    table_coordinate: str = Field(min_length=1)
    table_heading_normalized: str = Field(min_length=1)
    unit_caption_normalized: str = Field(min_length=1)
    row_label_normalized: str = Field(min_length=1)
    column_period_normalized: str = Field(min_length=1)
    normalized_period: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    financial_statement_role: Literal["consolidated_primary_financial_statement"]
    xbrl_concept_hint: str = Field(min_length=1)
    promotion_status: Literal["unpromoted"] = "unpromoted"
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentCandidateVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class SecDocumentParserVersion(ScopedVersion):
    case_id: str
    execution_instance_id: str = Field(min_length=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_candidate_id: str = Field(min_length=1)
    parser_candidate_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    candidate_version_ref: str = Field(min_length=1)
    candidate_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    table_coordinate: str = Field(min_length=1)
    parsed_table_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_policy_ref: str = Field(min_length=1)
    parse_status: Literal["parsed_unpromoted"] = "parsed_unpromoted"

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentParserVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class SecDocumentNumericFactVersion(ScopedVersion):
    case_id: str
    execution_instance_id: str = Field(min_length=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_fact_id: str = Field(min_length=1)
    normalized_fact_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    parser_candidate_version_ref: str = Field(min_length=1)
    parser_candidate_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_label_normalized: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    unit: Literal["USD_millions"]
    scale_multiplier: Literal[1000000] = 1000000
    period: str = Field(min_length=1)
    source_coordinate: str = Field(min_length=1)
    promotion_status: Literal["unpromoted"] = "unpromoted"

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentNumericFactVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class SecDocumentNumericTraceVersion(ScopedVersion):
    case_id: str
    execution_instance_id: str = Field(min_length=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    numeric_trace_id: str = Field(min_length=1)
    numeric_trace_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    normalized_fact_version_ref: str = Field(min_length=1)
    normalized_fact_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    program_steps: tuple[str, ...] = Field(min_length=1)
    output_value: str = Field(min_length=1)
    promotion_status: Literal["unpromoted"] = "unpromoted"
    writer_citable: Literal[False] = False

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentNumericTraceVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class SecDocumentTerminalStopVersion(ScopedVersion):
    case_id: str
    terminal_stop_id: str = Field(min_length=1)
    terminal_stop_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    receipt_version_ref: str = Field(min_length=1)
    receipt_content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    stop_code: str = Field(min_length=1)
    attempt_budget: Literal[0] = 0
    sourcehunter_admission: Literal["not_admitted"] = "not_admitted"
    retry_admission: Literal["not_admitted"] = "not_admitted"

    @classmethod
    def create(cls, **payload: Any) -> "SecDocumentTerminalStopVersion":
        draft = cls(**{**payload, "content_digest": ""})
        digest = canonical_digest({key: value for key, value in draft.model_dump(mode="json").items() if key != "content_digest"})
        return draft.model_copy(update={"content_digest": digest})


class PositiveSecDocumentExecutionResult(StrictModel):
    status: Literal["positive_chain_persisted", "typed_terminal_stop", "blocked_before_send", "outcome_unknown"]
    receipt: SecDocumentInvocationReceiptVersion
    candidate: SecDocumentCandidateVersion | None = None
    parser: SecDocumentParserVersion | None = None
    fact: SecDocumentNumericFactVersion | None = None
    trace: SecDocumentNumericTraceVersion | None = None
    terminal_stop: SecDocumentTerminalStopVersion | None = None
    reused_terminal_receipt: bool = False
    model_call_count: Literal[0] = 0
    external_call_count: int = Field(ge=0, le=1)
    tool_invocation_count: int = Field(ge=0, le=1)
    store_write_count: int = Field(ge=0)


class SingleCallSecDocumentClient:
    """Pinned SEC Archives client; transport is fail-closed unless injected."""

    def __init__(self, *, user_agent: str, timeout_seconds: int, user_agent_min_length: int, forbidden_user_agent_values: tuple[str, ...], session: HttpSession | None = None):
        self._user_agent = SingleCallSecSubmissionsClient._validate_user_agent(
            user_agent,
            minimum_length=user_agent_min_length,
            forbidden_values=forbidden_user_agent_values,
        )
        self.user_agent_fingerprint = hashlib.sha256(self._user_agent.encode("utf-8")).hexdigest()
        self._timeout_seconds = timeout_seconds
        self._session = session or _FailClosedHttpSession()

    def fetch(self, *, exact_url: str) -> tuple[SecDocumentFetchResult, str]:
        parsed = urlparse(exact_url)
        if parsed.scheme != "https" or parsed.hostname != "www.sec.gov" or not parsed.path.startswith("/Archives/edgar/data/"):
            raise BoundedSecDocumentExecutionError("sec_document_endpoint_policy_violation")
        try:
            response = self._session.get(exact_url, headers={"User-Agent": self._user_agent, "Accept": "text/html"}, timeout=self._timeout_seconds, allow_redirects=False)
        except requests.RequestException as exc:
            raise SecDocumentTransportError("sec_document_single_call_transport_error") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise SecDocumentTransportError(f"sec_document_single_call_http_status:{response.status_code}")
        body = response.text
        if not body.strip():
            raise SecDocumentTransportError("sec_document_empty_response")
        encoded = body.encode("utf-8")
        return (
            SecDocumentFetchResult(
                source_url=exact_url,
                source_host="www.sec.gov",
                response_status_code=int(response.status_code),
                document_content_sha256=hashlib.sha256(encoded).hexdigest(),
                document_byte_length=len(encoded),
            ),
            body,
        )


@dataclass(frozen=True)
class _HtmlCell:
    text: str
    colspan: int
    rowspan: int


@dataclass(frozen=True)
class _CollectedTable:
    rows: tuple[tuple[_HtmlCell, ...], ...]
    context_blocks: tuple[str, ...]


class _TableCollector(HTMLParser):
    """Collect top-level tables with adjacent, table-local document context."""

    _BLOCK_TAGS = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "caption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_CollectedTable] = []
        self._table_stack = 0
        self._current_table: list[list[_HtmlCell]] | None = None
        self._current_table_context: tuple[str, ...] = ()
        self._current_row: list[_HtmlCell] | None = None
        self._current_cell_text: list[str] | None = None
        self._current_cell_colspan = 1
        self._current_cell_rowspan = 1
        self._blocks_since_last_top_level_table: list[str] = []
        self._outside_block_depth = 0
        self._outside_text: list[str] = []

    @staticmethod
    def _span(attrs: dict[str, str | None], key: str) -> int:
        try:
            return max(1, int(attrs.get(key) or "1"))
        except ValueError:
            return 1

    def _flush_outside_block(self) -> None:
        text = _normalize("".join(self._outside_text))
        self._outside_text = []
        if text:
            self._blocks_since_last_top_level_table.append(text)
            self._blocks_since_last_top_level_table = self._blocks_since_last_top_level_table[-12:]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._table_stack == 0:
                self._flush_outside_block()
                self._current_table = []
                self._current_table_context = tuple(self._blocks_since_last_top_level_table[-8:])
                self._blocks_since_last_top_level_table = []
            self._table_stack += 1
            return
        if self._table_stack == 0:
            if tag in self._BLOCK_TAGS:
                if self._outside_block_depth == 0:
                    self._outside_text = []
                self._outside_block_depth += 1
            return
        if self._table_stack != 1:
            return
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            values = dict(attrs)
            self._current_cell_text = []
            self._current_cell_colspan = self._span(values, "colspan")
            self._current_cell_rowspan = self._span(values, "rowspan")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "table" and self._table_stack:
            self._table_stack -= 1
            if self._table_stack == 0 and self._current_table is not None:
                self.tables.append(
                    _CollectedTable(
                        rows=tuple(tuple(row) for row in self._current_table),
                        context_blocks=self._current_table_context,
                    )
                )
                self._current_table = None
                self._current_table_context = ()
            return
        if self._table_stack == 0:
            if tag in self._BLOCK_TAGS and self._outside_block_depth:
                self._outside_block_depth -= 1
                if self._outside_block_depth == 0:
                    self._flush_outside_block()
            return
        if self._table_stack != 1:
            return
        if tag in {"td", "th"} and self._current_cell_text is not None and self._current_row is not None:
            self._current_row.append(
                _HtmlCell(
                    text="".join(self._current_cell_text),
                    colspan=self._current_cell_colspan,
                    rowspan=self._current_cell_rowspan,
                )
            )
            self._current_cell_text = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if not data.strip():
            return
        if self._current_cell_text is not None:
            self._current_cell_text.append(data)
        elif self._table_stack == 0:
            self._outside_text.append(data)


def _normalize(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split()).strip()


def _normalize_upper(value: str) -> str:
    return _normalize(value).upper()


def _context_key(value: str) -> str:
    return _normalize_upper(value).strip("()[] ")


def _parse_period_to_iso(value: str) -> str | None:
    normalized = _normalize(value).replace(".", "")
    iso_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", normalized)
    if iso_match:
        try:
            return date(*map(int, iso_match.groups())).isoformat()
        except ValueError:
            return None
    months = {
        "JAN": 1,
        "FEB": 2,
        "MAR": 3,
        "APR": 4,
        "MAY": 5,
        "JUN": 6,
        "JUL": 7,
        "AUG": 8,
        "SEP": 9,
        "OCT": 10,
        "NOV": 11,
        "DEC": 12,
    }
    match = re.search(
        r"\b(JAN(?:UARY)?|FEB(?:RUARY)?|MAR(?:CH)?|APR(?:IL)?|MAY|JUN(?:E)?|JUL(?:Y)?|AUG(?:UST)?|SEP(?:TEMBER)?|OCT(?:OBER)?|NOV(?:EMBER)?|DEC(?:EMBER)?)\s+(\d{1,2}),?\s+(\d{4})\b",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        return None
    month = months[match.group(1).upper()[:3]]
    try:
        return date(int(match.group(3)), month, int(match.group(2))).isoformat()
    except ValueError:
        return None


def _logical_grid(table: _CollectedTable) -> list[list[_HtmlCell | None]]:
    grid: list[list[_HtmlCell | None]] = []
    for row_index, source_row in enumerate(table.rows):
        while len(grid) <= row_index:
            grid.append([])
        column = 0
        for cell in source_row:
            while column < len(grid[row_index]) and grid[row_index][column] is not None:
                column += 1
            for covered_row in range(row_index, row_index + cell.rowspan):
                while len(grid) <= covered_row:
                    grid.append([])
                required_width = column + cell.colspan
                if len(grid[covered_row]) < required_width:
                    grid[covered_row].extend([None] * (required_width - len(grid[covered_row])))
                for covered_column in range(column, column + cell.colspan):
                    if grid[covered_row][covered_column] is not None:
                        raise SecDocumentParseError("html_table_span_overlap")
                    grid[covered_row][covered_column] = cell
            column += cell.colspan
    width = max((len(row) for row in grid), default=0)
    return [row + [None] * (width - len(row)) for row in grid]


def _is_primary_statement_table(table: _CollectedTable, selector: SecDocumentTableSelector) -> bool:
    heading = _context_key(selector.table_heading_normalized)
    unit = _context_key(selector.unit_caption_normalized)
    context = {_context_key(block) for block in table.context_blocks}
    return heading in context and unit in context


def _target_period_groups(grid: list[list[_HtmlCell | None]], target_period: str) -> list[tuple[int, int]]:
    groups: list[tuple[int, int]] = []
    header_limit = min(10, len(grid))
    for row_index, row in enumerate(grid[:header_limit]):
        starts: list[tuple[int, str]] = []
        for column_index, cell in enumerate(row):
            if cell is None or (column_index > 0 and row[column_index - 1] is cell):
                continue
            period = _parse_period_to_iso(cell.text)
            if period is not None:
                starts.append((column_index, period))
        if not starts:
            continue
        has_year_ended_group = any(
            _context_key(cell.text) == "YEAR ENDED"
            for preceding_row in grid[:row_index]
            for cell in preceding_row
            if cell is not None
        )
        if not has_year_ended_group:
            continue
        for index, (start, period) in enumerate(starts):
            if period == target_period:
                end = starts[index + 1][0] if index + 1 < len(starts) else len(row)
                if end > start:
                    groups.append((start, end))
    return groups


def _extract_group_numeric_value(row: list[_HtmlCell | None], start: int, end: int) -> tuple[int, str, str] | None:
    numeric_cells: list[tuple[int, str, str]] = []
    for column_index in range(start, min(end, len(row))):
        cell = row[column_index]
        if cell is None:
            continue
        raw = _normalize(cell.text)
        if not raw:
            continue
        try:
            numeric_cells.append((column_index, raw, _parse_decimal(raw)))
        except SecDocumentParseError:
            continue
    if len(numeric_cells) != 1:
        return None
    column_index, raw, parsed = numeric_cells[0]
    has_currency_marker = any(
        row[candidate] is not None and _normalize(row[candidate].text) == "$"
        for candidate in range(start, column_index)
    )
    if not has_currency_marker:
        return None
    return column_index, _normalize(f"$ {raw}"), parsed


def _parse_decimal(raw_value: str) -> str:
    cleaned = raw_value.replace("$", "").replace(",", "").replace("\xa0", " ").strip()
    cleaned = re.sub(r"\[[^\]]*\]|\([^\d,.-]*\)$", "", cleaned).strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1].strip()
    match = re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        raise SecDocumentParseError("target_numeric_cell_not_decimal")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise SecDocumentParseError("target_numeric_cell_not_decimal") from exc
    if negative:
        value = -value
    return format(value, "f")


def extract_approved_table_value(*, html: str, selector: SecDocumentTableSelector) -> ExtractedTableValue:
    collector = _TableCollector()
    collector.feed(html)
    collector.close()
    row_label = _normalize_upper(selector.row_label_normalized)
    target_period = _parse_period_to_iso(selector.column_period_normalized)
    if target_period is None:
        raise SecDocumentParseError("target_period_not_iso_normalizable")
    matches: list[tuple[int, int, int, int, int, str, str]] = []
    for table_index, table in enumerate(collector.tables):
        if not _is_primary_statement_table(table, selector):
            continue
        grid = _logical_grid(table)
        for group_start, group_end in _target_period_groups(grid, target_period):
            for row_index, row in enumerate(grid):
                label_cells = {
                    id(cell)
                    for cell in row
                    if cell is not None and _normalize_upper(cell.text) == row_label
                }
                if len(label_cells) != 1:
                    continue
                extracted = _extract_group_numeric_value(row, group_start, group_end)
                if extracted is None:
                    continue
                column_index, raw_value, parsed = extracted
                matches.append((table_index, row_index, column_index, group_start, group_end, raw_value, parsed))
    if not matches:
        raise SecDocumentParseError("approved_primary_statement_row_or_period_not_found")
    if len(matches) != 1:
        raise SecDocumentParseError("approved_primary_statement_row_or_period_ambiguous")
    table_index, row_index, column_index, group_start, group_end, raw_value, parsed = matches[0]
    return ExtractedTableValue(
        table_index=table_index,
        row_index=row_index,
        column_index=column_index,
        table_coordinate=f"table[{table_index}]/row[{row_index}]/period_group[{group_start}:{group_end}]/value_column[{column_index}]",
        table_heading_normalized=selector.table_heading_normalized,
        unit_caption_normalized=selector.unit_caption_normalized,
        row_label_normalized=selector.row_label_normalized,
        column_period_normalized=selector.column_period_normalized,
        normalized_period=target_period,
        financial_statement_role=selector.financial_statement_role,
        raw_value=raw_value,
        parsed_value=parsed,
    )


class BoundedSecDocumentExecutor:
    """Persist one unpromoted positive chain or a zero-attempt terminal stop."""

    receipt_table = "canonical_sec_document_invocation_receipt_versions"
    candidate_table = "canonical_sec_document_candidate_versions"
    parser_table = "canonical_sec_document_parser_versions"
    fact_table = "canonical_sec_document_numeric_fact_versions"
    trace_table = "canonical_sec_document_numeric_trace_versions"
    stop_table = "canonical_sec_document_terminal_stop_versions"

    def __init__(self, *, facade: RuntimeFacade, security: CapabilitySecurityService, budgets: BudgetControlService, policy: BoundedSecDocumentExecutionPolicy, global_approval_service: M6GlobalOneShotApprovalService, global_approval_id: str, pilot_package: M6PilotPackageDigest, after_send_started_hook: Callable[[], None] | None = None, after_http_send_hook: Callable[[], None] | None = None):
        self.facade = facade
        self.security = security
        self.budgets = budgets
        self.policy = policy
        self.global_approval_service = global_approval_service
        self.global_approval_id = global_approval_id
        self.pilot_package = pilot_package
        self.after_send_started_hook = after_send_started_hook
        self.after_http_send_hook = after_http_send_hook

    def execute(self, *, command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, capability_grant_id: str, reservation: BudgetReservationRequest, client: SingleCallSecDocumentClient) -> PositiveSecDocumentExecutionResult:
        self._validate_inputs(command=command, request=request, plan=plan, reservation=reservation)
        consumed_invocation_id = self._consumed_invocation_id()
        if consumed_invocation_id:
            existing = self.facade.store.get_latest(self.receipt_table, consumed_invocation_id)
            if existing:
                return self._terminal_from_existing(SecDocumentInvocationReceiptVersion.model_validate(existing))
            raise BoundedSecDocumentExecutionError("consumed_global_approval_has_no_local_execution_instance")
        scope = build_m6_pilot_scope(
            command=command,
            request=request,
            plan=plan,
            approval_ref=self.policy.approval_ref,
            approved_execution_scope=self.policy.approved_execution_scope,
            tool_id=self.policy.tool_id,
            route_id=self.policy.route_id,
            network_host=self.policy.allowed_network_host,
            target_cik=self.policy.allowed_cik,
            endpoint_path=self.policy.exact_path,
            execution_policy_digest=canonical_digest(self.policy),
        )
        active_approval = self.global_approval_service.verify_active_exact_receipt(
            scope=scope,
            package_ref=self.pilot_package.package_ref,
            package_digest=self.pilot_package.package_digest,
            package_manifest_digest=self.pilot_package.manifest_digest,
            approval_id=self.global_approval_id,
            at=command.requested_at,
        )
        invocation_id = self._invocation_id(
            command=command,
            request=request,
            plan=plan,
            active_approval=active_approval,
            local_store_identity=self.facade.store.store_identity(),
        )
        existing = self.facade.store.get_latest(self.receipt_table, invocation_id)
        if existing:
            receipt = SecDocumentInvocationReceiptVersion.model_validate(existing)
            if receipt.invocation_state in {"prepared", "send_authorized", "send_started"} or receipt.downstream_status == "source_received":
                raise BoundedSecDocumentExecutionError("active_or_incomplete_invocation_requires_explicit_reconciliation")
            return self._terminal_from_existing(receipt)
        admission_request = self._admission_request(command, capability_grant_id)
        initial_admission = self.security.admit(command, admission_request)
        if not initial_admission.allowed:
            raise CapabilitySecurityError(initial_admission)
        self.budgets.reserve(reservation)
        try:
            approval = self.global_approval_service.consume(
                scope=scope,
                package_ref=self.pilot_package.package_ref,
                package_digest=self.pilot_package.package_digest,
                package_manifest_digest=self.pilot_package.manifest_digest,
                approval_id=self.global_approval_id,
                invocation_id=invocation_id,
                local_store_identity=self.facade.store.store_identity(),
                at=command.requested_at,
            )
        except Exception:
            self._refund(reservation.reservation_id, "m6_3_5_global_approval_denied_before_send")
            raise
        prepared = self._record_receipt(command, request, plan, capability_grant_id, reservation.reservation_id, initial_admission, None, approval, "prepared", "not_started", 0, client.user_agent_fingerprint, None, None, invocation_id=invocation_id, approval_activation_digest=active_approval.content_digest)
        execution_command = command.model_copy(update={"command_id": f"{command.command_id}:execution-gate", "requested_at": utc_now()})
        execution_admission = self.security.admit(execution_command, admission_request)
        if not execution_admission.allowed:
            blocked = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, prepared, None, "blocked_before_send", "not_available", 0, client.user_agent_fingerprint, None, execution_admission.denial_code or "security_admission_denied", invocation_id=invocation_id)
            self._refund(reservation.reservation_id, "m6_3_5_execution_admission_denied_before_send")
            return PositiveSecDocumentExecutionResult(status="blocked_before_send", receipt=blocked, external_call_count=0, tool_invocation_count=0, store_write_count=2)
        authorized = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, prepared, None, "send_authorized", "not_started", 0, client.user_agent_fingerprint, None, None, invocation_id=invocation_id)
        sent_at = utc_now()
        started = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, authorized, None, "send_started", "not_started", 1, client.user_agent_fingerprint, None, None, sent_at=sent_at, invocation_id=invocation_id)
        if self.after_send_started_hook:
            self.after_send_started_hook()
        try:
            source, html = client.fetch(exact_url=self.policy.exact_url)
        except SecDocumentTransportError as exc:
            self._consume(reservation.reservation_id, "m6_3_5_single_send_outcome_unknown")
            unknown = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, started, None, "outcome_unknown", "not_available", 1, client.user_agent_fingerprint, None, str(exc), sent_at=sent_at, invocation_id=invocation_id)
            return PositiveSecDocumentExecutionResult(status="outcome_unknown", receipt=unknown, external_call_count=1, tool_invocation_count=1, store_write_count=4)
        if self.after_http_send_hook:
            self.after_http_send_hook()
        self._consume(reservation.reservation_id, "m6_3_5_single_send_succeeded")
        received = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, started, None, "succeeded", "source_received", 1, client.user_agent_fingerprint, source, None, sent_at=sent_at, invocation_id=invocation_id)
        try:
            extracted = extract_approved_table_value(html=html, selector=self.policy.target_table_selector)
        except SecDocumentParseError as exc:
            stopped = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, received, None, "succeeded", "typed_terminal_stop", 1, client.user_agent_fingerprint, source, str(exc), sent_at=sent_at, invocation_id=invocation_id)
            terminal_stop = self._persist_terminal_stop(command=execution_command, request=request, receipt=stopped, stop_code=str(exc))
            return PositiveSecDocumentExecutionResult(status="typed_terminal_stop", receipt=stopped, terminal_stop=terminal_stop, external_call_count=1, tool_invocation_count=1, store_write_count=6)
        candidate, parser, fact, trace = self._persist_positive_chain(command=execution_command, request=request, receipt=received, extracted=extracted)
        terminal = self._record_receipt(execution_command, request, plan, capability_grant_id, reservation.reservation_id, execution_admission, received, None, "succeeded", "positive_chain_persisted", 1, client.user_agent_fingerprint, source, None, sent_at=sent_at, invocation_id=invocation_id)
        return PositiveSecDocumentExecutionResult(status="positive_chain_persisted", receipt=terminal, candidate=candidate, parser=parser, fact=fact, trace=trace, external_call_count=1, tool_invocation_count=1, store_write_count=9)

    def reconcile(self, *, command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, reservation: BudgetReservationRequest) -> PositiveSecDocumentExecutionResult:
        self._validate_inputs(command=command, request=request, plan=plan, reservation=reservation)
        invocation_id = self._consumed_invocation_id()
        if not invocation_id:
            raise BoundedSecDocumentExecutionError("reconciliation_consumed_execution_instance_not_found")
        raw = self.facade.store.get_latest(self.receipt_table, invocation_id)
        if not raw:
            raise BoundedSecDocumentExecutionError("reconciliation_receipt_not_found")
        previous = SecDocumentInvocationReceiptVersion.model_validate(raw)
        if previous.invocation_state in {"prepared", "send_authorized"}:
            self._refund(reservation.reservation_id, "m6_3_5_reconcile_before_send_marker")
            terminal = self._record_receipt(command, request, plan, previous.capability_grant_id, reservation.reservation_id, None, previous, None, "aborted_before_send_reconciled", "not_available", 0, previous.user_agent_fingerprint, None, "m6_3_5_reconciled_before_send_marker_no_resend", invocation_id=invocation_id)
            return PositiveSecDocumentExecutionResult(status="blocked_before_send", receipt=terminal, external_call_count=0, tool_invocation_count=0, store_write_count=1)
        if previous.invocation_state == "send_started":
            self._consume(reservation.reservation_id, "m6_3_5_reconcile_send_started_outcome_unknown")
            terminal = self._record_receipt(command, request, plan, previous.capability_grant_id, reservation.reservation_id, None, previous, None, "outcome_unknown", "not_available", 1, previous.user_agent_fingerprint, None, "m6_3_5_reconciled_after_send_started_no_resend", invocation_id=invocation_id)
            return PositiveSecDocumentExecutionResult(status="outcome_unknown", receipt=terminal, external_call_count=1, tool_invocation_count=1, store_write_count=1)
        if previous.invocation_state == "succeeded" and previous.downstream_status == "source_received":
            terminal = self._record_receipt(command, request, plan, previous.capability_grant_id, reservation.reservation_id, None, previous, None, "succeeded", "typed_terminal_stop", 1, previous.user_agent_fingerprint, previous.source_document, "m6_3_5_downstream_not_durable_after_source_received_no_resend", invocation_id=invocation_id)
            stop = self._persist_terminal_stop(command=command, request=request, receipt=terminal, stop_code="m6_3_5_downstream_not_durable_after_source_received_no_resend")
            return PositiveSecDocumentExecutionResult(status="typed_terminal_stop", receipt=terminal, terminal_stop=stop, external_call_count=1, tool_invocation_count=1, store_write_count=2)
        return self._terminal_from_existing(previous)

    def _validate_inputs(self, *, command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, reservation: BudgetReservationRequest) -> None:
        self.facade._authorize("point01_shadow_compiler")
        if command.case_id is None or (request.tenant_id, request.project_id, request.case_id) != (command.tenant_id, command.project_id, command.case_id):
            raise BoundedSecDocumentExecutionError("request_command_scope_mismatch")
        if request.execution_admission != "not_admitted" or plan.persistence_admission != "not_admitted":
            raise BoundedSecDocumentExecutionError("execution_admission_must_be_declarative_before_runtime_gate")
        if plan.request_id != request.request_id or plan.request_digest != request.request_digest or plan.registry_snapshot_id != self.policy.required_registry_snapshot_id:
            raise BoundedSecDocumentExecutionError("tool_selection_plan_lineage_or_registry_mismatch")
        if plan.status != "await_execution_admission" or len(plan.steps) != 1:
            raise BoundedSecDocumentExecutionError("exact_single_tool_plan_required")
        step = plan.steps[0]
        if step.selected_tool_id != self.policy.tool_id or step.selected_route_id != self.policy.route_id or step.required_capability != self.policy.capability or step.fallback_if_fail is not None:
            raise BoundedSecDocumentExecutionError("approved_tool_route_capability_required")
        if request.target_entities != ("NVDA",) or request.target_periods != (self.policy.report_period,) or request.metric_intent != ("revenue",):
            raise BoundedSecDocumentExecutionError("evidence_request_not_exact_target_document_scope")
        if reservation.tool_calls != 1 or reservation.work_unit_id != str(command.payload.get("work_unit_id") or "") or reservation.attempt_id != str(command.payload.get("attempt_id") or ""):
            raise BoundedSecDocumentExecutionError("execution_reservation_not_exactly_one_bound_to_attempt")

    def _admission_request(self, command: CommandEnvelope, capability_grant_id: str) -> SandboxAdmissionRequest:
        return SandboxAdmissionRequest(capability_grant_id=capability_grant_id, capability=self.policy.capability, tool_id=self.policy.tool_id, target_tenant_id=command.tenant_id, target_project_id=command.project_id, target_case_id=command.case_id, data_classification="public", network_host=self.policy.allowed_network_host, path=self.policy.exact_path.lstrip("/"))

    def _record_receipt(self, command: CommandEnvelope, request: EvidenceRequest, plan: ToolSelectionPlan, capability_grant_id: str, reservation_id: str, admission: SecurityAdmissionDecision | None, previous: SecDocumentInvocationReceiptVersion | None, approval: M6GlobalOneShotApprovalReceipt | None, invocation_state: Literal["prepared", "blocked_before_send", "send_authorized", "send_started", "succeeded", "outcome_unknown", "aborted_before_send_reconciled"], downstream_status: Literal["not_started", "source_received", "positive_chain_persisted", "typed_terminal_stop", "not_available"], external_call_count: int, user_agent_fingerprint: str, source: SecDocumentFetchResult | None, error_code: str | None, *, sent_at: datetime | None = None, invocation_id: str, approval_activation_digest: str | None = None) -> SecDocumentInvocationReceiptVersion:
        if previous is None and approval is None:
            raise BoundedSecDocumentExecutionError("global_approval_receipt_required")
        version = 1 if previous is None else previous.invocation_version + 1
        approval_id = approval.approval_id if approval else str(previous.global_approval_id)
        approval_nonce_sha256 = approval.approval_nonce_sha256 if approval else str(previous.global_approval_nonce_sha256)
        activation_digest = approval_activation_digest or (str(previous.global_approval_activation_digest) if previous else "")
        if not activation_digest:
            raise BoundedSecDocumentExecutionError("global_approval_activation_digest_required")
        approval_digest = approval.content_digest if approval else str(previous.global_approval_receipt_digest)
        approval_store = approval.authority_store_identity if approval else str(previous.global_approval_store_identity)
        admission_id = admission.decision_id if admission else str(previous.admission_decision_id)
        admission_digest = canonical_digest(admission) if admission else str(previous.admission_decision_digest)
        now = utc_now()
        receipt = SecDocumentInvocationReceiptVersion.create(
            **self.facade._scope(command, case_id=self.facade._require_case(command)),
            invocation_id=invocation_id, invocation_version=version, state_version=version, invocation_state=invocation_state, downstream_status=downstream_status,
            request_id=request.request_id, request_digest=request.request_digest, tool_selection_plan_id=plan.plan_id, tool_selection_plan_digest=plan.plan_digest,
            registry_snapshot_id=plan.registry_snapshot_id, registry_snapshot_digest=plan.registry_snapshot_digest, policy_ref=self.policy.policy_ref, policy_digest=canonical_digest(self.policy), approval_ref=self.policy.approval_ref,
            global_approval_id=approval_id, global_approval_nonce_sha256=approval_nonce_sha256, global_approval_activation_digest=activation_digest, global_approval_receipt_digest=approval_digest, global_approval_store_identity=approval_store,
            approved_execution_scope=self.policy.approved_execution_scope, target_cik=self.policy.allowed_cik, accession_number=self.policy.accession_number, endpoint_host=self.policy.allowed_network_host, endpoint_path=self.policy.exact_path,
            capability_grant_id=capability_grant_id, admission_decision_id=admission_id, admission_decision_digest=admission_digest, budget_reservation_id=reservation_id, external_call_count=external_call_count,
            request_sent_at=sent_at or (previous.request_sent_at if previous else None), send_authorized_at=now if invocation_state == "send_authorized" else (previous.send_authorized_at if previous else None), send_started_at=sent_at if invocation_state == "send_started" else (previous.send_started_at if previous else None),
            user_agent_fingerprint=user_agent_fingerprint, terminal_at=now if invocation_state in {"succeeded", "outcome_unknown", "blocked_before_send", "aborted_before_send_reconciled"} and downstream_status != "source_received" else None,
            source_document=source, source_document_digest=canonical_digest(source) if source else None, error_code=error_code, current_status=invocation_state, supersedes_version_id=f"{invocation_id}:v{version - 1}" if previous else None,
        )
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(tx, command, self.facade._require_case(command), str(command.payload["work_unit_id"]), str(command.payload["attempt_id"]))
            current = tx.get_latest(self.receipt_table, invocation_id)
            if previous is None and current is not None:
                raise BoundedSecDocumentExecutionError("sec_document_receipt_already_exists")
            if previous is not None and (current is None or current.get("content_digest") != previous.content_digest):
                raise BoundedSecDocumentExecutionError("sec_document_receipt_transition_conflict")
            tx.insert(self.receipt_table, invocation_id, version, receipt.model_dump(mode="json"))
            event = self.facade._event(tx, command, "SEC_DOCUMENT_INVOCATION_RECEIPT_RECORDED", {"invocation_id": invocation_id, "invocation_version": version, "invocation_state": invocation_state, "downstream_status": downstream_status, "external_call_count": external_call_count, "request_digest": request.request_digest}, work_unit_id=str(command.payload["work_unit_id"]), attempt_id=str(command.payload["attempt_id"])).model_copy(update={"state_version_before": 0 if previous is None else previous.state_version, "state_version_after": version})
            tx.append_event(event)
        return receipt

    def _persist_positive_chain(self, *, command: CommandEnvelope, request: EvidenceRequest, receipt: SecDocumentInvocationReceiptVersion, extracted: ExtractedTableValue) -> tuple[SecDocumentCandidateVersion, SecDocumentParserVersion, SecDocumentNumericFactVersion, SecDocumentNumericTraceVersion]:
        if receipt.source_document is None or receipt.downstream_status != "source_received":
            raise BoundedSecDocumentExecutionError("source_received_receipt_required_for_positive_chain")
        receipt_ref = f"{receipt.invocation_id}:v{receipt.invocation_version}"
        candidate_seed = canonical_digest({"receipt": receipt.content_digest, "coordinate": extracted.table_coordinate, "selector": self.policy.target_table_selector})
        candidate_id = f"sec_document_candidate_{candidate_seed[:20]}"
        candidate = SecDocumentCandidateVersion.create(**self.facade._scope(command, case_id=self.facade._require_case(command)), execution_instance_id=receipt.invocation_id, candidate_id=candidate_id, candidate_version=1, state_version=1, receipt_version_ref=receipt_ref, receipt_content_digest=receipt.content_digest, request_id=request.request_id, request_digest=request.request_digest, source_url=receipt.source_document.source_url, source_document_sha256=receipt.source_document.document_content_sha256, table_coordinate=extracted.table_coordinate, table_heading_normalized=extracted.table_heading_normalized, unit_caption_normalized=extracted.unit_caption_normalized, row_label_normalized=extracted.row_label_normalized, column_period_normalized=extracted.column_period_normalized, normalized_period=extracted.normalized_period, financial_statement_role=extracted.financial_statement_role, xbrl_concept_hint=self.policy.target_table_selector.xbrl_concept_hint, current_status="unpromoted_candidate")
        candidate_ref = f"{candidate.candidate_id}:v1"
        parser_seed = canonical_digest({"candidate": candidate.content_digest, "table_coordinate": extracted.table_coordinate})
        parser = SecDocumentParserVersion.create(**self.facade._scope(command, case_id=self.facade._require_case(command)), execution_instance_id=receipt.invocation_id, receipt_version_ref=receipt_ref, receipt_content_digest=receipt.content_digest, parser_candidate_id=f"sec_document_parser_{parser_seed[:20]}", parser_candidate_version=1, state_version=1, candidate_version_ref=candidate_ref, candidate_content_digest=candidate.content_digest, table_coordinate=extracted.table_coordinate, parsed_table_digest=canonical_digest({"document": receipt.source_document.document_content_sha256, "coordinate": extracted.table_coordinate, "selector": self.policy.target_table_selector}), parser_policy_ref=self.policy.policy_ref, current_status="parsed_unpromoted")
        parser_ref = f"{parser.parser_candidate_id}:v1"
        fact_seed = canonical_digest({"parser": parser.content_digest, "value": extracted.parsed_value, "period": extracted.normalized_period})
        fact = SecDocumentNumericFactVersion.create(**self.facade._scope(command, case_id=self.facade._require_case(command)), execution_instance_id=receipt.invocation_id, receipt_version_ref=receipt_ref, receipt_content_digest=receipt.content_digest, normalized_fact_id=f"sec_document_numeric_fact_{fact_seed[:20]}", normalized_fact_version=1, state_version=1, parser_candidate_version_ref=parser_ref, parser_candidate_content_digest=parser.content_digest, row_label_normalized=extracted.row_label_normalized, normalized_value=extracted.parsed_value, unit=extracted.unit, period=extracted.normalized_period, source_coordinate=extracted.table_coordinate, current_status="unpromoted_numeric_fact")
        fact_ref = f"{fact.normalized_fact_id}:v1"
        trace_seed = canonical_digest({"fact": fact.content_digest, "raw": extracted.raw_value, "coordinate": extracted.table_coordinate})
        trace = SecDocumentNumericTraceVersion.create(**self.facade._scope(command, case_id=self.facade._require_case(command)), execution_instance_id=receipt.invocation_id, receipt_version_ref=receipt_ref, receipt_content_digest=receipt.content_digest, numeric_trace_id=f"sec_document_numeric_trace_{trace_seed[:20]}", numeric_trace_version=1, state_version=1, normalized_fact_version_ref=fact_ref, normalized_fact_content_digest=fact.content_digest, input_digest=canonical_digest({"raw_value": extracted.raw_value, "document_sha256": receipt.source_document.document_content_sha256, "coordinate": extracted.table_coordinate}), program_steps=("html_table_parse", "table_local_heading_unit_bind", "primary_statement_role_bind", "semantic_period_group_iso_normalization", "currency_numeric_cell_bind", "decimal_parse", "unit_caption_scale_preserved"), output_value=fact.normalized_value, current_status="unpromoted_numeric_trace")
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(tx, command, self.facade._require_case(command), str(command.payload["work_unit_id"]), str(command.payload["attempt_id"]))
            persisted_receipt = tx.get_version(self.receipt_table, receipt.invocation_id, receipt.invocation_version)
            if not persisted_receipt or persisted_receipt.get("content_digest") != receipt.content_digest:
                raise BoundedSecDocumentExecutionError("receipt_changed_before_positive_chain_persistence")
            for table, logical_id, value, event_type in (
                (self.candidate_table, candidate.candidate_id, candidate, "SEC_DOCUMENT_CANDIDATE_PERSISTED"),
                (self.parser_table, parser.parser_candidate_id, parser, "SEC_DOCUMENT_PARSER_CANDIDATE_PERSISTED"),
                (self.fact_table, fact.normalized_fact_id, fact, "SEC_DOCUMENT_NUMERIC_FACT_PERSISTED"),
                (self.trace_table, trace.numeric_trace_id, trace, "SEC_DOCUMENT_NUMERIC_TRACE_PERSISTED"),
            ):
                if tx.get_latest(table, logical_id):
                    raise BoundedSecDocumentExecutionError("positive_chain_concurrent_insert_conflict")
                tx.insert(table, logical_id, 1, value.model_dump(mode="json"))
                tx.append_event(self.facade._event(tx, command, event_type, {"logical_id": logical_id, "content_digest": value.content_digest, "receipt_version_ref": receipt_ref}, work_unit_id=str(command.payload["work_unit_id"]), attempt_id=str(command.payload["attempt_id"])).model_copy(update={"state_version_before": 0, "state_version_after": 1}))
        return candidate, parser, fact, trace

    def _persist_terminal_stop(self, *, command: CommandEnvelope, request: EvidenceRequest, receipt: SecDocumentInvocationReceiptVersion, stop_code: str) -> SecDocumentTerminalStopVersion:
        seed = canonical_digest({"receipt": receipt.content_digest, "request": request.request_digest, "stop": stop_code})
        stop = SecDocumentTerminalStopVersion.create(**self.facade._scope(command, case_id=self.facade._require_case(command)), terminal_stop_id=f"sec_document_terminal_stop_{seed[:20]}", terminal_stop_version=1, state_version=1, receipt_version_ref=f"{receipt.invocation_id}:v{receipt.invocation_version}", receipt_content_digest=receipt.content_digest, stop_code=stop_code, current_status="typed_terminal_stop")
        with self.facade.store.transaction() as tx:
            self.facade._require_running_execution(tx, command, self.facade._require_case(command), str(command.payload["work_unit_id"]), str(command.payload["attempt_id"]))
            if tx.get_latest(self.stop_table, stop.terminal_stop_id):
                raw = tx.get_latest(self.stop_table, stop.terminal_stop_id)
                return SecDocumentTerminalStopVersion.model_validate(raw)
            tx.insert(self.stop_table, stop.terminal_stop_id, 1, stop.model_dump(mode="json"))
            tx.append_event(self.facade._event(tx, command, "SEC_DOCUMENT_TYPED_TERMINAL_STOP_PERSISTED", {"terminal_stop_id": stop.terminal_stop_id, "stop_code": stop_code, "receipt_version_ref": stop.receipt_version_ref}, work_unit_id=str(command.payload["work_unit_id"]), attempt_id=str(command.payload["attempt_id"])).model_copy(update={"state_version_before": 0, "state_version_after": 1}))
        return stop

    def _terminal_from_existing(self, receipt: SecDocumentInvocationReceiptVersion) -> PositiveSecDocumentExecutionResult:
        if receipt.downstream_status == "positive_chain_persisted":
            candidate = self._only_version(self.candidate_table, SecDocumentCandidateVersion)
            parser = self._only_version(self.parser_table, SecDocumentParserVersion)
            fact = self._only_version(self.fact_table, SecDocumentNumericFactVersion)
            trace = self._only_version(self.trace_table, SecDocumentNumericTraceVersion)
            return PositiveSecDocumentExecutionResult(status="positive_chain_persisted", receipt=receipt, candidate=candidate, parser=parser, fact=fact, trace=trace, reused_terminal_receipt=True, external_call_count=1, tool_invocation_count=1)
        if receipt.downstream_status == "typed_terminal_stop":
            stops = self.facade.store.list_latest(self.stop_table, case_id=receipt.case_id)
            stop = SecDocumentTerminalStopVersion.model_validate(stops[-1]) if stops else None
            return PositiveSecDocumentExecutionResult(status="typed_terminal_stop", receipt=receipt, terminal_stop=stop, reused_terminal_receipt=True, external_call_count=receipt.external_call_count, tool_invocation_count=receipt.external_call_count)
        if receipt.invocation_state == "outcome_unknown":
            return PositiveSecDocumentExecutionResult(status="outcome_unknown", receipt=receipt, reused_terminal_receipt=True, external_call_count=1, tool_invocation_count=1)
        return PositiveSecDocumentExecutionResult(status="blocked_before_send", receipt=receipt, reused_terminal_receipt=True, external_call_count=0, tool_invocation_count=0)

    def _only_version(self, table: str, model: type[StrictModel]) -> Any:
        rows = self.facade.store.list_latest(table)
        if len(rows) != 1:
            raise BoundedSecDocumentExecutionError(f"positive_chain_latest_count_invalid:{table}")
        return model.model_validate(rows[0])

    def _consume(self, reservation_id: str, reason: str) -> None:
        row = self.facade.store.get_latest("canonical_budget_reservation_versions", reservation_id)
        if not row or row.get("reservation_state") not in {"reserved", "consumed"}:
            raise BoundedSecDocumentExecutionError("send_boundary_budget_not_consumable")
        if row.get("reservation_state") == "reserved":
            self.budgets.consume(reservation_id, reason=reason)

    def _refund(self, reservation_id: str, reason: str) -> None:
        row = self.facade.store.get_latest("canonical_budget_reservation_versions", reservation_id)
        if not row or row.get("reservation_state") not in {"reserved", "released"}:
            raise BoundedSecDocumentExecutionError("send_boundary_budget_not_refundable")
        if row.get("reservation_state") == "reserved":
            request = BudgetReservationRequest.model_validate(row["request"])
            self.budgets.refund(reservation_id, token_units=request.token_units, tool_calls=request.tool_calls, time_seconds=request.time_seconds, reason=reason)

    def _consumed_invocation_id(self) -> str | None:
        """Return the already-consumed execution identity without re-authorizing.

        This supports terminal/reconciliation reads after the atomic one-shot
        consumption.  It never treats a consumed receipt as active authority.
        """
        raw = self.global_approval_service.store.get_latest(
            self.global_approval_service.table,
            self.global_approval_id,
        )
        if not raw or raw.get("approval_state") != "consumed":
            return None
        invocation_id = raw.get("consumed_by_invocation_id")
        return str(invocation_id) if invocation_id else None

    @staticmethod
    def _invocation_id(
        *,
        command: CommandEnvelope,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        active_approval: M6GlobalOneShotApprovalReceipt,
        local_store_identity: str,
    ) -> str:
        """Build a globally distinct execution identity before the send gate.

        Request/plan digests are intentionally reusable across pilots.  The
        active receipt digest, WorkUnit/Attempt and target store turn that
        reusable plan into one auditable execution instance.
        """
        execution_seed = canonical_digest(
            {
                "request_digest": request.request_digest,
                "tool_selection_plan_digest": plan.plan_digest,
                "approval_id": active_approval.approval_id,
                "approval_version": active_approval.approval_version,
                "active_approval_receipt_digest": active_approval.content_digest,
                "work_unit_id": str(command.payload.get("work_unit_id") or ""),
                "attempt_id": str(command.payload.get("attempt_id") or ""),
                "task_run_ref": command.correlation_id,
                "local_store_identity": local_store_identity,
            }
        )
        return f"sec_document_execution_{execution_seed[:24]}"


BOUNDED_SEC_DOCUMENT_EXECUTION_MODELS = (
    BoundedSecDocumentExecutionPolicy,
    SecDocumentFetchResult,
    SecDocumentInvocationReceiptVersion,
    SecDocumentCandidateVersion,
    SecDocumentParserVersion,
    SecDocumentNumericFactVersion,
    SecDocumentNumericTraceVersion,
    SecDocumentTerminalStopVersion,
)
