"""Development-only, manually declared query constraints; no answer-ID routing."""
from hashlib import sha256
import json

from sec_agent.research_foundation.organization_source_filter import (
    OrganizationSourceFilter, original_source_metadata, source_metadata_details, select_documents,
)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation


def validate_plan(plan, rows):
    if (set(plan) != {'role', 'queries'} or plan['role'] != 'development_query_only_manual_constraints'
            or any(row['split'] != 'development' for row in rows)
            or set(plan['queries']) != {row['id'] for row in rows}):
        raise ValueError('filter_diagnosis_requires_explicit_development_plan')
    for row in rows:
        entry = plan['queries'][row['id']]
        if (set(entry) != {'query_sha256', 'variants'} or entry['query_sha256'] != sha256(row['query'].encode()).hexdigest()
                or not 0 < len(entry['variants']) <= 5):
            raise ValueError('filter_plan_query_changed_or_invalid_variants')
        names = set()
        for variant in entry['variants']:
            if (set(variant) != {'name', 'constraint', 'basis', 'unresolved'}
                    or not variant['name'] or variant['name'] in names or not variant['basis']
                    or not isinstance(variant['unresolved'], list)):
                raise ValueError('filter_plan_variant_invalid')
            OrganizationSourceFilter.model_validate(variant['constraint'])
            names.add(variant['name'])
    return plan['queries']


def metadata_maps(root, intake, publication, manifest, guard):
    """Verify every source file, retaining descriptors/spans, not corpus bodies."""
    documents = {item['resource_id']: OrganizationSourceNavigation._identity(item) for item in manifest['inputs']}
    raw, resolved, proofs = {}, {}, []
    for number, item in enumerate(intake['sources']):
        path = (root/item['directory']/'source.json').resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError('filter_audit_source_path_outside_intake')
        content = path.read_bytes()
        if sha256(content).hexdigest() != item['files']['source.json']:
            raise ValueError('filter_audit_source_changed')
        bundle = json.loads(content)
        if bundle['source']['id'] != item['source_id']:
            raise ValueError('filter_audit_source_identity_changed')
        document = documents[publication['resources'][item['source_id']]]
        raw[document] = original_source_metadata(bundle)
        resolved[document], proof = source_metadata_details(bundle)
        if proof:
            proofs.append({'document': document, **proof})
        del content, bundle
        if (number+1) % 200 == 0:
            guard('source_metadata:'+str(number+1))
    return raw, resolved, proofs


def scope_records(records, metadata, constraint):
    documents, receipt = select_documents(metadata, OrganizationSourceFilter.model_validate(constraint))
    return [r for r in records if r['document_id'] in documents], receipt
