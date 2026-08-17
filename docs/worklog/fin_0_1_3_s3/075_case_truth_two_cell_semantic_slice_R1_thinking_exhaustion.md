# 075 两单元 Case Truth semantic slice R1：max thinking 再次耗尽

时间：2026-08-17

## 结果

绑定 clean/synced commit `1ce3dea2b891dddd165ca1501660cb1ede10d263` 的唯一两单元 successor 已执行。Operating 与 Counterevidence 各自只获得本 cell 的三个 claim surface，但分析节点仍读取完整 compact Case Truth view，并使用 `thinking=max / max_tokens=16000`。

两次分析均返回完整 HTTP 200 JSON、无 transport error、无截断，却把全部 completion budget 用作私有 reasoning，零可见 content：

- Operating：prompt `10,056`、completion `16,000`、reasoning `16,000`、total `26,056`，约 177 秒；
- Counterevidence：prompt `9,977`、completion `16,000`、reasoning `16,000`、total `25,977`，约 196 秒；
- 两次均 `finish_reason=length`、visible content=`0`、Tool Call=`0`；
- 因没有分析草稿，两个 non-thinking strict submission 均未执行；总调用 `2/4`，0 retry/fallback/protocol switch/source network/embedding/rewrite/report/publication。

## 判断

这不是网络、IncompleteRead、strict Tool Schema、local Validator 或模型语义内容失败；模型从未交出可评价内容。切成三 surface 后 prompt 从全案 R1 的 `14,576` tokens 降到约 `10k`，但 `thinking=max` 仍把 16k 全部耗尽。对“把现有文本映射到已给 alias/state”的 bounded classification 使用 max thinking，任务类型与 profile 不匹配；继续加到 32k 只会增加成本，不能证明会出现可见答案。

## 下一处置

保持完整 Case Truth、claim slice、local Validator 和 strict submission 不变，不再扩大 token。只把 visible semantic analysis 改为独立 non-thinking classification profile，预算最多 4k；submission 仍使用原 non-thinking strict-beta profile。以 fresh authority 重新执行同两 cell，0 retry。若仍无可见输出或出现系统性语义错配，再决定是否引入更小的 alias index／provider-neutral selector 或更换语义分类 profile，不能继续为 DeepSeek 增加专用 Prompt 迷宫。
