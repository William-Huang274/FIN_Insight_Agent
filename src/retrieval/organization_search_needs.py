"""Bounded query-only lexical needs, not answers or financial equivalences.

Explicit syntax and a reviewed navigation glossary supply candidate surfaces.
No labels, source IDs, known amounts, model calls or permission decisions enter
this module. Unknown language stays literal and is reported, never guessed.
"""
import re
from hashlib import sha256
import json
from .text import tokenize

POLICY = 'organization-search-needs.v1'
# Navigation translations only. For example revenue is not interchangeable
# with cash collections; commitments are not expenditures already incurred.
GLOSSARY = (
    ('资本支出', 'capital expenditures'), ('合同承诺', 'contractual commitments'),
    ('未计提', 'unaccrued'), ('同比增加', 'increase year over year'),
    ('经营现金流', 'operating cash flow'), ('自由现金流', 'free cash flow'),
    ('收入', 'revenue'), ('营业利润', 'operating income'), ('毛利率', 'gross margin'),
    ('净利润', 'net income'), ('应收账款', 'accounts receivable'), ('存货', 'inventory'),
    ('债务', 'debt'), ('租赁', 'leases'), ('到期', 'maturity'), ('利息', 'interest'),
    ('收购', 'acquisition acquired'), ('交割', 'closing close'),
    ('或有对价', 'contingent consideration'), ('支付形式', 'payment consideration'),
    ('业绩条件', 'performance conditions'), ('容量', 'capacity'),
    ('燃气', 'natural gas'), ('机组', 'generation facilities fleet'),
    ('概述', 'overview summary'), ('交易', 'transaction'),
    ('数据中心', 'data center'), ('基础设施', 'infrastructure'),
    ('扩充', 'expansion expand'), ('制造', 'manufacturing'),
    ('研发', 'research development'), ('产能', 'production capacity'),
)
STOP = set('the a an of to in on and or for from with both retrieve find preserve please '
           '请 同时 找出 分别 保留 原文 依据 如何 什么 不要 直接'.split())


def lexical_surfaces(text):
    matches = [(zh, en) for zh, en in GLOSSARY if zh in text]
    literal = list(dict.fromkeys(t for t in tokenize(text) if t not in STOP))
    # Keep proper names/periods, translate recognized financial concepts, and
    # keep a separate literal route for Chinese sources and unmapped words.
    translated = list(dict.fromkeys([t for t in literal if re.search('[a-z]', t)] +
                                   [t for _, en in matches for t in tokenize(en)]))
    routes = [translated, literal] if matches and translated else [literal]
    return [r for i,r in enumerate(routes) if r and r not in routes[:i]], matches


def compile_needs(query, plan):
    pieces = []
    explicit = re.search(r'(?:同时找出|同时查找|分别查找)(.+?)(?:和|与|以及)(.+?)(?:[，。；]|$)', query)
    if explicit is None:
        explicit = re.search(r'\bboth\s+(.+?)\s+and\s+(.+?)(?:[.;]|$)', query, re.I)
    if explicit:
        pieces = [part.strip() for part in explicit.groups()]
    owners = plan.get('constraint', {}).get('issuer_union', [])
    constraint = plan.get('constraint', {})
    # A clause can omit the subject named once in the complete question.
    # Unknown-source recall remains available through dense/general search,
    # but cannot claim to satisfy this explicitly owned coverage slot.
    inherited_owner = ({k:constraint.get(k) for k in ('issuer_id', 'company_names')}
                       if pieces and (constraint.get('issuer_id') or constraint.get('company_names')) else None)
    if len(owners) > 8:
        raise ValueError('organization_comparison_exceeds_eight_owners')
    needs = []
    for number, (text, owner) in enumerate(
            [(query, o) for o in owners] if owners else [(p, inherited_owner) for p in pieces or [query]], 1):
        routes, matches = lexical_surfaces(text)
        needs.append({'id':f'need-{number}', 'text':text, 'owner':owner,
                      'lexical_routes':routes, 'translations':matches})
    result = {'policy':POLICY, 'needs':needs, 'decomposition':
            'explicit_owner_comparison' if owners else 'explicit_both_clauses' if pieces else 'single_query',
            'preferred_report_year':plan.get('preferences', {}).get('verified_report_year'),
            'coverage_semantics':'candidate_routes_not_answer_sufficiency',
            'translation_scope':'reviewed_glossary_other_terms_remain_literal'}
    if plan.get('policy') in {'conservative.v4','conservative.v5'}:
        from .financial_query_needs import compile_financial_needs
        result = compile_financial_needs(query, plan, result)
        if plan.get('policy') == 'conservative.v5':
            for need in result['needs']:
                owner=need.get('owner')
                if owner and (identifiers:=plan.get('fact_entity_by_issuer',{}).get(owner.get('issuer_id'))):
                    need['owner']={**owner,'fact_entity_identifiers':identifiers}
            from .fact_period_matching import query_period, query_period_requirements, POLICY as PERIOD_POLICY
            result['period_policy'] = PERIOD_POLICY
            result['period_target'] = query_period(query)
            result['period_requirements'] = query_period_requirements(query)
            targets = result['period_requirements']['targets']
            if len(targets)>1:
                expanded=[]
                for need in result['needs']:
                    for target in targets:
                        expanded.append({**need,'id':f'need-{len(expanded)+1}','period_target':target})
                if len(expanded)>32:
                    raise ValueError('organization_period_needs_exceed_32')
                result['needs']=expanded
        return result
    return result


