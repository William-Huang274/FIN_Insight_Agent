"""Lossless writer-facing organization; selection and financial meaning stay with the author."""

EDITORIAL_BRIEF = (
    '沿着提纲里的读者问题写。保存一节前，重读开头，看看读者何时才能说出你的判断和理由。'
    '试着拿掉一段分类、一个案例或一组数字：如果会丢掉关键推导、会改变选择的反证，或让判断无从检验，就保留它；'
    '如果一句话已能讲清，就用这一句。读完末段，回看本节的读者问题。'
    '找出最后一句仍会改变答案、支撑理由或适用条件的话，在那里收住。随后引出的其他问题交给对应章节。 '
    'Reuse the lead decision and its accepted scope; check originals for new claims or quantities. Saved chapters are '
    'reference versions whose structure can change. Apply the shared writing profile to the '
    'report body as well as chat. No required edit percentage or prohibited words. Update the outline to the '
    'sections actually used (remove_sections keeps underlying judgments and archived chapters), '
    'then save the requested artifact; final report binding covers the complete adopted outline. '
    'For a local workset, retain the report map and edit only the selected chapters and necessary links. '
    'If a judgment changes, update its affected sections. This is authoring, not independent review '
    'or permission for new research.'
)


def writing_judgments(judgments):
    """Move exact fields, never summarize, delete qualifications or reinterpret their importance."""
    return {
        'judgments': {key: {f: value[f] for f in ('statement', 'rationale', 'status') if f in value}
                      for key, value in judgments.items()},
        'decision_conditions': {key: {f: value[f] for f in ('conditions', 'counterevidence') if f in value}
                                for key, value in judgments.items()},
        'open_questions': {key: value.get('decision_uncertainty', value['remaining'])
                           for key, value in judgments.items() if 'remaining' in value},
        'reading_contract': 'These are exact saved research fields, organized by use, not report copy. '
            'Select and explain their implications in your own argument. Conditions and counterevidence '
            'remain part of the judgment. Full records and historical process are available through '
            'read_authoring_context(include_history=true).',
    }
