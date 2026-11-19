"""One reader-facing style source for model-bound chat and report writing."""
from hashlib import sha256
from importlib.resources import files


def reader_writing_profile():
    content = files('sec_agent.research_foundation').joinpath(
        'methods_judgment', 'writer.md').read_text(encoding='utf-8')
    text = content.split('\n## 共同写作原则\n', 1)[1].split('\n## ', 1)[0].strip()
    return {'id': 'reader_argument_v1', 'text': text,
            'digest': sha256(text.encode()).hexdigest()}


def reader_writing_guidance():
    profile = reader_writing_profile()
    return '\n[Writing profile: ' + profile['id'] + ']\n' + profile['text'] + '\n'
