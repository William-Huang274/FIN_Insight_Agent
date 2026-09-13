from __future__ import annotations

import re


def tokenize(text: str) -> list[str]:
    result = []
    for match in re.finditer(r"[a-z0-9][a-z0-9&'/-]*|[\u3400-\u9fff]+", text.lower()):
        part = match.group()
        if '\u3400' <= part[0] <= '\u9fff':
            import jieba
            result.extend(jieba.cut_for_search(part, HMM=False))
        else:
            result.append(part)
    return result


def evidence_search_text(record: dict) -> str:
    metadata = record.get("metadata", {})
    parts = [
        record.get("ticker"),
        str(record.get("fiscal_year") or ""),
        record.get("section"),
        record.get("subsection"),
        record.get("evidence_type"),
        " ".join(record.get("topics") or []),
        metadata.get("category"),
        metadata.get("block_type"),
        record.get("text"),
    ]
    return "\n".join(str(part) for part in parts if part)
