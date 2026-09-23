export type BusinessCommand = {status: 'ready'|'unknown'|'received'|'rejected'; operation_id: string; result?: {run_id?:string; status?:string; detail?:string}};
export type BusinessTask = {id:string; project_id:string; title:string; question:string; submission_key:string; created_at:string;
  binding:{snapshot_ref:string; research_as_of:string}; research_options?:{execution?:{mode:string;model:string};project_materials?:{document_ids:string[]}}; thread_id?:string; prepare:BusinessCommand; start:BusinessCommand};
export async function businessRequest<T>(path:string, method='GET', body?:unknown, key?:string):Promise<T> {
  const response=await fetch(`/api/v1/business/${path}`,{method,cache:'no-store',headers:{'Content-Type':'application/json','X-Workbench-Request':'1',...(key?{'Idempotency-Key':key}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});
  const value=await response.json();
  if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'请求未完成，请重新读取原任务核对。');
  return value;
}
