"""Read historical metric cases; retain exact cards and small isolated SQL copies.

No provider/client configuration is loaded. Output is private engineering evidence,
not a reviewed financial answer set or a replacement for the published library.
"""
import argparse
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import socket
import sqlite3

from sec_agent.research_foundation.financial_library import content_digest
from sec_agent.research_foundation.metric_workspace import query_metrics
from scripts.data_retrieval.benchmark_library_queries import digest as historical_digest


def prepare(library, cases, output, entities):
    library, cases, output = map(Path, (library, cases, output))
    spec = json.loads(cases.read_text(encoding="utf8"))
    if len(set(entities)) != len(entities) or len(entities) < 2:
        raise ValueError("two_or_more_distinct_historical_companies_required")
    with library.open("rb") as stream:
        digest = __import__("hashlib").file_digest(stream, "sha256").hexdigest()
    if digest != spec["library_sha256"]:
        raise ValueError("historical_library_digest_mismatch")
    output.mkdir(parents=True, exist_ok=False)
    selected, replay, dependencies = [], [], {}
    with closing(sqlite3.connect(library.resolve().as_uri()+"?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        for entity in entities:
            matches = [c for c in spec["cases"] if c["operation"] == "metric"
                        and c["arguments"].get("entity_ids") == [entity]
                        and c["arguments"].get("section") == "history"]
            if not matches:
                raise ValueError("historical_company_case_missing:"+entity)
            case = matches[0]
            history = query_metrics(library, **case["arguments"])
            assert historical_digest(history) == case["expected_sha256"], "historical_query_changed"
            # Historical digest is provenance, not an independent answer oracle.
            replay.append({"id": case["id"], "arguments": case["arguments"],
                           "historical_digest": case["expected_sha256"],
                           "current_digest": historical_digest(history), "total": history["total"]})
            originals = db.execute("""SELECT * FROM industry_metric_observations
                WHERE entity_id=? ORDER BY available_at DESC,metric,id LIMIT 3""", (entity,)).fetchall()
            if len(originals) != 3:
                raise ValueError("three_historical_observations_required:"+entity)
            cards = []
            for raw in originals:
                card = query_metrics(library, [entity], section="card", record_id=raw["id"],
                                     as_of=case["arguments"]["as_of"])["items"][0]
                for field in ("id", "entity_id", "metric", "value", "unit", "period_kind",
                              "available_at", "source_id", "business_scope", "fiscal_year",
                              "fiscal_period", "period_start", "period_end", "observation_date",
                              "value_state", "comparator"):
                    assert card[field] == raw[field], (entity, raw["id"], field)
                for projected, stored in (("start", "period_start"), ("end", "period_end"),
                                          ("fiscal_year", "fiscal_year"), ("fiscal_period", "fiscal_period")):
                    assert card["financial_basis"][projected] == raw[stored]
                before = (date.fromisoformat(raw["available_at"])-timedelta(days=1)).isoformat()
                try:
                    query_metrics(library, [entity], section="card", record_id=raw["id"], as_of=before)
                except ValueError as exc:
                    assert str(exc) == "metric_record_not_found_at_cutoff"
                else:
                    raise AssertionError("future_card_visible")
                other = next(e for e in entities if e != entity)
                try:
                    query_metrics(library, [other], section="card", record_id=raw["id"])
                except ValueError as exc:
                    assert str(exc) == "metric_record_not_found_at_cutoff"
                else:
                    raise AssertionError("wrong_company_card_visible")
                def check_quote(row):
                    body = "\n".join(r[0] for r in db.execute(
                        "SELECT body FROM passages WHERE source_id=? ORDER BY locator", (row["source_id"],)))
                    assert row.get("evidence_quote") and row["evidence_quote"] in body, (
                        "historical_quote_not_in_original", entity, row["id"])
                if card["record_type"] == "calculated":
                    assert card["formula_version"] == "industry-ratio.v1"
                    operands = {}
                    for operand in card["inputs"]:
                        item = query_metrics(library, [entity], section="card",
                            record_id=operand["id"], as_of=card["available_at"])["items"][0]
                        assert item["value"] == operand["value"] and item["unit"] == operand["unit"]
                        check_quote(item)
                        dependencies[item["id"]] = item
                        operands[operand["role"]] = Decimal(item["value"])
                    assert Decimal(card["value"]) == operands["a"]/operands["b"]*100
                else:
                    check_quote(card)
                cards.append(card)
            query = {"kind": "metric_cards", "entity_ids": [entity],
                     "record_ids": [c["id"] for c in cards], "as_of": case["arguments"]["as_of"]}
            # Reuse the existing fixed structured-row capture contract. This is
            # an explicit host preparation adapter, not a browser capture route.
            snapshot = {"schema_version": "project_source_snapshot.v1", "kind": "financial",
                        "query": query, "query_digest": content_digest({"query": query, "rows": cards}),
                        "matching_count": len(cards), "selection_mode": "explicit_rows", "rows": cards}
            selected.append({"id": case["id"], "entity_id": entity, "snapshot": snapshot})
        all_rows = [r for c in selected for r in c["snapshot"]["rows"]] + list(dependencies.values())
        ids = list({r["id"] for r in all_rows})
        source_ids = list({r["source_id"] for r in all_rows})
        # Small copy with original schemas/IDs; never copy/rebuild the multi-GB library.
        with closing(sqlite3.connect(output/"build.sqlite")) as dest, dest:
            conditions = {
                "entities": ("id", entities), "company_cards": ("entity_id", entities),
                "sources": ("id", source_ids), "passages": ("source_id", source_ids),
                "entity_sources": ("source_id", source_ids),
                "industry_metric_observations": ("id", ids),
                "industry_metric_definitions": (None, []),
                "industry_metric_reviews": ("entity_id", entities),
                "data_gaps": ("entity_id", entities), "snapshot_metadata": (None, []),
            }
            for table, (column, values) in conditions.items():
                schema = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
                dest.execute(schema)
                clause = " WHERE "+column+" IN ("+",".join("?" for _ in values)+")" if column else ""
                for row in db.execute("SELECT * FROM "+table+clause, values):
                    dest.execute("INSERT INTO "+table+" VALUES("+",".join("?" for _ in row)+")", tuple(row))
            dest.execute("UPDATE snapshot_metadata SET value='engineering_unpublished_copy' WHERE key='state'")
            for name in ("industry_metric_series",):
                dest.execute(db.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0])
            dest.execute("CREATE VIRTUAL TABLE passage_search USING fts5(id UNINDEXED, source_id UNINDEXED, body)")
            dest.execute("INSERT INTO passage_search SELECT id,source_id,body FROM passages")
            plans = [list(r) for r in dest.execute("EXPLAIN QUERY PLAN SELECT payload FROM industry_metric_observations WHERE id=?", (ids[0],))]
    for row in all_rows:
        assert query_metrics(output/"build.sqlite", [row["entity_id"]], section="card",
                             record_id=row["id"], as_of="2026-09-23")["items"][0] == row, "isolated_card_copy_changed"
    result = {"schema_version": "structured_sql_cases.v1", "library_sha256": digest,
              "historical_cases_sha256": sha256(cases.read_bytes()).hexdigest(),
              "provider_calls": 0, "as_of": "2026-09-23", "cases": selected,
              "historical_replay": replay, "card_query_plan": plans,
              "calculation_inputs": list(dependencies.values()),
              "scope": "historical engineering replay; no financial answer gold"}
    (output/"cases.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for flag in ("library", "cases", "output"):
        parser.add_argument("--"+flag, required=True)
    parser.add_argument("--entities", nargs="+", required=True)
    args = parser.parse_args()
    def forbidden(*args, **kwargs):
        raise AssertionError("structured_sql_preparation_forbids_network")
    socket.socket.connect = forbidden
    result = prepare(args.library, args.cases, args.output, args.entities)
    print(json.dumps({"cases": len(result["cases"]), "cards": sum(len(c["snapshot"]["rows"]) for c in result["cases"]),
                      "provider_calls": 0}))
