from __future__ import annotations

import argparse
from collections import Counter
from contextlib import AbstractContextManager
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from retrieval.cross_encoder import (  # noqa: E402
    cross_encoder_model_identity,
    load_local_qwen3_reranker,
    score_qwen3_reranker_pairs,
)
from retrieval.embedding_runtime import (  # noqa: E402
    load_qwen_embedding_runtime,
    local_model_identity,
)
from retrieval.quantized_shadow import (  # noqa: E402
    build_qwen3_reranker_prompt,
    compile_controlled_ranking_metrics,
    compile_quantized_shadow_decision,
    llama_cpp_tool_identity,
    parse_llama_yes_no_margin,
    quantized_gguf_identity,
    sha256_file,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_quantized_4b_controlled_shadow_program_v1_0.json"
)
OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_quantized_4b_controlled_shadow_result_v1_0.json"
)
ATTEMPT_ID = "controlled-shadow-r1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered 0.6B versus Q4_K_M 4B controlled-pool "
            "embedding and reranker shadow without runtime authority."
        )
    )
    parser.add_argument("--program", default=PROGRAM)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--attempt-id", default=ATTEMPT_ID)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"quantized_shadow_json_object_required:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    os.replace(temporary, path)


def _repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("quantized_shadow_repo_path_escape")
    return path


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _clean_git_receipt() -> dict[str, Any]:
    status = _run_git("status", "--porcelain", "--untracked-files=all")
    head = _run_git("rev-parse", "HEAD")
    upstream = _run_git("rev-parse", "@{upstream}")
    if status or head != upstream:
        raise ValueError("quantized_shadow_clean_synced_commit_required")
    return {
        "head": head,
        "upstream": upstream,
        "clean": True,
        "upstream_equal": True,
        "status_porcelain": status,
    }


def _verify_program(program_path: Path, program: Mapping[str, Any]) -> None:
    unsigned = {key: value for key, value in program.items() if key != "result_digest"}
    if not (
        program_path == _repo_path(PROGRAM)
        and program.get("schema_version")
        == "fin_ia_s1_quantized_4b_controlled_shadow_program_v1_0"
        and program.get("status")
        == "preregistered_controlled_shadow_ready_after_clean_commit"
        and program.get("attempt_id") == ATTEMPT_ID
        and program.get("result_digest") == canonical_digest(unsigned)
    ):
        raise ValueError("quantized_shadow_program_invalid")
    for section in ("bound_inputs", "implementation_bindings"):
        rows = program.get(section)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"quantized_shadow_{section}_invalid")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError(f"quantized_shadow_{section}_invalid")
            path = _repo_path(str(row.get("path") or ""))
            if not path.is_file() or _sha256(path) != row.get("sha256"):
                raise ValueError(
                    f"quantized_shadow_binding_drift:{section}:{row.get('path')}"
                )


