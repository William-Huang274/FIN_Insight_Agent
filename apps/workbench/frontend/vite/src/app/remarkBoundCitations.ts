/** FIN citation adapter over react-markdown's existing remark tree.
 * Only server-bound IDs become links. Unbound code and links remain literal.
 */
type Node = { type: string; value?: string; url?: string; children?: Node[] };

export function remarkBoundCitations({ ids }: { ids: string[] }) {
  const escaped = ids.map(id => id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const alternatives = escaped.sort((a, b) => b.length - a.length).join("|");
  const pattern = new RegExp(alternatives ? `\\[(${alternatives})\\]|(?<![\\w:/\\[])(${alternatives})(?![\\w:/-]|\\.[\\w])` : "(?!)", "g");
  // An identifier outside the supplied binding catalog is explanatory text,
  // never a fabricated source link. Code and source originals remain literal.
  const plainText = (value: string): Node => ({ type: "text", value: value.replace(
    /(?<![\w:/])(?:NUMFACT::[a-f\d]+|CALC::[a-f\d]+|P\d+:C[\w-]+|P\d+:S\d+)(?![\w:/])/g,
    (id, offset: number) => /(?:财务数据编号|计算编号|判断编号|来源编号)\s*$/.test(value.slice(0, offset)) ? id
      : `${id.startsWith("NUMFACT::") ? "财务数据编号" : id.startsWith("CALC::") ? "计算编号" : /:C/.test(id) ? "判断编号" : "来源编号"} ${id}`,
  ) });
  function visit(parent: Node) {
    if (!parent.children || ["link", "linkReference", "image", "code", "inlineCode"].includes(parent.type)) return;
    parent.children = parent.children.flatMap(child => {
      // Earlier native answers rendered [REF](url), or formatted an exact
      // reference as inline code. Use the saved binding, never the model URL.
      const label = child.type === 'inlineCode' ? child.value?.replace(/^\[|\]$/g, '') :
        child.type === 'link' && child.children?.length === 1 && child.children[0].type === 'text'
          ? child.children[0].value : undefined;
      if (label && ids.includes(label)) return [{type: 'link', url: `#claim:${encodeURIComponent(label)}`,
        children: [{type: 'text', value: String(ids.indexOf(label) + 1)}]}];
      if (child.type !== "text" || !child.value) { visit(child); return [child]; }
      const text = child.value;
      const result: Node[] = [];
      let offset = 0;
      for (const match of text.matchAll(pattern)) {
        const start = match.index!;
        if (start > offset) result.push(plainText(text.slice(offset, start)));
        const id = match[1] || match[2];
        result.push({ type: "link", url: `#claim:${encodeURIComponent(id)}`,
          children: [{ type: "text", value: String(ids.indexOf(id) + 1) }] });
        offset = start + match[0].length;
      }
      if (!result.length) return [plainText(text)];
      if (offset < text.length) result.push(plainText(text.slice(offset)));
      return result;
    });
  }
  return visit;
}
