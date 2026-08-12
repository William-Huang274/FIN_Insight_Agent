from __future__ import annotations

from datetime import date
from typing import Any, Mapping


def _valid_iso_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value or ""))
    except ValueError:
        return False
    return True


def reporting_temporal_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Bind an object to its reporting period without erasing source dates.

    Current-report filings such as 8-K earnings releases often use the filing or
    publication date as the source-record period.  When the parser has preserved
    an explicit reporting period in source-bound metadata, retrieval and object
    contracts must use that period while retaining both values for audit.
    """

    metadata = record.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    source_fiscal_year = record.get("fiscal_year")
    reported_fiscal_year = metadata.get("reported_fiscal_year")
    try:
        reporting_fiscal_year = int(
            reported_fiscal_year
            if reported_fiscal_year not in (None, "")
            else source_fiscal_year
        )
    except (TypeError, ValueError):
        reporting_fiscal_year = None

    source_period_end = str(record.get("period_end") or "").strip()
    reported_period_end = str(metadata.get("reported_period_end") or "").strip()
    reporting_period_end = (
        reported_period_end
        if _valid_iso_date(reported_period_end)
        else source_period_end
    )
    return {
        "reporting_fiscal_year": reporting_fiscal_year,
        "reporting_fiscal_year_source": (
            "metadata.reported_fiscal_year"
            if reported_fiscal_year not in (None, "")
            else "source_record.fiscal_year"
        ),
        "reporting_period_end": reporting_period_end,
        "reporting_period_end_source": (
            "metadata.reported_period_end"
            if _valid_iso_date(reported_period_end)
            else "source_record.period_end"
        ),
        "source_record_fiscal_year": source_fiscal_year,
        "source_record_period_end": source_period_end,
    }


__all__ = ["reporting_temporal_projection"]
