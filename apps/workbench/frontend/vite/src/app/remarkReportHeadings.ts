/** Stable, duplicate-safe anchors over the existing Markdown AST. */
type Node = { type: string; children?: Node[]; data?: { hProperties?: Record<string, unknown> }; position?: { start: { offset?: number } } };
export function remarkReportHeadings({ enabled }: { enabled: boolean }) {
  return (tree: Node) => {
    if (!enabled) return;
    let index = 0;
    function visit(node: Node) {
      if (node.type === "heading") {
        node.data = { ...node.data, hProperties: { ...node.data?.hProperties,
          id: `report-section-${node.position?.start.offset ?? index++}` } };
      }
      node.children?.forEach(visit);
    }
    visit(tree);
  };
}
