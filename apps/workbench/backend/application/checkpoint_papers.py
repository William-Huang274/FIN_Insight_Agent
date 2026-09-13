"""Public prose from existing research submissions; never expose notebooks/traces."""
import hashlib
import json


def checkpoint_papers(state):
    values = state.get('values', {})
    papers = [(p, '研究历史提交') for p in values.get('case_papers', [])]
    papers += [(row.get('agent_state') or {}, '未完成的候选底稿') for row in values.get('research_failed_workpapers', [])]
    result = []
    for paper, status in papers:
        attempt = paper.get('last_submission_attempt') or {}
        submission = paper.get('final_submission') or attempt.get('arguments') or attempt.get('readable_candidate') or {}
        if not isinstance(submission, dict) or not isinstance(submission.get('narrative_markdown'), str) or not submission['narrative_markdown']:
            continue
        body = submission['narrative_markdown']
        for field, label in [('claims','判断与依据'), ('counterevidence','反证'), ('what_would_change','改变判断的条件'), ('open_gaps','待核查事项')]:
            entries = submission.get(field) or []
            lines = [x.get('statement','') if isinstance(x,dict) else x for x in entries]
            if lines:
                body += '\n\n## '+label+'\n\n'+'\n\n'.join(str(x) for x in lines)
        identity = hashlib.sha256(json.dumps([paper.get('agent_id'),paper.get('task'),submission], sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        result.append({'id':'checkpoint:'+identity, 'title':submission.get('thesis') or '研究底稿',
            'actor':(paper.get('task') or {}).get('branch_id') or paper.get('agent_id') or 'specialist',
            'version':1, 'body':body, 'preview':body[:240], 'editable':False, 'origin':status,
            'found':True, 'is_current':True, 'total_characters':len(body)})
    unique = {}
    for row in result: unique.setdefault(row['id'],row)
    corrections = {}
    for decision in values.get('human_edits', []):
        for edit in decision.get('papers', []):
            body = edit['after']
            identity = hashlib.sha256(json.dumps([edit['paper_id'],decision['number'],body],ensure_ascii=False).encode()).hexdigest()
            corrections[edit['paper_id']] = {'id':'checkpoint:'+identity,
                'title':edit['title'], 'actor':edit['actor'], 'version':decision['number']+1,
                'body':body, 'preview':body[:240], 'editable':False,
                'origin':f"人工修改 {decision['number']} 次 · 已确认报告底稿",
                'found':True, 'is_current':True, 'total_characters':len(body)}
    return [*corrections.values(), *unique.values()]
