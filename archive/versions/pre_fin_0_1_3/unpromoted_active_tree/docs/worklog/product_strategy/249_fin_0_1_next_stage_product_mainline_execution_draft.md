# FIN 0.1 Next-Stage Product Mainline Execution Draft

Date: 2026-07-19

Status: `docs_only_discussion_draft`

## Problem

The PRD, TECH documents and Point plans describe a large system, while the current FIN 0.1 product path only proves a deterministic internal vertical. A durable next-stage document was needed to prevent Workbench, Agent, Skill, Tool, Graph, Writer and Human Review from continuing as separately passing but disconnected slices.

## Decision

Created `docs/architecture/repository/FIN_0_1_NEXT_STAGE_PRODUCT_MAINLINE_EXECUTION_DRAFT_20260719.zh-CN.md` as a discussion draft. It translates five product-mainline completion conditions into current state, acceptance evidence and bounded execution points:

1. Workbench creates a canonical internal Case;
2. the Case runs only through `Fin01ResearchRuntime`;
3. Agent/Skill/Tool/Graph usage is traceable;
4. Workpaper/Report/Trace/Human Review share one exact Run;
5. UI does not confuse deterministic fallback with real Agent execution.

## Boundaries

- No runtime or product code changed.
- No ReleaseContract, FeatureScope or machine backlog authority changed.
- No model, provider, network, tool, paid, commercial-data or operational execution occurred.
- No real business Case mutation, production cutover or release admission was authorized.
- The draft must absorb the remaining Agent Core, search/graph, judgment/workpaper, writer/review and release discussions before it can become an accepted overlay.

## Next Discussion

Decompose the historical Multi-Agent/LangGraph, Agent Registry and Skill implementation into retain/refactor/absorb/retire decisions, and map the accepted target into `PM-EP2` without creating another parallel Agent framework.
