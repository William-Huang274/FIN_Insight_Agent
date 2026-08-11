"""Executable governance for the legacy-to-canonical engineering handoff."""

from __future__ import annotations

import fnmatch
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping


CANONICAL_SCHEMA = "finsight_canonical_object_registry_v0_1"
MAPPING_SCHEMA = "finsight_legacy_object_mapping_matrix_v0_1"
TEST_PROFILE_SCHEMA = "finsight_test_profile_registry_v0_1"
HANDOFF_SCHEMA = "finsight_engineering_handoff_summary_v0_1"

REQUIRED_CANONICAL_FIELDS = {
    "object_id",
    "object_name",
    "domain",
    "owner",
    "identity_fields",
    "version_fields",
    "target_store",
    "producer_boundary",
    "consumer_boundary",
    "maturity",
    "runtime_write_status",
}
REQUIRED_MAPPING_FIELDS = {
    "mapping_id",
    "legacy_object",
    "legacy_refs",
    "canonical_object_ids",
    "migration_mode",
    "adapter_direction",
    "transition_source_of_truth",
    "target_write_policy",
    "information_loss",
    "cutover_gate",
}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_canonical_registry(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != CANONICAL_SCHEMA:
        errors.append("canonical_schema_version_invalid")
    objects = payload.get("objects")
    if not isinstance(objects, list) or not objects:
        return [*errors, "canonical_objects_required"]
    ids: set[str] = set()
    for index, item in enumerate(objects):
        if not isinstance(item, Mapping):
            errors.append(f"canonical_object_{index}_not_object")
            continue
        missing = sorted(REQUIRED_CANONICAL_FIELDS - set(item))
        if missing:
            errors.append(f"canonical_object_{index}_missing:{','.join(missing)}")
        object_id = str(item.get("object_id") or "")
        if not object_id.startswith("co_"):
            errors.append(f"canonical_object_id_invalid:{object_id or index}")
        if object_id in ids:
            errors.append(f"canonical_object_id_duplicate:{object_id}")
        ids.add(object_id)
        if not item.get("identity_fields") or not item.get("version_fields"):
            errors.append(f"canonical_identity_or_version_missing:{object_id}")
        if item.get("runtime_write_status") != "not_cut_over":
            errors.append(f"canonical_runtime_write_status_must_be_not_cut_over:{object_id}")
    for item in objects:
        for dependency in item.get("depends_on", []):
            if dependency not in ids:
                errors.append(f"canonical_dependency_missing:{item.get('object_id')}:{dependency}")
    return errors


def validate_legacy_mapping(
    payload: Mapping[str, Any],
    canonical_payload: Mapping[str, Any],
    *,
    repo_root: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != MAPPING_SCHEMA:
        errors.append("mapping_schema_version_invalid")
    canonical_ids = {item["object_id"] for item in canonical_payload.get("objects", [])}
    covered_ids: set[str] = set()
    mapping_ids: set[str] = set()
    root = Path(repo_root).resolve() if repo_root else None
    rows = payload.get("mappings")
    if not isinstance(rows, list) or not rows:
        return [*errors, "legacy_mappings_required"]
    for index, item in enumerate(rows):
        if not isinstance(item, Mapping):
            errors.append(f"legacy_mapping_{index}_not_object")
            continue
        missing = sorted(REQUIRED_MAPPING_FIELDS - set(item))
        if missing:
            errors.append(f"legacy_mapping_{index}_missing:{','.join(missing)}")
        mapping_id = str(item.get("mapping_id") or "")
        if mapping_id in mapping_ids:
            errors.append(f"legacy_mapping_id_duplicate:{mapping_id}")
        mapping_ids.add(mapping_id)
        targets = item.get("canonical_object_ids") or []
        for target in targets:
            if target not in canonical_ids:
                errors.append(f"legacy_mapping_unknown_target:{mapping_id}:{target}")
            covered_ids.add(target)
        if item.get("adapter_direction") != "legacy_to_canonical":
            errors.append(f"legacy_mapping_direction_invalid:{mapping_id}")
        if item.get("transition_source_of_truth") != "legacy_until_cutover_gate":
            errors.append(f"legacy_mapping_source_of_truth_invalid:{mapping_id}")
        if root:
            for ref in item.get("legacy_refs") or []:
                if not (root / ref).exists():
                    errors.append(f"legacy_mapping_ref_missing:{mapping_id}:{ref}")
    for object_id in sorted(canonical_ids - covered_ids):
        errors.append(f"canonical_object_without_handoff_mapping:{object_id}")
    return errors


def validate_test_profile_registry(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != TEST_PROFILE_SCHEMA:
        errors.append("test_profile_schema_version_invalid")
    profiles = payload.get("profiles") or []
    profile_ids = [str(item.get("profile_id") or "") for item in profiles if isinstance(item, Mapping)]
    if len(profile_ids) != len(set(profile_ids)):
        errors.append("test_profile_id_duplicate")
    default_profile = payload.get("default_profile")
    if default_profile not in profile_ids:
        errors.append("test_default_profile_unknown")
    for index, rule in enumerate(payload.get("rules") or []):
        if rule.get("profile") not in profile_ids:
            errors.append(f"test_profile_rule_unknown_profile:{index}")
        if not rule.get("nodeid_glob"):
            errors.append(f"test_profile_rule_pattern_missing:{index}")
    return errors


def classify_test_nodeid(nodeid: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = nodeid.replace("\\", "/")
    profile = str(payload.get("default_profile") or "fast_contract")
    requirements: set[str] = set()
    matched_rules: list[str] = []
    for index, rule in enumerate(payload.get("rules") or []):
        if fnmatch.fnmatchcase(normalized, str(rule.get("nodeid_glob") or "")):
            profile = str(rule["profile"])
            requirements.update(str(value) for value in rule.get("requirements") or [])
            matched_rules.append(str(rule.get("rule_id") or f"rule_{index}"))
            if rule.get("terminal", True):
                break
    return {
        "nodeid": normalized,
        "profile": profile,
        "requirements": sorted(requirements),
        "matched_rules": matched_rules,
    }


def build_test_file_audit(repo_root: str | Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    rows = []
    for path in sorted((root / "tests").glob("test_*.py")):
        relative = path.relative_to(root).as_posix()
        classified = classify_test_nodeid(f"{relative}::*", payload)
        rows.append(
            {
                "path": relative,
                "default_profile": classified["profile"],
                "requirements": classified["requirements"],
                "line_count": len(path.read_text(encoding="utf-8").splitlines()),
            }
        )
    return {
        "test_file_count": len(rows),
        "profile_file_counts": dict(sorted(Counter(row["default_profile"] for row in rows).items())),
        "files": rows,
    }


def build_handoff_summary(
    repo_root: str | Path,
    canonical_payload: Mapping[str, Any],
    mapping_payload: Mapping[str, Any],
    test_profile_payload: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    canonical_errors = validate_canonical_registry(canonical_payload)
    mapping_errors = validate_legacy_mapping(mapping_payload, canonical_payload, repo_root=root)
    test_errors = validate_test_profile_registry(test_profile_payload)
    test_audit = build_test_file_audit(root, test_profile_payload)
    collection_path = root / "data" / "manifests" / "test_profile_collection_v0_1.json"
    collection_audit = load_json(collection_path) if collection_path.exists() else {}
    errors = [*canonical_errors, *mapping_errors, *test_errors]
    objects = canonical_payload.get("objects") or []
    mappings = mapping_payload.get("mappings") or []
    return {
        "schema_version": HANDOFF_SCHEMA,
        "status": "pass" if not errors else "fail",
        "canonical_object_count": len(objects),
        "canonical_domain_counts": dict(sorted(Counter(item["domain"] for item in objects).items())),
        "legacy_mapping_count": len(mappings),
        "migration_mode_counts": dict(sorted(Counter(item["migration_mode"] for item in mappings).items())),
        "runtime_cutover_count": sum(item.get("runtime_write_status") != "not_cut_over" for item in objects),
        "canonical_objects": [
            {
                "object_id": item["object_id"],
                "object_name": item["object_name"],
                "domain": item["domain"],
                "owner": item["owner"],
                "target_store": item["target_store"],
                "runtime_write_status": item["runtime_write_status"],
            }
            for item in objects
        ],
        "legacy_mappings": [
            {
                "mapping_id": item["mapping_id"],
                "legacy_object": item["legacy_object"],
                "canonical_object_ids": item["canonical_object_ids"],
                "migration_mode": item["migration_mode"],
                "cutover_gate": item["cutover_gate"],
            }
            for item in mappings
        ],
        "test_profile_audit": test_audit,
        "test_profile_collection": {
            "manifest_present": bool(collection_audit),
            "collected_item_count": collection_audit.get("collected_item_count", 0),
            "profile_counts": collection_audit.get("profile_counts", {}),
            "requirement_counts": collection_audit.get("requirement_counts", {}),
        },
        "errors": errors,
        "boundaries": {
            "prd_or_tech_requirement_added": False,
            "runtime_write_path_changed": False,
            "legacy_store_remains_source_of_truth_until_cutover_gate": True,
            "paid_model_or_full_chain_executed": False,
        },
    }


def render_handoff_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Canonical / Legacy 工程交接基线",
        "",
        "日期：2026-07-11",
        "",
        f"状态：`{summary['status']}`。本文件是工程交接记录，不新增 PRD/TECH 需求，不表示 canonical runtime 已切换。",
        "",
        "## 1. 交接结果",
        "",
        f"- Canonical objects：{summary['canonical_object_count']}。",
        f"- Legacy mappings：{summary['legacy_mapping_count']}。",
        f"- Runtime cutovers：{summary['runtime_cutover_count']}。",
        f"- Test files：{summary['test_profile_audit']['test_file_count']}。",
        f"- Collected test items：{summary['test_profile_collection']['collected_item_count']}。",
        "",
        "| Canonical domain | Objects |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in summary["canonical_domain_counts"].items())
    lines.extend(["", "| Test profile | Files by default file rule |", "| --- | ---: |"])
    lines.extend(
        f"| `{key}` | {value} |" for key, value in summary["test_profile_audit"]["profile_file_counts"].items()
    )
    if summary["test_profile_collection"]["manifest_present"]:
        lines.extend(["", "| Test profile | Collected items |", "| --- | ---: |"])
        lines.extend(
            f"| `{key}` | {value} |"
            for key, value in summary["test_profile_collection"]["profile_counts"].items()
        )
    lines.extend(
        [
            "",
            "说明：node-specific rule 可覆盖文件默认 profile；最终 item 统计由 pytest collection manifest 提供。",
            "",
            "## 2. Source-of-truth 规则",
            "",
            "1. 当前 legacy store 继续拥有写权限，直到对应 mapping 的 cutover gate 通过。",
            "2. Adapter 方向只允许 legacy -> canonical；禁止 canonical -> legacy -> canonical 循环。",
            "3. Canonical registry 的 `not_cut_over` 是硬边界，不得解释为 runtime 已实现。",
            "4. Cutover 必须有 shadow diff、identity/version parity、trace、rollback 和 legacy read-only 证据。",
            "5. PRD/TECH 仍定义产品和技术 owner；本基线只负责旧资产如何交接，不扩展需求。",
            "",
            "## 3. Canonical object registry",
            "",
            "| Object | Domain | Owner | Target store | Runtime write |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{item['object_name']}` | `{item['domain']}` | `{item['owner']}` | `{item['target_store']}` | `{item['runtime_write_status']}` |"
        for item in summary["canonical_objects"]
    )
    lines.extend(
        [
            "",
            "## 4. Legacy mapping matrix",
            "",
            "| Mapping | Legacy object | Canonical target | Mode |",
            "| --- | --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{item['mapping_id']}` | {item['legacy_object']} | `{', '.join(item['canonical_object_ids'])}` | `{item['migration_mode']}` |"
        for item in summary["legacy_mappings"]
    )
    lines.extend(
        [
            "",
            "每条 mapping 的 legacy refs、information loss 和 cutover gate 以 `configs/engineering_handoff/legacy_object_mapping_matrix_v0_1.json` 为准。",
            "",
            "## 5. Test profile 使用",
            "",
            "```powershell",
            "pytest -m fast_contract",
            "pytest -m fixture_integration",
            "pytest -m local_data_integration",
            "pytest -m frontend_e2e",
            "pytest -m full_chain",
            "pytest -m paid_model",
            "pytest --collect-only -q --test-profile-report data/manifests/test_profile_collection_v0_1.json",
            "```",
            "",
            "默认 `pytest` 行为暂不改变，避免在交接阶段静默隐藏旧测试。CI 默认 profile 的切换应在基线稳定后作为单独工程决策进行。",
            "",
            "## 6. Validation",
            "",
            f"- Error count：{len(summary['errors'])}。",
        ]
    )
    if summary["errors"]:
        lines.extend(f"- `{error}`" for error in summary["errors"])
    else:
        lines.append("- Canonical registry、legacy mapping 和 test profile registry 交叉校验通过。")
    lines.append("")
    return "\n".join(lines)


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def collection_profile_rows(nodeids: Iterable[str], payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [classify_test_nodeid(nodeid, payload) for nodeid in nodeids]
