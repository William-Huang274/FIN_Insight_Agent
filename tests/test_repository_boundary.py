"""Dependency checks must see package initializers and dynamically launched CLIs."""
from pathlib import Path

from scripts.engineering import verify_active_baseline as boundary


def test_import_closure_includes_package_initializer_and_dynamic_script(tmp_path, monkeypatch):
    sources = {
        "apps/start.py": "import sec_agent.feature\nRUNNER = 'scripts/dev/build.py'\n",
        "src/sec_agent/__init__.py": "from sec_agent import shared\n",
        "src/sec_agent/feature.py": "VALUE = 1\n",
        "src/sec_agent/shared.py": "VALUE = 2\n",
        "scripts/dev/build.py": "VALUE = 3\n",
    }
    for ref, text in sources.items():
        path = tmp_path / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(boundary, "ROOT", tmp_path)
    refs, unresolved = boundary.python_closure(["apps/start.py"])
    assert unresolved == []
    assert set(refs) == set(sources)


def test_removed_local_module_is_reported_not_treated_as_external(tmp_path, monkeypatch):
    source = tmp_path / "start.py"
    source.write_text("from scripts.qualification.retired import run\n", encoding="utf-8")
    monkeypatch.setattr(boundary, "ROOT", tmp_path)
    refs, errors = boundary._resolve_python_imports(source, "start", {})
    assert refs == set()
    assert errors == ["start.py:scripts.qualification.retired"]


def test_runtime_does_not_admit_retired_script_families():
    assert boundary._forbidden_refs([
        "scripts/qualification/example.py", "scripts/research/old.py", "archive/old.py"
    ]) == ["archive/old.py", "scripts/qualification/example.py", "scripts/research/old.py"]
