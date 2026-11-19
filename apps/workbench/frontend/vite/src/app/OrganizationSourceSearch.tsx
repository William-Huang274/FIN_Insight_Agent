import {useEffect, useState} from 'react';
import {assetRequest} from '../api/assetWorkspace';

type Hit = {node_id: string; title: string; preview: string; readback: Record<string, unknown>};
type Hits = {items: Hit[]; total_matches: number; next_offset: number | null};
type Passage = {passage: string; next_readback?: Record<string, unknown>};

export function OrganizationSourceSearch({project, draft, execution}: {project: string; draft: string; execution: string}) {
  const [enabled, setEnabled] = useState(false);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('bm25');
  const [hits, setHits] = useState<Hits | null>(null);
  const [passage, setPassage] = useState<Passage | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const path = `asset-workspace/organization-projects/${project}/research-drafts/${draft}/executions/${execution}/navigate`;
  useEffect(() => {
    let current = true;
    assetRequest<{source_search?: boolean}>('organization-research-capabilities')
      .then(value => {if (current) setEnabled(!!value.source_search);})
      .catch(() => {if (current) setEnabled(false);});
    return () => {current = false;};
  }, []);
  function clearResults() {
    setHits(null);
    setPassage(null);
    setError('');
  }
  async function search(offset = 0) {
    if (busy || !query.trim()) return;
    clearResults();
    setBusy(true);
    try {
      const result = await assetRequest<Hits>(path, 'POST', {source_space: 'organization', operation: 'search',
        organization_retrieval_mode: mode, query: query.trim(), offset});
      setHits(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {setBusy(false);}
  }
  async function read(body: Record<string, unknown>) {
    setBusy(true);
    setError('');
    setPassage(null);
    try {
      const result = await assetRequest<{items: Passage[]}>(path, 'POST', body);
      setPassage(result.items[0] ?? null);
    } catch (e) {
      setHits(null);
      setError((e as Error).message);
    } finally {setBusy(false);}
  }
  if (!enabled) return null;
  return <section aria-label="检索本次研究资料">
    <h4>检索本次研究资料</h4>
    <form className="pw-toolbar" onSubmit={e => {e.preventDefault(); void search();}}>
      <label>检索方式<select value={mode} disabled={busy} onChange={e => {setMode(e.target.value); clearResults();}}>
        <option value="bm25">关键词 BM25 · 本地免费</option><option value="hybrid">混合检索 · 可能产生服务商费用</option>
      </select></label>
      <label>关键词<input type="search" maxLength={600} value={query} disabled={busy}
        onChange={e => {setQuery(e.target.value); clearResults();}} /></label>
      <button disabled={busy || !query.trim()}>搜索资料</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {hits && <><p role="status">共 {hits.total_matches} 个匹配片段</p>
      <ul>{hits.items.map(item => <li key={item.node_id}><strong>{item.title}</strong><p>{item.preview}</p>
        <button disabled={busy} onClick={() => void read({...item.readback, character_offset: 0, max_characters: 4000})}>读取原文</button></li>)}</ul>
      {hits.next_offset !== null && <button disabled={busy} onClick={() => void search(hits.next_offset!)}>下一页匹配</button>}</>}
    {passage && <section aria-label="原文片段"><p>{passage.passage}</p>
      {passage.next_readback && <button disabled={busy} onClick={() => void read(passage.next_readback!)}>继续阅读</button>}</section>}
  </section>;
}
