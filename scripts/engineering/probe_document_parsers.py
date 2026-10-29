"""Offline, one-document parser comparison; outputs are qualification artifacts.

Run in an isolated optional-dependency environment, not the product environment.
No fetching, embedding, financial inference or index publication is performed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import ipaddress
from pathlib import Path
import socket
import sys
import time
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def deny_network(*args, **kwargs):
    raise RuntimeError("offline_parser_network_attempt")


def local_socket_only(original):
    def connect(sock, address):
        # Windows asyncio creates a loopback socketpair for its own event loop.
        try:
            if ipaddress.ip_address(address[0]).is_loopback:
                return original(sock, address)
        except (ValueError, TypeError, IndexError):
            pass
        return deny_network()
    return connect


def parse(raw: bytes, title: str, parser: str, form: str = "") -> dict:
    if parser == "edgartools":
        from edgar.documents import parse_html
        document = parse_html(raw.decode("utf-8-sig"))
        blocks = []

        def visit(node):
            kind = node.type.name.lower()
            if kind == "table":
                def cells(row):
                    return [{"text": c.text(), "rowspan": c.rowspan,
                             "colspan": c.colspan, "is_header": c.is_header} for c in row]
                headers = [cells(row) for row in node.headers]
                rows = [cells(row.cells) for row in node.rows]
                footer = [cells(row.cells) for row in node.footer]
                blocks.append({"kind": kind, "rows": rows, "headers": headers,
                               "footer": footer, "caption": node.caption,
                               "table_type": node.table_type.name,
                               "text": "\n".join([node.caption or ""] + [" | ".join(c["text"] for c in row) for row in headers + rows + footer]),
                               "parser_path": str(node.path),
                               "metadata": node.metadata})
            elif node.children:
                for child in node.children:
                    visit(child)
            else:
                text = node.text()
                if text:
                    blocks.append({"kind": kind, "text": text,
                                   "parser_path": str(node.path), "metadata": node.metadata})

        visit(document.root)
        return {"blocks": blocks, "text": "\n\n".join(b["text"] for b in blocks),
                "display_text": document.text(),
                "xbrl_facts": [f.to_dict() for f in document.xbrl_facts],
                "sections": {k: {"title": s.title, "start": s.start_offset,
                                  "end": s.end_offset} for k, s in document.sections.items()}}
    if parser == "doc2dict":
        from doc2dict import html2dict, flatten_dict
        native = html2dict(raw.decode("utf-8-sig"))
        return {"native": native, "text": flatten_dict(native, format="text")}
    if parser in {"datamule", "datamule_clean"}:
        from datamule import Document
        content = raw.decode("utf-8-sig")
        removed_tags = 0
        if parser == "datamule_clean":
            from lxml import html
            tree = html.fromstring(raw)
            for node in tree.xpath('//script|//style'):
                node.drop_tree()
                removed_tags += 1
            content = html.tostring(tree, encoding="unicode")
        document = Document(type=form, content=content,
                            filename="local-original.htm", accession=None, filing_date=None)
        return {"native": dict(document.data), "text": str(document.text),
                "tuples": list(document.data_tuples), "form_hint": form,
                "removed_non_display_tags": removed_tags}
    if parser == "fin_trafilatura":
        from ingestion.structured_document_adapter import _generic_sections_from_html
        sections = _generic_sections_from_html(raw, title)
        blocks = [{"kind": b.kind, "text": b.content, "section": s.path}
                  for s in sections for b in s.blocks]
        return {"sections": [asdict(s) for s in sections], "blocks": blocks,
                "text": "\n\n".join(b["text"] for b in blocks)}
    if parser.startswith("trafilatura"):
        import trafilatura
        xml = trafilatura.extract(raw, output_format="xml", include_tables=True,
                                  include_comments=False, include_formatting=True,
                                  include_links=False, favor_recall=True)
        if not xml:
            raise ValueError("empty_extraction")
        root = ET.fromstring(xml)
        blocks = []

        def visit(el):
            if el.tag in {"p", "head", "item", "table", "quote", "code"}:
                blocks.append({"kind": el.tag, "text": " ".join(el.itertext()),
                               "xml": ET.tostring(el, encoding="unicode")})
            else:
                for child in el:
                    visit(child)

        visit(root)
        return {"xml": xml, "blocks": blocks,
                "text": "\n\n".join(b["text"] for b in blocks)}
    raise ValueError(f"unsupported_parser: {parser}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--parser", choices=["edgartools", "doc2dict", "datamule", "datamule_clean", "trafilatura_xml", "fin_trafilatura"], required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_bytes = args.manifest.read_bytes()
    sample = next(s for s in json.loads(manifest_bytes)["samples"] if s["id"] == args.id)
    raw = Path(sample["path"]).read_bytes()
    if sha256(raw).hexdigest() != sample["raw_sha256"]:
        raise ValueError("original_digest_mismatch")
    # Cover ordinary socket-based HTTP clients; no source-fetching API is used.
    socket.socket.connect = local_socket_only(socket.socket.connect)
    socket.socket.connect_ex = local_socket_only(socket.socket.connect_ex)
    socket.create_connection = deny_network
    started = time.perf_counter()
    result = {"id": args.id, "parser": args.parser, "raw_sha256": sample["raw_sha256"],
              "manifest_sha256": sha256(manifest_bytes).hexdigest(),
              "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "provider_calls": 0, "scope": "parser_probe_not_retrieval_or_financial_quality_pass"}
    try:
        result["output"] = parse(raw, sample["title"], args.parser, sample.get("form", ""))
        result["status"] = "parsed"
    except Exception as exc:
        result.update(status="failed", error=type(exc).__name__, detail=str(exc))
    result["elapsed_seconds"] = time.perf_counter() - started
    result["versions"] = {}
    for package in ["edgartools", "doc2dict", "datamule", "trafilatura", "lxml"]:
        try:
            result["versions"][package] = version(package)
        except PackageNotFoundError:
            pass
    try:
        import psutil
        mem = psutil.Process().memory_info()
        result["peak_working_set_bytes"] = getattr(mem, "peak_wset", None)
        result["rss_bytes_at_end"] = mem.rss
    except ImportError:
        pass
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "output"}, ensure_ascii=False))
    return 0 if result["status"] == "parsed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
