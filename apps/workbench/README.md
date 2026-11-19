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
