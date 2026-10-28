"""One original-context preparation path for service and frozen evaluation.

The source adapter owns current authorization or an explicitly offline frozen
scope. This function does not supply grants, provider clients or result grades.
"""


def prepare_candidates(adapter,ranked,eligible,manifest,*,needs,wanted,
                       document_context=False,table_context=False):
    rows=adapter.materialize(ranked,manifest)
    if needs or wanted or table_context:rows=adapter.contextualize(rows,manifest)
    if wanted:
        from .evidence_scoring_view import attach_scoring_view
        rows=[attach_scoring_view(row,wanted) for row in rows]
    if document_context:
        from .rerank_document_context import with_document_context
        rows=with_document_context(rows,adapter.source_metadata)
    receipt=None
    if table_context:
        rows,receipt=adapter.complete_tables(rows,eligible,manifest,independent_candidates=True)
        for row in rows:row['rerank_table_completion']=row.pop('table_completion')
    # Preserve the archived embedding input for vector validation. Reranking
    # must not treat a preceding body row in that input as this candidate's own
    # evidence. Verified same-table dependencies have their separate channel.
    from .original_input_context import POLICY
    for row in rows:row['scoring_context_policy']=POLICY
    return rows,receipt
