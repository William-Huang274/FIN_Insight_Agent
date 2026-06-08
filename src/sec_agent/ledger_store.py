from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "sec_agent_lightweight_ledger_store_v0.1"
LEDGER_STORE_CASE_ID = "__ledger_store__"
METRIC_FAMILY_ALIASES = {
    "capex": ["capital_expenditure_proxy", "capital_expenditures", "capital_expenditure"],
    "capital_expenditure": ["capex", "capital_expenditure_proxy", "capital_expenditures"],
    "capital_expenditures": ["capex", "capital_expenditure_proxy", "capital_expenditure"],
    "margin": ["gross_margin", "operating_margin", "operating_income", "net_income", "revenue", "total_revenue"],
    "gross_margin": ["margin"],
    "operating_margin": ["margin"],
    "revenue": ["revenues", "net_revenue", "net_sales", "sales_revenue"],
}
LEDGER_FACT_COLUMNS = [
    "metric_id_tail",
    "object_id",
    "source_evidence_id",
    "ticker",
    "fiscal_year",
    "source_fiscal_year",
    "period",
    "period_role",
    "form_type",
    "source_type",
    "source_tier",
    "period_end",
    "period_type",
    "duration_months",
    "fiscal_period",
    "metric_family",
    "metric_role",
    "metric_name",
    "raw_value_text",
    "display_value_zh",
    "value",
    "value_text",
    "unit",
    "section",
    "row_label",
    "column_label",
    "cell_kind",
    "table_object_id",
    "table_title",
    "active_group",
    "row_index",
    "source_text",
    "record_title",
    "payload_json",
]


