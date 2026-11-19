import React, { useEffect, useState } from 'react';
import './identity.css';

type Identity = { mode: string; authenticated: boolean; browser_login: boolean; owner: string | null;
  display_name?:string|null;registration?:boolean;account_url?:string|null };
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
    <span className="identity-brand">FinSight</span><h1>进入研究工作区</h1><p>整理资料、开展研究，并保存你的报告与依据。</p>
    {identity.browser_login ? <a href="/auth/login">安全登录</a> : <p>当前部署尚未配置浏览器登录，请联系管理员。</p>}
    {identity.registration&&<a className="identity-secondary" href="/auth/register">创建账户</a>}
  </main>;
  async function signOut(){
    const response = await fetch('/auth/logout', { method: 'POST', headers: { 'X-Workbench-Request': '1' } });
    if (response.ok) location.reload(); else setError('退出未完成，请重试。');
  }
  if(location.pathname==='/workspace/account')return <main className="identity-account">
    <a href="/workspace/projects">← 返回项目</a>
    <header><span className="identity-brand">FinSight</span><h1>账户与权限</h1><p>{identity.display_name||'我的研究工作区'}</p></header>
    <section><h2>登录账户</h2><p>{identity.mode==='local'?'本机工作区':'已通过身份服务登录'}</p>
      {identity.owner&&<label>工作区身份标识<code>{identity.owner}</code></label>}
      {identity.account_url&&<a href={identity.account_url} target="_blank" rel="noreferrer">管理个人信息与密码 ↗</a>}
      {identity.mode!=='local'&&<button onClick={()=>void signOut()}>退出工作区</button>}
    </section>
    <section><h2>团队与资料权限</h2><p>在资料空间中创建组织、生成邀请码或加入团队，为成员分配资料访问权限。项目成员与资料空间权限分别管理。</p>
      <a href="/workspace/assets?view=files&manage=1">管理组织、邀请码与资料空间 →</a>
      <a href="/workspace/projects?scope=organization">查看组织项目 →</a>
    </section>{error&&<p role="alert">{error}</p>}
  </main>;
  return <React.Fragment key={browserOwner}>{identity.mode !== 'local'&&<a className="identity-signout" href="/workspace/account">我的账户</a>}{children}{error&&<p role="alert">{error}</p>}</React.Fragment>;
}