def owner_matches(metadata, owner):
    if owner is None:
        return True
    if owner.get('issuer_id') in metadata.get('same_document_issuer_ids', []):
        return True
    if metadata.get('issuer_id') and owner.get('issuer_id'):
        return metadata['issuer_id'] == owner['issuer_id']
    actual_names = {n.casefold() for n in [metadata.get('company_name'),
        *(metadata.get('verified_company_names') or [])] if n}
    return bool(actual_names & {n.casefold() for n in (owner.get('company_names') or [])})


def interleave(channels, limit=None):
    result = []
    for offset in range(max(map(len, channels), default=0)):
        for channel in channels:
            if offset < len(channel) and channel[offset] not in result:
                result.append(channel[offset])
                if limit is not None and len(result) >= limit:
                    return result
    return result


def lexical_candidates(path, records, needs, metadata, *, population_cache=None, capture_trace=False, trace_sink=None):
    from .published_lexical_index import scores_from_identities
    rankings, receipts = [], []
    for need in needs['needs']:
        scoped = [r for r in records if owner_matches(metadata.get(r['parent_document_id'], {}), need['owner'])]
        routes, traces = [], []
        for route_number, terms in enumerate(need['lexical_routes']):
            if not scoped:
                continue
            scores, overlap, _ = scores_from_identities(path,
                ((r['node_id'],r['content_sha256'],r['lexical_input_sha256']) for r in scoped),
                terms, population_cache=population_cache)
            # Bound per-route materialization; equal allocation is across
            # explicit needs, not raw scores from different languages/scopes.
            complete = None
            if route_number == 0 and need.get('term_groups'):
                complete = set(range(len(scoped)))
                for group in need['term_groups']:
                    _, group_overlap, _ = scores_from_identities(path,
                        ((r['node_id'],r['content_sha256'],r['lexical_input_sha256']) for r in scoped),
                        group, population_cache=population_cache)
                    complete.intersection_update(group_overlap)
            raw_order = sorted(overlap, key=lambda i:(-float(scores[i]), scoped[i]['node_id'])) if capture_trace else []
            ranked = sorted(overlap, key=lambda i:(
                0 if complete is None or i in complete else 1,
                -float(scores[i]), scoped[i]['node_id']))[:48]
            routes.append([scoped[i]['node_id'] for i in ranked])
            if capture_trace:
                full_receipt = trace_sink(need['id'], route_number, (
                    {'node_id':scoped[i]['node_id'], 'score':float(scores[i]), 'rank':rank+1}
                    for rank, i in enumerate(raw_order))) if trace_sink is not None else None
                traces.append({'route':route_number, 'terms':terms, 'population_count':len(scoped),
                'population_sha256':sha256(json.dumps([(r['node_id'],r['content_sha256'],
                    r['lexical_input_sha256']) for r in scoped], separators=(',', ':')).encode()).hexdigest(),
                'matched_count':len(overlap), 'trace_limit':96, 'trace_truncated':len(raw_order)>96,
                **({'full_raw_bm25_artifact':full_receipt} if full_receipt is not None else {}),
                'raw_bm25': [{'node_id':scoped[i]['node_id'], 'score':float(scores[i]), 'rank':rank+1}
                             for rank,i in enumerate(raw_order[:96])],
                'selected_before_interleave':routes[-1],
                'term_group_preference':complete is not None,
                'complete_term_group_ids':[scoped[i]['node_id'] for i in ranked if complete is not None and i in complete]})
        if needs['policy'] == 'organization-financial-needs.v2' and need.get('concept'):
            # Reserve two of three opportunities for the explicit business
            # need, one for the unchanged question (dates/unrecognized terms).
            # Allocation across NEEDS below remains equal and duplicate-free.
            merged = interleave([routes[0][::2], routes[0][1::2], *routes[1:]], 48) if routes else []
        else:
            merged = interleave(routes, 48)
        rankings.append(merged)
        receipts.append({'need_id':need['id'], 'candidate_ids':merged, 'route_ids':routes,
                         **({'route_traces':traces} if capture_trace else {})})
    return interleave(rankings, 48), receipts


