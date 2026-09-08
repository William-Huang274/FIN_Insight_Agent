# Three-minute product tour

[中文](demo-and-engineering.zh-CN.md) · [Run requirements](quickstart.en.md) · FIN 0.1.3

Use a configured workspace and saved results; there is no need to rerun full research for a demonstration. Dell v5 awaits human review. Public screenshots show the actual application without distributing the full report or source corpus.

## Walkthrough

| Time | Action | What to explain |
| --- | --- | --- |
| 0:00–0:25 | Open the start page and project sidebar | Begin with a research question. Project groups live in the browser; tasks and reports live on the server. |
| 0:25–1:00 | Navigate overview → topic → judgment | Browse report content without treating the execution graph as the report outline; follow a judgment to its evidence. |
| 1:00–1:30 | Expand source context or a calculation | Inspect periods, units, operands and source locations; arithmetic checks do not establish financial interpretation. |
| 1:30–2:00 | Inspect the existing v4→v5 diff, then collapse it | Targeted feedback carries a target and baseline. Revisions preserve the old report; completed execution is not human acceptance. |
| 2:00–2:30 | Open Studio and select a role/Skill | Methods, concurrency and dual-review order are editable. Saved snapshots persist natively and can be applied to tasks; viewing does not require saving. |
| 2:30–3:00 | Inspect run history and play/pause replay | Stage cards and public events are connected. Cost remains the whole operation's recorded usage; replay makes no model calls. |

![Editable research methods](images/research-studio.png)

Studio is backed by runtime configuration rather than a raw JSON draft. A live short question verified that edited instructions entered two model requests and changed answer organization: about 15 seconds, 43,622 tokens and estimated CNY0.085984. This is neither a full research cost nor a cross-role effectiveness comparison.

![Run history and public activity](images/research-runtime.png)

Saved guidance, input delivery at a later phase and actual adoption are different states. Cancellation cannot reverse incurred cost; uncertain requests are not automatically resubmitted. During a read-only demo, do not start research, save configurations, submit revisions or accept a report.

## Three engineering topics worth inspecting

**From a UI node to a real revision.** Sections provide navigation. A judgment carries an artifact ID, version, digest and checkpoint. The BFF checks the baseline and the native graph executes the revision. A new report version and actual diff return to the UI; company names in titles do not select hardcoded revision behavior.

**From an edited method to execution.** Native Assistants store independent configuration snapshots fixed for each run. Methods enter role prompts and MCP reads. Specialist context is bound before its request digest is generated, preserving receipt validation. The editor exposes supported order/concurrency choices and retains required review.

**Preserving evidence while managing context.** Native checkpoints retain original messages and artifacts. Outgoing requests can clear old tool bodies and retrieve them by ID later. Saved calculations keep their operands/provenance and do not become authoritative database facts just because they are reused. Automatic summaries remain disabled; cache hit rate is neither compression nor overall savings.

See [architecture](architecture.en.md) for implementation paths and [evidence](sharing-scope.md) for actual failures and development costs. Later success does not erase earlier failed attempts.

## Testing and feedback

Without the complete research data, use the source and synthetic browser checks in the [quickstart](quickstart.en.md). They verify interactions and wiring, not report quality. Report the page, exact steps, expected/actual result and code version. Do not submit private model context or source documents.

Demonstrated engineering work includes source binding, native state and human revision, configuration consumption, usage visibility and multi-format delivery. Production HA, universal company coverage, unassisted accuracy and general cost savings remain unproven.
