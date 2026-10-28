"""Server-owned evidence relevance task, separate from a user's question.

The instruction contains no company, source ID, target answer or score cutoff.
Selection is explicit until independently evaluated with the serving pipeline.
"""
POLICY = 'financial-evidence.v1'
TEXT = (
    'Judge whether the passage itself provides evidence answering a requested part of the question, '
    'not merely whether it discusses the same company or repeats the same terms. Respect any specified filing, '
    'reporting entity, asset ownership, measure and fact date. A comparative column can answer a historical '
    'date when the question does not require a particular filing. Group cash and cash equivalents are not '
    'restricted cash, fund assets, pension assets, a subsidiary balance, cash flows, or cash plus investments. '
    'For announcement questions, the passage must connect the requested event to its release date, reporting '
    'period or exhibit; signatures, certification exhibits and generic press release language are insufficient. '
    'For a claim-checking question, evidence refuting the claim is relevant; matching its stated number is not '
    'enough. Verified table headers, units and footnotes provide context only for their own table. '
    'Partial but direct evidence is relevant; a table of contents or topic-only discussion is not an answer.'
)


def configured_instruction(model):
    import os
    policy = os.getenv('FINSIGHT_ORGANIZATION_RERANK_INSTRUCTION', '')
    if not policy:
        return None
    if policy != POLICY or model != 'qwen3.7-text-rerank':
        raise ValueError('organization_rerank_instruction_configuration_invalid')
    return TEXT
