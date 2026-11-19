# Organization retrieval

Start the local identity and native research services first. Organization retrieval uses Java's current project and source permissions, the signed-in BFF, the native worker and a shared workbench state volume. A private project upload becomes eligible after its owner publishes a version into an organization space and links it to the organization project.

From the checkout root, define this shell shortcut for the same Compose project. Run `fin up -d --build --wait`. Use the four Compose files and both environment files on subsequent starts.

```sh
fin() {
  docker compose --env-file .env --env-file .secrets/identity/identity.env \
    -f compose.yaml -f deploy/agent_server/compose.native.yaml \
    -f deploy/identity/compose.identity.yaml -f deploy/organization/compose.retrieval.yaml "$@"
}
```

In PowerShell the equivalent shortcut is:

```powershell
function fin { docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/agent_server/compose.native.yaml -f deploy/identity/compose.identity.yaml -f deploy/organization/compose.retrieval.yaml @args }
```

## Search your own documents with BM25

Publish the document version to an organization space, link it to the project and select it on a research input sheet. Choose **准备研究执行**. On the research record or prepared input sheet, open **检索本次研究资料**, keep **关键词 BM25 · 本地免费**, enter any keyword and select **搜索资料**. **读取原文** opens the matching passage from the version bound to that execution. You can use this before starting a model run or publishing a vector index.

The same-origin authenticated API accepts `POST /api/v1/asset-workspace/organization-projects/{project}/research-drafts/{draft}/executions/{execution}/navigate`, the `x-workbench-request: 1` header and the body below. The public organization profile defaults to BM25 when an API request omits the mode. BM25 reads the bound originals or the pinned release’s verified postings, ranks passages with overlapping tokens and makes zero external retrieval calls. An unmatched keyword returns zero results. Current project access, source version and execution binding are checked on each search and readback.

```json
{"source_space":"organization","operation":"search","organization_retrieval_mode":"bm25","query":"working capital"}
```

## Optional semantic retrieval and costs

Select **混合检索** or send `"organization_retrieval_mode":"hybrid"` to combine dense and BM25 rankings for a pinned release. The organization overlay passes the same settings to the BFF and native worker. A release with an exact prepared query vector can run hybrid search offline if reranking is off. A new hybrid query needs the configured query embedding provider. An unprepared hybrid query with that adapter disabled returns HTTP 422.

| Private setting | Effect |
| --- | --- |
| `FINSIGHT_ORGANIZATION_DEFAULT_RETRIEVAL` | `bm25` by default in the public organization profile. Set `hybrid` to make requests without an explicit mode use the pinned hybrid release. |
| `FINSIGHT_ORGANIZATION_QUERY_EMBEDDING=qwen` | Enables an external embedding for a new query on a frozen release. The release pins `text-embedding-v4` or `qwen3.7-text-embedding`, 1,024 dimensions. |
| `FINSIGHT_ORGANIZATION_RERANK=qwen` | Enables external reranking on complete chunk releases with a published candidate navigation index. Plain text uploads use the text projection and local fusion. |
| `FINSIGHT_ORGANIZATION_RERANK_MODEL` | Supports `qwen3-rerank` (default) and `qwen3.7-text-rerank`. |
| `QWEN_API_KEY` | Your deployment's DashScope credential for the selected adapters. The embedding service receives the query. The reranking service receives the query and authorized candidate passages. |

Set only the desired switches in the private `.env`, then apply them with `fin up -d`. The query and reranking adapters record usage and stop on failed or unknown requests. Reranking supports up to 48 authorized candidates per request. Expanding a corpus, uploading a file or installing the overlay does not automatically embed it.

## Publish a release

