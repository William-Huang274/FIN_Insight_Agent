import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {remarkBoundCitations} from './remarkBoundCitations';
import {remarkReportHeadings} from './remarkReportHeadings';
import {sourceUrl,sourceHost} from './sourceUrl';
import type {Citation, Source} from '../api/reportSessions';
import './bound-citations.css';
import {ReportNote} from './ReportNote';

export function citationPreview(citation: Citation) {
  const sources = citation.sources.map(s => [
    sourceLabel(s),
    s.ticker, s.period_end, s.unit,
  ].filter(Boolean).join(' · '));
  return sources.join('\n') || citation.claim?.statement || '查看引用依据';
}

export function sourceLabel(s: Omit<Source,'next_offset'>) {
  if(s.calculation?.rationale) return s.calculation.rationale;
  if (s.title && s.title !== s.source_id && !/^(PASSAGE|WEB|CALC|UPLOAD)::/.test(s.title)) return s.title;
  if (s.calculation) return s.calculation.rationale || `计算：${s.calculation.expression}`;
  const url = sourceUrl(s.source_url || s.citation_urls?.[0]);
  return [s.ticker, s.metric_id, s.period_end].filter(Boolean).join(' · ') || (url ? sourceHost(url) : '已保存原文摘录');
}

/** Same numbered citations for conversation and report; identity never changes. */
export function BoundCitationMarkdown({text, citations = {}, onCitation, reportHeadings = false, headingOffset = 0}: {
  text: string; citations?: Record<string, Citation>;
  onCitation: (key: string, citation: Citation) => void; reportHeadings?: boolean; headingOffset?: number;
}) {
  const keys = Object.keys(citations);
  return <ReactMarkdown skipHtml
    remarkPlugins={[remarkGfm, [remarkBoundCitations, {ids: keys}], [remarkReportHeadings, {enabled: reportHeadings, offset: headingOffset}]]}
    components={{a: ({href, children}) => {
      if (href?.startsWith('#claim:')) {
        let key: string;
        try { key = decodeURIComponent(href.slice(7)); } catch { return <span>{children}</span>; }
        if (!citations[key]) return <span>{children}</span>;
        const number = keys.indexOf(key) + 1;
        return <button className="rs-cite" aria-label={`依据 ${number}`} title={citationPreview(citations[key])}
          onClick={() => onCitation(key, citations[key])}>[{number}]</button>;
      }
      const url = sourceUrl(href);
      return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>;
    }, table: ({children}) => <div className="fs-report-table" role="region" aria-label="报告数据表，可横向滚动" tabIndex={0}><table>{children}</table></div>,
    blockquote: ({children}) => <ReportNote>{children}</ReportNote>,
    img: ({alt}) => <span className="rs-image-note">[图示：{alt || '未自动加载外部图片'}]</span>}}>{text}</ReactMarkdown>;
}
