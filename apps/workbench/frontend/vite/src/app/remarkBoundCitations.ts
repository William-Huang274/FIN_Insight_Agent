/** FIN citation adapter over react-markdown's existing remark tree.
 * Only server-bound IDs become links. Code and existing links remain literal.
 */
type Node = { type: string; value?: string; url?: string; children?: Node[] };

export function remarkBoundCitations({ ids }: { ids: string[] }) {
  const escaped = ids.map(id => id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!escaped.length) return () => {};
  const alternatives = escaped.sort((a, b) => b.length - a.length).join("|");
  const pattern = new RegExp(`\\[(${alternatives})\\]|(?<![\\w:/\\[])(${alternatives})(?![\\w:/-]|\\.[\\w])`, "g");
  function visit(parent: Node) {
    if (!parent.children || ["link", "linkReference", "image", "code", "inlineCode"].includes(parent.type)) return;
    parent.children = parent.children.flatMap(child => {
      if (child.type !== "text" || !child.value) { visit(child); return [child]; }
      const text = child.value;
      const result: Node[] = [];
      let offset = 0;
      for (const match of text.matchAll(pattern)) {
        const start = match.index!;
        if (start > offset) result.push({ type: "text", value: text.slice(offset, start) });
        const id = match[1] || match[2];
        result.push({ type: "link", url: `#claim:${encodeURIComponent(id)}`,
          children: [{ type: "text", value: String(ids.indexOf(id) + 1) }] });
        offset = start + match[0].length;
      }
      if (!result.length) return [child];
      if (offset < text.length) result.push({ type: "text", value: text.slice(offset) });
      return result;
    });
  }
  return visit;
}
