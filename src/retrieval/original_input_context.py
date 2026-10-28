"""Document identity for scoring, separate from inherited neighboring text.

Legacy embedding_context can include a preceding table row. It is an archived
model input, not proof that the row belongs to every new retrieval unit.
"""
import re

POLICY='document-identity-only.v1'


def document_context(row):
    title=row.get('title') or ''
    if not isinstance(title,str):raise ValueError('original_context_title_invalid')
    title=' '.join(title.split())
    title=re.sub(r'\.md$', '',title,flags=re.I)
    locator=(row.get('original_source') or {}).get('locator') or ''
    if not isinstance(locator,str):raise ValueError('original_context_locator_invalid')
    # Generated source locators have a closed grammar. Never copy a free-text
    # section heading, table cell or arbitrary preview as document identity.
    match=re.fullmatch(r'(text-part:\d+)(?: / chars \d+:\d+)?',locator)
    # Capture adapters sanitize filesystem-forbidden punctuation in filenames.
    # Preserve an existing *identity-only* input when that reversible naming
    # difference is the only change. No third line or arbitrary locator passes.
    old=row.get('embedding_context','')
    lines=old.split('\n') if isinstance(old,str) else []
    title_key=lambda value:' '.join(re.sub(r'[<>:"/\\|?*]',' ',value).split())
    if (title and lines and title_key(lines[0])==title_key(title)
            and (len(lines)==1 and not match or len(lines)==2 and match and lines[1]==match[1])):
        return old
    return '\n'.join(v for v in (title,match[1] if match else '') if v)
