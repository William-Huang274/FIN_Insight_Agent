import type {ReactNode} from 'react';

/** Keep the accepted current manuscript distinct from its conversation history. */
export function ResearchDeliveryLayout({report,history,hasReport,historyOpen,onHistoryToggle}:{
  report:ReactNode;history:ReactNode;hasReport:boolean;historyOpen:boolean;onHistoryToggle:(open:boolean)=>void;
}) {
  return <>
    <section aria-label="当前研究成果">{report}</section>
    {history&&<details aria-label="历史交流与版本修改" open={!hasReport||historyOpen}
      onToggle={event=>onHistoryToggle(event.currentTarget.open)}>
      <summary>历史交流、复核意见与版本修改</summary>{history}
    </details>}
  </>;
}
