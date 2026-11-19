import type { TaskOutcome } from "../api/reportSessions";

const status = { submitted: "底稿已提交", needs_attention: "任务待处理", error: "执行失败", cancelled: "已取消", incomplete: "未完成" };
const coverage = { completed: "作者认为已完成", partial: "部分完成", not_completed: "未完成", not_applicable: "作者认为不适用" };
const owner: Record<string,string> = {author:"原作者",lead:"研究负责人",data_tool:"资料或工具",reviewer:"复核者",user:"用户"};
const field: Record<string,string> = {thesis:"核心判断",mechanism:"机制分析",narrative_markdown:"底稿正文",claims:"主张",counterevidence:"反证",what_would_change:"判断改变条件",open_gaps:"未解决缺口"};
const locate = (row: {claim_ids: string[]; fields: string[]}) => [...row.claim_ids, ...row.fields.map(f=>field[f] || f)].join("、") || "未提供具体位置";

export function TaskOutcomeCard({note}: {note: TaskOutcome}) {
  return <section aria-label="任务结果说明">
    <strong>{status[note.execution_status]}</strong>
    <p>{note.author_note?.summary || (note.author_note_status === "invalid" ? "作者说明格式无效，以下保留实际执行记录。" : "未提供作者任务说明，以下仅展示已有记录。")}</p>
    <small>本次交接记录 · 作者完成度不代表独立复核通过。后续修改与复核请查看相应阶段。</small>
    {note.stop_reason && <p>停止原因：{note.stop_reason}</p>}
    {!!note.author_note?.issues.length && <ul>{note.author_note.issues.map((issue,i)=><li key={i}>{issue.description}<p>建议：{issue.next_action} · {owner[issue.suggested_owner] || issue.suggested_owner}</p></li>)}</ul>}
    <details><summary>查看目标覆盖与修改定位</summary>
      {note.success_criteria.map((criterion,i) => <div key={i}><strong>{criterion}</strong>{note.author_note?.coverage.filter(c=>c.criterion===criterion).length ? note.author_note.coverage.filter(c=>c.criterion===criterion).map((row,j)=><p key={j}>{coverage[row.status]}：{row.explanation}<br/>定位：{locate(row)}</p>) : <p>尚未提供此项完成情况。</p>}</div>)}
      {note.author_note?.changes && <p>本次修改：{note.author_note.changes}</p>}
      {!!note.runtime_changes?.length && <div><strong>系统记录的实际修改</strong>
        {note.runtime_changes.map((change,i)=><p key={i}>{[...change.changed_claim_ids,
          ...change.locations.map(row=>field[row.path.slice(1)] || (row.path === "/task_note" ? "任务说明" : row.path))].join("、") || "研究内容未变化"}</p>)}
        <small>位置变化已记录；是否解决研究问题，以后续独立复核为准。</small></div>}
      {note.author_note?.issues.map((issue,i)=><p key={i}>问题 {issue.issue_id} · {locate(issue)}</p>)}
      {note.open_gaps.map((gap,i)=><p key={i}>研究缺口：{gap}</p>)}
      {!!note.navigation_issues.length && <p>任务说明存在未匹配目标或定位，需核对：{note.navigation_issues.join("；")}</p>}
      {note.validation_locations.map((location,i)=><p key={i}>提交校验位置：{location.join(" / ")}</p>)}
      <p>记录绑定任务：{note.task_id} · 尝试：{note.attempt_id || "未记录"}</p>
      <p style={{overflowWrap:"anywhere"}}>本次{note.artifact_status === "candidate" ? "候选" : "提交"}版本：{note.artifact_digest || "没有产物"}</p>
      <small>费用以本次用量记录为准；此说明不代表费用已全部确认。</small>
    </details>
  </section>;
}
