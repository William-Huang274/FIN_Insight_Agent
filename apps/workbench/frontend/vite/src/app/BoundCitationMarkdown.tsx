import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {remarkBoundCitations} from './remarkBoundCitations';
import {remarkReportHeadings} from './remarkReportHeadings';
import {sourceUrl} from './sourceUrl';
import type {Citation} from '../api/reportSessions';
import './bound-citations.css';

export function citationPreview(citation: Citation) {
  const sources = citation.sources.map(s => [
    s.title && s.title !== s.source_id ? s.title : s.calculation ? '来源绑定计算' : '原文摘录',
    s.ticker, s.period_end, s.unit,
  ].filter(Boolean).join(' · '));
  return sources.join('\n') || citation.claim?.statement || '查看引用依据';
}

/** Same numbered citations for conversation and report; identity never changes. */
export function BoundCitationMarkdown({text, citations = {}, onCitation, reportHeadings = false}: {
  text: string; citations?: Record<string, Citation>;
  onCitation: (key: string, citation: Citation) => void; reportHeadings?: boolean;
}) {
  const keys = Object.keys(citations);
  return <ReactMarkdown skipHtml
    remarkPlugins={[remarkGfm, [remarkBoundCitations, {ids: keys}], [remarkReportHeadings, {enabled: reportHeadings}]]}
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
    }, img: ({alt}) => <span className="rs-image-note">[图示：{alt || '未自动加载外部图片'}]</span>}}>{text}</ReactMarkdown>;
}
