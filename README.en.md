# FinSight Agent

FinSight is a self-hosted workspace for financial research. Add two quarterly filings to a project and ask why a bank earned more interest income as rates fell. Follow the investigation, open the disclosure behind a figure, and compare answers when the next filing arrives.

[中文](README.md) · [Quickstart](docs/public/quickstart.en.md) · [Architecture](docs/public/architecture.en.md) · [Example research skill](examples/skills/source-comparison/SKILL.md)

![A bank report comparing interest margins, earning assets and income](docs/public/images/report-preview.png)

*Current workbench UI. The bank, disclosures and figures in both screenshots are illustrative.*

## What you can do in the workbench

| Task | How it works |
| --- | --- |
| Follow a company over time | Keep documents, research sessions, working notes and reports in a project. Ask follow-up questions in a conversation or start a research session with a question, cutoff date and attachments. |
| Check disclosures and financial figures | Filter documents by company, period and filing type. Inspect financial accounts, units and sources, and trace derived figures to formulas and operands. Coverage depends on the data you import and sources you connect. |
| Search team documents | Publish a document version to a shared space and select it for a project investigation. Local BM25 can find passages before any model run. Configure embeddings and reranking for hybrid retrieval. [Organization retrieval](deploy/organization/README.md) |
| Choose investigators and budgets | Ordinary research uses one investigator and an independent reviewer. Deep research can delegate topics and reconcile findings. Personal sessions accept a DeepSeek key for V4 Flash or Pro. Organizations can fund a specific task with GPT-6.2 Sol high as lead and DeepSeek Flash as investigator. [Model setup](apps/workbench/README.md) |
| Reuse a research method | Edit research directions, role skills, expert concurrency and review order in the configuration screen. Save a version and apply it to a task. [Source-comparison skill](examples/skills/source-comparison/SKILL.md) |
| Follow and steer a run | Read public progress, tool activity and recorded usage. Where the run supports interaction, send a question to investigate, request a stop or inspect why an earlier run stopped. |
| Review and deliver | Open cited passages, chart data and calculation notes. Request a revision to a working note, compare report versions and export to a web page, Markdown, PDF, Word or PowerPoint. |
| Collaborate across accounts | In a multi-user deployment, register accounts, assign organization, project and resource-space roles, share specific document versions and revoke access. Access checks apply to searches, reads and downloads. |

Operators supply contact details or credentials for external sources such as SEC EDGAR, OpenDART, HiThink and Alpha Vantage. Bring your own documents, data subscriptions and team indexes. [Data and deployment configuration](docs/public/quickstart.en.md)

## Follow a finding back to the filing

Two filings give the investigator a starting point for explaining the change in interest income at one bank. To ask which bank benefits more, a deeper investigation can compare deposit costs, loan mix and valuation across lenders.

In the example, net interest margin fell from 2.1% to 2.0%, while average earning assets rose from 10 billion to 11 billion yuan. At those margins, estimated annualized net interest income rose from 210 million to 220 million yuan. Open the citation to check the inputs. If assets hold steady, a margin of about 1.91% would bring income back to its previous level. That gives the analyst a figure to watch next quarter.

![An expanded citation showing the reporting date and the passage behind the figures](docs/public/images/source-preview.png)

When the next filing arrives, add it to the same project and ask how the new margin compares with that threshold. Switch report versions to see which judgment changed.

## Open the workbench locally

With Docker Compose and Python 3.10 or later installed, run these commands from the repository root.

```sh
python scripts/deployment/initialize.py
docker compose up -d --build
```

Open [Projects](http://127.0.0.1:8765/workspace/projects). The base installation provides project, document and account services. Live research requires the native execution service, your own provider credentials and a budget. See the guide for multi-user sign-in, model selection and retrieval setup. [Quickstart](docs/public/quickstart.en.md) · [Smoke test](scripts/dev/verify_public_checkout.py)
