import {Children, cloneElement, isValidElement, type ReactNode, type ReactElement} from 'react';

/** Only author-marked notes fold. Ordinary qualifications remain in the prose. */
export function ReportNote({children}: {children?: ReactNode}) {
  const rows = Children.toArray(children);
  const index = rows.findIndex(row => isValidElement(row));
  const first = rows[index] as ReactElement<{children?: ReactNode}> | undefined;
  const parts = first && isValidElement(first) ? Children.toArray(first.props.children) : [];
  const head = parts[0];
  const match = typeof head === 'string' ? /^\[!NOTE\][ \t]*([^\n]*)(?:\n|$)/.exec(head) : null;
  if (!match) return <blockquote className="fs-report-note">{children}</blockquote>;
  const label = match[1].trim() || '依据与条件';
  const remaining = (head as string).slice(match[0].length);
  rows[index] = cloneElement(first!, {}, ...[remaining, ...parts.slice(1)]);
  return <details className="fs-report-note fs-report-note-expandable">
    <summary>{label}</summary><div>{rows}</div>
  </details>;
}
