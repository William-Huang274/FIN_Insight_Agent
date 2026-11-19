/** Stable, duplicate-safe anchors over the existing Markdown AST. */
type Node = { type: string; children?: Node[]; data?: { hName?: string; hProperties?: Record<string, unknown> }; position?: { start: { offset?: number } } };
export function remarkReportHeadings({ enabled, offset = 0, chartsBefore }: { enabled: boolean; offset?: number; chartsBefore?: Map<number, number[]> }) {
  return (tree: Node) => {
    if (!enabled) return;
    let index = 0;
    function visit(node: Node) {
      if (node.type === "heading") {
        node.data = { ...node.data, hProperties: { ...node.data?.hProperties,
          id: `report-section-${offset + (node.position?.start.offset ?? index++)}` } };
      }
      node.children?.forEach(visit);
    }
    visit(tree);
    if (chartsBefore && tree.children) {
      tree.children = tree.children.flatMap(node => {
        const charts = chartsBefore.get(node.position?.start.offset ?? -1) || [];
        return [...charts.map(i => ({type: 'paragraph', children: [], data: {
          hName: 'div', hProperties: {'data-report-chart': i},
        }})), node];
      });
    }
  };
}
