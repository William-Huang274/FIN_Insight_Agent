# Workbench

The React frontend lives in `frontend/vite` and the same-origin Python API in `backend`. Build the browser bundle with `npm ci` and `npm run build` in `frontend`. See the [quickstart](../../docs/public/quickstart.en.md) for deployment and service configuration.

## Personal research

Open **新建个人研究** in the workspace or visit `/workspace/session?view=new`. Ordinary research sends the sole investigator’s cited report to an independent verifier before human review. Deep research delegates work according to the question and retains the existing review pipeline. The page offers role defaults, DeepSeek V4 Flash and V4 Pro. Each run records its selected model and mode. Uploads are parsed before dispatch. Saving a draft allows inspection without model usage.

The personal key field accepts the user’s own official DeepSeek API key. The BFF encrypts credentials per owner and returns only configured status. The BFF and Agent Server require the same private `FINSIGHT_PERSONAL_KEY_STORE` directory and read-only `FINSIGHT_PERSONAL_KEY_FILE` containing a Fernet master key. Back up the key separately from the store. Key removal blocks future personal-key runs including continuations. An in-progress worker may already have loaded the key. The selected key also applies to enabled image-reading calls.

Keep single-user local identity on loopback. Use authenticated product identity and HTTPS for shared service. With a provisioned key store, users supply their own credentials. An operator may set `FINSIGHT_ALLOW_LOCAL_PROVIDER_KEY=1` for a private single-user deployment. Authenticated users always need personal credentials. `FINSIGHT_PERSONAL_RESEARCH_ENABLED=1` enables personal creation alongside organization on-demand mode when the personal runtime is installed.

## Organization model combination

A funded continuous execution can use GPT-6.2 Sol with high reasoning as lead and DeepSeek Flash as investigator. The lead calls investigators as needed. Preparing an execution makes no provider call. Mandatory independent report review is available through the standard workflow.

In the deployment's private report-session settings, define `organization_model_profiles["sol-high-flash"]` with `binary`, `binary_sha256`, `context_window`, `output_tokens`, `summary_tokens`, `token_budget_basis` and `research_delegate`. The delegate has its own window, output and summary limits, token budget basis, positive `reservation_micros` and `reservation_basis`. Each token budget basis follows the existing `TokenBudgetBasis` schema. Supply the verified harness binary separately.

For each funded execution ID set `organization_profile_bindings[execution_id]` to the authorized draft’s exact `organization_id`, `project_id`, `draft_id` and `manifest_digest`. Its existing `model_budget_bindings[execution_id]` must reference that organization’s provisioned PostgreSQL budget, lead reservation and prices for `gpt-6.2-sol` and `deepseek-flash`. The BFF checks budget availability when offering the choice for an accessible draft. The native runtime rechecks Java authority, budget, and the digest of the selected execution binding before using it.

Provision `FINSIGHT_ORGANIZATION_MODEL_KEYS/<organization UUID>/openai.key` and `deepseek.key`. The BFF needs matching settings, release and credential-file availability. The native worker loads credential contents after authorization. The parent and investigator use fixed official endpoints and separate keys. The harness subprocess receives an opaque per-run loopback token. An unconfigured installation exposes only the default execution choice.

### Provision the optional organization model combination

The repository ships a settings generator and checker. Install the locked `agent-runtime` extra, obtain a verified compatible DS Harness executable with its release checksum, and run these commands where its absolute path matches the native worker. Start from `deploy/agent_server/settings.json` for a fresh installation, or supply the current deployment settings to preserve existing bindings. Keep the generated settings outside Git.

Choose a new execution UUID. Copy the organization, project, draft and manifest identifiers from the authorized draft. Set the context-window variables to the capacities approved for the deployed models. Set the six rate variables to your contract's integer currency **micros per million tokens**, in uncached-input, cached-input, output order. Set the two reservation variables to **currency micros per request**. The generator takes no keys or database passwords as arguments.

