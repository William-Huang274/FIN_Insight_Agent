import {submissionFetch} from './submissionFetch';

/** Wire contract: Python AssetRef / AssetContextRequest in OpenAPI is authoritative. */
export type AssetRef={project_id:string;kind:'document'|'sec';asset_id:string;version_id:string;digest:string};
export type AssetVersion={ref:AssetRef;title:string;sequence:number;created_at:string;status:string;access_status:string;role:'document'|'report'|'database'};
export type Asset={asset_id:string;kind:AssetRef['kind'];versions:AssetVersion[];current:AssetVersion};
export type AssetProfile={version:number;body:string};
export type AssetContext={schema_version:'asset_context.v1';context_id:string;question:string;refs:AssetRef[];titles:string[];memory:AssetProfile;created_at:string;source_status?:{ref:AssetRef;status:string}[]};
export async function assetRequest<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const response=await submissionFetch(`/api/v1/${path}`,{method,headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const result=await response.json();
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`操作未完成 (${response.status})，请检查输入与版本`);
  return result;
}
