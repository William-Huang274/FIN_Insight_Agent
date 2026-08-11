from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "finsight_repository_architecture_inventory_v0_1"
PATH_REFERENCE_RE = re.compile(
    r"(?P<path>(?:src|scripts|tests|apps|docs|configs|data/manifests)/[A-Za-z0-9_.\-/]+)"
)
QUOTED_FILE_REFERENCE_RE = re.compile(r"['\"](?P<name>[A-Za-z0-9_.-]+\.(?:py|md|json|jsonl|yaml|yml|toml|ps1|sh))['\"]")
TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".jsonl",
    ".toml",
    ".yaml",
    ".yml",
    ".txt",
    ".tsx",
    ".ts",
    ".js",
    ".ps1",
    ".sh",
    ".java",
    ".kt",
    ".css",
    ".html",
}
CODE_SUFFIXES = {".py", ".tsx", ".ts", ".js", ".ps1", ".sh", ".java", ".kt", ".css", ".html"}


@dataclass(frozen=True)
class RepositoryNode:
    path: str
    kind: str
    classification: str
    size_bytes: int
    line_count: int
    digest: str
    has_main: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "classification": self.classification,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "digest": self.digest,
            "has_main": self.has_main,
        }


def load_inventory_policy(path: str | Path) -> dict[str, Any]:
    policy_path = Path(path)
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "finsight_repository_architecture_policy_v0_1":
        raise ValueError(f"Unsupported repository policy: {payload.get('schema_version')}")
    return payload


def build_repository_architecture_inventory(repo_root: str | Path, policy: dict[str, Any]) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    files = _collect_repository_files(root, policy)
    nodes = [_build_node(root, path, policy) for path in files]
    node_by_path = {node.path: node for node in nodes}
    basename_to_paths: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        basename_to_paths[PurePosixPath(node.path).name].append(node.path)
    module_to_path = _python_module_map(nodes)

    edges: set[tuple[str, str, str]] = set()
    parse_errors: list[dict[str, str]] = []
    for node in nodes:
        path = root / node.path
        if path.suffix == ".py":
            try:
                for target in _python_import_targets(path, node.path, module_to_path):
                    if target in node_by_path and target != node.path:
                        edges.add((node.path, target, "python_import"))
            except (SyntaxError, UnicodeDecodeError) as exc:
                parse_errors.append({"path": node.path, "error": f"{type(exc).__name__}: {exc}"})
        if path.suffix in TEXT_SUFFIXES | {".py"}:
            for target in _text_path_references(path, node_by_path, basename_to_paths):
                if target != node.path:
                    edges.add((node.path, target, "path_reference"))

    incoming: Counter[str] = Counter()
    outgoing: Counter[str] = Counter()
    runtime_incoming: Counter[str] = Counter()
    test_incoming: Counter[str] = Counter()
    doc_incoming: Counter[str] = Counter()
    for source, target, _edge_type in edges:
        incoming[target] += 1
        outgoing[source] += 1
        if source.startswith(("src/", "scripts/", "apps/")):
            runtime_incoming[target] += 1
        if source.startswith("tests/"):
            test_incoming[target] += 1
        if source.startswith("docs/"):
            doc_incoming[target] += 1

    reachable = _reachable_from_entrypoints(policy.get("stable_entrypoints", []), edges)
    enriched_nodes = []
    for node in nodes:
        item = node.as_dict()
        item.update(
            {
                "incoming_reference_count": incoming[node.path],
                "runtime_reference_count": runtime_incoming[node.path],
                "outgoing_reference_count": outgoing[node.path],
                "test_reference_count": test_incoming[node.path],
                "documentation_reference_count": doc_incoming[node.path],
                "reachable_from_stable_entrypoint": node.path in reachable,
                "review_status": _review_status(
                    node,
                    runtime_incoming[node.path],
                    test_incoming[node.path],
                    node.path in reachable,
                ),
            }
        )
        enriched_nodes.append(item)

    entrypoint_status = [
        {"path": path, "exists": path in node_by_path, "reachable_node_count": len(_reachable_from_entrypoints([path], edges))}
        for path in policy.get("stable_entrypoints", [])
    ]
    data_assets = _collect_data_assets(root)
    summary = _build_summary(enriched_nodes, edges, data_assets, parse_errors, entrypoint_status)
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(root),
        "policy_version": policy.get("schema_version"),
        "summary": summary,
        "nodes": sorted(enriched_nodes, key=lambda item: item["path"]),
        "edges": [
            {"source": source, "target": target, "edge_type": edge_type}
            for source, target, edge_type in sorted(edges)
        ],
        "data_assets": data_assets,
        "stable_entrypoints": entrypoint_status,
        "parse_errors": parse_errors,
    }
    inventory["inventory_digest"] = _stable_digest(inventory)
    return inventory


