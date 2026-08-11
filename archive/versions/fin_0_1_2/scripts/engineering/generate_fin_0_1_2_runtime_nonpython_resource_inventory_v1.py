from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.research_skills import PROMPT_ROOT, SKILL_FILES


OUTPUT = ROOT / (
    "configs/runtime/fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0.json"
)
REGISTRY = ROOT / "src/sec_agent/research_skills.py"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def generate(output: Path = OUTPUT) -> str:
    resources = []
    for skill_id, filename in sorted(SKILL_FILES.items()):
        path = PROMPT_ROOT / filename
        value = path.read_bytes()
        resources.append(
            {
                "skill_id": skill_id,
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(value),
                "sha256": _sha256(value),
            }
        )
    resource_digest = _sha256(_canonical_bytes(resources))
    inventory = {
        "schema_version": (
            "fin_ia_0_1_2_runtime_nonpython_resource_inventory_v1_0"
        ),
        "inventory_id": (
            "FIN-0.1.2-PRE-S2-RUNTIME-NONPYTHON-RESOURCE-INVENTORY-R1"
        ),
        "status": "tracked_exact_runtime_resource_inventory",
        "registry_ref": REGISTRY.relative_to(ROOT).as_posix(),
        "registry_mapping_name": "SKILL_FILES",
        "registry_source_sha256": _sha256(REGISTRY.read_bytes()),
        "resource_root": PROMPT_ROOT.relative_to(ROOT).as_posix(),
        "resource_count": len(resources),
        "resource_bytes": sum(row["bytes"] for row in resources),
        "resource_canonical_digest": resource_digest,
        "resources": resources,
        "package_contract": {
            "registry_mapping_is_source_of_truth": True,
            "directory_glob_is_authority": False,
            "missing_resource_fails_before_pytest": True,
            "duplicate_skill_or_path_fails_before_pytest": True,
            "path_or_hash_drift_fails_before_pytest": True,
            "unknown_inventory_resource_fails_before_pytest": True,
        },
    }
    rendered = (
        json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise RuntimeError("runtime_resource_inventory_output_exists_with_drift")
    output.write_text(rendered, encoding="utf-8", newline="\n")
    return _sha256(rendered.encode("utf-8"))


def main() -> int:
    digest = generate()
    print(
        json.dumps(
            {
                "status": "pass_runtime_resource_inventory_generated",
                "output_ref": OUTPUT.relative_to(ROOT).as_posix(),
                "inventory_sha256": digest,
                "resource_count": len(SKILL_FILES),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
