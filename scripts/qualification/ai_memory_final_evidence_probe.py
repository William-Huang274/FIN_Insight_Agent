"""Compatibility entry point; use scripts.qualification.ai_memory.final_evidence_probe."""
import importlib
import runpy
import sys

if __name__ == "__main__":
    runpy.run_module("scripts.qualification.ai_memory.final_evidence_probe", run_name="__main__")
else:
    sys.modules[__name__] = importlib.import_module("scripts.qualification.ai_memory.final_evidence_probe")
