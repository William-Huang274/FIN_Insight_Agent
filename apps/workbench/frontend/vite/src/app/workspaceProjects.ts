import { useEffect, useRef, useState } from "react";
import { browserOwner } from './IdentityBoundary';

export type WorkspaceProject = {id:string;name:string;description?:string;archived?:boolean};
export type ProjectIndex = { projects: WorkspaceProject[]; assignments: Record<string, string>; pinned: string[] };
type SavedIndex = ProjectIndex & { revision: number };
const storageKey = () => browserOwner === 'local-pilot' ? 'finsight.project-index.v1' : `finsight.project-index.v1:${browserOwner}`;
const empty: ProjectIndex = { projects: [], assignments: {}, pinned: [] };
export function useWorkspaceProjects() {
  const [index, setIndex] = useState<SavedIndex>({...empty, revision:0});
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false); const inFlight=useRef(false);
  const [legacy] = useState<ProjectIndex | null>(() => {
    try { const value=JSON.parse(localStorage.getItem(storageKey()) || 'null'); return value?.projects?.length && value.assignments && Array.isArray(value.pinned) ? value : null; } catch { return null; }
  });
  const [error, setError] = useState("");
  const reload = async () => {
    setError('');
    try { const response=await fetch('/api/v1/projects'); const body=await response.json();
      if (!response.ok || !Number.isInteger(body.revision) || !Array.isArray(body.projects)) throw new Error('无法读取服务端项目，请重试。');
      setIndex(current=>body.revision>=current.revision?body:current); setReady(true); return true;
    } catch (e) { setError((e as Error).message); return false; }
  };
  useEffect(() => { void reload(); }, []);
  const update = async (next: ProjectIndex) => {
    if (!ready || inFlight.current) return false;
    inFlight.current=true; setSaving(true); setError('');
    try { const response=await fetch('/api/v1/projects',{method:'PUT',headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},body:JSON.stringify({...next,revision:index.revision})});
      const body=await response.json();
      if (!response.ok) { if(response.status===409) await reload(); throw new Error(typeof body.detail==='string' ? body.detail : '项目保存失败，请检查名称和研究归属。'); }
      setIndex(current=>body.revision>=current.revision?body:current); return true;
    } catch (e) { setError((e as Error).message+' 未自动重试，请重新载入确认保存结果。'); return false; }
    finally { inFlight.current=false; setSaving(false); }
  };
  return { index, error, update, ready, saving, reload, legacy: index.revision===0 ? legacy : null };
}
