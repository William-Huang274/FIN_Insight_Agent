import React, { useEffect, useState } from 'react';
import './identity.css';

type Identity = { mode: string; authenticated: boolean; browser_login: boolean; owner: string | null };
export let browserOwner = 'local-pilot';

export function IdentityBoundary({ children }: { children: React.ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const response = await fetch('/auth/status', { cache: 'no-store' });
        if (!response.ok) throw new Error('身份服务暂时不可用，请刷新重试。');
        const value: Identity = await response.json();
        if (active) {
          browserOwner = value.mode === 'local' ? 'local-pilot' : value.owner || 'signed-out';
          setIdentity(value); setError('');
        }
      } catch (e) { if (active) { setIdentity(null); setError(String(e)); } }
    };
    void check();
    const timer = setInterval(check, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  if (!identity) return <main className="identity-entry"><h1>FinSight</h1><p role="status">{error || '正在连接工作区…'}</p></main>;
  if (!identity.authenticated) return <main className="identity-entry">
    <h1>登录研究工作区</h1><p>登录后查看你的研究、底稿和报告。</p>
    {identity.browser_login ? <a href="/auth/login">安全登录</a> : <p>当前部署尚未配置浏览器登录，请联系管理员。</p>}
  </main>;
  return <React.Fragment key={browserOwner}>{identity.mode !== 'local' && <button className="identity-signout" onClick={async () => {
    const response = await fetch('/auth/logout', { method: 'POST', headers: { 'X-Workbench-Request': '1' } });
    if (response.ok) location.reload(); else setError('退出未完成，请重试。');
  }}>退出工作区</button>}{children}{error && <p role="alert">{error}</p>}</React.Fragment>;
}
