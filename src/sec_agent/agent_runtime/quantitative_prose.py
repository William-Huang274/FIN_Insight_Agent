"""Advisory readback for changed quantitative prose. Never alter a manuscript or a receipt."""
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from .source_references import HANDLE, reference_handle
from .source_result_view import _calculation_basis

# Split prose, retaining a decimal point inside a number.
SPLIT = re.compile(r'(?<=[。！？!?])|(?<=\.)\s+(?=[A-Z])|\n+')
NUM = r'(?<![\d.])(-?\d[\d,]*(?:\.\d+)?)'
AMOUNT = re.compile(r'(?:\$\s*)?' + NUM + r'\s*(billion|million|bn(?![A-Za-z])|万亿|亿|百万|万)(?:\s*(?:美元|美金))?', re.I)
YEAR = re.compile(r"(?<![0-9])(?:19|20)[0-9]{2}(?![0-9])")
PERCENT = re.compile(NUM + r'\s*[%％]')
SCALE = dict(billion=10**9, million=10**6, bn=10**9, 万亿=10**12, 亿=10**8, 百万=10**6, 万=10**4)
HYPOTHESIS = re.compile(r'假设|即使|若将|若把|如果|assuming|if allocated|even if|hypothetical',re.I)
ADJUST = re.compile(r'剔除|扣除|扣掉|减去|excluding|subtract|net of',re.I)
# Use an explicit non-allocation statement by the writer, not an industry/entity dictionary.
LIMIT = re.compile(r'(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9&.-]{1,30})\s*(?:分部|业务|部门)?\s*(?:单独|单列|单项|独立|精确|专属|具体|拆分)[^。；;，,\n]{0,20}?(?:未披露|未知|未给出|无法确定|不详)',re.I)

def sentences(text):
    # Citations after a Chinese full stop belong to the preceding sentence.
    text = re.sub(r'([。！？])((?:\[(?:REF-[\da-f]+|CALC::[^\]]+)\])+)', r'\2\1', text)
    return [s.strip() for s in SPLIT.split(text) if s.strip()]

def changed_sentences(before, after):
    old, new = sentences(before), sentences(after)
    return [s for op, _, _, start, end in SequenceMatcher(None,old,new,autojunk=False).get_opcodes()
            if op != 'equal' for s in new[start:end] if re.search(r'\d', HANDLE.sub('',s))]

def amounts(text):
    return {Decimal(m[1].replace(',','')) * SCALE[m[2].lower()] for m in AMOUNT.finditer(text)}

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

def audit_changes(before, after, sources, *, context=''):
    cards = ratio_cards(sources)
    restrictions = [(m[1],line) for line in sentences(context+'\n'+after) for m in LIMIT.finditer(line)]
    findings=[]
    linked = {}
    for s in changed_sentences(before,after):
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
    return {'status':'advisory','findings':findings, 'linked_ratio_bases':list(linked.values())}


def quantitative_prose_tool(prior_answer):
    from langchain_core.tools import tool
    from langgraph.prebuilt import ToolRuntime
    from .conversation_agent import GrantedTool
    from .conversation_tools import calculator_observations

    @tool
    def check_quantitative_changes(text: str, runtime: ToolRuntime):
        """Compare proposed changed quantitative sentences and scope statements with saved CALC receipts.
        Supply only affected prose, including related limits or scenarios; returns advisory evidence for the author."""
        return audit_changes(prior_answer, text, calculator_observations(runtime.state.get('messages', [])))

    return GrantedTool(check_quantitative_changes, 'read', '已观察计算与局部修订措辞核对')