def _hardware_receipt() -> dict[str, Any]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free,memory.used,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rows = [row.strip() for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise ValueError("quantized_shadow_single_gpu_required")
    values = [value.strip() for value in rows[0].split(",")]
    if len(values) != 6:
        raise ValueError("quantized_shadow_gpu_receipt_invalid")
    return {
        "device_name": values[0],
        "total_vram_mib": int(values[1]),
        "free_vram_mib": int(values[2]),
        "used_vram_mib": int(values[3]),
        "driver_version": values[4],
        "compute_capability": values[5],
    }


class GpuMonitor:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.samples: list[dict[str, int]] = []

    def __enter__(self) -> "GpuMonitor":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                receipt = _hardware_receipt()
                self.samples.append(
                    {
                        "used_vram_mib": receipt["used_vram_mib"],
                        "free_vram_mib": receipt["free_vram_mib"],
                    }
                )
            except Exception:
                pass
            self._stop.wait(0.5)

    def receipt(self) -> dict[str, Any]:
        if not self.samples:
            raise ValueError("quantized_shadow_gpu_monitor_empty")
        return {
            "sample_count": len(self.samples),
            "maximum_used_vram_mib": max(row["used_vram_mib"] for row in self.samples),
            "minimum_free_vram_mib": min(row["free_vram_mib"] for row in self.samples),
        }


def _release_cuda() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _load_eval(path: Path, expected_digest: str) -> list[dict[str, Any]]:
    payload = _read_json(path)
    unsigned = {key: value for key, value in payload.items() if key != "result_digest"}
    if not (
        payload.get("schema_version")
        == "fin_ia_s1_large_model_dev_only_role_eval_v1_0"
        and payload.get("status") == "development_only_projection_ready"
        and payload.get("result_digest") == canonical_digest(unsigned)
        and payload.get("result_digest") == expected_digest
        and payload.get("query_count") == 18
    ):
        raise ValueError("quantized_shadow_eval_binding_invalid")
    rows: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    occurrence_count = 0
    label_inventory: Counter[str] = Counter()
    eligible_comparison_cases: set[str] = set()
    for raw in payload.get("queries") or []:
        query_id = str(raw.get("query_id") or "")
        case_key = str(raw.get("case_key") or "")
        query_text = str(raw.get("query_text") or "")
        if (
            not query_id
            or query_id in seen_queries
            or case_key not in {"DELL", "MU", "NVDA"}
            or not query_text
            or query_text != query_text.strip()
        ):
            raise ValueError("quantized_shadow_eval_query_invalid")
        seen_queries.add(query_id)
        candidates: list[dict[str, Any]] = []
        seen_candidates: set[str] = set()
        for source_key, label in (
            ("positives", "positive"),
            ("hard_negatives", "hard_negative"),
        ):
            for candidate in raw.get(source_key) or []:
                candidate_id = str(candidate.get("document_id") or "")
                document_text = str(candidate.get("document_text") or "")
                if (
                    not candidate_id
                    or candidate_id in seen_candidates
                    or not document_text
                    or document_text != document_text.strip()
                ):
                    raise ValueError("quantized_shadow_eval_candidate_invalid")
                seen_candidates.add(candidate_id)
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "label": label,
                        "document_text": document_text,
                        "document_digest": hashlib.sha256(
                            document_text.encode("utf-8")
                        ).hexdigest(),
                    }
                )
                occurrence_count += 1
                label_inventory[label] += 1
        if not candidates:
            raise ValueError("quantized_shadow_eval_candidate_inventory_empty")
        if any(row["label"] == "positive" for row in candidates) and any(
            row["label"] == "hard_negative" for row in candidates
        ):
            eligible_comparison_cases.add(case_key)
        rows.append(
            {
                "query_id": query_id,
                "case_key": case_key,
                "query_text": query_text,
                "candidates": candidates,
            }
        )
    if not (
        len(rows) == 18
        and occurrence_count == 86
        and label_inventory == {"positive": 21, "hard_negative": 65}
        and eligible_comparison_cases == {"DELL", "MU", "NVDA"}
    ):
        raise ValueError("quantized_shadow_eval_scale_invalid")
    return rows


def _unique_documents(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    documents: dict[str, str] = {}
    for row in rows:
        for candidate in row["candidates"]:
            key = str(candidate["document_digest"])
            text = str(candidate["document_text"])
            if key in documents and documents[key] != text:
                raise ValueError("quantized_shadow_document_digest_collision")
            documents[key] = text
    return documents


def _embedding_metric_rows(
    rows: Sequence[Mapping[str, Any]],
    query_vectors: Mapping[str, np.ndarray],
    document_vectors: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        query = query_vectors[str(row["query_id"])]
        candidates = []
        for candidate in row["candidates"]:
            document = document_vectors[str(candidate["document_digest"])]
            score = float(np.dot(query, document))
            if not math.isfinite(score):
                raise ValueError("quantized_shadow_embedding_score_not_finite")
            candidates.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "label": candidate["label"],
                    "score": score,
                }
            )
        output.append(
            {
                "query_id": row["query_id"],
                "case_key": row["case_key"],
                "candidates": candidates,
            }
        )
    return output


def _reranker_metric_rows(
    rows: Sequence[Mapping[str, Any]], scores: Sequence[float]
) -> list[dict[str, Any]]:
    expected = sum(len(row["candidates"]) for row in rows)
    if len(scores) != expected:
        raise ValueError("quantized_shadow_reranker_score_count_invalid")
    output: list[dict[str, Any]] = []
    offset = 0
    for row in rows:
        candidates = []
        for candidate in row["candidates"]:
            score = float(scores[offset])
            offset += 1
            if not math.isfinite(score):
                raise ValueError("quantized_shadow_reranker_score_not_finite")
            candidates.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "label": candidate["label"],
                    "score": score,
                }
            )
        output.append(
            {
                "query_id": row["query_id"],
                "case_key": row["case_key"],
                "candidates": candidates,
            }
        )
    return output


def _token_lengths(tokenizer: Any, texts: Sequence[str]) -> list[int]:
    encoded = tokenizer(
        list(texts),
        add_special_tokens=True,
        padding=False,
        truncation=False,
        return_attention_mask=False,
    )
    return [len(row) for row in encoded["input_ids"]]


