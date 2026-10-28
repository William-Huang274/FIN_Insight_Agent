"""Query-only financial navigation concepts; never amounts or answer labels.

Variants broaden retrieval, not financial equivalence. No company-specific
rules, model calls, date inference or index mutation. Legacy needs stay intact.
"""
import re
from .text import tokenize

POLICY = 'organization-financial-needs.v2'
TERM_GROUPS = {
    'earnings_release': [['earnings','results','业绩'], ['release','announced','announcing','announcement','发布','公告']],
    'cash_equivalents': [['cash','现金'],['equivalents','等价物']],
    'restricted_cash': [['cash','现金'],['restricted','受限']],
    'equity_commitments': [['equity','股权'],['commitment','commitments','承诺']],
    'investment_capacity': [['investment','投资'],['support','supports','capacity','支持','容量']],
    'capital_expenditures': [['capital','资本'],['expenditure','expenditures','支出']],
    'repurchase_authorization': [['repurchase','repurchases','repurchasing','buyback','buybacks','回购'],
                                ['authorization','authorizations','authorized','remaining','授权','剩余']],
    'debt_maturity': [['debt','notes','note','bonds','bond','debentures','loan','loans','债务','债券','借款','转债'],
                      ['maturity','maturities','mature','matures','matured','到期']],
}
# Each tuple is a distinct evidence need, not a bag of interchangeable facts.
EXTENDED_CONCEPTS = (
    ('revenue', r'收入|营收|\brevenues?\b|\bnet sales\b', 'revenue revenues sales 收入 营收'),
    ('operating_income', r'营业利润|经营利润|\boperating (?:income|profit)\b', 'operating income profit 营业利润 经营利润'),
    ('net_income', r'净利润|净收益|\bnet (?:income|earnings|profit)\b', 'net income earnings profit 净利润 净收益'),
    ('gross_margin', r'毛利率|\bgross margin\b', 'gross margin 毛利率'),
    ('accounts_receivable', r'应收账款|\baccounts receivable\b', 'accounts receivable 应收账款'),
    ('inventory', r'存货|\binventor(?:y|ies)\b', 'inventory inventories 存货'),
)
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


def concepts(text, *, extended=True):
    vocabulary = (*EXTENDED_CONCEPTS, *CONCEPTS) if extended else CONCEPTS
    found = [(name, words, m.start()) for name, pattern, words in vocabulary
             if (m := re.search(pattern, text, re.I))]
    if re.search(r'到期|\bexpir(?:e|es|ed|ation)\b|\bmatur(?:ity|ities|e|es|ed)\b', text, re.I):
        if any(n == 'repurchase_authorization' for n, _, _ in found):
            found.append(('authorization_expiration', 'expire expires expired expiration 到期', 0))
        elif re.search(r'债务|债券|借款|(?:可转换|可转|转)债|\b(?:debt|notes?|bonds?|debentures?|loans?)\b', text, re.I):
            found.append(('debt_maturity',
                          'debt notes note bonds bond debentures loan loans maturity maturities mature matures matured 债务 债券 借款 转债 到期', 0))
        # Unknown meaning is left to the literal route, never guessed.
    return found


