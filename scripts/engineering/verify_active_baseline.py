from __future__ import annotations

import argparse
import ast
from collections import deque
import json
from pathlib import Path
import re
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
_BASE_PYTHON_ENTRYPOINTS = (
    "apps/workbench/backend/app.py",
    "scripts/data_retrieval/build_bm25_index.py",
    "scripts/data_retrieval/build_current_compiled_object_views.py",
    "scripts/data_retrieval/build_current_financial_object_store.py",
    "scripts/data_retrieval/build_current_retrieval_snapshot.py",
    "scripts/data_retrieval/build_evidence_store.py",
    "scripts/data_retrieval/build_s2_company_financial_fact_mart.py",
    "scripts/data_retrieval/capture_s1b_official_sources.py",
    "scripts/data_retrieval/run_s1d_source_intake.py",
    "scripts/data_retrieval/run_s1d_official_pdf_successor.py",
    "scripts/data_retrieval/run_current_evidence_pack_promotion.py",
    "scripts/data_retrieval/materialize_s1c_financial_role_eval_set.py",
    "scripts/data_retrieval/materialize_s1c_object_role_review_set.py",
    "scripts/data_retrieval/materialize_s1c_requalified_qrels.py",
    "scripts/data_retrieval/run_s1c_compiled_object_retriever_comparison.py",
    "scripts/data_retrieval/run_s1c_cross_encoder_role_shadow.py",
    "scripts/data_retrieval/run_s1c_object_role_shadow.py",
    "scripts/data_retrieval/run_s1c_ranking_comparison.py",
    "scripts/data_sec/build_sec_8k_earnings_chunks.py",
    "scripts/data_sec/build_sec_8k_earnings_manifest.py",
    "scripts/data_sec/build_sec_chunks.py",
    "scripts/data_sec/build_sec_manifest.py",
    "scripts/data_sec/download_sec_8k_earnings.py",
    "scripts/data_sec/download_sec_filings.py",
    "scripts/data_sec/merge_sec_source_gaps.py",
    "scripts/dev/run_workbench_backend.py",
    "scripts/engineering/build_archive_redirect_index.py",
    "scripts/engineering/accept_current_three_case_product.py",
    "scripts/engineering/check_repository_secrets.py",
    "scripts/engineering/verify_active_baseline.py",
    "scripts/industry/10_download_industry_source_snapshot.py",
    "scripts/market/06_download_yahoo_chart_snapshot.py",
    "scripts/market/07_enrich_market_snapshot_valuation_fmp.py",
    "scripts/market/08_build_market_events_from_sec_manifest.py",
    "scripts/market/09_download_fmp_historical_snapshot.py",
    "scripts/market/10_normalize_market_snapshot_fixture.py",
    "scripts/market/20_build_market_snapshot_catalog.py",
    "scripts/market/30_compute_market_analytics.py",
    "scripts/market/40_build_market_evidence_pack.py",
    "scripts/market/50_validate_market_snapshot.py",
    "scripts/research/run_s3_current_research_consumer_zero_call.py",
    "scripts/research/run_s3_current_research_consumer_canary.py",
)


def _workbench_data_build_entrypoints() -> tuple[str, ...]:
    """Treat every maintained Operations data-build step as active code.

    These scripts are launched from catalog data rather than imported, so an
    ordinary AST import closure cannot discover them.  Keeping the catalog as
    the source of truth prevents a UI-reachable build from being audited as an
    orphan or omitted from old-reference checks.
    """

    source_root = str((ROOT / "src").resolve())
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from sec_agent.workbench.data_build import data_build_catalog

    return tuple(sorted({step.script for step in data_build_catalog()}))


PYTHON_ENTRYPOINTS = tuple(
    dict.fromkeys((*_BASE_PYTHON_ENTRYPOINTS, *_workbench_data_build_entrypoints()))
)
FRONTEND_ENTRYPOINTS = (
    "apps/workbench/frontend/vite/src/main.tsx",
)
REGISTRY_REF = (
    "configs/runtime/"
    "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
)
FORBIDDEN_ACTIVE_PATH_TOKENS = (
    "archive/",
    "fin_0_1_2",
    "p36",
    "r53_r60",
    "point02",
    "point03",
    "/attempts/",
)
_FRONTEND_IMPORT = re.compile(
    r"(?:from\s+|import\s*\(?\s*)[\"'](?P<ref>\.[^\"']+)[\"']"
)


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _active_python_modules() -> tuple[dict[str, Path], dict[Path, str]]:
    by_module: dict[str, Path] = {}
    by_path: dict[Path, str] = {}
    for path in ROOT.rglob("*.py"):
        relative = _relative(path)
        if relative.startswith(("archive/", ".codex_runtime/", ".git/")):
            continue
        if relative.startswith("src/"):
            parts = list(path.relative_to(ROOT / "src").with_suffix("").parts)
        else:
            parts = list(path.relative_to(ROOT).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)
        if module:
            by_module[module] = path.resolve()
            by_path[path.resolve()] = module
    return by_module, by_path