def write_ledger_store(
    rows: list[dict[str, Any]],
    db_path: str | Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with LedgerStoreWriter(db_path) as writer:
        writer.append_rows(rows)
        return writer.finalize(metadata=metadata)


class LedgerStoreWriter:
    def __init__(
        self,
        db_path: str | Path,
        *,
        duckdb_threads: int | None = None,
        transaction_commit_rows: int = 50_000,
    ) -> None:
        self.db_path = Path(db_path)
        self.duckdb_threads = duckdb_threads
        self.transaction_commit_rows = max(0, int(transaction_commit_rows))
        self.con: Any = None
        self.row_count = 0
        self._transaction_open = False
        self._next_commit_row = self.transaction_commit_rows

    def __enter__(self) -> "LedgerStoreWriter":
        import duckdb

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.db_path))
        _configure_duckdb_connection(self.con, duckdb_threads=self.duckdb_threads)
        _create_empty_ledger_store_tables(self.con)
        self._begin_transaction()
        return self

    def append_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.append_row_values([normalize_ledger_fact_values(row) for row in rows])

    def append_row_values(self, rows: list[list[Any]]) -> None:
        if not rows:
            return
        placeholders = ", ".join("?" for _ in LEDGER_FACT_COLUMNS)
        self.con.executemany(
            f"INSERT INTO ledger_facts ({', '.join(LEDGER_FACT_COLUMNS)}) VALUES ({placeholders})",
            rows,
        )
        self.row_count += len(rows)
        if self.transaction_commit_rows and self.row_count >= self._next_commit_row:
            self._commit_transaction()
            self._begin_transaction()
            self._next_commit_row = self.row_count + self.transaction_commit_rows

    def finalize(self, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._transaction_open:
            self._commit_transaction()
        _create_indexes(self.con)
        summary = {
            "schema_version": SCHEMA_VERSION,
            "row_count": self.row_count,
            "metadata": {
                **(metadata or {}),
                "transaction_commit_rows": self.transaction_commit_rows,
            },
        }
        self.con.execute("CREATE TABLE ledger_store_metadata AS SELECT ? AS payload_json", [json.dumps(summary, ensure_ascii=False)])
        return summary

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.con is not None:
            if self._transaction_open:
                try:
                    self.con.execute("ROLLBACK")
                except Exception:
                    pass
                self._transaction_open = False
            self.con.close()

    def _begin_transaction(self) -> None:
        self.con.execute("BEGIN TRANSACTION")
        self._transaction_open = True

    def _commit_transaction(self) -> None:
        self.con.execute("COMMIT")
        self._transaction_open = False


class LedgerStoreBulkCsvWriter:
    def __init__(
        self,
        db_path: str | Path,
        *,
        duckdb_threads: int | None = None,
        staging_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.duckdb_threads = duckdb_threads
        self.staging_path = Path(staging_path) if staging_path else self.db_path.with_name(f"{self.db_path.name}.rows.tsv.tmp")
        self.row_count = 0
        self._handle: Any = None
        self._writer: csv.writer | None = None

    def __enter__(self) -> "LedgerStoreBulkCsvWriter":
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.staging_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.staging_path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._handle, delimiter="\t", lineterminator="\n")
        self._writer.writerow(LEDGER_FACT_COLUMNS)
        return self

    def append_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self.append_row_values([normalize_ledger_fact_values(row) for row in rows])

    def append_row_values(self, rows: list[list[Any]]) -> None:
        if not rows:
            return
        assert self._writer is not None
        null_safe_rows = [["\\N" if value is None else value for value in row] for row in rows]
        self._writer.writerows(null_safe_rows)
        self.row_count += len(rows)

    def finalize(self, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        import duckdb

        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None
        con = duckdb.connect(str(self.db_path))
        try:
            _configure_duckdb_connection(con, duckdb_threads=self.duckdb_threads)
            _create_empty_ledger_store_tables(con)
            con.execute(
                f"""
                COPY ledger_facts
                FROM {_duckdb_sql_string(self.staging_path)}
                (HEADER, DELIMITER '\t', QUOTE '"', ESCAPE '"', NULL '\\N')
                """
            )
            _create_indexes(con)
            summary = {
                "schema_version": SCHEMA_VERSION,
                "row_count": self.row_count,
                "metadata": {
                    **(metadata or {}),
                    "write_mode": "csv_copy",
                    "staging_csv_path": str(self.staging_path),
                },
            }
            con.execute("CREATE TABLE ledger_store_metadata AS SELECT ? AS payload_json", [json.dumps(summary, ensure_ascii=False)])
            return summary
        finally:
            con.close()
            if self.staging_path.exists():
                self.staging_path.unlink()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def query_ledger_facts(
    db_path: str | Path,
    *,
    case_id: str,
    object_ids: list[str] | None = None,
    tickers: list[str] | None = None,
    years: list[int] | None = None,
    filing_types: list[str] | None = None,
    source_tiers: list[str] | None = None,
    metric_families: list[str] | None = None,
    period_roles: list[str] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    import duckdb

    db_path = Path(db_path)
    if not db_path.exists():
        return []
    where: list[str] = []
    params: list[Any] = []
    _add_in_filter(where, params, "object_id", object_ids)
    _add_in_filter(where, params, "ticker", _upper_list(tickers))
    _add_in_filter(where, params, "fiscal_year", years)
    _add_in_filter(where, params, "form_type", _form_list(filing_types))
    _add_in_filter(where, params, "source_tier", source_tiers)
    _add_in_filter(where, params, "metric_family", _metric_family_list(metric_families))
    _add_in_filter(where, params, "period_role", _lower_list(period_roles))
    sql = "SELECT * FROM ledger_facts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {_ledger_fact_order_by_sql()} LIMIT ?"
    params.append(max(1, int(limit)))
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result = con.execute(sql, params)
        columns = [desc[0] for desc in result.description]
        rows = [dict(zip(columns, values)) for values in result.fetchall()]
    finally:
        con.close()
    return [_hydrate_runtime_row(row, case_id=case_id) for row in rows]


def _ledger_fact_order_by_sql() -> str:
    text_expr = (
        "lower(coalesce(metric_name, '') || ' ' || coalesce(row_label, '') || ' ' || "
        "coalesce(column_label, '') || ' ' || coalesce(table_title, '') || ' ' || coalesce(record_title, ''))"
    )
    label_expr = "lower(coalesce(metric_name, '') || ' ' || coalesce(row_label, ''))"
    return f"""
        ticker,
        fiscal_year DESC,
        CASE WHEN table_object_id IS NOT NULL AND table_object_id <> '' THEN 0 ELSE 1 END,
        CASE lower(coalesce(period_role, ''))
            WHEN 'annual' THEN 0
            WHEN 'ytd' THEN 1
            WHEN 'qtd' THEN 2
            ELSE 3
        END,
        CASE
            WHEN lower(coalesce(unit, '')) LIKE 'usd%' THEN 0
            WHEN lower(coalesce(unit, '')) = 'percent' THEN 1
            ELSE 2
        END,
        CASE lower(coalesce(cell_kind, ''))
            WHEN 'period_value' THEN 0
            WHEN 'value' THEN 1
            WHEN 'change_value' THEN 2
            WHEN 'percentage' THEN 3
            ELSE 4
        END,
        CASE
            WHEN metric_family = 'capital_expenditure_proxy'
                AND regexp_matches({text_expr}, 'additions to property|capital expenditure|capital expenditures|purchases of property') THEN 0
            WHEN metric_family = 'capital_expenditure_proxy'
                AND regexp_matches({text_expr}, 'accumulated depreciation|depreciation|buildings and improvements|furniture and equipment') THEN 2
            WHEN metric_family IN ('revenue', 'total_revenue', 'data_center_revenue', 'cloud_revenue')
                AND regexp_matches({label_expr}, '(^| )revenue($| )|total revenue|net revenue|net sales|compute & networking|data center|graphics') THEN 0
            WHEN metric_family IN ('revenue', 'total_revenue', 'data_center_revenue', 'cloud_revenue')
                AND regexp_matches({text_expr}, 'operating expenses|interest income|interest expense|income tax|tax expense|other income|other, net') THEN 2
            ELSE 1
        END,
        metric_family,
        metric_role
    """


def read_ledger_store_metadata(db_path: str | Path) -> dict[str, Any]:
    import duckdb

    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        table_count = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='ledger_store_metadata'"
        ).fetchone()[0]
        if not table_count:
            return {}
        row = con.execute("SELECT payload_json FROM ledger_store_metadata LIMIT 1").fetchone()
    finally:
        con.close()
    if not row:
        return {}
    return json.loads(row[0])


def _normalize_fact_row(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("value")
    value_double = float(value) if isinstance(value, (int, float)) else None
    metric_id_tail = _metric_id_tail(row.get("metric_id"))
    payload = {
        key: value
        for key, value in row.items()
        if key not in {"case_id", "metric_id"} and key not in LEDGER_FACT_COLUMNS
    }
    return {
        "metric_id_tail": metric_id_tail,
        "object_id": _str_or_none(row.get("object_id")),
        "source_evidence_id": _str_or_none(row.get("source_evidence_id")),
        "ticker": _str_or_none(row.get("ticker")).upper() if row.get("ticker") else None,
        "fiscal_year": _int_or_none(row.get("fiscal_year")),
        "source_fiscal_year": _int_or_none(row.get("source_fiscal_year")),
        "period": _str_or_none(row.get("period")),
        "period_role": _str_or_none(row.get("period_role")),
        "form_type": _normalize_form_type(row.get("form_type")),
        "source_type": _normalize_form_type(row.get("source_type")),
        "source_tier": _str_or_none(row.get("source_tier")),
        "period_end": _str_or_none(row.get("period_end")),
        "period_type": _str_or_none(row.get("period_type")),
        "duration_months": _int_or_none(row.get("duration_months")),
        "fiscal_period": _str_or_none(row.get("fiscal_period")),
        "metric_family": _str_or_none(row.get("metric_family")),
        "metric_role": _str_or_none(row.get("metric_role")),
        "metric_name": _str_or_none(row.get("metric_name")),
        "raw_value_text": _str_or_none(row.get("raw_value_text")),
        "display_value_zh": _str_or_none(row.get("display_value_zh")),
        "value": value_double,
        "value_text": None if value_double is not None else _str_or_none(value),
        "unit": _str_or_none(row.get("unit")),
        "section": _str_or_none(row.get("section")),
        "row_label": _str_or_none(row.get("row_label")),
        "column_label": _str_or_none(row.get("column_label")),
        "cell_kind": _str_or_none(row.get("cell_kind")),
        "table_object_id": _str_or_none(row.get("table_object_id")),
        "table_title": _str_or_none(row.get("table_title")),
        "active_group": _str_or_none(row.get("active_group")),
        "row_index": _int_or_none(row.get("row_index")),
        "source_text": _str_or_none(row.get("source_text")),
        "record_title": _str_or_none(row.get("record_title")),
        "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }


def normalize_ledger_fact_values(row: dict[str, Any]) -> list[Any]:
    normalized = _normalize_fact_row(row)
    return [normalized.get(column) for column in LEDGER_FACT_COLUMNS]


def _hydrate_runtime_row(row: dict[str, Any], *, case_id: str) -> dict[str, Any]:
    payload = json.loads(row.pop("payload_json") or "{}")
    hydrated = {**payload, **{key: value for key, value in row.items() if value is not None}}
    hydrated["case_id"] = case_id
    tail = str(row.get("metric_id_tail") or "").strip()
    hydrated["metric_id"] = f"{case_id}::{tail}" if tail else _fallback_metric_id(hydrated, case_id)
    if hydrated.get("value") is None and hydrated.get("value_text") is not None:
        hydrated["value"] = hydrated.get("value_text")
    hydrated.pop("metric_id_tail", None)
    hydrated.pop("value_text", None)
    return hydrated


def _fallback_metric_id(row: dict[str, Any], case_id: str) -> str:
    parts = [
        case_id,
        str(row.get("ticker") or "").upper(),
        str(row.get("fiscal_year") or ""),
        str(row.get("metric_family") or ""),
        str(row.get("metric_role") or ""),
    ]
    if row.get("period_role"):
        parts.append(str(row.get("period_role")))
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", str(row.get("row_label") or "").strip().lower()).strip("_")
    if suffix:
        parts.append(suffix)
    return "::".join(parts)


def _metric_id_tail(metric_id: Any) -> str:
    parts = str(metric_id or "").split("::")
    if len(parts) <= 1:
        return str(metric_id or "")
    return "::".join(parts[1:])


def _configure_duckdb_connection(con: Any, *, duckdb_threads: int | None = None) -> None:
    if duckdb_threads:
        con.execute(f"PRAGMA threads={max(1, int(duckdb_threads))}")
    try:
        con.execute("SET preserve_insertion_order=false")
    except Exception:
        try:
            con.execute("PRAGMA preserve_insertion_order=false")
        except Exception:
            pass


def _create_empty_ledger_store_tables(con: Any) -> None:
    con.execute("DROP TABLE IF EXISTS ledger_facts")
    con.execute("DROP TABLE IF EXISTS ledger_store_metadata")
    con.execute(
        """
        CREATE TABLE ledger_facts (
            metric_id_tail VARCHAR,
            object_id VARCHAR,
            source_evidence_id VARCHAR,
            ticker VARCHAR,
            fiscal_year INTEGER,
            source_fiscal_year INTEGER,
            period VARCHAR,
            period_role VARCHAR,
            form_type VARCHAR,
            source_type VARCHAR,
            source_tier VARCHAR,
            period_end VARCHAR,
            period_type VARCHAR,
            duration_months INTEGER,
            fiscal_period VARCHAR,
            metric_family VARCHAR,
            metric_role VARCHAR,
            metric_name VARCHAR,
            raw_value_text VARCHAR,
            display_value_zh VARCHAR,
            value DOUBLE,
            value_text VARCHAR,
            unit VARCHAR,
            section VARCHAR,
            row_label VARCHAR,
            column_label VARCHAR,
            cell_kind VARCHAR,
            table_object_id VARCHAR,
            table_title VARCHAR,
            active_group VARCHAR,
            row_index INTEGER,
            source_text VARCHAR,
            record_title VARCHAR,
            payload_json VARCHAR
        )
        """
    )


def _duckdb_sql_string(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _add_in_filter(where: list[str], params: list[Any], column: str, values: list[Any] | None) -> None:
    cleaned = [value for value in (values or []) if value is not None and str(value) != ""]
    if not cleaned:
        return
    placeholders = ", ".join("?" for _ in cleaned)
    where.append(f"{column} IN ({placeholders})")
    params.extend(cleaned)


def _create_indexes(con: Any) -> None:
    for column in ("object_id", "ticker", "fiscal_year", "form_type", "source_tier", "metric_family", "period_role"):
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_ledger_facts_{column} ON ledger_facts ({column})")


def _upper_list(values: list[str] | None) -> list[str]:
    return [str(value).upper().strip() for value in values or [] if str(value).strip()]


def _form_list(values: list[str] | None) -> list[str]:
    return [_normalize_form_type(value) for value in values or [] if _normalize_form_type(value)]


def _lower_list(values: list[str] | None) -> list[str]:
    return [str(value).lower().strip() for value in values or [] if str(value).strip()]


def _metric_family_list(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        aliases = [text, *METRIC_FAMILY_ALIASES.get(text.lower(), [])]
        for item in aliases:
            clean = str(item).strip()
            if clean and clean not in seen:
                seen.add(clean)
                out.append(clean)
    return out


def _normalize_form_type(value: Any) -> str | None:
    text = str(value or "").upper().strip().replace("10K", "10-K").replace("10Q", "10-Q")
    return text or None


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
