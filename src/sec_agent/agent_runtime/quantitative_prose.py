"""Advisory readback for changed quantitative prose. Never alter a manuscript or a receipt."""
import json
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from .source_references import HANDLE, REFERENCE_TOKEN, reference_handle
from .source_result_view import _calculation_basis

# Split prose, retaining a decimal point inside a number.
SPLIT = re.compile(r'(?<=[。！？!?])|(?<=\.)\s+(?=[A-Z])|\n+')
NUM = r'(?<![\d.])(-?\d[\d,]*(?:\.\d+)?)'
AMOUNT = re.compile(r'(?:\$\s*)?' + NUM + r'\s*(billion|million|bn(?![A-Za-z])|万亿|亿|百万|万)(?:\s*(?:美元|美金))?', re.I)
YEAR = re.compile(r"(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])")
PERCENT = re.compile(NUM + r'\s*[%％]')
# An explicit definition followed by a two-symbol subtraction. Symbols may
# already denote rates; report the unexpressed transform, never infer their units.
RATE_WORD = r'(?:增长率|增速|同比增幅)'
SYMBOL = r'[A-Za-z][A-Za-z0-9_]*(?:-[A-Za-z][A-Za-z0-9_]*)*'
RATE_DIFFERENCE = re.compile(RATE_WORD + r'\s*(?:减去|减|[−－-])\s*[^。！？；，,()（）\n]{1,45}?' +
    RATE_WORD + r'\s*[（(]\s*(' + SYMBOL + r')\s*([−－]|\s-\s)\s*(' + SYMBOL + r')\s*[）)]')


def metric_definition_checks(text):
    findings = []
    for match in RATE_DIFFERENCE.finditer(text):
        if all(re.search(r'growth|yoy|qoq|cagr', term, re.I) for term in (match[1], match[3])):
            continue
        findings.append({'kind':'rate_difference_notation', 'excerpt':match[0],
            'operands':[match[1], match[3]],
            'action':'文字比较两项增长率，括号直接相减。若符号表示原指标，请写出两个增速及比较期间，结果以百分点表示；若符号已定义为增长率，请核对该定义。'})
    return findings
SCALE = dict(billion=10**9, million=10**6, bn=10**9, 万亿=10**12, 亿=10**8, 百万=10**6, 万=10**4)
HYPOTHESIS = re.compile(r'假设|即使|若将|若把|如果|assuming|if allocated|even if|hypothetical',re.I)
ADJUST = re.compile(r'剔除|扣除|扣掉|减去|excluding|subtract|net of',re.I)
# Use an explicit non-allocation statement by the writer, not an industry/entity dictionary.
LIMIT = re.compile(r'(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9&.-]{1,30})\s*(?:分部|业务|部门)?\s*(?:单独|单列|单项|独立|精确|专属|具体|拆分)[^。；;，,\n]{0,20}?(?:未披露|未知|未给出|无法确定|不详)',re.I)

def sentences(text):
    # Citations after a Chinese full stop belong to the preceding sentence.
    text = re.sub(r'([。！？])((?:\[(?:REF-[\da-f]+|CALC::[^\]]+)\])+)', r'\2\1', text)
    return [s.strip() for s in SPLIT.split(text) if s.strip()]

def sentence_edits(before, after):
    old, new = sentences(before), sentences(after)
    for op, i, j, start, end in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if op == 'equal':
            continue
        # Only a one-to-one replacement has an unambiguous sentence predecessor.
        previous = old[i] if op == 'replace' and j - i == end - start == 1 else None
        for sentence in new[start:end]:
            yield previous, sentence


def saved_note_wording(messages):
    """Only committed note text from this authorised business history; never treat it as evidence."""
    from langchain_core.messages import ToolMessage

    calls = {}
    versions = {}
    for message in messages:
        for call in getattr(message, 'tool_calls', ()):
            if call.get('name') == 'WriteWorkingNote':
                original = message.additional_kwargs.get('original_tool_arguments')
                calls[call['id']] = original if isinstance(original, dict) and len(message.tool_calls) == 1 else call.get('args', {})
        if not isinstance(message, ToolMessage) or message.name != 'WriteWorkingNote' or message.status != 'success':
            continue
        args = calls.pop(message.tool_call_id, {})
        body = args.get('body')
        if not isinstance(body, str):
            continue
        receipt = message.content
        if isinstance(receipt, str):
            try:
                receipt = json.loads(receipt)
            except ValueError:
                continue
        if not isinstance(receipt, dict) or receipt.get('saved') is not True:
            continue
        note_id, version = receipt.get('note_id'), receipt.get('version')
        if not note_id or type(version) is not int:
            continue
        prior_version, prior_body = versions.get(note_id, (None, ''))
        if args.get('mode') == 'append' and prior_version == version - 1:
            body = prior_body + '\n' + body
        versions[note_id] = (version, body)
    return '\n'.join(body for _, body in versions.values())


