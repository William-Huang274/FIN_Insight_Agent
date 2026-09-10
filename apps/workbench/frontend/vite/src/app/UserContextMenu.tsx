import { useRef, useState, type ReactNode } from 'react';
import { Settings2, X, Save } from 'lucide-react';
import './working-notes.css';

export function UserContextMenu({endpoint,children}:{endpoint:string;children?:ReactNode}) {
  const dialog=useRef<HTMLDialogElement>(null);
  const [body,setBody]=useState(''),[original,setOriginal]=useState(''),[version,setVersion]=useState(0);
  const [busy,setBusy]=useState(false),[ready,setReady]=useState(false),[notice,setNotice]=useState('');
  const dirty=body!==original;
  async function open(){
    dialog.current?.showModal();setBusy(true);setReady(false);setNotice('');
    try{const r=await fetch(endpoint);if(!r.ok)throw new Error('研究要求暂时无法读取');const value=await r.json();
      setBody(value.body||'');setOriginal(value.body||'');setVersion(value.version||0);setReady(!!value.enabled);
      if(!value.enabled)setNotice('本部署尚未启用持久记忆。');
    }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  function close(){if(dirty){setNotice('修改尚未保存，请先保存或放弃修改。');return;}dialog.current?.close();}
  async function save(){
    setBusy(true);setNotice('');
    try{const r=await fetch(endpoint,{method:'PUT',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({body,version})});const value=await r.json();
      if(!r.ok)throw new Error(typeof value.detail==='string'?value.detail:'保存失败');setVersion(value.version);setOriginal(body);setNotice(value.notice);
    }catch(e){setNotice((e as Error).message);}finally{setBusy(false);}
  }
  return <><button className="fs-context-menu-button" onClick={()=>void open()}><Settings2 size={16}/>研究设置与记忆</button>
    <dialog ref={dialog} className="fs-working-notes fs-context-editor" aria-label="研究设置与记忆" onCancel={e=>{if(dirty){e.preventDefault();close();}}} onClick={e=>{if(e.target===dialog.current)close();}}>
      <header><div><h2>我的研究要求</h2><p>直接编辑研究范围、排除事项、表达偏好和下一步安排。</p></div><button aria-label="关闭研究设置" onClick={close}><X size={20}/></button></header>
      <label className="fs-context-field">当前要求<textarea aria-label="我的研究要求" maxLength={6000} disabled={!ready||busy} value={body} onChange={e=>setBody(e.target.value)} placeholder="例如：只比较完整财年；保留原始币种；暂不进行估值；等待我补充附注后再研究现金流原因。"/></label>
      <p>保存后由后续运行读取，不自动启动模型。这里的观点或假设不会变成已核验事实；不会改动历史回答、来源和工具权限。</p>
      <div className="fs-context-actions"><button disabled={!ready||busy||!dirty} onClick={()=>void save()}><Save size={16}/>保存要求</button><button disabled={busy||!dirty} onClick={()=>{setBody(original);setNotice('已放弃未保存修改。');}}>放弃修改</button><small>已保存版本 {version} · {body.length}/6000</small></div>
      {notice&&<p role="status">{notice}</p>}
      {children&&<details className="fs-context-records"><summary>查看只读记录与用量</summary>{children}</details>}
    </dialog></>;
}
