"""Separate captured display state from source-content purpose.

An HTML hidden attribute is not proof that content is machine metadata.
Standard controls and the maintained UIkit accordion contract provide positive
disclosure evidence. Unknown hidden content stays intact and reviewable.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import re
from urllib.parse import urlsplit

from lxml import html

from source_visibility import visibility_map


def normalized(text):
    return ' '.join(text.split())


def _classes(element):
    return set((element.get('class') or '').split())


def purposes(raw):
    visibility = visibility_map(raw)
    try:
        raw.decode('utf-8-sig')
        root = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8', no_network=True))
    except UnicodeDecodeError:
        root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    tree = root.getroottree(); paths = {}; ids = defaultdict(list); controls = defaultdict(list)
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        paths[tree.getpath(element)] = element
        if element.get('id'):
            ids[element.get('id')].append(element)
        if element.tag in {'button', 'a'} or element.get('role') == 'button':
            if element.get('aria-expanded') in {'true', 'false'}:
                for target in (element.get('aria-controls') or '').split():
                    controls[target].append(element)

    def purpose(element, display):
        ancestry = (element, *element.iterancestors())
        for ancestor in ancestry:
            if (ancestor.tag == 'ix:hidden'
                and any('inlineXBRL' in (p.get('xmlns:ix') or '') for p in (ancestor, *ancestor.iterancestors()))):
                return dict(purpose='inline_xbrl_metadata', basis='declared_inline_xbrl_hidden_container',
                            original_container=tree.getpath(ancestor), candidate_policy='structured_metadata_only')
        for ancestor in ancestry:
            if (ancestor.tag in {'ix:nonnumeric', 'ix:nonfraction', 'ix:fraction'}
                and ancestor.get('name') and ancestor.get('contextref')
                and any('inlineXBRL' in (p.get('xmlns:ix') or '') for p in (ancestor, *ancestor.iterancestors()))):
                return dict(purpose='inline_xbrl_fact_representation', basis='hidden_content_inside_declared_inline_fact',
                            original_container=tree.getpath(ancestor), candidate_policy='source_fact_context',
                            fact=dict(name=ancestor.get('name'), context_ref=ancestor.get('contextref'), id=ancestor.get('id'),
                                      escape=ancestor.get('escape')), financial_semantics_inferred=False)
        for ancestor in ancestry:
            if ancestor.tag == 'nav' or ancestor.get('role') in {'navigation', 'menu', 'menubar'}:
                return dict(purpose='interactive_navigation', basis='original_navigation_element_or_role',
                            original_container=tree.getpath(ancestor), candidate_policy='retained_navigation')
        for ancestor in ancestry:
            identifier = ancestor.get('id')
            if identifier and len(ids[identifier]) == 1 and len(controls[identifier]) == 1:
                return dict(purpose='interactive_disclosure', basis='unique_original_aria_control_target',
                            original_container=tree.getpath(ancestor),
                            original_controller=tree.getpath(controls[identifier][0]), candidate_policy='body_content')
            if 'uk-accordion-content' in _classes(ancestor):
                item = ancestor.getparent(); group = item.getparent() if item is not None else None
                if group is not None and ('uk-accordion' in group.attrib or 'data-uk-accordion' in group.attrib):
                    titles = [e for e in item if isinstance(e.tag, str) and e.tag == 'a'
                              and 'uk-accordion-title' in _classes(e) and normalized(''.join(e.itertext()))]
                    panels = [e for e in item if isinstance(e.tag, str) and 'uk-accordion-content' in _classes(e)]
                    if len(titles) == len(panels) == 1:
                        return dict(purpose='interactive_disclosure', basis='uikit_original_accordion_structure',
                                    original_container=tree.getpath(ancestor),
                                    original_controller=tree.getpath(titles[0]), candidate_policy='body_content')
            if ('uk-navbar-dropdown' in _classes(ancestor)
                and ('uk-navbar' in ancestor.attrib or 'data-uk-navbar' in ancestor.attrib)
                and ancestor.xpath('.//a[@href]')):
                return dict(purpose='interactive_navigation', basis='uikit_original_navbar_dropdown',
                            original_container=tree.getpath(ancestor), candidate_policy='retained_navigation')
        hidden = paths[display['ancestor_xpath']]
        media = []
        for modal in hidden.xpath('.//*[@data-video-embed-field-modal]'):
            encoded = modal.get('data-video-embed-field-modal')
            if not encoded or len(encoded) > 100000:
                continue
            try:
                fragment = html.fragment_fromstring(encoded, create_parent='source-fragment', parser=html.HTMLParser(no_network=True))
            except (ValueError, html.etree.ParserError):
                continue
            for frame in fragment.xpath('.//iframe'):
                url = frame.get('src') or frame.get('data-src')
                try:
                    valid = bool(url and urlsplit(url).scheme in {'http', 'https'} and urlsplit(url).netloc)
                except ValueError:
                    valid = False
                if valid:
                    media.append(dict(modal_xpath=tree.getpath(modal), iframe_url=url))
        if media:
            return dict(purpose='embedded_media_caption', basis='original_encoded_video_modal_with_external_iframe',
                        original_container=tree.getpath(hidden), candidate_policy='media_caption_context',
                        media=media, transcript_available=False)
        if display['basis'] == 'inline_display_none' and re.fullmatch(r'\d{1,5}', normalized(''.join(hidden.itertext()))):
            parent = hidden.getparent()
            if parent is not None:
                breaks = [e for e in parent if e is not hidden and isinstance(e.tag, str)
                          and re.search(r'(?:^|;)\s*(?:break-after\s*:\s*page|page-break-after\s*:\s*always)\s*(?:;|$)',
                                        e.get('style') or '', re.I)
                          and not normalized(''.join(e.itertext())) and e.xpath('.//hr')]
                if breaks:
                    return dict(purpose='layout_page_marker', basis='hidden_number_and_sibling_page_break_rule',
                                original_container=tree.getpath(hidden),
                                original_page_break=tree.getpath(breaks[0]), candidate_policy='retained_structure')
        return dict(purpose='undetermined_hidden_content', basis='display_state_does_not_establish_purpose',
                    original_container=display['ancestor_xpath'], candidate_policy='retained_pending_purpose_review')

    return {path: dict(display_state='hidden_at_capture', display=display,
                      within_navigation=bool(paths[path].xpath('ancestor-or-self::nav|ancestor-or-self::aside|ancestor-or-self::footer|ancestor-or-self::script|ancestor-or-self::style|ancestor-or-self::*[@role="navigation" or @role="menu" or @role="menubar"]')),
                      **purpose(paths[path], display))
            for path, display in visibility.items() if path in paths}


def repair(document, raw):
    if sha256(raw).hexdigest() != document['source_sha256']:
        raise ValueError('source_display_identity_changed')
    if document.get('source_display_purpose_repairs'):
        return document, []
    evidence = purposes(raw); changes = []
    for source in document.get('source_containers', []):
        path = source['id'].split(':', 1)[-1]
        if path in evidence:
            changes.append(dict(source_id=source['id'], evidence=evidence[path],
                prior={key: source.get(key) for key in ('source_visibility', 'excluded_navigation', 'source_display_purpose')},
                prior_keys=[key for key in ('source_visibility', 'excluded_navigation', 'source_display_purpose') if key in source]))
    if not changes:
        return document, []
    updated = deepcopy(document); by_id = {s['id']: s for s in updated['source_containers']}
    for change in changes:
        source = by_id[change['source_id']]; proof = change['evidence']
        source['source_visibility'] = dict(status='hidden_at_capture', **proof['display'])
        source['source_display_purpose'] = proof
        # A positive interactive-body proof corrects a prior blanket hidden
        # exclusion. Explicit navigation ancestors remain excluded below.
        if proof['candidate_policy'] == 'body_content':
            source['excluded_navigation'] = proof['within_navigation']
        else:
            source['excluded_navigation'] = True
    block_changes = []
    policies = {'structured_metadata_only': 'retained_metadata', 'retained_structure': 'retained_structure',
                'retained_navigation': 'retained_structure', 'source_fact_context': 'attached_context_candidate',
                'media_caption_context': 'attached_context_candidate',
                'retained_pending_purpose_review': 'attached_context_candidate'}
    for i, block in enumerate(updated['blocks']):
        source = by_id.get(block.get('source_container_id'), {})
        policy = source.get('source_display_purpose', {}).get('candidate_policy')
        if policy not in policies:
            continue
        block_changes.append(dict(block=i, prior_role=block.get('candidate_role'), prior_role_present='candidate_role' in block))
        block['candidate_role'] = policies[policy]
    updated['source_display_purpose_repairs'] = changes
    updated['source_display_block_repairs'] = block_changes
    return updated, changes


def verify(document, raw):
    proofs = document.get('source_display_purpose_repairs', [])
    if not proofs:
        if sha256(raw).hexdigest() != document['source_sha256']:
            raise ValueError('source_display_identity_changed')
        if any(s.get('source_display_purpose') for s in document.get('source_containers', [])):
            evidence = purposes(raw)
            for source in document['source_containers']:
                if source.get('source_display_purpose'):
                    fresh = evidence.get(source['id'].split(':', 1)[-1])
                    excluded=fresh['within_navigation'] if fresh and fresh['candidate_policy']=='body_content' else True
                    if (fresh != source['source_display_purpose'] or source.get('excluded_navigation') != excluded
                        or source.get('source_visibility') != dict(status='hidden_at_capture',**(fresh or {}).get('display',{}))):
                        raise ValueError('initial_source_display_purpose_not_reproducible')
        return
    previous = deepcopy(document); sources = {s['id']: s for s in previous['source_containers']}
    for proof in proofs:
        source = sources[proof['source_id']]
        for key in ('source_visibility', 'excluded_navigation', 'source_display_purpose'):
            if key in proof['prior_keys']:
                source[key] = proof['prior'][key]
            else:
                source.pop(key, None)
    for change in document.get('source_display_block_repairs', []):
        block = previous['blocks'][change['block']]
        if change['prior_role_present']:
            block['candidate_role'] = change['prior_role']
        else:
            block.pop('candidate_role', None)
    previous.pop('source_display_purpose_repairs', None); previous.pop('source_display_block_repairs', None)
    rebuilt, fresh = repair(previous, raw)
    if fresh != proofs or rebuilt != document:
        raise ValueError('source_display_purpose_not_reproducible')
