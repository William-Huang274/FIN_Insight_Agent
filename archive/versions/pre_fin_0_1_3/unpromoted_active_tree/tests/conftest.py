from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sec_agent.engineering_handoff import classify_test_nodeid, load_json


PROFILE_IDS = (
    "fast_contract",
    "fixture_integration",
    "local_data_integration",
    "frontend_e2e",
    "full_chain",
    "paid_model",
)


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--test-profile-report",
        action="store",
        default="",
        help="Write the collected item-to-test-profile classification as JSON.",
    )


def pytest_collection_modifyitems(config, items) -> None:
    root = Path(str(config.rootpath))
    registry = load_json(root / "configs" / "engineering_handoff" / "test_profile_registry_v0_1.json")
    rows = []
    for item in items:
        classified = classify_test_nodeid(item.nodeid, registry)
        profile = classified["profile"]
        if profile not in PROFILE_IDS:
            raise RuntimeError(f"Unknown test profile {profile!r} for {item.nodeid}")
        item.add_marker(profile)
        for requirement in classified["requirements"]:
            item.add_marker(requirement)
        rows.append(classified)
    report = str(config.getoption("--test-profile-report") or "").strip()
    if report:
        target = Path(report)
        if not target.is_absolute():
            target = root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "finsight_test_profile_collection_v0_1",
            "collected_item_count": len(rows),
            "profile_counts": dict(sorted(Counter(row["profile"] for row in rows).items())),
            "requirement_counts": dict(
                sorted(Counter(value for row in rows for value in row["requirements"]).items())
            ),
            "items": rows,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
