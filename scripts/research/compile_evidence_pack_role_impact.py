from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.research.multi_agent_preview import (  # noqa: E402
    load_multi_agent_role_topology,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    compile_evidence_pack_role_impact_zero_call_projection,
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a zero-call proposition-bound specialist impact receipt "
            "for two immutable reviewed Evidence Packs."
        )
    )
    parser.add_argument("--topology", required=True)
    parser.add_argument("--objective", required=True)
    parser.add_argument("--specialist-checkpoint", required=True)
    parser.add_argument("--lead-checkpoint", required=True)
    parser.add_argument("--predecessor-pack", required=True)
    parser.add_argument("--successor-pack", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = {
        "topology": _resolve(args.topology),
        "objective": _resolve(args.objective),
        "specialist_checkpoint": _resolve(args.specialist_checkpoint),
        "lead_checkpoint": _resolve(args.lead_checkpoint),
        "predecessor_pack": _resolve(args.predecessor_pack),
        "successor_pack": _resolve(args.successor_pack),
        "output": _resolve(args.output),
    }
    topology = load_multi_agent_role_topology(_load(paths["topology"]))
    specialist_checkpoint = validate_specialist_plan_checkpoint(
        _load(paths["specialist_checkpoint"]), topology=topology
    )
    opinions = list(specialist_checkpoint["specialist_plans"])
    lead_checkpoint = validate_lead_plan_checkpoint(
        _load(paths["lead_checkpoint"]),
        opinions=opinions,
        topology=topology,
    )
    result = compile_evidence_pack_role_impact_zero_call_projection(
        repo_root=ROOT,
        topology=topology,
        objective_payload=_load(paths["objective"]),
        opinions=opinions,
        lead_plan=lead_checkpoint["lead_plan"],
        predecessor_evidence_pack=_load(paths["predecessor_pack"]),
        successor_evidence_pack=_load(paths["successor_pack"]),
    )
    result["input_bindings"] = {
        key: {"ref": _relative(path), "sha256": _sha256(path)}
        for key, path in paths.items()
        if key != "output"
    }
    result_without_digest = {
        key: value for key, value in result.items() if key != "result_digest"
    }
    from sec_agent.canonical_runtime import canonical_digest

    result["result_digest"] = canonical_digest(result_without_digest)
    paths["output"].parent.mkdir(parents=True, exist_ok=True)
    paths["output"].write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
