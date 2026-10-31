"""Capture maintained parsers' native results before FIN semantic adaptation.

This is a versioned offline parsing boundary, not a financial quality assertion.
Native graph references are scoped to this artifact, never citation/wire IDs.
Unknown field types fail visibly instead of being silently stringified/dropped.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from importlib.metadata import version
import base64
import json
import math
from pathlib import Path
import sys


class NativeEncoder:
    def __init__(self, node_type=None):
        self.node_type = node_type
        self.nodes = []
        self.identities = {}

    def encode(self, value):
        if isinstance(value, Enum):
            return {"$enum": type(value).__qualname__, "name": value.name,
                    "value": self.encode(value.value)}
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                return {"$float": repr(value)}
            return value
        if isinstance(value, Decimal):
            return {"$decimal": str(value)}
        if isinstance(value, (date, datetime)):
            return {"$date_type": type(value).__name__, "value": value.isoformat()}
        if isinstance(value, bytes):
            return {"$bytes_base64": base64.b64encode(value).decode("ascii")}
        if self.node_type is not None and isinstance(value, self.node_type):
            return self.node(value)
        if isinstance(value, dict):
            if not all(isinstance(k, str) for k in value):
                return {"$mapping": [[self.encode(k), self.encode(v)] for k, v in value.items()]}
            return {k: self.encode(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            items = [self.encode(v) for v in value]
            if isinstance(value, (set, frozenset)):
                items.sort(key=lambda x: json.dumps(x, sort_keys=True))
            return items if isinstance(value, list) else {"$sequence_type": type(value).__name__, "items": items}
        if is_dataclass(value):
            return {"$class": type(value).__qualname__, "fields": {
                f.name: self.encode(getattr(value, f.name)) for f in fields(value)
                if not f.name.startswith("_")}}
        # Web body/comments trees contain attributes, text and tails, not just text().
        from lxml import etree
        if isinstance(value, etree._Element):
            return {"$xml": etree.tostring(value, encoding="unicode", with_tail=True)}
        raise TypeError(f"unsupported_native_field:{type(value).__module__}.{type(value).__qualname__}")

    def node(self, node):
        key = id(node)
        if key in self.identities:
            return {"$node": self.identities[key]}
        ref = f"node:{len(self.nodes)}"
        self.identities[key] = ref
        record = {"ref": ref, "class": type(node).__qualname__}
        self.nodes.append(record)  # Reserve before traversing parent/child cycles.
        public = {f.name for f in fields(node) if not f.name.startswith("_")}
        public.update(k for k in vars(node) if not k.startswith("_"))
        record["fields"] = {k: self.encode(getattr(node, k)) for k in sorted(public)}
        # Table .text() is a display renderer and may truncate cells. Cell.content
        # and its complete nested native graph above are the authoritative surface.
        if node.type.name.lower() in {"heading", "paragraph", "list_item", "text", "link"}:
            record["rendered_text"] = node.text()
        return {"$node": ref}


def _envelope(raw, route, packages, options, native):
    prefixes = {"edgartools": "edgar.documents", "trafilatura": "trafilatura",
                "markdown-it-py": "markdown_it", "mdit-py-plugins": "mdit_py_plugins",
                "datamule": "datamule", "doc2dict": "doc2dict"}
    module_hashes = {}
    for name, module in tuple(sys.modules.items()):
        if not any(name == prefixes.get(p) or name.startswith(prefixes.get(p, "!") + ".") for p in packages):
            continue
        filename = getattr(module, "__file__", None)
        if filename and filename.endswith(".py"):
            module_hashes[name] = sha256(Path(filename).read_bytes()).hexdigest()
    result = {"schema": "fin_native_document_v1", "source_sha256": sha256(raw).hexdigest(),
              "source_bytes": len(raw), "route": route,
              "packages": {p: version(p) for p in packages}, "options": options,
              "native": native, "fin_adaptation_applied": False,
              "loaded_parser_module_sha256": module_hashes,
              "quality_status": "native_output_not_independently_qualified",
              "excluded_capabilities": ["fetching", "model_calls", "search", "embeddings",
                                        "numeric_dataframe_conversion", "financial_inference"]}
    # Enforce the storage contract here, not default=str in a downstream writer.
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    return result


def capture_edgar_document(document, raw, options):
    from edgar.documents.nodes import Node
    encoder = NativeEncoder(Node)
    root = encoder.encode(document.root)
    sections = {}
    for key, section in document.sections.items():
        # Public data fields include node membership, offsets, part/item, method,
        # confidence, validation/warnings and combined-item declarations.
        sections[key] = encoder.encode(section)
        # TOC sections may store their content behind lazy public methods rather
        # than node.children. Materialize both, otherwise a field-only snapshot
        # silently loses the very section capability we are trying to retain.
        sections[key]["native_text"] = section.text()
        sections[key]["native_tables"] = [encoder.encode(t) for t in section.tables()]
    metadata = encoder.encode(document.metadata)
    # Statistics are a public lazy property, not a dataclass field.
    metadata["statistics"] = encoder.encode(document.metadata.statistics)
    native = {"root": root, "nodes": encoder.nodes, "sections": sections,
              "metadata": metadata, "tables": [encoder.encode(t) for t in document.tables],
              "headings": [encoder.encode(h) for h in document.headings],
              "xbrl_facts": encoder.encode(document.xbrl_facts),
              "serialization_policy": "public_node_and_dataclass_fields; private caches/callables excluded; no numeric cell coercion"}
    return _envelope(raw, "edgartools", ["edgartools", "lxml"], options, native)


def datamule_table_compatibility(document):
    """Adapt the known 6-field doc2dict view to Datamule's 4-field consumer.

    The native document is never mutated. Extra role/position fields remain in
    the capture and the provenance below; upstream code still builds tables.
    """
    from datamule import Document
    tuples = document.data_tuples
    if not tuples or not all(isinstance(row, (tuple, list)) and len(row) == 6 for row in tuples):
        raise ValueError("unsupported_datamule_tuple_compatibility")
    class TableView(Document):
        @property
        def data_tuples(self):
            converted = []
            for identity, role, content, level, _, _ in tuples:
                # New doc2dict flattens these descriptions to strings; the
                # existing Table constructor consumes text/textsmall objects.
                if role in {"table_preamble", "table_postamble", "table_footnote"} and isinstance(content, str):
                    content = {"text": content}
                converted.append((identity, role, content, level))
            return converted
    view = TableView(type=document.type, content=document.content, filename=document.filename,
                     accession=document.accession, filing_date=document.filing_date)
    encoder = NativeEncoder()
    return {"adapter": "doc2dict_six_fields_to_datamule_four_fields_v1",
            "tables": [encoder.encode({k: v for k, v in vars(t).items() if not k.startswith("_")})
                       for t in view.tables.tables],
            "tuple_provenance": encoder.encode(tuples),
            "quality_status": "compatibility_only_not_financial_table_validation"}


def capture_native(raw, route, *, title="", form="", web_focus="balanced"):
    if route == "edgartools":
        from edgar.documents import parse_html, ParserConfig
        from probe_document_parsers import resolve_form
        resolution = resolve_form(raw, title, form)
        config = ParserConfig(form=resolution["form"], enable_parallel=False)
        document = parse_html(raw.decode("utf-8-sig"), config=config)
        options = {"form_resolution": resolution, "parser_config": NativeEncoder().encode(config)}
        return capture_edgar_document(document, raw, options)
    if route == "trafilatura":
        import trafilatura
        if web_focus not in {"balanced", "precision", "recall"}:
            raise ValueError("invalid_web_focus")
        options = dict(include_tables=True, include_comments=True, include_formatting=True,
                       include_links=True, include_images=True, with_metadata=True,
                       favor_precision=web_focus == "precision", favor_recall=web_focus == "recall")
        doc = trafilatura.bare_extraction(raw, **options)
        native = {"status": "empty_extraction" if doc is None else "extracted",
                  "document": None if doc is None else NativeEncoder().encode(doc.as_dict())}
        return _envelope(raw, route, ["trafilatura", "lxml"], options, native)
    if route == "datamule":
        from datamule import Document
        from probe_document_parsers import resolve_form
        resolution = resolve_form(raw, title, form)
        document = Document(type=resolution["form"], content=raw.decode("utf-8-sig"),
                            filename="local-original.htm", accession=None, filing_date=None)
        encoder = NativeEncoder()
        # Keep each public parsing view. Tables.__iter__ yields rows, so using
        # list(document.tables) would silently discard table/footnote identity.
        native = {name: encoder.encode(getattr(document, name)) for name in
                  ("data", "data_tuples", "data_tuples_columnar", "text", "markdown")}
        try:
            native_tables = document.tables.tables
        except Exception as exc:
            # Preserve the other native views, but never call a failed public
            # capability an empty table list or a complete capture.
            native["tables"] = None
            native["capability_errors"] = [{"capability": "tables", "error": type(exc).__name__,
                                            "detail": str(exc)}]
        else:
            native["tables"] = [encoder.encode({k: v for k, v in vars(table).items()
                                               if not k.startswith("_")}) for table in native_tables]
        native["document_fields"] = encoder.encode({k: v for k, v in vars(document).items()
                                                    if not k.startswith("_")})
        result = _envelope(raw, route, ["datamule", "doc2dict"],
                           {"form_resolution": resolution, "source_preprocessing": "none"}, native)
        if native.get("capability_errors") and all(len(row) == 6 for row in document.data_tuples):
            try:
                result["compatibility_adaptations"] = {"tables": datamule_table_compatibility(document)}
            except Exception as exc:
                result["compatibility_adaptation_errors"] = [{"capability": "tables",
                    "error": type(exc).__name__, "detail": str(exc)}]
        return result
    if route == "markdown":
        from markdown_it import MarkdownIt
        from mdit_py_plugins.front_matter import front_matter_plugin
        text = raw.decode("utf-8-sig")
        parser = MarkdownIt("commonmark").enable("table").use(front_matter_plugin)
        environment = {}
        tokens = parser.parse(text, environment)
        native = {"tokens": [t.as_dict() for t in tokens], "environment": environment,
                  "source_text": text, "utf8_bom_present": raw.startswith(b'\xef\xbb\xbf'),
                  "position_contract": "token.map: zero-based half-open source lines; not cell byte offsets"}
        return _envelope(raw, route, ["markdown-it-py", "mdit-py-plugins"],
                         {"preset": "commonmark", "enabled": ["table", "front_matter"],
                          "html_rendering_performed": False}, native)
    raise ValueError(f"unsupported_native_route:{route}")


def validate_capture(result):
    """Validate references and source ranges without asserting semantic accuracy."""
    if result["schema"] != "fin_native_document_v1":
        raise ValueError("unsupported_native_schema")
    native = result["native"]
    if result["route"] == "edgartools":
        nodes = native["nodes"]; ids = {n["ref"] for n in nodes}
        if len(ids) != len(nodes):
            raise ValueError("duplicate_native_node")
        def visit(value):
            if isinstance(value, dict):
                if "$node" in value and value["$node"] not in ids:
                    raise ValueError("dangling_native_node")
                for v in value.values(): visit(v)
            elif isinstance(value, list):
                for v in value: visit(v)
        visit(native)
    elif result["route"] == "markdown":
        line_count = len(native["source_text"].splitlines())
        def visit(tokens):
            for token in tokens:
                span = token.get("map")
                if span is not None and not (0 <= span[0] <= span[1] <= line_count):
                    raise ValueError("invalid_native_line_range")
                visit(token.get("children") or [])
        visit(native["tokens"])
    elif result["route"] == "trafilatura":
        if native["status"] == "empty_extraction" and native["document"] is not None:
            raise ValueError("inconsistent_empty_extraction")
    json.dumps(result, allow_nan=False)
    return True


def read_capture(path, *, expected_sha256, expected_source_sha256):
    """Downstream adapters consume the frozen output, without rerunning a parser."""
    import gzip
    packed = Path(path).read_bytes()
    if sha256(packed).hexdigest() != expected_sha256:
        raise ValueError("native_artifact_digest_mismatch")
    result = json.loads(gzip.decompress(packed))
    if result["source_sha256"] != expected_source_sha256:
        raise ValueError("native_source_identity_mismatch")
    validate_capture(result)
    return result


def main():
    """Read one frozen original; capture first, optionally compare old FIN output."""
    import argparse
    import gzip
    from pathlib import Path
    import socket
    import sqlite3
    import time
    import zlib
    from probe_document_parsers import deny_network, local_socket_only

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--id", required=True, help="Exact original SHA256 in manifest.jobs")
    parser.add_argument("--route", choices=["edgartools", "datamule", "trafilatura", "markdown"], required=True)
    parser.add_argument("--web-focus", choices=["balanced", "precision", "recall"], default="balanced")
    parser.add_argument("--compare-fin", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    job = next(j for j in manifest["jobs"] if j["id"] == args.id)
    socket.socket.connect = local_socket_only(socket.socket.connect)
    socket.socket.connect_ex = local_socket_only(socket.socket.connect_ex)
    socket.create_connection = deny_network
    receipt = {"source_sha256": args.id, "manifest_sha256": sha256(manifest_bytes).hexdigest(),
               "implementation_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
               "provider_calls": 0, "published": False, "native_is_fin_quality_pass": False}
    started = time.perf_counter()
    status = 1
    try:
        with sqlite3.connect(Path(manifest["database"]).as_uri() + "?mode=ro", uri=True) as db:
            capture = db.execute("SELECT body_zlib FROM raw_captures WHERE digest=? AND status=200 LIMIT 1", (args.id,)).fetchone()
        if capture is None:
            raise ValueError("original_missing")
        raw = zlib.decompress(capture[0])
        if sha256(raw).hexdigest() != args.id:
            raise ValueError("original_digest_mismatch")
        native = capture_native(raw, args.route, title=job["title"], form=job.get("form") or "",
                                web_focus=args.web_focus)
        validate_capture(native)
        packed = gzip.compress(json.dumps(native, ensure_ascii=False, allow_nan=False).encode("utf-8"), mtime=0)
        (args.output / "native.json.gz").write_bytes(packed)
        receipt.update(native_sha256=sha256(packed).hexdigest(), native_bytes=len(packed),
                       native_completed_seconds=time.perf_counter() - started)
        if args.compare_fin:
            from document_structure_audit import inspect
            from refine_document_chapters import refine
            from validate_source_structure_audit import validate
            # A distinct comparison branch. No claim that the old projection is
            # already consuming the complete native graph/token contract.
            legacy = refine(inspect(raw, job))
            problems = validate(legacy)
            if problems:
                raise ValueError(f"legacy_comparison_invalid:{problems}")
            packed_legacy = gzip.compress(json.dumps(legacy, ensure_ascii=False).encode("utf-8"), mtime=0)
            (args.output / "fin-comparison.json.gz").write_bytes(packed_legacy)
            receipt.update(fin_comparison_sha256=sha256(packed_legacy).hexdigest(),
                           fin_projection_status="existing_separate_branch_not_native_adaptation")
        errors = native["native"].get("capability_errors", [])
        receipt["status"] = "partial_capture" if errors else "captured"
        receipt["capability_errors"] = errors
        status = 2 if errors else 0
    except Exception as exc:
        receipt.update(status="failed", error=type(exc).__name__, detail=str(exc))
    receipt["elapsed_seconds"] = time.perf_counter() - started
    try:
        import psutil
        memory = psutil.Process().memory_info()
        receipt["peak_working_set_bytes"] = getattr(memory, "peak_wset", memory.rss)
    except ImportError:
        pass
    (args.output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
