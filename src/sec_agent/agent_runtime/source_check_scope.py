"""Required reads over existing immutable source references, not another retriever."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


class RequiredSourceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    criterion: str = Field(min_length=1, max_length=2000)
    selection: SourceDocumentRequest
    required_source_ids: list[str] = Field(min_length=1, max_length=32,
        description="Exact reference IDs resolved by trusted source-scope preparation; not model-created evidence.")
    inspect: list[str] = Field(min_length=1, max_length=24,
        description="Rows, headers, units, periods and footnotes to inspect; no precomputed financial answer.")

    @model_validator(mode="after")
    def bounded_read(self):
        if self.selection.operation != "read" or not self.selection.document_id:
            raise ValueError("required_source_check_needs_original_read")
        if len(set(self.required_source_ids)) != len(self.required_source_ids):
            raise ValueError("required_source_check_duplicate_reference")
        return self


SOURCE_CHECK_GUIDANCE = (
    "The required_source_checks are mandatory inspection scope, not optional suggestions or financial answers. "
    "Use their exact read selections and inspect ALL listed rows, table headers, periods, units and footnotes. "
    "Outline/search previews do not complete a required read. Tool failure means execution incomplete, not "
    "issuer non-disclosure. Runtime checks successful observed reference IDs before accepting submission. "
    "For EACH exact criterion, task_note.coverage must state completed and locate the affected claims/fields, "
    "or stop with an honest incomplete task note. Read coverage is not proof of understanding. State the "
    "actual findings and remaining limits. Keep 'not yet inspected', 'not found within inspected scope', "
    "'not disclosed by the issuer' and 'disclosed but insufficient for causal attribution' distinct. "
    "General knowledge only proposes hypotheses and next checks; it cannot establish what this document "
    "contains. If original information contradicts your prior draft or Lead, explicitly correct ALL affected "
    "prose, counterevidence, claims and open gaps, retaining unaffected work. Do not repeat a corrected "
    "absence claim under a different heading. Summaries are not citable originals."
)


def source_check_progress(checks, notebook):
    observed = {r["ref_id"] for o in notebook.get("observations", []) if o.get("status") == "success"
        for r in o.get("references", []) if r.get("writer_citable") and r.get("authority_state") == "source_bound_passage"}
    return [{**c, "missing_source_ids": sorted(set(c["required_source_ids"]) - observed),
        "read_status": "observed_not_semantically_verified" if set(c["required_source_ids"]).issubset(observed) else "required_read_pending"}
        for c in checks]


def source_check_errors(checks, notebook, action):
    errors=[]
    note=action.task_note
    coverage=note.coverage if note else []
    for check in source_check_progress(checks, notebook):
        if check["missing_source_ids"]:
            errors.append("required_source_read_missing:" + check["criterion"] + ":" + ",".join(check["missing_source_ids"]))
        assessments=[c for c in coverage if c.criterion == check["criterion"]]
        if len(assessments)!=1 or assessments[0].status!="completed" or not (assessments[0].claim_ids or assessments[0].fields):
            errors.append("required_source_check_assessment_missing:" + check["criterion"])
    return errors