def _run_baseline_embedding(
    rows: Sequence[Mapping[str, Any]],
    *,
    model_dir: Path,
    instruction: str,
    maximum_tokens: int,
    call_counts: Counter[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], Any]:
    import torch

    documents = _unique_documents(rows)
    queries = {
        str(row["query_id"]): f"Instruct: {instruction}\nQuery:{row['query_text']}"
        for row in rows
    }
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with GpuMonitor() as monitor:
        runtime = load_qwen_embedding_runtime(model_dir)
        runtime.max_seq_length = maximum_tokens
        query_lengths = _token_lengths(runtime.tokenizer, list(queries.values()))
        document_lengths = _token_lengths(
            runtime.tokenizer, list(documents.values())
        )
        if max(query_lengths + document_lengths) > maximum_tokens:
            raise ValueError("quantized_shadow_embedding_token_budget_exceeded")
        query_array = runtime.encode(
            list(queries.values()),
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
        document_array = runtime.encode(
            list(documents.values()),
            batch_size=1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)
        query_vectors = {
            key: query_array[index] for index, key in enumerate(queries)
        }
        document_vectors = {
            key: document_array[index] for index, key in enumerate(documents)
        }
        metric_rows = _embedding_metric_rows(rows, query_vectors, document_vectors)
        call_counts["baseline_embedding_scored_inputs"] += len(queries) + len(
            documents
        )
        receipt = {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "query_count": len(queries),
            "unique_document_count": len(documents),
            "candidate_occurrence_count": sum(
                len(row["candidates"]) for row in rows
            ),
            "maximum_query_tokens": max(query_lengths),
            "maximum_document_tokens": max(document_lengths),
            "maximum_tokens": maximum_tokens,
            "embedding_dimensions": int(query_array.shape[1]),
            "torch_peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "torch_peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
        }
        tokenizer = runtime.tokenizer
        del runtime, query_array, document_array, query_vectors, document_vectors
    receipt["gpu_monitor"] = monitor.receipt()
    _release_cuda()
    return receipt, metric_rows, tokenizer


def _http_json(
    method: str,
    url: str,
    *,
    payload: Mapping[str, Any] | None,
    call_counts: Counter[str],
    timeout: int = 300,
) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    endpoint = urllib.parse.urlparse(url).path
    call_counts[f"localhost_http:{endpoint}"] += 1
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(
            f"quantized_shadow_local_http_error:{endpoint}:{exc.code}:{detail}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError(f"quantized_shadow_local_http_object_required:{endpoint}")
    return value


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class LocalLlamaServer(AbstractContextManager["LocalLlamaServer"]):
    def __init__(
        self,
        *,
        server_path: Path,
        model_path: Path,
        tool_dir: Path,
        log_path: Path,
        mode: str,
        context_size: int,
        call_counts: Counter[str],
    ) -> None:
        self.server_path = server_path
        self.model_path = model_path
        self.tool_dir = tool_dir
        self.log_path = log_path
        self.mode = mode
        self.context_size = context_size
        self.call_counts = call_counts
        self.port = _free_local_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[str] | None = None
        self.monitor: GpuMonitor | None = None
        self.log_handle: Any = None
        self.receipt: dict[str, Any] = {}
        self.started = 0.0

    def __enter__(self) -> "LocalLlamaServer":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open(
            "w", encoding="utf-8", errors="replace", newline="\n"
        )
        command = [
            str(self.server_path),
            "--model",
            str(self.model_path),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--offline",
            "--no-webui",
            "--fit",
            "off",
            "--n-gpu-layers",
            "99",
            "--split-mode",
            "none",
            "--main-gpu",
            "0",
            "--ctx-size",
            str(self.context_size),
            "--batch-size",
            str(self.context_size),
            "--ubatch-size",
            "512",
            "--parallel",
            "1",
            "--no-cont-batching",
            "--threads",
            "8",
            "--threads-batch",
            "8",
        ]
        if self.mode == "embedding":
            command.extend(
                ["--embedding", "--pooling", "last", "--embd-normalize", "2"]
            )
        elif self.mode != "completion":
            raise ValueError("quantized_shadow_llama_mode_invalid")
        environment = dict(os.environ)
        environment.update(
            {
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "CUDA_VISIBLE_DEVICES": "0",
            }
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.monitor = GpuMonitor()
        self.monitor.__enter__()
        self.started = time.perf_counter()
        self.process = subprocess.Popen(
            command,
            cwd=self.tool_dir,
            env=environment,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        try:
            deadline = time.monotonic() + 240
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        "quantized_shadow_llama_server_exited:"
                        f"{self.process.returncode}:{self._log_tail()}"
                    )
                try:
                    health = _http_json(
                        "GET",
                        self.base_url + "/health",
                        payload=None,
                        call_counts=self.call_counts,
                        timeout=5,
                    )
                    if health.get("status") == "ok":
                        self.receipt["health"] = health
                        self.receipt["ready_seconds"] = round(
                            time.perf_counter() - self.started, 3
                        )
                        return self
                except Exception:
                    pass
                time.sleep(0.5)
            raise TimeoutError("quantized_shadow_llama_server_ready_timeout")
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.log_handle is not None:
            self.log_handle.flush()
            self.log_handle.close()
        if self.monitor is not None:
            self.monitor.__exit__(exc_type, exc, traceback)
            self.receipt["gpu_monitor"] = self.monitor.receipt()
        self.receipt["elapsed_seconds"] = round(
            time.perf_counter() - self.started, 3
        )
        if self.log_path.is_file():
            log_text = self.log_path.read_text(encoding="utf-8", errors="replace")
            matches = re.findall(
                r"offloaded\s+(\d+)/(\d+)\s+layers\s+to\s+GPU", log_text
            )
            full_offload = any(int(left) == int(right) for left, right in matches)
            self.receipt["full_gpu_offload_proved"] = full_offload
            self.receipt["offload_log_matches"] = [
                {"offloaded": int(left), "total": int(right)}
                for left, right in matches
            ]
            self.receipt["log_ref"] = self.log_path.relative_to(ROOT).as_posix()
            self.receipt["log_bytes"] = self.log_path.stat().st_size
            self.receipt["log_sha256"] = _sha256(self.log_path)
            if exc_type is None and not full_offload:
                raise ValueError("quantized_shadow_full_gpu_offload_not_proved")

    def _log_tail(self) -> str:
        if self.log_handle is not None:
            self.log_handle.flush()
        if not self.log_path.is_file():
            return ""
        return self.log_path.read_text(encoding="utf-8", errors="replace")[-4000:]

    def post(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return _http_json(
            "POST",
            self.base_url + endpoint,
            payload=payload,
            call_counts=self.call_counts,
        )


def _server_token_ids(server: LocalLlamaServer, text: str) -> list[int]:
    response = server.post(
        "/tokenize",
        {"content": text, "add_special": False, "parse_special": True},
    )
    tokens = response.get("tokens")
    if not isinstance(tokens, list) or any(
        isinstance(value, bool) or not isinstance(value, int) for value in tokens
    ):
        raise ValueError("quantized_shadow_server_tokenization_invalid")
    return tokens


def _extract_embedding(response: Mapping[str, Any]) -> np.ndarray:
    data = response.get("data")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], Mapping):
        raise ValueError("quantized_shadow_embedding_response_invalid")
    values = data[0].get("embedding")
    if not isinstance(values, list) or not values:
        raise ValueError("quantized_shadow_embedding_vector_invalid")
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise ValueError("quantized_shadow_embedding_vector_invalid")
    norm = float(np.linalg.norm(array))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("quantized_shadow_embedding_norm_invalid")
    return array / norm


def _run_challenger_embedding(
    rows: Sequence[Mapping[str, Any]],
    *,
    baseline_tokenizer: Any,
    model_path: Path,
    server_path: Path,
    tool_dir: Path,
    log_path: Path,
    instruction: str,
    maximum_tokens: int,
    context_size: int,
    expected_dimensions: int,
    call_counts: Counter[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    documents = _unique_documents(rows)
    queries = {
        str(row["query_id"]): f"Instruct: {instruction}\nQuery:{row['query_text']}"
        for row in rows
    }
    query_vectors: dict[str, np.ndarray] = {}
    document_vectors: dict[str, np.ndarray] = {}
    token_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    server = LocalLlamaServer(
        server_path=server_path,
        model_path=model_path,
        tool_dir=tool_dir,
        log_path=log_path,
        mode="embedding",
        context_size=context_size,
        call_counts=call_counts,
    )
    with server:
        for kind, values, output in (
            ("query", queries, query_vectors),
            ("document", documents, document_vectors),
        ):
            for key, text in values.items():
                baseline_ids = baseline_tokenizer.encode(
                    text, add_special_tokens=False
                )
                server_ids = _server_token_ids(server, text)
                if baseline_ids != server_ids or len(server_ids) > maximum_tokens:
                    raise ValueError(
                        f"quantized_shadow_embedding_tokenizer_drift:{kind}:{key}"
                    )
                response = server.post(
                    "/v1/embeddings", {"model": "local", "input": text}
                )
                vector = _extract_embedding(response)
                if vector.shape[0] != expected_dimensions:
                    raise ValueError("quantized_shadow_embedding_dimension_drift")
                output[str(key)] = vector
                call_counts["challenger_embedding_scored_inputs"] += 1
                token_rows.append(
                    {
                        "kind": kind,
                        "input_key": str(key),
                        "token_count": len(server_ids),
                        "token_digest": canonical_digest(server_ids),
                    }
                )
        metric_rows = _embedding_metric_rows(rows, query_vectors, document_vectors)
    receipt = {
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "query_count": len(queries),
        "unique_document_count": len(documents),
        "candidate_occurrence_count": sum(len(row["candidates"]) for row in rows),
        "maximum_query_tokens": max(
            row["token_count"] for row in token_rows if row["kind"] == "query"
        ),
        "maximum_document_tokens": max(
            row["token_count"] for row in token_rows if row["kind"] == "document"
        ),
        "maximum_tokens": maximum_tokens,
        "embedding_dimensions": expected_dimensions,
        "tokenizer_exact_match_vs_0_6b": True,
        "tokenization_digest": canonical_digest(token_rows),
        "server": server.receipt,
    }
    return receipt, metric_rows


def _flatten_pairs(
    rows: Sequence[Mapping[str, Any]]
) -> list[tuple[str, str]]:
    return [
        (str(row["query_text"]), str(candidate["document_text"]))
        for row in rows
        for candidate in row["candidates"]
    ]


def _run_baseline_reranker(
    rows: Sequence[Mapping[str, Any]],
    *,
    model_dir: Path,
    instruction: str,
    maximum_tokens: int,
    call_counts: Counter[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], Any, list[list[int]], int, int]:
    import torch

    pairs = _flatten_pairs(rows)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with GpuMonitor() as monitor:
        runtime = load_local_qwen3_reranker(
            model_dir,
            maximum_sequence_length=maximum_tokens,
            instruction=instruction,
        )
        tokenizer = runtime[0]
        yes_token_id = int(runtime[6])
        no_token_id = int(runtime[5])
        prompts = [
            build_qwen3_reranker_prompt(
                instruction=instruction, query=query, document=document
            )
            for query, document in pairs
        ]
        prompt_ids = [
            tokenizer.encode(prompt, add_special_tokens=False) for prompt in prompts
        ]
        lengths = [len(row) for row in prompt_ids]
        if max(lengths) > maximum_tokens:
            raise ValueError("quantized_shadow_reranker_token_budget_exceeded")
        scores = score_qwen3_reranker_pairs(runtime, pairs, batch_size=1)
        call_counts["baseline_reranker_scored_pairs"] += len(pairs)
        metric_rows = _reranker_metric_rows(rows, scores)
        receipt = {
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "pair_count": len(pairs),
            "maximum_prompt_tokens": max(lengths),
            "p95_prompt_tokens": sorted(lengths)[int(len(lengths) * 0.95) - 1],
            "maximum_tokens": maximum_tokens,
            "yes_token_id": yes_token_id,
            "no_token_id": no_token_id,
            "prompt_token_digest": canonical_digest(prompt_ids),
            "torch_peak_allocated_bytes": int(torch.cuda.max_memory_allocated()),
            "torch_peak_reserved_bytes": int(torch.cuda.max_memory_reserved()),
        }
        del runtime, scores
    receipt["gpu_monitor"] = monitor.receipt()
    _release_cuda()
    return (
        receipt,
        metric_rows,
        tokenizer,
        prompt_ids,
        yes_token_id,
        no_token_id,
    )


def _run_challenger_reranker(
    rows: Sequence[Mapping[str, Any]],
    *,
    baseline_tokenizer: Any,
    baseline_prompt_ids: Sequence[Sequence[int]],
    yes_token_id: int,
    no_token_id: int,
    instruction: str,
    model_path: Path,
    server_path: Path,
    tool_dir: Path,
    log_path: Path,
    maximum_tokens: int,
    context_size: int,
    n_probs: int,
    call_counts: Counter[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pairs = _flatten_pairs(rows)
    prompts = [
        build_qwen3_reranker_prompt(
            instruction=instruction, query=query, document=document
        )
        for query, document in pairs
    ]
    if len(prompts) != len(baseline_prompt_ids):
        raise ValueError("quantized_shadow_prompt_inventory_drift")
    server = LocalLlamaServer(
        server_path=server_path,
        model_path=model_path,
        tool_dir=tool_dir,
        log_path=log_path,
        mode="completion",
        context_size=context_size,
        call_counts=call_counts,
    )
    parsed_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    started = time.perf_counter()
    with server:
        for token_text, expected in (("yes", yes_token_id), ("no", no_token_id)):
            baseline_ids = baseline_tokenizer.encode(
                token_text, add_special_tokens=False
            )
            server_ids = _server_token_ids(server, token_text)
            if baseline_ids != [expected] or server_ids != [expected]:
                raise ValueError(
                    f"quantized_shadow_yes_no_tokenizer_drift:{token_text}"
                )
        for index, (prompt, expected_ids) in enumerate(
            zip(prompts, baseline_prompt_ids)
        ):
            server_ids = _server_token_ids(server, prompt)
            if (
                server_ids != list(expected_ids)
                or len(server_ids) > maximum_tokens
            ):
                raise ValueError(
                    f"quantized_shadow_reranker_tokenizer_drift:{index}"
                )
            response = server.post(
                "/completion",
                {
                    "prompt": server_ids,
                    "n_predict": 1,
                    "temperature": -1,
                    "n_probs": n_probs,
                    "min_keep": n_probs,
                    "cache_prompt": False,
                    "return_tokens": True,
                    "timings_per_token": True,
                    "seed": 0,
                    "samplers": ["temperature"],
                },
            )
            parsed = parse_llama_yes_no_margin(
                response,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
            )
            if parsed["tokens_evaluated"] != len(server_ids):
                raise ValueError(
                    f"quantized_shadow_reranker_tokens_evaluated_drift:{index}"
                )
            scores.append(float(parsed["score"]))
            call_counts["challenger_reranker_scored_pairs"] += 1
            parsed_rows.append(
                {
                    "pair_index": index,
                    "prompt_tokens": len(server_ids),
                    **parsed,
                }
            )
        metric_rows = _reranker_metric_rows(rows, scores)
    receipt = {
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "pair_count": len(pairs),
        "maximum_prompt_tokens": max(
            int(row["prompt_tokens"]) for row in parsed_rows
        ),
        "maximum_tokens": maximum_tokens,
        "n_probs": n_probs,
        "yes_token_id": yes_token_id,
        "no_token_id": no_token_id,
        "tokenizer_exact_match_vs_0_6b": True,
        "raw_score_receipts": parsed_rows,
        "raw_score_receipt_digest": canonical_digest(parsed_rows),
        "server": server.receipt,
        "direct_rerank_endpoint_used": False,
        "completion_logit_margin_surface_used": True,
    }
    return receipt, metric_rows


def _validate_artifacts(
    program: Mapping[str, Any], acquisition: Mapping[str, Any]
) -> dict[str, Any]:
    artifacts = program["artifacts"]
    embedding_dir = Path(artifacts["challenger_embedding_directory"]).resolve()
    reranker_dir = Path(artifacts["challenger_reranker_directory"]).resolve()
    tool_dir = Path(artifacts["llama_cpp_directory"]).resolve()
    embedding_identity = quantized_gguf_identity(
        embedding_dir,
        expected_repo_id="Qwen/Qwen3-Embedding-4B-GGUF",
        expected_revision="f4602530db1d980e16da9d7d3a70294cf5c190be",
        expected_source_model_id="Qwen/Qwen3-Embedding-4B",
        expected_quantization="Q4_K_M",
    )
    reranker_identity = quantized_gguf_identity(
        reranker_dir,
        expected_repo_id="giladgd/Qwen3-Reranker-4B-GGUF",
        expected_revision="618ca919a196583806708d695f64dc002bd229a3",
        expected_source_model_id="Qwen/Qwen3-Reranker-4B",
        expected_quantization="Q4_K_M",
    )
    tool_identity = llama_cpp_tool_identity(
        tool_dir,
        expected_release_tag="b10516",
        expected_server_relative_path="llama-server.exe",
    )
    identities = {
        "embedding": embedding_identity,
        "reranker": reranker_identity,
        "tool": tool_identity,
    }
    expected = program["expected_identity_digests"]
    if not (
        embedding_identity["model_digest"] == expected["embedding_model_digest"]
        == acquisition["model_identities"]["embedding"]["model_digest"]
        and reranker_identity["model_digest"] == expected["reranker_model_digest"]
        == acquisition["model_identities"]["reranker"]["model_digest"]
        and tool_identity["tool_digest"] == expected["llama_cpp_tool_digest"]
        == acquisition["tool_identity"]["tool_digest"]
    ):
        raise ValueError("quantized_shadow_artifact_identity_drift")
    return identities


def _validate_baselines(program: Mapping[str, Any]) -> dict[str, Any]:
    baseline = program["baseline_models"]
    embedding_dir = Path(baseline["embedding"]["local_directory"]).resolve()
    reranker_dir = Path(baseline["reranker"]["local_directory"]).resolve()
    embedding_identity = local_model_identity(
        embedding_dir, "Qwen/Qwen3-Embedding-0.6B"
    )
    reranker_identity = cross_encoder_model_identity(
        reranker_dir, model_id="Qwen/Qwen3-Reranker-0.6B"
    )
    if not (
        embedding_identity["model_digest"]
        == baseline["embedding"]["model_digest"]
        and reranker_identity["model_digest"]
        == baseline["reranker"]["model_digest"]
    ):
        raise ValueError("quantized_shadow_baseline_model_drift")
    for row in baseline["reranker"]["tokenizer_files"]:
        path = reranker_dir / row["name"]
        if not (
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and _sha256(path) == row["sha256"]
        ):
            raise ValueError("quantized_shadow_baseline_tokenizer_drift")
    return {"embedding": embedding_identity, "reranker": reranker_identity}


def _result_with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    plain = dict(body)
    return {**plain, "result_digest": canonical_digest(plain)}


def main() -> int:
    args = parse_args()
    if args.attempt_id != ATTEMPT_ID:
        raise ValueError("quantized_shadow_attempt_id_not_frozen")
    program_path = _repo_path(args.program)
    output_path = _repo_path(args.output)
    private_dir = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1_quantized_4b_shadow"
        / args.attempt_id
    ).resolve()
    private_path = private_dir / "full_result.json"
    if output_path.exists() or private_path.exists() or private_dir.exists():
        raise ValueError("quantized_shadow_attempt_output_already_exists")
    program = _read_json(program_path)
    _verify_program(program_path, program)
    git_receipt = _clean_git_receipt()
    hardware = _hardware_receipt()
    gate = program["resource_gate"]
    if not (
        gate["required_device_name_contains"] in hardware["device_name"]
        and hardware["total_vram_mib"] >= gate["minimum_total_vram_mib"]
        and hardware["free_vram_mib"] >= gate["minimum_free_vram_mib"]
    ):
        raise ValueError("quantized_shadow_resource_gate_failed")

    acquisition_path = _repo_path(program["acquisition_result_ref"])
    acquisition = _read_json(acquisition_path)
    acquisition_unsigned = {
        key: value for key, value in acquisition.items() if key != "result_digest"
    }
    if not (
        acquisition.get("status")
        == "acquisition_succeeded_development_shadow_only"
        and acquisition.get("result_digest") == canonical_digest(acquisition_unsigned)
        and acquisition.get("result_digest") == program["acquisition_result_digest"]
        and acquisition.get("execution_authorized") is True
    ):
        raise ValueError("quantized_shadow_acquisition_result_invalid")
    identities = _validate_artifacts(program, acquisition)
    baseline_identities = _validate_baselines(program)
    eval_path = _repo_path(program["eval_ref"])
    rows = _load_eval(eval_path, program["eval_result_digest"])

    private_dir.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    call_counts: Counter[str] = Counter()
    stage_receipts: dict[str, Any] = {}
    try:
        settings = program["execution_settings"]
        baseline = program["baseline_models"]
        artifacts = program["artifacts"]
        tool_dir = Path(artifacts["llama_cpp_directory"]).resolve()
        server_path = tool_dir / "llama-server.exe"
        embedding_model_path = (
            Path(artifacts["challenger_embedding_directory"]).resolve()
            / identities["embedding"]["selected_model_file"]["path"]
        )
        reranker_model_path = (
            Path(artifacts["challenger_reranker_directory"]).resolve()
            / identities["reranker"]["selected_model_file"]["path"]
        )

        baseline_embedding_receipt, baseline_embedding_rows, embedding_tokenizer = (
            _run_baseline_embedding(
                rows,
                model_dir=Path(baseline["embedding"]["local_directory"]).resolve(),
                instruction=settings["embedding_instruction"],
                maximum_tokens=settings["maximum_input_tokens"],
                call_counts=call_counts,
            )
        )
        baseline_embedding_metrics = compile_controlled_ranking_metrics(
            baseline_embedding_rows
        )
        stage_receipts["baseline_embedding_0_6b"] = baseline_embedding_receipt

        challenger_embedding_receipt, challenger_embedding_rows = (
            _run_challenger_embedding(
                rows,
                baseline_tokenizer=embedding_tokenizer,
                model_path=embedding_model_path,
                server_path=server_path,
                tool_dir=tool_dir,
                log_path=private_dir / "challenger_embedding_server.log",
                instruction=settings["embedding_instruction"],
                maximum_tokens=settings["maximum_input_tokens"],
                context_size=settings["llama_context_size"],
                expected_dimensions=settings["challenger_embedding_dimensions"],
                call_counts=call_counts,
            )
        )
        challenger_embedding_metrics = compile_controlled_ranking_metrics(
            challenger_embedding_rows
        )
        stage_receipts["challenger_embedding_4b_q4_k_m"] = (
            challenger_embedding_receipt
        )
        del embedding_tokenizer
        _release_cuda()

        (
            baseline_reranker_receipt,
            baseline_reranker_rows,
            reranker_tokenizer,
            prompt_ids,
            yes_token_id,
            no_token_id,
        ) = _run_baseline_reranker(
            rows,
            model_dir=Path(baseline["reranker"]["local_directory"]).resolve(),
            instruction=settings["reranker_instruction"],
            maximum_tokens=settings["maximum_input_tokens"],
            call_counts=call_counts,
        )
        baseline_reranker_metrics = compile_controlled_ranking_metrics(
            baseline_reranker_rows
        )
        stage_receipts["baseline_reranker_0_6b"] = baseline_reranker_receipt

        challenger_reranker_receipt, challenger_reranker_rows = (
            _run_challenger_reranker(
                rows,
                baseline_tokenizer=reranker_tokenizer,
                baseline_prompt_ids=prompt_ids,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                instruction=settings["reranker_instruction"],
                model_path=reranker_model_path,
                server_path=server_path,
                tool_dir=tool_dir,
                log_path=private_dir / "challenger_reranker_server.log",
                maximum_tokens=settings["maximum_input_tokens"],
                context_size=settings["llama_context_size"],
                n_probs=settings["reranker_n_probs"],
                call_counts=call_counts,
            )
        )
        challenger_reranker_metrics = compile_controlled_ranking_metrics(
            challenger_reranker_rows
        )
        stage_receipts["challenger_reranker_4b_q4_k_m"] = (
            challenger_reranker_receipt
        )
        del reranker_tokenizer, prompt_ids
        _release_cuda()

        decision = compile_quantized_shadow_decision(
            baseline_embedding=baseline_embedding_metrics,
            challenger_embedding=challenger_embedding_metrics,
            baseline_reranker=baseline_reranker_metrics,
            challenger_reranker=challenger_reranker_metrics,
            gates=program["quality_gates"],
        )
        body = {
            "schema_version": "fin_ia_s1_quantized_4b_controlled_shadow_result_v1_0",
            "status": "controlled_shadow_complete_no_runtime_or_s1_authority",
            "recorded_at": "2026-08-24",
            "started_at_utc": started_at,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_id": args.attempt_id,
            "program_ref": program_path.relative_to(ROOT).as_posix(),
            "program_sha256": _sha256(program_path),
            "program_result_digest": program["result_digest"],
            "git_receipt": git_receipt,
            "hardware_before": hardware,
            "eval": {
                "ref": eval_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(eval_path),
                "result_digest": program["eval_result_digest"],
                "query_count": len(rows),
                "candidate_occurrence_count": sum(
                    len(row["candidates"]) for row in rows
                ),
                "unique_document_count": len(_unique_documents(rows)),
                "case_inventory": sorted({str(row["case_key"]) for row in rows}),
                "forbidden_cases_loaded": [],
                "controlled_pool_only": True,
            },
            "acquisition": {
                "ref": acquisition_path.relative_to(ROOT).as_posix(),
                "sha256": _sha256(acquisition_path),
                "result_digest": acquisition["result_digest"],
            },
            "baseline_identities": baseline_identities,
            "challenger_identities": identities,
            "execution_settings": settings,
            "stage_receipts": stage_receipts,
            "metrics": {
                "baseline_embedding_0_6b": baseline_embedding_metrics,
                "challenger_embedding_4b_q4_k_m": challenger_embedding_metrics,
                "baseline_reranker_0_6b": baseline_reranker_metrics,
                "challenger_reranker_4b_q4_k_m": challenger_reranker_metrics,
            },
            "score_rows": {
                "baseline_embedding_0_6b": baseline_embedding_rows,
                "challenger_embedding_4b_q4_k_m": challenger_embedding_rows,
                "baseline_reranker_0_6b": baseline_reranker_rows,
                "challenger_reranker_4b_q4_k_m": challenger_reranker_rows,
            },
            "decision": decision,
            "calls": {
                **dict(sorted(call_counts.items())),
                "external_network": 0,
                "provider": 0,
                "paid_model": 0,
                "model_nodes": 4,
            },
            "authority": dict(program["authority"]),
            "known_boundary": program["known_boundary"],
        }
        result = _result_with_digest(body)
        _write_json(private_path, result)
        _write_json(output_path, result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "attempt_id": result["attempt_id"],
                    "metrics": {
                        key: value["overall"]
                        for key, value in result["metrics"].items()
                    },
                    "decision": result["decision"],
                    "calls": result["calls"],
                    "result_digest": result["result_digest"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        _release_cuda()
        body = {
            "schema_version": "fin_ia_s1_quantized_4b_controlled_shadow_result_v1_0",
            "status": "controlled_shadow_failed_successor_attempt_required",
            "recorded_at": "2026-08-24",
            "started_at_utc": started_at,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_id": args.attempt_id,
            "program_ref": program_path.relative_to(ROOT).as_posix(),
            "program_sha256": _sha256(program_path),
            "program_result_digest": program["result_digest"],
            "git_receipt": git_receipt,
            "hardware_before": hardware,
            "failure": {
                "exception_type": type(exc).__name__,
                "message": str(exc)[:8000],
            },
            "completed_stage_receipts": stage_receipts,
            "calls": {
                **dict(sorted(call_counts.items())),
                "external_network": 0,
                "provider": 0,
                "paid_model": 0,
            },
            "runtime_promotion_authorized": False,
            "S1_qualification_authorized": False,
            "successor_attempt_required": True,
        }
        result = _result_with_digest(body)
        _write_json(private_path, result)
        _write_json(output_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