def render_repository_architecture_markdown(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    nodes = inventory["nodes"]
    data_assets = inventory["data_assets"]
    hotspots = sorted(
        [node for node in nodes if node["kind"] in {"source", "script", "app"}],
        key=lambda item: (item["line_count"], item["size_bytes"]),
        reverse=True,
    )[:20]
    review_candidates = [node for node in nodes if node["review_status"] == "review_candidate"][:80]
    classification_counts = Counter(node["classification"] for node in nodes)
    kind_counts = Counter(node["kind"] for node in nodes)
    data_type_counts = Counter(item["asset_type"] for item in data_assets)

    lines = [
        "# FinSight Repository Architecture Map",
        "",
        "生成方式：`python scripts/engineering/build_repository_architecture_inventory.py`。",
        "",
        f"Schema：`{inventory['schema_version']}`；digest：`{inventory['inventory_digest']}`。",
        "",
        "## 1. 使用边界",
        "",
        "本图由静态 AST import、文档/配置路径引用和文件元数据生成。动态 import、字符串拼接路径、外部 scheduler 和人工运行命令可能无法完全识别；`review_candidate` 只表示需要人工审查，不等于可删除。",
        "",
        "## 2. 仓库摘要",
        "",
        f"- 节点：{summary['node_count']}；引用边：{summary['edge_count']}。",
        f"- Python parse errors：{summary['python_parse_error_count']}。",
        f"- stable entrypoint 可达节点：{summary['reachable_node_count']}。",
        f"- 缺失 stable entrypoints：{summary['missing_stable_entrypoint_count']}。",
        f"- review candidates：{summary['review_candidate_count']}。",
        "",
        "| Kind | Files |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in sorted(kind_counts.items()))
    lines.extend(["", "| Classification | Files |", "| --- | ---: |"])
    lines.extend(f"| `{key}` | {value} |" for key, value in sorted(classification_counts.items()))

    lines.extend(
        [
            "",
            "## 3. 功能关系图",
            "",
            "```mermaid",
            "flowchart LR",
            '    UI["Workbench / CLI / MCP"] --> RT["Runtime and Task Spine"]',
            '    RT --> LEAD["Lead / Decision Surface / Workpaper"]',
            '    LEAD --> EV["EvidenceRequest / Retrieval / RAG / DB"]',
            '    EV --> NUM["Parser / Numeric / Promotion"]',
            '    NUM --> DOM["Domain Operators / Graph / Market / Risk"]',
            '    DOM --> JUD["Cell Adjudication / LeadReview"]',
            '    JUD --> WR["Writer / Deliverable / Verifier"]',
            '    WR --> UI',
            '    RT --> CTX["Context / Memory / Skills"]',
            '    RT --> HAR["Durable State / Permission / Trace"]',
            '    HAR --> EVAL["Eval / Failure Attribution / Release"]',
            '    EV --> DATA["SEC / Public Sources / SQL / Vector / Graph"]',
            "```",
            "",
            "## 4. 目录与引用职责",
            "",
            "```mermaid",
            "flowchart TD",
            '    DOCS["docs/product + TECH + worklog"] --> CFG["configs / contracts"]',
            '    CFG --> SRC["src libraries and runtime"]',
            '    SCRIPTS["scripts entrypoints / builders / eval"] --> SRC',
            '    TESTS["tests deterministic and integration"] --> SRC',
            '    APPS["apps/workbench"] --> SRC',
            '    SRC --> MAN["data/manifests reviewed summaries"]',
            '    SRC --> PRIVATE["data private / indexes / databases"]',
            '    SRC --> OUT["eval / reports runtime outputs"]',
            '    MAN --> DOCS',
            '    OUT -. "ignored; referenced by durable summaries" .-> DOCS',
            "```",
            "",
            "## 5. 复杂度热点",
            "",
            "| Path | Lines | Bytes | Incoming | Tests | Classification |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    lines.extend(
        f"| `{node['path']}` | {node['line_count']} | {node['size_bytes']} | {node['incoming_reference_count']} | {node['test_reference_count']} | `{node['classification']}` |"
        for node in hotspots
    )
    lines.extend(
        [
            "",
            "复杂文件不是自动 archive 候选。超过阈值的核心 runtime 应优先拆 pure contracts、selectors、state transitions 和 adapters，并以 characterization tests 保护行为。",
            "",
            "## 6. 数据、RAG、向量与数据库资产",
            "",
            "| Asset type | Count |",
            "| --- | ---: |",
        ]
    )
    lines.extend(f"| `{key}` | {value} |" for key, value in sorted(data_type_counts.items()))
    lines.extend(
        [
            "",
            "完整路径、大小和 metadata 位于 `data/manifests/repository_architecture_inventory_v0_1.json` 的 `data_assets`。私有 raw data、索引和数据库不进入 Git；这里只跟踪元数据和可复现入口。",
            "",
            "## 7. Review Candidates",
            "",
            "以下仅表示静态图中没有稳定入口可达、test 或其他引用。动态调用仍需人工确认。",
            "",
            "| Path | Kind | Classification | Incoming |",
            "| --- | --- | --- | ---: |",
        ]
    )
    if review_candidates:
        lines.extend(
            f"| `{node['path']}` | `{node['kind']}` | `{node['classification']}` | {node['incoming_reference_count']} |"
            for node in review_candidates
        )
    else:
        lines.append("| _none_ | | | 0 |")
    lines.extend(
        [
            "",
            "## 8. 持续维护规则",
            "",
            "1. 新增/移动 source、script、test、TECH 或 manifest 后重跑 inventory builder。",
            "2. CI 比较 inventory digest、parse errors、stable entrypoint 缺失和新增 review candidates。",
            "3. archive 前必须有零 runtime/test/doc 引用、替代入口、迁移说明和 targeted tests。",
            "4. generated outputs 只保留 summary/manifest/ref，不把 raw eval、index、database 或 private data 加入 Git。",
            "5. 单文件超过 warning threshold 时创建 complexity debt；超过 critical threshold 时原则上禁止继续堆新职责，除非有明确例外和拆分计划。",
            "",
        ]
    )
    return "\n".join(lines)


def write_inventory_outputs(
    inventory: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> None:
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_target.parent.mkdir(parents=True, exist_ok=True)
    markdown_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_target.write_text(render_repository_architecture_markdown(inventory), encoding="utf-8")


def evaluate_repository_architecture_guard(
    inventory: dict[str, Any],
    guard_policy: dict[str, Any],
    *,
    tracked_paths: Iterable[str] = (),
) -> dict[str, Any]:
    if guard_policy.get("schema_version") != "finsight_repository_code_health_guard_v0_1":
        raise ValueError(f"Unsupported code-health policy: {guard_policy.get('schema_version')}")
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    summary = inventory["summary"]
    if summary.get("python_parse_error_count"):
        errors.append({"code": "python_parse_error", "count": summary["python_parse_error_count"]})
    if summary.get("missing_stable_entrypoint_count"):
        errors.append({"code": "missing_stable_entrypoint", "count": summary["missing_stable_entrypoint_count"]})
    if summary.get("review_candidate_count", 0) > int(guard_policy.get("max_review_candidates", 0)):
        errors.append(
            {
                "code": "review_candidate_budget_exceeded",
                "count": summary["review_candidate_count"],
                "limit": guard_policy.get("max_review_candidates"),
            }
        )

    node_by_path = {node["path"]: node for node in inventory["nodes"]}
    critical_threshold = int(guard_policy.get("critical_line_threshold", 4000))
    warning_threshold = int(guard_policy.get("warning_line_threshold", 1500))
    grandfathered = guard_policy.get("grandfathered_hotspots", {})
    for node in inventory["nodes"]:
        if node["kind"] not in {"source", "script", "app"} or node["classification"] == "archived":
            continue
        if not node["path"].endswith((".py", ".tsx", ".ts", ".js", ".java", ".kt")):
            continue
        lines = int(node["line_count"])
        path = node["path"]
        if path in grandfathered and lines > int(grandfathered[path]):
            errors.append(
                {"code": "grandfathered_hotspot_growth", "path": path, "lines": lines, "limit": grandfathered[path]}
            )
        elif lines >= critical_threshold and path not in grandfathered:
            errors.append({"code": "unregistered_critical_hotspot", "path": path, "lines": lines})
        elif lines >= warning_threshold:
            warnings.append({"code": "complexity_warning", "path": path, "lines": lines})

    for edge in inventory["edges"]:
        source = node_by_path.get(edge["source"])
        target = node_by_path.get(edge["target"])
        if (
            source
            and target
            and source["kind"] in {"source", "script", "app"}
            and source["classification"] != "archived"
            and target["classification"] == "archived"
        ):
            errors.append(
                {
                    "code": "active_dependency_on_archive",
                    "source": edge["source"],
                    "target": edge["target"],
                    "edge_type": edge["edge_type"],
                }
            )

    forbidden_prefixes = tuple(guard_policy.get("forbidden_tracked_prefixes", []))
    forbidden_names = set(guard_policy.get("forbidden_tracked_names", []))
    for path in tracked_paths:
        normalized = str(path).replace("\\", "/").lstrip("./")
        if normalized in forbidden_names or normalized.startswith(forbidden_prefixes):
            errors.append({"code": "forbidden_tracked_artifact", "path": normalized})
        if "/__pycache__/" in f"/{normalized}/" or normalized.endswith(".pyc"):
            errors.append({"code": "tracked_python_cache", "path": normalized})

    return {
        "schema_version": "finsight_repository_code_health_guard_result_v0_1",
        "status": "pass" if not errors else "fail",
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }


def _collect_repository_files(root: Path, policy: dict[str, Any]) -> list[Path]:
    roots = [
        *policy.get("source_roots", []),
        *policy.get("script_roots", []),
        *policy.get("test_roots", []),
        *policy.get("app_roots", []),
        *policy.get("documentation_roots", []),
        *policy.get("config_roots", []),
        *policy.get("audit_roots", []),
    ]
    excluded = set(policy.get("excluded_directory_names", []))
    files: list[Path] = []
    for relative_root in roots:
        base = root / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or any(part in excluded for part in path.relative_to(root).parts):
                continue
            if path.suffix in CODE_SUFFIXES | TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"}:
                files.append(path)
    for relative_path in policy.get("root_files", []):
        path = root / relative_path
        if path.is_file():
            files.append(path)
    return sorted(set(files))


def _build_node(root: Path, path: Path, policy: dict[str, Any]) -> RepositoryNode:
    relative = path.relative_to(root).as_posix()
    raw = path.read_bytes()
    try:
        line_count = len(raw.decode("utf-8").splitlines())
    except UnicodeDecodeError:
        line_count = 0
    return RepositoryNode(
        path=relative,
        kind=_kind(relative),
        classification=_classification(relative, policy),
        size_bytes=len(raw),
        line_count=line_count,
        digest=hashlib.sha256(raw).hexdigest(),
        has_main=b"__main__" in raw if path.suffix == ".py" else False,
    )


def _kind(path: str) -> str:
    if path.startswith("src/"):
        return "source"
    if path.startswith("scripts/"):
        return "script"
    if path.startswith("tests/"):
        return "test"
    if path.startswith("apps/"):
        return "app"
    if path.startswith("docs/"):
        return "documentation"
    if path.startswith("configs/"):
        return "config"
    if path.startswith("archive/"):
        return "archive"
    if "/java/" in path or path.endswith((".java", ".kt")):
        return "app"
    if "/frontend/" in path or path.endswith((".tsx", ".ts", ".js", ".css", ".html")):
        return "app"
    if "/backend/" in path:
        return "app"
    if "/" not in path:
        return "build_config"
    return "other"


def _classification(path: str, policy: dict[str, Any]) -> str:
    if any(path == root or path.startswith(f"{root}/") for root in policy.get("archive_roots", [])):
        return "archived"
    if path in policy.get("manual_entrypoint_paths", []):
        return "manual_entrypoint"
    if path in policy.get("superseded_compatible_paths", []):
        return "superseded_compatible"
    if any(path.startswith(prefix) for prefix in policy.get("legacy_compatible_prefixes", [])):
        return "legacy_compatible"
    if any(path.startswith(prefix) for prefix in policy.get("phase_fixture_prefixes", [])):
        return "phase_fixture"
    if path.startswith("tests/"):
        return "test_asset"
    if path.startswith("docs/worklog/") or path.startswith("docs/internal/"):
        return "historical_audit"
    if path.startswith("docs/architecture/agent_graph_vnext/TECH_") or path.startswith("docs/product/"):
        return "canonical_contract"
    if path.startswith("scripts/"):
        return "active_script"
    if path.startswith("apps/"):
        return "product_surface"
    if path.startswith("configs/"):
        return "runtime_config"
    return "active_source"


def _python_module_map(nodes: Iterable[RepositoryNode]) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in nodes:
        if node.kind != "source" or not node.path.endswith(".py"):
            continue
        path = node.path.removeprefix("src/").removesuffix(".py")
        if path.endswith("/__init__"):
            path = path[: -len("/__init__")]
        result[path.replace("/", ".")] = node.path
    return result


def _python_import_targets(path: Path, relative_path: str, module_to_path: dict[str, str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current_module = relative_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    if current_module.endswith(".__init__"):
        current_module = current_module[: -len(".__init__")]
    targets: set[str] = set()
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = (
                    current_module.split(".")
                    if relative_path.endswith("/__init__.py")
                    else current_module.split(".")[:-1]
                )
                keep = max(0, len(package) - node.level + 1)
                base = ".".join([*package[:keep], *([base] if base else [])])
            modules.append(base)
        for module in modules:
            candidate = module
            while candidate:
                if candidate in module_to_path:
                    targets.add(module_to_path[candidate])
                    break
                candidate = candidate.rpartition(".")[0]
            else:
                sibling = (PurePosixPath(relative_path).parent / f"{module}.py").as_posix()
                targets.add(sibling)
    return targets


def _text_path_references(
    path: Path,
    node_by_path: dict[str, RepositoryNode],
    basename_to_paths: dict[str, list[str]],
) -> set[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return set()
    targets = set()
    for match in PATH_REFERENCE_RE.finditer(content.replace("\\", "/")):
        candidate = match.group("path").rstrip(".,;:)]}>`'\"")
        if candidate in node_by_path:
            targets.add(candidate)
    for match in QUOTED_FILE_REFERENCE_RE.finditer(content):
        matches = basename_to_paths.get(match.group("name"), [])
        if len(matches) == 1:
            targets.add(matches[0])
    return targets


def _reachable_from_entrypoints(entrypoints: Iterable[str], edges: Iterable[tuple[str, str, str]]) -> set[str]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for source, target, _edge_type in edges:
        adjacency[source].add(target)
    queue = deque(entrypoints)
    visited = set(entrypoints)
    while queue:
        current = queue.popleft()
        for target in adjacency.get(current, set()):
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return visited


def _review_status(node: RepositoryNode, runtime_incoming: int, test_incoming: int, reachable: bool) -> str:
    if node.classification == "archived":
        return "archived"
    if node.classification in {"manual_entrypoint", "superseded_compatible"}:
        return "retain"
    if node.path.endswith("/__init__.py") or node.path in {"src/__init__.py"}:
        return "retain"
    if node.kind == "script" and node.has_main:
        return "retain"
    if node.kind in {"source", "script"} and runtime_incoming == 0 and test_incoming == 0 and not reachable:
        return "review_candidate"
    return "retain"


def _collect_data_assets(root: Path) -> list[dict[str, Any]]:
    data_root = root / "data"
    if not data_root.exists():
        return []
    assets: list[dict[str, Any]] = []
    interesting_suffixes = {".sqlite", ".db", ".duckdb", ".faiss", ".index", ".pkl"}
    for path in data_root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        asset_type = None
        if path.suffix.lower() in {".sqlite", ".db", ".duckdb"}:
            asset_type = "database"
        elif path.suffix.lower() in {".faiss", ".index"} or "milvus" in relative.lower():
            asset_type = "vector_index_or_metadata"
        elif path.suffix.lower() == ".pkl" and "bm25" in relative.lower():
            asset_type = "lexical_index"
        elif relative.startswith("data/manifests/") and path.suffix.lower() in {".json", ".jsonl"}:
            asset_type = "manifest"
        elif relative.startswith("data/indexes/") and path.suffix.lower() in interesting_suffixes | {".json", ".jsonl"}:
            asset_type = "index_artifact"
        if asset_type:
            assets.append({"path": relative, "asset_type": asset_type, "size_bytes": path.stat().st_size})
    return sorted(assets, key=lambda item: (item["asset_type"], item["path"]))


def _build_summary(
    nodes: list[dict[str, Any]],
    edges: set[tuple[str, str, str]],
    data_assets: list[dict[str, Any]],
    parse_errors: list[dict[str, str]],
    entrypoint_status: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "python_parse_error_count": len(parse_errors),
        "reachable_node_count": sum(1 for node in nodes if node["reachable_from_stable_entrypoint"]),
        "review_candidate_count": sum(1 for node in nodes if node["review_status"] == "review_candidate"),
        "data_asset_count": len(data_assets),
        "missing_stable_entrypoint_count": sum(1 for item in entrypoint_status if not item["exists"]),
        "kind_counts": dict(sorted(Counter(node["kind"] for node in nodes).items())),
        "classification_counts": dict(sorted(Counter(node["classification"] for node in nodes).items())),
        "edge_type_counts": dict(sorted(Counter(edge_type for _, _, edge_type in edges).items())),
    }


def _stable_digest(payload: dict[str, Any]) -> str:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    normalized.pop("inventory_digest", None)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