def select_coverage(rows, needs, lane_receipts, metadata):
    """Protect one matching candidate per explicit need, preserve the tail.

    A route hit never proves an answer. All original candidates remain available
    and no absent fact is manufactured. Matching is on body, not title alone.
    """
    if len(needs['needs']) == 1 and (not needs.get('period_policy') or needs['period_target']['kind']=='unknown'):
        return rows, []
    chosen, receipts = [], []
    for need, lane in zip(needs['needs'], lane_receipts, strict=True):
        ranked = {n:i for i,n in enumerate(lane['candidate_ids'])}
        eligible = []
        for row in rows:
            if row['node_id'] not in ranked or not owner_matches(metadata.get(row['parent_document_id'], {}), need['owner']):
                continue
            body_terms = set(tokenize(row['content']))
            surface_terms = {t for route in need['lexical_routes'] for t in route if not t.isdigit()}
            matches = bool(body_terms & surface_terms)
            if need.get('term_groups'):
                matches = all(body_terms & set(group) for group in need['term_groups'])
            if matches:
                eligible.append(row)
        # Use the corresponding need's retrieval order, not the combined
        # question's rerank score. This avoids losing the other half of a query.
        year = needs.get('preferred_report_year')
        eligible.sort(key=lambda r:(
            0 if year and metadata.get(r['parent_document_id'], {}).get('calendar_annual_year') == year else 1,
            ranked[r['node_id']]))
        if needs['policy'] == 'organization-financial-needs.v2' and need.get('concept'):
            # Preserve the scorer's order within a financial need. Route rank
            # alone must not promote an old-period paragraph over the reranker.
            order = {r['node_id']:i for i,r in enumerate(rows)}
            eligible.sort(key=lambda r:order[r['node_id']])
        period_states = {}
        if needs.get('period_policy'):
            from .fact_period_matching import match_period
            period_states = {r['node_id']:match_period(r,need,need.get('period_target',needs['period_target'])) for r in eligible}
            # Prefer a positively associated fact. Unknown and other-period
            # fragments retain their relative order and remain in the result.
            eligible.sort(key=lambda r:period_states[r['node_id']]!='match')
        picked = eligible[0] if eligible else None
        if len(needs['needs']) == 1 and 'match' not in period_states.values():
            picked = None
        if picked:
            if picked['node_id'] not in chosen:
                chosen.append(picked['node_id'])
        receipts.append({'need_id':need['id'], 'selected_id':picked['node_id'] if picked else None,
                         'state':'candidate_selected_requires_readback' if picked else
                            'period_unresolved_order_preserved' if eligible and needs.get('period_policy') else 'uncovered'})
        if needs.get('period_policy'):
            receipts[-1]['period_matches'] = period_states
    by_id = {r['node_id']:r for r in rows}
    return [by_id[n] for n in chosen] + [r for r in rows if r['node_id'] not in chosen], receipts
