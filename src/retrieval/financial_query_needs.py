"""Query-only financial navigation concepts; never amounts or answer labels.

Variants broaden retrieval, not financial equivalence. No company-specific
rules, model calls, date inference or index mutation. Legacy needs stay intact.
"""
import re
from .text import tokenize

POLICY = 'organization-financial-needs.v2'
TERM_GROUPS = {
    'cash_equivalents': [['cash','现金'],['equivalents','等价物']],
    'restricted_cash': [['cash','现金'],['restricted','受限']],
    'equity_commitments': [['equity','股权'],['commitment','commitments','承诺']],
    'investment_capacity': [['investment','投资'],['support','supports','capacity','支持','容量']],
    'capital_expenditures': [['capital','资本'],['expenditure','expenditures','支出']],
    'repurchase_authorization': [['repurchase','repurchases','repurchasing','buyback','buybacks','回购'],
                                ['authorization','authorizations','authorized','remaining','授权','剩余']],
}
# Each tuple is a distinct evidence need, not a bag of interchangeable facts.
CONCEPTS = (
    ('cash_equivalents', r'现金(?:及|和|与)?现金等价物|现金等价物|\bcash(?: and cash)? equivalents\b',
     'cash equivalents 现金 现金等价物'),
    ('restricted_cash', r'受限现金|\brestricted cash\b', 'restricted cash 受限现金'),
    ('equity_commitments', r'股权.{0,8}承诺|出资承诺|\bequity (?:capital )?commitments?\b',
     'equity commitments commitment 股权 出资 承诺'),
    ('investment_capacity', r'支持.{0,18}投资|投资容量|总投资|\binvestment capacity\b|\btotal .{0,20}investment\b',
     'support supports total investment capacity 支持 总投资 投资容量'),
    ('repurchase_authorization', r'回购|\b(?:share[- ]|stock[- ])?repurchas(?:e|es|ing)\b|\bbuybacks?\b',
     'repurchase repurchases repurchasing buyback buybacks authorization authorizations authorized remaining 回购 授权 剩余 额度'),
    ('financing', r'融资|\bfinanc(?:e|ed|ing)\b|\bindebtedness\b',
     'finance financed financing indebtedness borrowings 融资 借款 债务'),
    ('capital_expenditures', r'资本支出|\bcapital expenditur(?:e|es)\b|\bcapex\b',
     'capital expenditure expenditures capex 资本支出'),
    ('operating_cash_flow', r'经营现金流|\boperating cash flow\b|\bcash (?:provided by|from) operat',
     'operating cash flow activities 经营现金流'),
)


def concepts(text):
    found = [(name, words, m.start()) for name, pattern, words in CONCEPTS
             if (m := re.search(pattern, text, re.I))]
    if re.search(r'到期|\bexpir(?:e|es|ed|ation)\b|\bmaturit(?:y|ies)\b', text, re.I):
        if any(n == 'repurchase_authorization' for n, _, _ in found):
            found.append(('authorization_expiration', 'expire expires expired expiration 到期', 0))
        elif re.search(r'债务|债券|借款|\bdebt\b|\bnotes\b|\bbonds\b', text, re.I):
            found.append(('debt_maturity', 'maturity maturities 到期', 0))
        # Unknown meaning is left to the literal route, never guessed.
    return found


def compile_financial_needs(query, plan, legacy):
    found = concepts(query)
    if not found:
        return {**legacy, 'financial_concepts': [],
                'decomposition': 'legacy_syntax_no_recognized_financial_concept'}
    constraint = plan.get('constraint', {})
    owners = constraint.get('issuer_union') or ([{k:constraint.get(k) for k in ('issuer_id','company_names')}]
        if constraint.get('issuer_id') or constraint.get('company_names') else [None])
    if len(owners) > 8:
        raise ValueError('organization_comparison_exceeds_eight_owners')
    # Bind topics to explicit owner spans only if EVERY owner has its own
    # topic-bearing span. "Alpha and Beta cash" keeps the shared topic.
    mentions = sorted(plan.get('issuer_mentions', []), key=lambda m:m['start'])
    per_owner = {}
    if len(owners) > 1:
        for i, mention in enumerate(mentions):
            end = mentions[i+1]['start'] if i+1 < len(mentions) else len(query)
            local = concepts(query[mention['end']:end])
            if len(mention['issuer_ids']) == 1 and local:
                per_owner.setdefault(mention['issuer_ids'][0], []).extend(local)
    scoped = all(o and o.get('issuer_id') in per_owner for o in owners)
    needs = []
    for owner in owners:
        choices = per_owner[owner['issuer_id']] if scoped else found
        seen = set()
        for name, terms, _ in choices:
            if name in seen:
                continue
            seen.add(name)
            primary = list(dict.fromkeys(tokenize(terms)))
            needs.append({'id':f'need-{len(needs)+1}', 'text':query, 'owner':owner,
                'concept':name, 'concept_terms':primary,
                'term_groups':TERM_GROUPS.get(name, [primary]),
                'lexical_routes':[primary, list(dict.fromkeys(tokenize(query)))], 'translations':[],
                'period_state':'requires_original_fact_date_or_table_column_verification'})
    if len(needs) > 32:
        raise ValueError('organization_financial_needs_exceed_32')
    return {**legacy, 'policy':POLICY, 'needs':needs,
        'financial_concepts':sorted({n['concept'] for n in needs}),
        'decomposition':'explicit_owner_financial_concepts' if scoped else 'financial_concepts',
        'coverage_semantics':'candidate_routes_not_answer_sufficiency',
        'translation_scope':'versioned_financial_navigation_variants_not_fact_equivalence'}
