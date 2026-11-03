"""Original non-display evidence; no stylesheet or responsive-layout guesses."""
import re
from lxml import html


def hidden_display(style):
    # Split declarations respecting quoted strings and parenthesized values.
    # Unknown/unbalanced syntax provides no visibility proof.
    declarations=[];part=[];quote=None;depth=0;escape=False
    for c in style:
        if escape:part.append(c);escape=False;continue
        if c=='\\':part.append(c);escape=True;continue
        if quote:
            part.append(c)
            if c==quote:quote=None
            continue
        if c in {'"',"'"}:quote=c;part.append(c);continue
        if c=='(':depth+=1
        elif c==')':depth-=1
        if depth<0:return False
        if c==';' and depth==0:declarations.append(''.join(part));part=[]
        else:part.append(c)
    if quote or depth or '/*' in style or '*/' in style:return False
    declarations.append(''.join(part));values=[]
    for declaration in declarations:
        name,colon,value=declaration.partition(':')
        if colon and name.strip().casefold()=='display':
            important=bool(re.search(r'!\s*important\s*$',value,re.I))
            clean=re.sub(r'!\s*important\s*$','',value,flags=re.I).strip().casefold()
            values.append((important,clean))
    if not values:return False
    important=[v for p,v in values if p]
    return (important[-1] if important else values[-1][1])=='none'


def _maps(raw,requested_paths=None):
    try:
        raw.decode('utf-8-sig');dom=html.fromstring(raw,parser=html.HTMLParser(encoding='utf-8',no_network=True))
    except UnicodeDecodeError:dom=html.fromstring(raw,parser=html.HTMLParser(no_network=True))
    tree=dom.getroottree();states={};result={};containers={}
    for element in dom.iter():
        if not isinstance(element.tag,str):continue
        inherited=states.get(element.getparent());reason=None
        tag=element.tag.casefold()
        if tag=='ix:hidden' and any('inlineXBRL' in (a.get('xmlns:ix') or '') for a in (element,*element.iterancestors())):
            reason='inline_xbrl_hidden'
        elif 'hidden' in element.attrib:reason='html_hidden_attribute'
        elif hidden_display(element.get('style') or ''):reason='inline_display_none'
        if inherited is not None:state=inherited
        elif reason:state=dict(basis=reason,ancestor_xpath=tree.getpath(element))
        else:state=None
        states[element]=state
        path=tree.getpath(element)
        if state:result[path]=state
        if requested_paths is not None and path in requested_paths:
            containers[path]=dict(text=' '.join(''.join(element.itertext()).split()),visibility=state)
    return result,containers


def visibility_map(raw):
    return _maps(raw)[0]


def container_evidence(raw,paths):
    return _maps(raw,set(paths))[1]
