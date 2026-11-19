# Installation and use

Install Python 3.10 or later and Docker Compose. From the repository root, run:

```sh
python scripts/deployment/initialize.py
docker compose up -d --build
```

Open [Projects](http://127.0.0.1:8765/workspace/projects) to create a project. The default listener is on loopback. Keep the generated secrets with the database and storage backups.

## Connect model execution

For a multi-user deployment, initialize the local identity provider and start the HTTPS profile. Trust the generated `.secrets/identity/tls/ca.pem` on your local browser and open the [HTTPS workspace](https://localhost:18866/workspace). Users can register their own accounts and manage their identity profile. Organization and project roles govern access to shared material.

```sh
uv run --locked --extra workbench-auth python scripts/deployment/initialize_identity.py
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

Configure the native Agent Server's LangSmith access and your provider credentials, then run:

```sh
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml up -d --build
```

In a [research session](http://127.0.0.1:8765/workspace/session), select the model and research mode, enter the question and attach any documents. Save a draft to inspect the inputs before starting a paid run. Ordinary research uses one investigator followed by independent review. Deep research can delegate topics and consolidate their evidence. Available choices depend on the enabled execution service. Personal credentials belong to the signed-in user.

Attachments in a research session supply that session. For reusable material, upload to the project library, complete parsing and publish the searchable version. Embedding, reranking and external data APIs require your own services or credentials. See the [deployment guide](../../deploy/agent_server/README.md).

## Knowledge base and retrieval setup

Start with keyword retrieval. Enable the identity and native services and apply the [organization retrieval Compose configuration](../../deploy/organization/README.md). Sign in, publish a project document version to an authorized organization space, link it to the project and select it on a research input sheet. Prepare the execution, open **检索本次研究资料**, search for a phrase in the file and select **读取原文**. BM25 reads the bound text without external retrieval requests. For a missing search box, check the retrieval overlay and execution preparation. For zero hits, check the selected version and whether its text is searchable. Project text lookup does not cover text inside images or scanned pages.

For hybrid retrieval, export the authorized inputs, prepare document vectors, publish and register the index, then select it on a new sheet. For new query embeddings, set `FINSIGHT_ORGANIZATION_QUERY_EMBEDDING=qwen` and `QWEN_API_KEY` in the private deployment environment. Complete chunk releases also support `FINSIGHT_ORGANIZATION_RERANK=qwen`. Apply these settings with the guide's `fin up -d` command. Embeddings send input text to the provider; reranking sends the query and authorized candidates. These operations may incur fees. Uploading a file does not itself purchase embeddings. [Index publication commands](../../deploy/organization/README.md#publish-a-release)

## Quick checks

```sh
uv sync --locked --extra agent-runtime --extra workbench-auth --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout
```

To create synthetic exports, add `--output-directory .local/sample-report` using a new directory. To build the frontend, run `npm ci` followed by `npm run build` in `apps/workbench/frontend`. These checks do not contact a paid model.

For an organization execution with GPT-6.2 Sol high as lead and DeepSeek Flash as investigator, provision the two organization credentials and fund the execution before selecting the combination in its draft. The [organization model profile setup](../../apps/workbench/README.md#provision-the-optional-organization-model-combination) includes the settings generator, budget authorization and deployment check.
