from __future__ import annotations

import json
from pathlib import Path

from sec_agent.repository_architecture_inventory import (
    build_repository_architecture_inventory,
    evaluate_repository_architecture_guard,
    load_inventory_policy,
    render_repository_architecture_markdown,
)


def test_repository_inventory_resolves_imports_and_review_candidates(tmp_path: Path) -> None:
    (tmp_path / "src/demo").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / "apps").mkdir()
    (tmp_path / "src/demo/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src/demo/used.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "src/demo/unused.py").write_text("VALUE = 2\n", encoding="utf-8")
    (tmp_path / "scripts/run.py").write_text(
        "from demo.used import VALUE\nif __name__ == '__main__':\n    print(VALUE)\n",
        encoding="utf-8",
    )
    policy = {
        "schema_version": "finsight_repository_architecture_policy_v0_1",
        "source_roots": ["src"],
        "script_roots": ["scripts"],
        "test_roots": ["tests"],
        "app_roots": ["apps"],
        "documentation_roots": ["docs"],
        "config_roots": ["configs"],
        "audit_roots": [],
        "root_files": [],
        "excluded_directory_names": ["__pycache__"],
        "archive_roots": [],
        "legacy_compatible_prefixes": [],
        "phase_fixture_prefixes": [],
        "manual_entrypoint_paths": [],
        "superseded_compatible_paths": ["src/demo/unused.py"],
        "stable_entrypoints": ["scripts/run.py"],
    }

    inventory = build_repository_architecture_inventory(tmp_path, policy)
    nodes = {node["path"]: node for node in inventory["nodes"]}

    assert nodes["src/demo/used.py"]["reachable_from_stable_entrypoint"] is True
    assert nodes["src/demo/unused.py"]["classification"] == "superseded_compatible"
    assert nodes["src/demo/unused.py"]["review_status"] == "retain"
    assert any(
        edge["source"] == "scripts/run.py"
        and edge["target"] == "src/demo/used.py"
        and edge["edge_type"] == "python_import"
        for edge in inventory["edges"]
    )


def test_policy_and_markdown_are_reproducible(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "schema_version": "finsight_repository_architecture_policy_v0_1",
                "source_roots": [],
                "script_roots": [],
                "test_roots": [],
                "app_roots": [],
                "documentation_roots": [],
                "config_roots": [],
            }
        ),
        encoding="utf-8",
    )
    policy = load_inventory_policy(policy_path)
    first = build_repository_architecture_inventory(tmp_path, policy)
    second = build_repository_architecture_inventory(tmp_path, policy)

    assert first["inventory_digest"] == second["inventory_digest"]
    markdown = render_repository_architecture_markdown(first)
    assert "Repository Architecture Map" in markdown
    assert "持续维护规则" in markdown


def test_repository_guard_blocks_archive_dependency_and_tracked_output() -> None:
    inventory = {
        "summary": {
            "python_parse_error_count": 0,
            "missing_stable_entrypoint_count": 0,
            "review_candidate_count": 0,
        },
        "nodes": [
            {"path": "src/live.py", "kind": "source", "classification": "active_source", "line_count": 10},
            {"path": "archive/old.py", "kind": "archive", "classification": "archived", "line_count": 10},
        ],
        "edges": [
            {"source": "src/live.py", "target": "archive/old.py", "edge_type": "python_import"},
        ],
    }
    policy = {
        "schema_version": "finsight_repository_code_health_guard_v0_1",
        "critical_line_threshold": 4000,
        "warning_line_threshold": 1500,
        "max_review_candidates": 5,
        "forbidden_tracked_prefixes": ["eval/"],
        "forbidden_tracked_names": [".env"],
        "grandfathered_hotspots": {},
    }

    result = evaluate_repository_architecture_guard(
        inventory,
        policy,
        tracked_paths=["eval/output.json", ".env"],
    )

    assert result["status"] == "fail"
    codes = {item["code"] for item in result["errors"]}
    assert "active_dependency_on_archive" in codes
    assert "forbidden_tracked_artifact" in codes