def _resolve_python_imports(
    path: Path,
    module: str,
    by_module: dict[str, Path],
) -> tuple[set[Path], list[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return set(), [f"{_relative(path)}:{type(exc).__name__}"]
    discovered: set[Path] = set()
    unresolved: list[str] = []
    package_parts = module.split(".")
    if path.name != "__init__.py":
        package_parts = package_parts[:-1]

    def admit(name: str) -> bool:
        target = by_module.get(name)
        if target is not None:
            discovered.add(target)
            return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if not any(admit(".".join(parts[:index])) for index in range(len(parts), 0, -1)):
                    if alias.name.startswith(("apps.", "sec_agent.")):
                        unresolved.append(f"{_relative(path)}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package_parts) - node.level + 1
                base_parts = package_parts[: max(0, keep)]
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = node.module or ""
            matched = admit(base) if base else False
            for alias in node.names:
                if alias.name == "*":
                    continue
                candidate = f"{base}.{alias.name}" if base else alias.name
                matched = admit(candidate) or matched
            if not matched and base.startswith(("apps.", "sec_agent.")):
                unresolved.append(f"{_relative(path)}:{base}")
    return discovered, unresolved


def python_closure(entrypoints: Iterable[str]) -> tuple[list[str], list[str]]:
    by_module, by_path = _active_python_modules()
    queue: deque[Path] = deque()
    for ref in entrypoints:
        path = (ROOT / ref).resolve()
        if not path.is_file():
            raise RuntimeError(f"active_baseline_entrypoint_missing:{ref}")
        queue.append(path)
    visited: set[Path] = set()
    unresolved: list[str] = []
    while queue:
        path = queue.popleft()
        if path in visited:
            continue
        visited.add(path)
        module = by_path.get(path)
        if module is None:
            raise RuntimeError(f"active_baseline_module_unmapped:{_relative(path)}")
        dependencies, errors = _resolve_python_imports(path, module, by_module)
        unresolved.extend(errors)
        queue.extend(sorted(dependencies))
    return sorted(_relative(path) for path in visited), sorted(set(unresolved))


def _resolve_frontend_import(source: Path, ref: str) -> Path | None:
    candidate = (source.parent / ref).resolve()
    possibilities = (
        candidate,
        candidate.with_suffix(".ts"),
        candidate.with_suffix(".tsx"),
        candidate.with_suffix(".js"),
        candidate.with_suffix(".jsx"),
        candidate / "index.ts",
        candidate / "index.tsx",
    )
    for path in possibilities:
        if path.is_file():
            return path
    return None


def frontend_closure(entrypoints: Iterable[str]) -> tuple[list[str], list[str]]:
    queue = deque((ROOT / ref).resolve() for ref in entrypoints)
    visited: set[Path] = set()
    unresolved: list[str] = []
    while queue:
        path = queue.popleft()
        if path in visited:
            continue
        if not path.is_file():
            unresolved.append(f"missing:{_relative(path)}")
            continue
        visited.add(path)
        text = path.read_text(encoding="utf-8")
        for match in _FRONTEND_IMPORT.finditer(text):
            ref = match.group("ref")
            dependency = _resolve_frontend_import(path, ref)
            if dependency is None:
                unresolved.append(f"{_relative(path)}:{ref}")
            else:
                queue.append(dependency)
    return sorted(_relative(path) for path in visited), sorted(set(unresolved))


def _forbidden_refs(refs: Iterable[str]) -> list[str]:
    return sorted(
        ref
        for ref in refs
        if any(token in f"/{ref.lower()}" for token in FORBIDDEN_ACTIVE_PATH_TOKENS)
    )


def build_report() -> dict[str, object]:
    python_refs, python_unresolved = python_closure(PYTHON_ENTRYPOINTS)
    frontend_refs, frontend_unresolved = frontend_closure(FRONTEND_ENTRYPOINTS)
    registry_path = ROOT / REGISTRY_REF
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    detector_refs = [str(value) for value in registry.get("detector_python_refs") or ()]
    resource_refs = [
        str(row.get("repo_relative_path") or "")
        for row in registry.get("resources") or ()
    ]
    forbidden = {
        "python_import_graph": _forbidden_refs(python_refs),
        "frontend_import_graph": _forbidden_refs(frontend_refs),
        "runtime_registry_detectors": _forbidden_refs(detector_refs),
        "runtime_registry_resources": _forbidden_refs(resource_refs),
    }
    failures: list[str] = []
    if python_unresolved:
        failures.append("local_python_import_unresolved")
    if frontend_unresolved:
        failures.append("local_frontend_import_unresolved")
    if any(forbidden.values()):
        failures.append("forbidden_old_consumer_reachable")
    return {
        "schema_version": "fin_ia_active_baseline_import_graph_v1_0",
        "status": "pass" if not failures else "fail",
        "entrypoints": {
            "python": list(PYTHON_ENTRYPOINTS),
            "frontend": list(FRONTEND_ENTRYPOINTS),
            "runtime_registry": REGISTRY_REF,
        },
        "observed": {
            "python_files": len(python_refs),
            "frontend_files": len(frontend_refs),
            "runtime_detector_files": len(detector_refs),
            "runtime_resources": len(resource_refs),
        },
        "python_import_graph": python_refs,
        "frontend_import_graph": frontend_refs,
        "runtime_detector_refs": detector_refs,
        "runtime_resource_refs": resource_refs,
        "unresolved": {
            "python": python_unresolved,
            "frontend": frontend_unresolved,
        },
        "forbidden_references": forbidden,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the same report to a repository-relative JSON file.",
    )
    args = parser.parse_args()
    report = build_report()
    rendered = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if args.pretty else None,
    )
    if args.output is not None:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output = output.resolve()
        output.relative_to(ROOT)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