def cited_claim_context(edits, previous_text, sources):
    """Present attributable evidence, never infer the author’s intended denominator or allocation."""
    from collections import defaultdict
    def identifiers(sentence):
        for token in re.findall(REFERENCE_TOKEN, sentence):
            if HANDLE.fullmatch(token):
                yield token
            elif token in sources:
                yield reference_handle(token)

    cited = {ref for _, sentence in edits for ref in identifiers(sentence)}
    if not cited:
        return []
    observed = {}
    for key, row in sources.items():
        if isinstance(key, str) and isinstance(row, dict):
            ref = reference_handle(key)
            if ref in cited:
                observed[ref] = (key, row)
    history = defaultdict(list)
    for sentence in sentences(previous_text):
        for ref in set(identifiers(sentence)) & cited:
            history[ref].append(sentence)
    checks = []
    displayed = set()
    for previous, sentence in edits:
        evidence = []
        for ref in dict.fromkeys(identifiers(sentence)):
            if ref not in observed:
                continue
            key, row = observed[ref]
            if ref in displayed:
                evidence.append({'receipt':ref})
                continue
            if key.startswith('CALC::') and row.get('arithmetic_verified') is True:
                entry = {k:row.get(k) for k in ('expression','value_decimal','result_unit','rationale')}
                if str(entry['result_unit']).lower() in {'ratio', 'fraction', '比例'}:
                    try:
                        fraction = Decimal(str(entry['value_decimal']))
                        if fraction.is_finite():
                            entry['percent_of_specified_denominator'] = str(fraction * 100)
                    except InvalidOperation:
                        pass
                entry['inputs'] = {k:{field:v.get(field) for field in ('value_decimal','source_id')}
                                   for k,v in (row.get('operands') or {}).items() if isinstance(v, dict)}
            elif (row.get('result_state') == 'source_bound_passage' and row.get('writer_citable') is True
                  and isinstance(row.get('passage'), str)):
                entry = {'excerpt': row['passage'][:450], 'excerpt_truncated': len(row['passage']) > 450}
            else:
                continue
            entry.update(receipt=ref, readback={'tool':'read_research_source','arguments':{'source_id':key}})
            evidence.append(entry)
            displayed.add(ref)
        if evidence:
            # Prior statements are fallible context, not an additional source.
            prior = [previous] if previous else []
            for entry in evidence:
                prior.extend(history[entry['receipt']][-2:])
            checks.append({'sentence':sentence, 'earlier_statements':list(dict.fromkeys(prior)),
                           'evidence':evidence})
    return checks


def amounts(text):
    return {Decimal(m[1].replace(',','')) * SCALE[m[2].lower()] for m in AMOUNT.finditer(text)}


# Recognize explicit naming, rather than any co-occurrence of money and a rate.
RATE_LABEL = re.compile(r'(?:利润率|毛利率|收益率|回报率|margin)\s*(?:为|是|达|约为|of|=|:)\s*[约$]?\s*([-+]?\d+(?:\.\d+)?)\s*(美分|美元|元|cents?\b|dollars?\b)', re.I)
BACK_REFERENCE = re.compile(r'(?:后者|该差额|这一差额)[^。；，]{0,12}(?:称为|称作|叫作)[“「"]?[^。；，]{0,22}(?:利润率|毛利率|收益率|回报率)')
GROUP_CLAIM = re.compile(r'(?:[两二三四五六七八九十\d]+家|各家|多家|所有公司|这些公司)[^。；，]{0,18}(?:方向一致|均(?:有|已|实现|增长|下降|改善|上升|下滑)|都(?:增长|改善|下降))')
MONEY_UNIT = re.compile(r'^(?:cents?|dollars?|usd|cny|rmb|美分|美元|元)(?:$|\s*(?:per\b|/|每))', re.I)


