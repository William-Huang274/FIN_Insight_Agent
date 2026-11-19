import {useRef,useState} from 'react';
import {assetRequest,type AssetRef} from '../api/assetWorkspace';
import {businessRequest} from '../api/businessResearch';
import {currentIntent,intentId,finishIntent,type ResourceSpace} from './ResourceWorkspace';

type Publication={id:string;space_id:string;ref:AssetRef};
function pendingPublication():Publication|null{
  const prior=currentIntent('publish');
  if(!prior)return null;
  try{
    const body=JSON.parse(prior.encoded),ref=body.ref;
    if(typeof body.space_id!=='string'||ref?.kind!=='document'||
      !['project_id','asset_id','version_id','digest'].every(k=>typeof ref[k]==='string'))return null;
    return {id:prior.id,space_id:body.space_id,ref};
  }catch{return null;}
}
function sameRef(a:AssetRef,b:AssetRef){
  return ['project_id','kind','asset_id','version_id','digest'].every(k=>a[k as keyof AssetRef]===b[k as keyof AssetRef]);
}

export function PublishAsset({assets}:{assets:{title:string;ref:AssetRef}[]}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [opened,setOpened]=useState(false),[pending,setPending]=useState<Publication|null>(pendingPublication);
  const [spaces,setSpaces]=useState<ResourceSpace[]>([]),[space,setSpace]=useState(''),[asset,setAsset]=useState('');
  const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState('');
  async function open(){
    setOpened(true);dialog.current?.showModal();setError('');setResult('');setConfirmed(false);setBusy(true);
    setPending(pendingPublication());setSpace('');setAsset(assets.length===1?assets[0].ref.version_id:'');
    try{
      const c=await businessRequest<{resource_spaces?:boolean}>('config');
      if(!c.resource_spaces)throw new Error('当前部署尚未启用组织空间；现有项目资料继续保持原权限。');
      const v=await businessRequest<{spaces:ResourceSpace[]}>('workspaces');
      setSpaces(v.spaces.filter(s=>s.can_manage));
    }catch(e){setSpaces([]);setError((e as Error).message);}finally{setBusy(false);}
  }
  function completed(value:Publication){
    finishIntent('publish',value.id);setPending(null);
    setResult(`/workspace/assets?view=all-resources&space=${encodeURIComponent(value.space_id)}&resource=${encodeURIComponent(value.id)}`);
  }
  async function send(value:Publication){
    setBusy(true);setError('');
    try{
      const reply=await assetRequest<{id:string}>('asset-workspace/spaces/publish','POST',value);
      if(reply.id!==value.id)throw new Error('发布回执与本次请求不一致，请查询原发布结果。');
      completed(value);
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function publish(){
    // Another mounted publication dialog may have left an unresolved request.
    const prior=pendingPublication();
    if(prior){setPending(prior);setError('请先核对上一次发布，再开始新的发布。');return;}
    const selected=assets.find(a=>a.ref.version_id===asset);
    if(!selected||!space||!confirmed)return;
    try{
      const body={space_id:space,ref:selected.ref},value={...body,id:intentId('publish',body)};
      setPending(value);await send(value);
    }catch(e){setError((e as Error).message);}
  }
  async function check(){
    if(!pending)return;
    setBusy(true);setError('');
    try{
      const value=await assetRequest<{resource_id:string;publication:{space_id:string;source_ref:AssetRef}}>(
        `asset-workspace/spaces/resources/${encodeURIComponent(pending.id)}`);
      if(value.resource_id!==pending.id||value.publication.space_id!==pending.space_id||
        !sameRef(value.publication.source_ref,pending.ref))throw new Error('读取到的资料与原发布版本不一致。');
      completed(pending);
    }catch(e){
      setError(`当前无法确认发布结果。资料可能尚未登记、已撤销或当前无权读取，不能据此认定发布没有发生。${(e as Error).message}`);
    }finally{setBusy(false);}
  }
  function dismiss(){
    if(!pending||!window.confirm('结束核对只清除本浏览器的待办记录，不撤销服务器可能已保存的发布。请先核对目标空间；再次发起新的发布可能产生另一条记录。'))return;
    finishIntent('publish',pending.id);setPending(null);setConfirmed(false);setError('');
  }
  const pendingTitle=pending&&assets.find(a=>sameRef(a.ref,pending.ref))?.title;
  const pendingSpace=spaces.find(s=>s.id===pending?.space_id);
  return <>
    <button type="button" disabled={!assets.length&&!pending} onClick={()=>void open()}>发布到组织空间</button>
    <dialog className="pw-dialog" ref={dialog} aria-label="发布资料到组织空间" onClose={()=>setOpened(false)}>
      {opened&&<>
        <h2>{pending?'核对上次发布':'发布固定版本'}</h2>
        <p>将所选版本保存为归组织管理的独立副本。原文件后续修改或撤销不会自动影响此发布；空间管理员可单独撤销。</p>
        {error&&<p role="alert">{error}</p>}
        {result?<p role="status">发布已保存。<a href={result}>打开空间中的资料</a></p>:pending?
          <section aria-label="待核对的发布">
            <p>上次发布尚未收到确认，已保留当时的资料版本和目标空间。请先查询结果；需要重试时会使用原请求。</p>
            <p>资料：{pendingTitle||'上次选定的固定版本（不在当前列表中）'}</p>
            <p>目标：{pendingSpace?`${pendingSpace.organization_name} / ${pendingSpace.name}`:'原目标空间（当前列表中不可见）'}</p>
            <div className="pw-toolbar">
              <button type="button" className="pw-primary" disabled={busy} onClick={()=>void check()}>查询发布结果</button>
              <button type="button" disabled={busy} onClick={()=>void send(pending)}>按原请求重试</button>
              <button type="button" disabled={busy} onClick={dismiss}>结束本次核对</button>
            </div>
          </section>:
          <form className="pw-settings" onSubmit={e=>{e.preventDefault();void publish();}}>
            <label>本页资料<select disabled={busy} required value={asset} onChange={e=>setAsset(e.target.value)}>
              <option value="">选择要发布的版本</option>{assets.filter(a=>a.ref.kind==='document').map(a=><option value={a.ref.version_id} key={a.ref.version_id}>{a.title}</option>)}
            </select></label>
            <label>目标空间<select disabled={busy} required value={space} onChange={e=>setSpace(e.target.value)}>
              <option value="">选择目标空间</option>{spaces.map(s=><option value={s.id} key={s.id}>{s.organization_name} / {s.name}{s.kind==='personal'?'（默认仅本人可见）':'（授权团队成员可见）'}</option>)}
            </select></label>
            <label className="rw-publish-confirm"><input disabled={busy} type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/><span>我确认将此版本发布到所选空间，并按该空间权限提供阅读。</span></label>
            <button className="pw-primary" disabled={busy||!asset||!space||!confirmed}>确认发布此版本</button>
          </form>}
        <button type="button" disabled={busy} onClick={()=>dialog.current?.close()}>关闭</button>
      </>}
    </dialog>
  </>;
}
