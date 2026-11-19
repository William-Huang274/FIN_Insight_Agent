import {useEffect, useRef, useState} from 'react';

type Activity = {id: string; label: string; text: string};
type Props = {base: string; run?: string | null; busy: boolean; verifyAccess: () => Promise<boolean>};
const toolStates: Record<string, string> = {
  pending: '等待执行', in_progress: '执行中', completed: '已完成', failed: '执行失败',
};

function activity(value: Record<string, unknown>, eventId: string): Activity | null {
  if (!value || !['stage', 'tool', 'task', 'model'].includes(String(value.kind))) return null;
  const id = typeof value.call_id === 'string' && ['assistant_message', 'tool_activity'].includes(String(value.event))
    ? value.call_id : eventId || crypto.randomUUID();
  if (value.event === 'assistant_message' && typeof value.objective === 'string')
    return {id, label: '研究助手', text: value.objective};
  if (value.event === 'tool_activity' && typeof value.status === 'string' && toolStates[value.status])
    return {id, label: typeof value.tool === 'string' ? value.tool : '研究工具', text: toolStates[value.status]};
  const text = typeof value.objective === 'string' ? value.objective : value.event;
  return typeof text === 'string' ? {id, label: typeof value.actor === 'string' ? value.actor : '运行', text} : null;
}

export function OrganizationResearchEvents({base, run, busy, verifyAccess}: Props) {
  const [events, setEvents] = useState<Activity[]>([]);
  const [status, setStatus] = useState('');
  const [revision, refresh] = useState(0);
  const [expanded, setExpanded] = useState(busy);
  const list = useRef<HTMLOListElement>(null);
  const follow = useRef(true);
  useEffect(() => {
    if (expanded && follow.current && list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [events, expanded]);
  const verify = useRef(verifyAccess);
  verify.current = verifyAccess;
  useEffect(() => {
    setEvents([]);
    if (!run) return;
    let alive = true;
    const stream = new EventSource(`/api/v1/${base}/runs/${run}/events`);
    setStatus('正在读取');
    const append = (raw: MessageEvent, history: boolean) => {
      if (!alive) return;
      try {
        const value = JSON.parse(raw.data);
        const items = history ? value : [value];
        if (!Array.isArray(items)) return;
        const additions = items.map(item => activity(item, raw.lastEventId)).filter((row): row is Activity => !!row);
        setEvents(rows => [...new Map([...rows, ...additions].map(row => [row.id, row])).values()].slice(-80));
      } catch { /* Ignore malformed transport frames. */ }
    };
    stream.addEventListener('history', e => append(e as MessageEvent, true));
    stream.addEventListener('custom', e => append(e as MessageEvent, false));
    stream.onopen = () => alive && setStatus('已连接');
    async function recheck() {
      const allowed = await verify.current().catch(() => false);
      if (alive && !allowed) {
        alive = false;
        stream.close();
        setEvents([]);
        setStatus('读取权限已变化');
      }
      return allowed;
    }
    stream.onerror = async () => {
      stream.close();
      if (!alive) return;
      setStatus('正在核对读取权限');
      if (await recheck() && alive) setStatus('连接已结束');
    };
    const onFocus = () => { void recheck(); };
    window.addEventListener('focus', onFocus);
    return () => {
      alive = false;
      stream.close();
      window.removeEventListener('focus', onFocus);
    };
  }, [base, run, revision]);
  if (!run) return null;
  return <details className="org-events" open={expanded} onToggle={e => setExpanded(e.currentTarget.open)}>
    <summary>运行动态 <span>{status}</span></summary>
    {events.length > 0 ? <ol ref={list} onScroll={e => {
      const element = e.currentTarget;
      follow.current = element.scrollHeight - element.clientHeight - element.scrollTop < 32;
    }}>{events.map(row => <li key={row.id}><strong>{row.label}</strong>
      <div style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{row.text}</div></li>)}</ol>
      : <p className="pw-muted">暂无可显示的公开动态。</p>}
    <button onClick={() => refresh(n => n + 1)}>重新读取动态</button>
  </details>;
}
