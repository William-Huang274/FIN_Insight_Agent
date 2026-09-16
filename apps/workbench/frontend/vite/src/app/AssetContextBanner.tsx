import type {AssetContext} from '../api/assetWorkspace';
import './asset-context.css';

export function AssetContextBanner({context}:{context?:AssetContext}) {
  if(!context)return null;
  return <aside className="aw-source-banner" aria-label="资产交接信息"><div><strong>来自资产工作区 · 已固定资料版本</strong><p>{context.titles.join('、')}</p><small>个人记忆 v{context.memory.version} · 后续资产修改不会静默覆盖当前任务输入</small></div><a href={`/workspace/assets?project=${context.refs[0].project_id}&context=${context.context_id}`}>返回资产与原问题 →</a></aside>;
}