def bound_claim_checks(text, active, sources):
    """Resolve only citations in this version. Nearby wording is context, not proof."""
    def bound_refs(line):
        tokens = (k if HANDLE.fullmatch(k) else reference_handle(k) for k in re.findall(REFERENCE_TOKEN, line))
        return list(dict.fromkeys(k for k in tokens if k in sources))

    checks, summaries, observations = [], [], {}
    for paragraph in text.splitlines():
        previous = ''
        for line in sentences(paragraph):
            refs = bound_refs(line)
            for key in refs:
                src = sources[key]
                if not src.get('writer_citable') or not src.get('passage'):
                    continue
                observations.setdefault(key, {'statements_in_answer':[], 'receipt':key,
                    **{k:src[k] for k in ('title','publication_date','period','metric','entity','disclosure_type')
                       if src.get(k)}, 'readback':{'tool':'read_research_source','arguments':{'source_id':key}}})
                if line not in observations[key]['statements_in_answer']:
                    observations[key]['statements_in_answer'].append(line)
            if line in active:
                if GROUP_CLAIM.search(line):
                    summaries.append(line)
                label = RATE_LABEL.search(line)
                indirect = BACK_REFERENCE.search(line)
                if label or indirect:
                    anchors = refs if label else bound_refs(previous)
                    amounts_bound = []
                    for key in anchors:
                        src = sources.get(key, {})
                        if src.get('arithmetic_verified') is not True or not MONEY_UNIT.match(str(src.get('result_unit',''))):
                            continue
                        if label:
                            try:
                                if Decimal(str(src.get('value_decimal'))) != Decimal(label[1]):
                                    continue
                            except InvalidOperation:
                                continue
                        amounts_bound.append({'receipt':key, **{k:src.get(k) for k in ('expression','value_decimal','result_unit')}})
                    if amounts_bound:
                        checks.append({'kind':'verify_metric_name' if label else 'resolve_metric_referent',
                            'sentence':line, 'calculation_sentence':line if label else previous,
                            'calculations':amounts_bound,
                            'action':'核对名称指向哪项计算；金额或单位金额与利润率的分母不同。另有百分比或公司定义时可回读并保留。'})
            previous = line
    if summaries:
        checks.append({'kind':'compare_group_claims','statements':summaries,
            'cited_observations':list(observations.values()),
            'action':'按汇总句所指的指标比较各公司、期间、比较基数和实绩或指引。披露日不等于指标期间。可比时保留明确判断；不同口径也可作为分别标明的线索。'})
    return checks

def ratio_cards(sources):
    cards = []
    for key, row in sources.items():
        if not isinstance(key, str) or not key.startswith('CALC::') or not isinstance(row, dict) or row.get('arithmetic_verified') is not True:
            continue
        if str(row.get('result_unit','')).lower() not in {'ratio','fraction','比例'}:
            continue
        ratios = _calculation_basis(dict(row)).get('formula_basis',{}).get('ratios',[])
        if len(ratios)!=1:
            continue
        operands = row.get('operands',{})
        numerator = ratios[0]['numerator']['operand_keys']
        if len(numerator)!=1 or not all(isinstance(operand, dict) for operand in operands.values()):
            continue
        op = operands[numerator[0]]
        literal = str(op.get('literal') or op.get('value_decimal') or '')
        try:
            number = Decimal(literal.replace(',',''))
            value = Decimal(str(row['value_decimal'])) * 100
        except (InvalidOperation, KeyError):
            continue
        anchors={Decimal(m[1].replace(',','')) * SCALE[m[2].lower()]
                 for m in AMOUNT.finditer(op.get('quote') or '') if Decimal(m[1].replace(',',''))==number}
        if len(anchors)!=1:
            continue
        cards.append((value,anchors.pop(),{'receipt':reference_handle(key),'expression':row['expression'],
                 'numerator':ratios[0]['numerator']['expression'],'denominator':ratios[0]['denominator']['expression'],
                 'result_percent':str(value),'operand':literal, 'quote':op.get('quote',''),
                 'denominator_inputs':[{k:operands[name].get(k) for k in ('literal','value_decimal','source_id')}
                                       for name in ratios[0]['denominator']['operand_keys']],
                 'purpose':row.get('rationale','')}))
    return cards