Follow this procedure when you need a reusable vector index. To search the original text of a prepared execution first, use the [BM25 walkthrough](#search-your-own-documents-with-bm25).

1. In the organization project, create a research input sheet with a cutoff and the published sources. Select **准备执行** to bind this sheet. This prepares an execution without starting a model run. Record the project, draft and execution UUIDs and the draft's `manifest_digest`. The workbench research-draft API exposes the stored digest.
2. Export the authorized inputs through the native worker. The operator CLI rechecks the Java grant and original content. In the following commands replace `EXECUTION_UUID`, `sha256:DIGEST`, `ORG_UUID` and `RELEASE_UUID` with actual values. Choose a new release UUID and a fresh input file for each publication.

   ```sh
   fin exec langgraph-api mkdir -p /app/state/index-inputs/EXECUTION_UUID
   fin exec langgraph-api python -m sec_agent.research_foundation.organization_index_cli export --execution EXECUTION_UUID --manifest-digest sha256:DIGEST --inputs /app/state/index-inputs/EXECUTION_UUID/inputs.jsonl
   fin cp langgraph-api:/app/state/index-inputs/EXECUTION_UUID/inputs.jsonl ./.secrets/EXECUTION_UUID-inputs.jsonl
   ```

   Keep the exported inputs and embedding job output in the ignored private directory. The export contains original text, node IDs and SHA-256 digests. Each complete source chunk preserves its embedding context.

3. **Supply document vectors for hybrid search.** The organization CLI can read this exact export and run the same corpus embedding job as the library SQLite indexer. The default command below validates the original bindings, lists missing vectors and maximum provider requests, and saves `audit/TokenBudgetBasis.json`. The plan runs without a key or external calls.

   ```sh
   fin exec langgraph-api python -m sec_agent.research_foundation.organization_index_cli embed --execution EXECUTION_UUID --manifest-digest sha256:DIGEST --inputs /app/state/index-inputs/EXECUTION_UUID/inputs.jsonl --model text-embedding-v4
   ```

   To purchase corpus embedding, provide your own `QWEN_API_KEY`; review the model, text volume, provider pricing and plan. Run the same command with `--execute --max-requests N` only if you authorize sending the exported passages and approve that maximum request count. The count limits requests rather than currency. The local job ledger retains provider usage or unknown usage and blocks automatic resubmission of failed requests. Creating a `STOP` file in the printed job directory stops further dispatch and lets in-flight requests finish. A completed job prints the path to row-ordered `vectors.npy` and the audit directory is under the printed job path. Use that vector path with `publish` below.

   You can also use your own embedding job. Embed each exact `text` field in file order with one supported model and save a numeric NumPy matrix of shape `(number of lines, 1024)`. Retain the model, source digests, row order and job receipts. The release records operator-supplied provenance. For offline hybrid queries you can optionally supply a private JSON object mapping each exact query to its 1,024-dimensional vector from the same model.

   ```sh
   fin cp ./.secrets/EXECUTION_UUID-vectors.npy langgraph-api:/app/state/index-inputs/EXECUTION_UUID/vectors.npy
   fin exec langgraph-api python -m sec_agent.research_foundation.organization_index_cli publish --execution EXECUTION_UUID --manifest-digest sha256:DIGEST --inputs /app/state/index-inputs/EXECUTION_UUID/inputs.jsonl --vectors /app/state/index-inputs/EXECUTION_UUID/vectors.npy --model text-embedding-v4 --provenance YOUR_EMBEDDING_JOB_ID --release RELEASE_UUID
   fin exec langgraph-api python -m sec_agent.research_foundation.organization_index_cli check --organization ORG_UUID --release RELEASE_UUID
   ```

   Add `--query-vectors /app/state/index-inputs/EXECUTION_UUID/queries.json` to `publish` if you supplied offline queries. Publication checks current input IDs, text and digests, validates and normalizes the vectors, writes BM25 postings and seals the manifest. The check reads and verifies release files, their shapes, digests and unit vectors. Complete chunk releases also have `navigation.sqlite`. A partial or existing release directory is preserved and a new release needs a new UUID.

4. **Register the new release as a project manager.** With the project manager signed in, use the same-origin BFF endpoint below. Registration checks the original input sheet, source versions and current permissions before Java stores the release contract. Reconcile an unknown result with the GET endpoint. For example, in the HTTPS workbench's browser console:

   ```javascript
   const path = '/api/v1/asset-workspace/organization-projects/PROJECT_UUID/research-drafts/DRAFT_UUID/retrieval-releases/RELEASE_UUID'
   const submitted = await fetch(path + '/register', { method: 'POST', headers: { 'x-workbench-request': '1' } })
   console.log(submitted.status)
   console.log(await (await fetch(path + '/registration')).json())
   ```

5. Create a **new** organization input sheet, select the registered **检索版本** and save it. Prepare the new execution. Its manifest pins the release ID, index and matrix digests, model, dimensions and projection. Select the retrieval mode in the workbench or include it in the authenticated search body above. Inspect the returned source readback, `retrieval.mode`, `lexical_source`, `provider_calls` and, for hybrid searches, the query embedding and optional rerank receipts.

BFF and native both use `/app/state/organization-indexes/<organization>/releases/<release>/` on the same writable volume. Keep the index manifests and matrix immutable. Ranking caches, query receipts and verification locks require writable storage. Back up this volume together with its Java registration database and corresponding organization publications. Never publish private input/vector files in the source repository.
