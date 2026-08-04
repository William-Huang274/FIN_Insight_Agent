from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.fin_0_1_2_s3_t04_product_surface import (  # noqa: E402
    materialize_verified_product_surface,
)
from scripts.releases import (  # noqa: E402
    run_fin_ia_0_1_2_s3_t03_nvda_replacement_controlled_successor as replacement,
)


RESULT = (
    ROOT
    / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2/execution-result.json"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t04_product_surface_"
    "convergence_and_evidence_density_block_v1_0.json"
)


def assess() -> dict:
    execution_result = json.loads(RESULT.read_text(encoding="utf-8"))
    base = replacement._activate_issued_binding()
    target = base.load_target()
    admission = base.load_admission(target)
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t04-product-surface-"
    ) as temp:
        prepared = base.prepare_exact_input(Path(temp), target, admission)
    return materialize_verified_product_surface(
        execution_result=execution_result,
        input_pack=prepared.input_pack.model_dump(mode="json"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(
        assess(), ensure_ascii=False, indent=2, sort_keys=True
    )
    if args.output is not None:
        output = args.output.resolve()
        if output != DEFAULT_OUTPUT.resolve():
            raise ValueError("s3_t04_product_surface_output_path_not_allowed")
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
