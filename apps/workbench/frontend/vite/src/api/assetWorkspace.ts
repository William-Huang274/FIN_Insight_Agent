import {submissionFetch} from './submissionFetch';

/** Wire contract: Python AssetRef / AssetContextRequest in OpenAPI is authoritative. */
export type AssetRef={project_id:string;kind:'document'|'sec';asset_id:string;version_id:string;digest:string};
export type CapturedFinancialRow={selection_id:string;ticker:string;metric_id:string;value_decimal:string;unit:string;period_start:string;period_end:string;fiscal_year:number;fiscal_period:string;filed_at:string;citation_url:string;form?:string};
export type SourceCapture={kind:'library'|'financial';snapshot_digest:string;origin?:{document_id:string;stable_url:string;title:string};query?:Record<string,unknown>;section_ids?:string[];selected_count?:number;matching_count?:number;note?:string;rows?:CapturedFinancialRow[]};
export type AssetVersion={ref:AssetRef;title:string;sequence:number;created_at:string;status:string;access_status:string;role:'document'|'report'|'database';capture?:SourceCapture};
export type Asset={asset_id:string;kind:AssetRef['kind'];versions:AssetVersion[];current:AssetVersion};
export type AssetProfile={version:number;body:string};
export type AssetContext={schema_version:'asset_context.v1';context_id:string;question:string;refs:AssetRef[];titles:string[];memory:AssetProfile;created_at:string;source_status?:{ref:AssetRef;status:string}[]};
export async function assetRequest<T>(path:string,method='GET',body?:unknown):Promise<T>{
  const response=await submissionFetch(`/api/v1/${path}`,{method,headers:{'Content-Type':'application/json','X-Workbench-Request':'1'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const result=await response.json();
  if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:`操作未完成 (${response.status})，请检查输入与版本`);
  return result;
}
