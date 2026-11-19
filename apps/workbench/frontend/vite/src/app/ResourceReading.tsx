import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type {AssetVersion,SourceCapture} from '../api/assetWorkspace';
import {CapturedFinancialTable} from './SourceCapturePanel';

export function ResourceReading({reading}:{reading:{version:AssetVersion;text:string;truncated:boolean;needs_vision?:boolean;capture?:SourceCapture}}){
  return <article className="pw-card rw-reading"><h2>{reading.version.title}</h2><p>发布的固定版本 · 只读</p>{reading.capture?.rows&&<CapturedFinancialTable rows={reading.capture.rows}/>}<ReactMarkdown remarkPlugins={[remarkGfm]}>{reading.text}</ReactMarkdown>{reading.capture?.note&&<aside><h3>发布时的批注（非来源事实）</h3><p>{reading.capture.note}</p></aside>}{reading.truncated&&<p>正文超过当前阅读长度，页面只展示部分内容。</p>}{reading.needs_vision&&<p>该文件需要图像阅读，当前文本视图不能完整呈现。</p>}</article>;
}
