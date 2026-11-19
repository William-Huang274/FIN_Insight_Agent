"""Preserve native resume semantics at dynamically invoked graph boundaries."""


def native_subgraph_config(config):
    # LangGraph supplies checkpoint_id=None to dynamically invoked subgraphs.
    # Its replay detector tests key presence: forwarding that placeholder makes
    # a failed-step resume discard pending successful sibling writes. Omit only
    # the null placeholder; real checkpoint selections/time travel stay intact.
    return {**config, 'configurable': {k: v for k, v in config.get('configurable', {}).items()
                                      if k != 'checkpoint_id' or v is not None}}