```sh
uv run --locked --extra agent-runtime python scripts/deployment/organization_model_profile.py prepare \
  --settings deploy/agent_server/settings.json --out "$PRIVATE_SETTINGS" \
  --organization "$ORG_ID" --project "$PROJECT_ID" --draft "$DRAFT_ID" \
  --execution "$EXECUTION_ID" --manifest "$MANIFEST_DIGEST" \
  --binary "$HARNESS_BINARY" --binary-sha256 "$VERIFIED_RELEASE_SHA256" \
  --task-scope "$APPROVED_RESEARCH_SCOPE" --price-version "$DATED_PRICE_SOURCE" --currency USD \
  --lead-window "$LEAD_WINDOW" --investigator-window "$FLASH_WINDOW" --summary-tokens "$SUMMARY_LIMIT" \
  --lead-prices "$SOL_INPUT_MISS" "$SOL_INPUT_HIT" "$SOL_OUTPUT" \
  --investigator-prices "$FLASH_INPUT_MISS" "$FLASH_INPUT_HIT" "$FLASH_OUTPUT" \
  --lead-reservation "$LEAD_RESERVATION" --investigator-reservation "$FLASH_RESERVATION"
```

The generator refuses an existing output file. Its role limits and stop policies come from the checked-in research profile. Use `--roles` with a reviewed replacement for workloads whose input scale, expected output or risk differ. Each added execution gets a separate budget ID. Enabling the runtime's model-budget bindings requires a valid binding for each funded thread on that deployment.

Bootstrap a **dedicated** PostgreSQL budget database with SQL files 003, 005, then 004 from `src/sec_agent/agent_runtime/sql`. Apply them as the migration owner in a new database with no conflicting role names. Use a provisioner login in `fin_model_provisioner` for funding, and an unprivileged worker login in `fin_model_worker` for runtime checks. Supply their DSNs through `FIN_MODEL_BUDGET_PROVISIONER_URI` and `FIN_MODEL_BUDGET_POSTGRES_URI` respectively. Keep the provisioner DSN out of both product services. Place the organization's two provider key files under `FINSIGHT_ORGANIZATION_MODEL_KEYS` as described above.

```sh
uv run --locked --extra agent-runtime python scripts/deployment/organization_model_profile.py fund \
  --settings "$PRIVATE_SETTINGS" --execution "$EXECUTION_ID" \
  --authorized-micros "$APPROVED_TOTAL" --delivery-floor-micros "$DELIVERY_FLOOR"
uv run --locked --extra agent-runtime python scripts/deployment/organization_model_profile.py check \
  --settings "$PRIVATE_SETTINGS" --execution "$EXECUTION_ID"
```

The first command writes the expressly authorized ceiling to PostgreSQL. The second reads it using the runtime role, checks the executable checksum and credential-file availability, then prints the execution ID and profile reference. Neither command dispatches a model. Mount the settings at `FINSIGHT_REPORT_SESSION_SETTINGS` for both BFF and native worker, and provide the worker with a private writable `FINSIGHT_HARNESS_STATE_ROOT`. Enable organization start and on-demand execution on the participating services. In the project's research tab, open the matching draft and select **GPT-6.2 Sol high 主持 · DeepSeek Flash 调查** under **模型组合**. Preparing freezes the selected profile. Starting the execution is a separate billable action.

For Compose, add `-f deploy/organization/compose.harness.yaml` after the native, identity and organization retrieval files. Supply `FINSIGHT_FUNDED_SETTINGS_FILE`, `FINSIGHT_ORGANIZATION_KEY_DIRECTORY`, `FINSIGHT_DSH_BINARY_FILE` and the worker-only `FIN_MODEL_BUDGET_POSTGRES_URI`. The settings generator's verified executable path must resolve to `/opt/finsight/dsh` in both containers; run the generator in that filesystem layout. The overlay mounts the binary, settings and per-organization credential directory read-only. Grant the container service user read/execute access to the binary and read access to its scoped key files. The packaged ACP plugins live under `integrations/deepseek-harness/` in the worker image. Run `docker compose ... config --quiet` to check the combined configuration without printing credential values.


General conversations at `/workspace/assistant` use the same private DeepSeek key. Open **个人模型密钥** to save or replace the current account’s key. New messages, approval resumes, working-note revisions and automatic summaries use the conversation owner recorded by the native service. A missing key blocks dispatch. The Hermes preview uses a separately configured host service and is available only on a private local workstation with explicit host credentials enabled. Organization continuous work and its delegated children retain their admitted organization budgets and credential sources.
