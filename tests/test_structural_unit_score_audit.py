"""Saved-score diagnostics must never confuse evidence identity with rank."""
from hashlib import sha256
import json
import sqlite3
import zlib

import pytest
from scripts.engineering.audit_structural_unit_scores import audit


def setup_run(tmp_path):
    catalog = tmp_path / 'catalog.sqlite'
    run = tmp_path / 'run'; run.mkdir()
    judgments = tmp_path / 'judgments'; judgments.mkdir()
    content = '[/TABLE]'; context = 'Company quarterly filing'
    digest = sha256(content.encode()).hexdigest()
    input_digest = sha256((context+'\n'+content).encode()).hexdigest()
    unit = dict(unit_id='marker', parent_node_id='bad', content=content,
                embedding_context=context, embedding_input_sha256=input_digest,
                source_interval=[10, 18])
    with sqlite3.connect(catalog) as db:
        db.execute('CREATE TABLE units(id,parent,digest,input_digest,payload)')
        db.execute('INSERT INTO units VALUES(?,?,?,?,?)',
                   ('marker', 'bad', digest, input_digest, zlib.compress(json.dumps(unit).encode())))
    trace = run / 'trace.jsonl'
    rows = [dict(node_id='marker', parent_node_id='bad', source_interval=[10,18], score=.99),
            dict(node_id='signature', parent_node_id='bad', source_interval=[18,30], score=.5),
            dict(node_id='answer', parent_node_id='good', source_interval=[0,10], score=.9)]
    trace.write_text('\n'.join(map(json.dumps, rows)), encoding='utf8')
    query = 'cash balance'
    job = dict(query=query, retrieval_receipt={'full_dense_units_artifact':{
        'file': trace.name, 'sha256': sha256(trace.read_bytes()).hexdigest()}},
        candidates=[dict(node_id='bad', content_sha256='a'*64)])
    (run / 'q.input.json').write_text(json.dumps(job), encoding='utf8')
    (run / 'result.json').write_text(json.dumps({'samples':[{'id':'q','selected_ids':['bad','good']}]}), encoding='utf8')
    labels = [dict(question_id='q', query_sha256=sha256(query.encode()).hexdigest(),
                   node_id='bad', content_sha256='a'*64, grade=0)]
    (judgments / 'q.json').write_text(json.dumps(labels), encoding='utf8')
    return catalog, run, judgments


def test_saved_scores_have_explicit_non_quality_scope(tmp_path):
    result = audit(*setup_run(tmp_path))
    assert result['provider_calls'] == 0
    assert result['scope'] == 'saved_dense_scores_only_not_new_candidates_or_final_quality'
    assert result['counts']['selected_grade_0'] == 1
    change = result['queries'][0]['changed_parents'][0]
    assert (change['before_dense_rank'], change['after_dense_rank']) == (1, 2)
    assert (change['before_score'], change['after_score']) == (.99, .5)


def test_trace_tamper_is_not_a_new_experiment(tmp_path):
    paths = setup_run(tmp_path)
    with (paths[1] / 'trace.jsonl').open('a') as stream: stream.write('\n')
    with pytest.raises(ValueError, match='trace_changed'): audit(*paths)


def test_question_and_content_labels_must_match(tmp_path):
    paths = setup_run(tmp_path); target = paths[2] / 'q.json'
    rows = json.loads(target.read_text()); rows[0]['content_sha256'] = 'b'*64
    target.write_text(json.dumps(rows))
    result = audit(*paths)
    assert result['counts']['selected_grade_None'] == 1
    assert result['queries'][0]['changed_parents'][0]['grade'] is None
    rows[0]['query_sha256'] = 'c'*64; target.write_text(json.dumps(rows))
    with pytest.raises(ValueError, match='judgment_question_changed'): audit(*paths)