def compile_financial_needs(query, plan, legacy):
    positive = query
    exclusions = []
    if plan.get('policy') == 'conservative.v5':
        from .query_requirements import positive_view
        positive, exclusions = positive_view(query)
    extended = plan.get('policy') == 'conservative.v5'
    found = concepts(positive, extended=extended)
    if plan.get('policy') == 'conservative.v5':
        from .evidence_scope import plan_scope
        scope = plan_scope(positive)
        if scope and scope.get('event_type') == ['earnings_release']:
            # An explicit earnings announcement needs its event topic, not
            # just shared press-release/date/exhibit boilerplate. Preserve
            # the literal route as well; this is allocation, not a hard gate.
            found.append(('earnings_release',
                'earnings results release announced announcing announcement 业绩 发布 公告', 0))
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
            local = concepts(query[mention['end']:end], extended=extended)
            if len(mention['issuer_ids']) == 1 and local:
                per_owner.setdefault(mention['issuer_ids'][0], []).extend(local)
    scoped = all(o and o.get('issuer_id') in per_owner for o in owners)
    literal_clauses = {}
    if plan.get('policy') == 'conservative.v5' and len(owners) > 1:
        from .query_requirements import owner_clauses
        literal_clauses = owner_clauses(positive, mentions)
        scoped = all(o and o.get('issuer_id') in literal_clauses for o in owners)
    needs = []
    context_requests=[]
    for owner in owners:
        clause = ' '.join(literal_clauses[owner['issuer_id']]) if scoped and literal_clauses else None
        choices = concepts(clause, extended=extended) if clause is not None else per_owner[owner['issuer_id']] if scoped else found
        if clause is not None and not choices:
            # Preserve an unknown owner's full topic as its own literal need.
            # It cannot inherit a different owner's recognized financial fact.
            from .organization_search_needs import lexical_surfaces
            routes, translations = lexical_surfaces(clause)
            needs.append({'id':f'need-{len(needs)+1}', 'text':clause, 'owner':owner,
                'query_clause':clause,
                'concept':None, 'lexical_routes':routes, 'translations':translations,
                'interpretation':'unrecognized_owner_topic_preserved_literal'})
            continue
        seen = set()
        for name, terms, _ in choices:
            if name in seen:
                continue
            seen.add(name)
            primary = list(dict.fromkeys(tokenize(terms)))
            needs.append({'id':f'need-{len(needs)+1}', 'text':query, 'owner':owner,
                **({'query_clause':clause} if clause is not None else {}),
                'concept':name, 'concept_terms':primary,
                'term_groups':TERM_GROUPS.get(name, [primary]),
                'lexical_routes':[primary, list(dict.fromkeys(tokenize(query)))], 'translations':[],
                'period_state':'requires_original_fact_date_or_table_column_verification'})
        if extended:
            # A recognized measure must not erase an independent unknown
            # topic. Split only explicit conjunctions outside known phrases
            # ("cash and cash equivalents" is one concept, not two clauses).
            text = clause if clause is not None else positive
            if clause is None:
                chars = list(text)
                for mention in mentions:
                    chars[mention['start']:mention['end']] = ' ' * (mention['end']-mention['start'])
                text = ''.join(chars)
            spans = [(m.start(), m.end()) for _, pattern, _ in (*EXTENDED_CONCEPTS, *CONCEPTS)
                     for m in re.finditer(pattern, text, re.I)]
            cuts = [m for m in re.finditer(r'\band\b|\bas well as\b|以及|同时|并且', text, re.I)
                    if not any(a <= m.start() < b for a, b in spans)]
            start = 0
            for end, after in [*( (m.start(), m.end()) for m in cuts), (len(text), len(text))]:
                topic = text[start:end].strip(' ,;，；。.')
                topic = re.sub(r'^(?:compare|comparison of|find|retrieve|show|比较|对比|找出)\s*', '', topic, flags=re.I).strip()
                start = after
                if not cuts or not topic or concepts(topic):
                    continue
                from .fact_period_matching import DATE, FY
                nonperiod=FY.sub('',DATE.sub('',topic))
                if not re.search(r'[A-Za-z\u3400-\u9fff]',nonperiod):
                    continue
                from .query_context_requirements import context_requirements,is_assertion_context
                if is_assertion_context(topic,query):
                    context_requests.append({'text':topic,'roles':['assertion_to_verify'],'owner':owner})
                    continue
                if context:=context_requirements(topic):
                    context_requests.append({'text':topic,'roles':context,'owner':owner})
                    continue
                from .organization_search_needs import lexical_surfaces
                routes, translations = lexical_surfaces(topic)
                if routes:
                    needs.append({'id':f'need-{len(needs)+1}', 'text':topic, 'owner':owner,
                        **({'query_clause':clause} if clause is not None else {}),
                        'concept':None, 'lexical_routes':routes, 'translations':translations,
                        'interpretation':'unrecognized_conjoined_topic_preserved_literal'})
    if len(needs) > 32:
        raise ValueError('organization_financial_needs_exceed_32')
    return {**legacy, 'policy':POLICY, 'needs':needs,
        'financial_concepts':sorted({n['concept'] for n in needs if n.get('concept')}),
        'excluded_requirements':exclusions,
        'context_requirements':context_requests,
        'decomposition':'explicit_owner_financial_concepts' if scoped else 'financial_concepts',
        'coverage_semantics':'candidate_routes_not_answer_sufficiency',
        'translation_scope':'versioned_financial_navigation_variants_not_fact_equivalence'}