def audit_changes(before, after, sources, *, context='', earlier_notes=''):
    cards = ratio_cards(sources)
    restrictions = [(m[1],line) for line in sentences(context+'\n'+after) for m in LIMIT.finditer(line)]
    findings=[]
    linked = {}
    edits = list(sentence_edits(before, after))
    findings.extend(bound_claim_checks(after, {s for _, s in edits},
        {reference_handle(k):v for k,v in sources.items() if isinstance(k,str) and isinstance(v,dict)}))
    for _, s in edits:
        findings.extend(metric_definition_checks(s))
        if not re.search(r"\d", HANDLE.sub("", s)):
            continue
        values=amounts(s); rates=list(PERCENT.finditer(s)); matches=[]
        # One amount presented alongside several percentages is ambiguous when their
        # uniquely matching stored ratios used different amounts. Don't label it false.
        if len(rates)>=2:
            for m in rates:
                value=Decimal(m[1].replace(',','')); tolerance=Decimal(1).scaleb(value.as_tuple().exponent)/2
                hits=[(a,card) for v,a,card in cards if abs(v-value)<=tolerance]
                cited=[h for h in hits if h[1]['receipt'] in s]
                hits=cited or hits
                if len(hits)==1: matches.extend(hits)
            if len(matches) >= 2:
                linked.update((card["receipt"],card) for _,card in matches)
            expected = {a for a,_ in matches}
            if len(expected)>1 and len(expected & values)==1:
                findings.append({'kind':'different_numerators','sentence':s,'basis':[card for _,card in matches],
                    'action':'Check which amount the reader would use for each percentage; name both numerators if needed.'})
        if values and ADJUST.search(s) and not HYPOTHESIS.search(s):
            basis = [card for _, a, card in cards if a in values]
            target_years = set(YEAR.findall(s))
            if len(target_years) == 1:
                other_periods = [card for card in basis if len(set(YEAR.findall(card['purpose'] or ''))) == 1
                                 and target_years.isdisjoint(YEAR.findall(card['purpose'] or ''))]
                if other_periods:
                    findings.append({'kind':'check_period_of_adjustment','sentence':s,'basis':other_periods,
                        'action':'The period stated in this calculation differs from the proposed adjustment. Check the timing or identify the scenario.'})
            for subject,line in restrictions:
                if subject in s and line!=s and any(a in values for _,a,_ in cards):
                    findings.append({'kind':'allocation_basis_needed','sentence':s,'scope_statement':line,
                        'basis':[card for _,a,card in cards if a in values][:3],
                        'action':'Does the cited amount apply to this subject and period? Identify an allocation, retain the broader scope, or state the scenario.'})
                    break
    return {'status':'advisory','findings':findings, 'linked_ratio_bases':list(linked.values()),
            'cited_claim_context':cited_claim_context(edits, '\n'.join((before, context, earlier_notes)), sources)}


def quantitative_prose_tool(prior_answer, review_context=None):
    from langchain_core.tools import tool
    from langgraph.prebuilt import ToolRuntime
    from .conversation_agent import GrantedTool
    from .conversation_tools import calculator_observations

    @tool
    def check_quantitative_changes(runtime: ToolRuntime, text: str | None = None,
                                   edits: list[dict[str, str]] | None = None):
        """Compare proposed changed quantitative sentences and scope statements with saved CALC receipts.
        Supply affected prose for change checks. Omit text to inspect metric names and group claims
        in the last delivered answer with their bound receipts before revising it.
        For a reviewed answer, supply the full proposed text to preview related wording, including unchanged
        conclusions, alongside the reviewer's observations. Alternatively pass edits (unique before/after
        spans against the selected answer) to preview without copying unchanged text. No changes are saved."""
        messages = runtime.state.get('messages', [])
        context = review_context() if review_context else None
        base, opinion = context or (prior_answer, '')
        if edits is not None:
            from .answer_review import apply_response
            if text is not None:
                raise ValueError('supply_either_edits_or_text')
            # A pending read from an earlier bridge may contain expanded source IDs.
            # Use only the original arguments archived against this exact call.
            last = messages[-1] if messages else None
            call_id = getattr(runtime, 'tool_call_id', None)
            if call_id and any(c['id'] == call_id and c['name'] == 'check_quantitative_changes'
                               for c in getattr(last, 'tool_calls', [])):
                edits = last.additional_kwargs.get('original_tool_arguments', {}).get('edits', edits)
            try:
                text, _ = apply_response(base, json.dumps({'reason':'preview','edits':edits}))
            except ValueError as exc:
                return {'status':'proposal_needs_correction', 'detail':str(exc)[:500],
                        'anchor_counts':[base.count(e['before']) if e.get('before') else 0 for e in edits],
                        'changed':False}
        if text is None:
            sources = calculator_observations(messages)
            result = {'status':'advisory','findings':bound_claim_checks(base, set(sentences(base)),
                    {reference_handle(k):v for k,v in sources.items() if isinstance(k,str) and isinstance(v,dict)})}
        else:
            result = audit_changes(base, text, calculator_observations(messages), earlier_notes=saved_note_wording(messages))
        if opinion:
            from .revision_context import related_wording
            result['related_wording'] = related_wording(base, text if text is not None else base, opinion)
        return result

    return GrantedTool(check_quantitative_changes, 'read', '已观察计算与局部修订措辞核对')
