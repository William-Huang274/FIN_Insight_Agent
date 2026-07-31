# FIN 0.1 Layer 3 Agentic Search / Evidence Draft

Date: 2026-07-19

Status: `docs_only_discussion_draft`

## Decision

Created `docs/architecture/repository/FIN_0_1_LAYER_3_AGENTIC_SEARCH_EVIDENCE_EXECUTION_DRAFT_20260719.zh-CN.md` as the third-layer child of the Agent Core draft.

`L3-D05-AgenticSearchControl` is frozen as `evidence_request_driven_bounded_search_with_candidate_promotion_separation`:

- EvidenceRequest, not a free search string, is the product-ledger entry;
- Lead owns the evidence objective, Specialist may refine the request, Tool Planner proposes routes, ToolGateway admits execution, Operators return candidates and Evidence Gate exclusively owns promotion;
- RAG, SQL, Graph, memory and SourceHunter outputs remain candidates until metadata/parser/numeric lineage and Evidence Gate classification;
- each request carries its own bounded route/refinement/SourceHunter/cost policy and typed stop conditions;
- FIN 0.1 starts from existing local read-only assets; model permission does not imply network or commercial-data permission;
- Workbench shows research-purpose activity while exact tool/query/gate details remain inspectable.

`L3-D06-GraphResearchRoleAndAuthority` is frozen as `typed_provenance_graph_for_navigation_hypothesis_and_lineage`:

- Entity, business-relationship, evidence/claim, workflow and memory graphs are distinct logical namespaces with separate authority semantics;
- Graph primarily supports navigation, bounded mechanism exploration and lineage; a graph edge is not automatically Evidence;
- source-backed material edges must retain exact source/as-of/semantic boundaries and pass Evidence Gate, while inferred mechanisms remain hypotheses;
- Lead may request a profile-bounded graph expansion and source follow-up, but cannot write canonical graph state, invent authoritative edges, infer economic magnitude or bypass promotion;
- FIN 0.1 starts with at most two-hop exploration and proves one explainable graph use for each of the three launch cells;
- the Workbench presents compact source-backed/inferred/unresolved paths, with full Graph Explorer details available on inspection.

## Current Boundary

- Current Workbench still runs a fixed local BM25/SQL/Graph preview and does not prove Agentic Search.
- No Runtime, Tool Planner, ToolGateway, SourceHunter, frontend or data implementation changed.
- No model, network, provider, paid data, Evidence promotion, canonical Case mutation or release action occurred.
- The next discussion is `L3-D07-EvidencePromotionAndCounterevidenceAuthority`.
