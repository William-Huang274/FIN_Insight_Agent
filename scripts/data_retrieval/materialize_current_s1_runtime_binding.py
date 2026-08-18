from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.current_runtime_binding import (  # noqa: E402
    build_current_s1_runtime_binding_receipt,
)


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind the current S1 source, object, index, S2 and reviewed-Pack "
            "surfaces and expose declared-versus-executable route truth."
        )
    )
    parser.add_argument(
        "--policy",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_current_product_runtime_binding_policy_v1_2.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "configs/runtime/"
            "fin_ia_0_1_3_current_s1_runtime_binding_receipt_v1_2.json"
        ),
    )
    args = parser.parse_args()
    policy = _read_json(_resolve(args.policy))
    receipt = build_current_s1_runtime_binding_receipt(ROOT, policy)
    _write_json(_resolve(args.output), receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "source_record_count": receipt[
                    "source_object_index_lineage"
                ]["source_record_count"],
                "compiled_object_count": receipt[
                    "source_object_index_lineage"
                ]["compiled_object_count"],
                "unavailable_routes": receipt["route_execution_truth"][
                    "unavailable_routes"
                ],
                "result_digest": receipt["result_digest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
