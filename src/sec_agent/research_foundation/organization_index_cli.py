"""Export authorized organization inputs and publish operator-prepared vectors."""
import argparse
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

import numpy as np

from retrieval.prepared_node_store import PreparedNodeStore
from .asset_workspace import AssetWorkspace
from .organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
from .organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
from .organization_index_release import CHUNK_PROJECTION, PROJECTION, load_release


def input_row(node):
    text = node["content"]
    if "embedding_context" in node:
        text = node["embedding_context"] + "\n" + text
    digest = sha256(text.encode()).hexdigest()
    if digest != node.get("embedding_input_sha256", node["content_sha256"]):
        raise ValueError("organization_embedding_projection_changed")
    return {"node_id": node["node_id"], "input_sha256": digest, "text": text}


def embed_export(args, nodes, reader):
    from retrieval.library_vectors import DIM, prepare_rows, ready_index
    rows = []
    with args.inputs.open(encoding="utf8") as saved:
        for node, line in zip(nodes, saved, strict=True):
            row = input_row(node)
            if row != json.loads(line):
                raise ValueError("embedding_inputs_no_longer_match_originals")
            rows.append({"id": row["node_id"], "source_id": node["parent_document_id"], "text": row["text"]})
    reader.check()
    key = os.getenv("QWEN_API_KEY", "") if args.execute else ""
    if args.execute and (not key or args.max_requests is None or args.max_requests < 0):
        raise ValueError("corpus_embedding_execution_requires_own_key_and_max_requests")
    # Keep each job and its failed/unknown request ledger bound to this execution, input digest and model.
    job = args.inputs.parent / ("embedding-" + str(args.execution) + "-" + args.model + "-" + args.manifest_digest[7:])
    receipt = prepare_rows(rows, args.manifest_digest, job, key, job / "audit", execute=args.execute,
                           max_requests=args.max_requests, model=args.model, stop_file=job / "STOP")
    if args.execute and receipt.get("matrix_sha256"):
        reader.check()
        _, matrix, mapping = ready_index(job, args.manifest_digest)
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile(dir=job, suffix=".npy", delete=False) as tmp:
            pending = Path(tmp.name)
        try:
            output = np.lib.format.open_memmap(pending, mode="w+", dtype=np.float32, shape=(len(rows), DIM))
            for index, (row, mapped) in enumerate(zip(rows, mapping, strict=True)):
                if (mapped["id"], mapped["source_id"]) != (row["id"], row["source_id"]):
                    raise ValueError("embedding_mapping_differs_from_export")
                output[index] = matrix[mapped["vector_index"]]
            output.flush()
            del output
            pending.replace(job / "vectors.npy")
        finally:
            pending.unlink(missing_ok=True)
        receipt = {**receipt, "vectors": str(job / "vectors.npy")}
    print(json.dumps({"job": str(job), "receipt": receipt}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("export", "embed", "publish", "check"):
        sub = commands.add_parser(action)
        if action == "check":
            sub.add_argument("--organization", required=True, type=UUID)
        else:
            sub.add_argument("--execution", required=True, type=UUID)
            sub.add_argument("--manifest-digest", required=True)
            sub.add_argument("--inputs", required=True, type=Path)
        if action in ("publish", "check"):
            sub.add_argument("--release", required=True, type=UUID)
        if action == "embed":
            sub.add_argument("--model", choices=("text-embedding-v4", "qwen3.7-text-embedding"), default="text-embedding-v4")
            sub.add_argument("--execute", action="store_true", help="Authorize sending exported text to the model provider")
            sub.add_argument("--max-requests", type=int, help="Approve at most this many embedding requests")
        if action == "publish":
            sub.add_argument("--vectors", required=True, type=Path)
            sub.add_argument("--model", required=True, choices=("text-embedding-v4", "qwen3.7-text-embedding"))
            sub.add_argument("--provenance", required=True, help="Operator embedding job or receipt identifier")
            sub.add_argument("--query-vectors", type=Path, help="Optional JSON mapping exact query strings to prepared vectors in the same embedding space")
    args = parser.parse_args()
    root = Path(os.environ["FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT"])
    if args.action == "check":
        _, index, _, contract = load_release(root, str(args.organization), str(args.release))
        print(json.dumps({"contract": contract, "nodes": len(index["records"]), "bm25": index.get("lexical_index"),
                          "candidate_navigation": index.get("navigation_index")}))
        return
    authority = OrganizationExecutionAuthority(base_url=os.environ["FINSIGHT_BUSINESS_API_URL"],
        secret=os.environ["FINSIGHT_ORGANIZATION_RUNTIME_SECRET"], execution_id=str(args.execution),
        manifest_digest=args.manifest_digest, network_profile=os.getenv("FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK", "loopback"))
    reader = OrganizationExecutionReader(AssetWorkspace(Path(os.environ["FINSIGHT_ORGANIZATION_ASSETS_ROOT"])), authority)
    with TemporaryDirectory() as staging, closing(PreparedNodeStore(Path(staging) / "nodes.sqlite")) as store:
        org, nodes = preparation_nodes(reader, workbench_url="http://localhost", node_store=store)
        if not len(nodes):
            raise ValueError("organization_projection_is_empty")
        if args.action == "embed":
            embed_export(args, nodes, reader)
            return
        if args.action == "export":
            with args.inputs.open("x", encoding="utf8") as output:
                for node in nodes:
                    output.write(json.dumps(input_row(node), ensure_ascii=False) + "\n")
            print(json.dumps({"organization": org, "inputs": len(nodes)}))
            return
        vectors = np.load(args.vectors, mmap_mode="r", allow_pickle=False)
        if vectors.shape != (len(nodes), 1024):
            raise ValueError("expected_one_1024_dimensional_vector_per_input")
        chunk_count = 0
        with args.inputs.open(encoding="utf8") as saved:
            for node, line in zip(nodes, saved, strict=True):
                if input_row(node) != json.loads(line):
                    raise ValueError("embedding_inputs_no_longer_match_originals")
                chunk_count += int("embedding_input_sha256" in node)
        queries = json.loads(args.query_vectors.read_text(encoding="utf8")) if args.query_vectors else {}
        reader.check()
        publish_prepared_index(root, org, nodes, vectors, queries, model=args.model, provenance=args.provenance,
            release_id=str(args.release), projection=CHUNK_PROJECTION if chunk_count else PROJECTION,
            publish_navigation=chunk_count == len(nodes))
        _, _, _, contract = load_release(root, org, str(args.release))
        reader.check()
        print(json.dumps({"organization": org, "contract": contract, "registered": False}))


if __name__ == "__main__":
    main()
