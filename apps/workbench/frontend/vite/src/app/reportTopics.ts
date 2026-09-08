import { unified } from "unified";
import remarkParse from "remark-parse";
import remarkGfm from "remark-gfm";
import { remarkBoundCitations } from "./remarkBoundCitations";
import type { Session } from "../api/reportSessions";

type Ast = { type: string; depth?: number; value?: string; url?: string; children?: Ast[]; position?: { start: { offset?: number }; end: { offset?: number } } };
export type ReportTopic = { id: string; title: string; excerpt: string; markdown: string; claimIds: string[] };
const plain = (node: Ast): string => node.value || (node.children || []).map(plain).join("");
/** Membership is derived from actual Markdown citation links, never inferred causal edges. */
export function reportTopics(report: NonNullable<Session["report"]>): ReportTopic[] {
  const text = report.narrative_markdown;
  const processor = unified().use(remarkParse).use(remarkGfm).use(remarkBoundCitations, { ids: Object.keys(report.citations) });
  const tree = processor.runSync(processor.parse(text)) as Ast;
  const headingDepth = Math.min(...(tree.children || []).filter(n => n.type === "heading" && (n.depth || 0) >= 2).map(n => n.depth!), 6);
  const topics: ReportTopic[] = [];
  let current: ReportTopic = { id: "intro", title: "报告概述", excerpt: "", markdown: "", claimIds: [] };
  const collect = (node: Ast) => {
    if (node.type === "link" && node.url?.startsWith("#claim:")) {
      try { const id = decodeURIComponent(node.url.slice(7)); if (report.citations[id] && !current.claimIds.includes(id)) current.claimIds.push(id); } catch { /* Invalid links do not create a relationship. */ }
    }
    for (const child of node.children || []) collect(child);
  };
  for (const node of tree.children || []) {
    if (node.type === "heading" && node.depth === headingDepth) {
      if (current.markdown.trim()) topics.push(current);
      current = { id: `section:${node.position?.start.offset}`, title: plain(node), excerpt: "", markdown: "", claimIds: [] };
    }
    current.markdown += text.slice(node.position?.start.offset || 0, node.position?.end.offset || 0) + "\n\n";
    if (!current.excerpt && node.type === "paragraph") current.excerpt = plain(node).slice(0, 150);
    collect(node);
  }
  if (current.markdown.trim()) topics.push(current);
  const used = new Set(topics.flatMap(t => t.claimIds));
  const unplaced = Object.keys(report.citations).filter(id => !used.has(id));
  if (unplaced.length) topics.push({ id: "unplaced", title: "尚未定位到正文的引用", excerpt: "保留原绑定，不推定其属于某个专题。", markdown: "", claimIds: unplaced });
  return topics;
}
