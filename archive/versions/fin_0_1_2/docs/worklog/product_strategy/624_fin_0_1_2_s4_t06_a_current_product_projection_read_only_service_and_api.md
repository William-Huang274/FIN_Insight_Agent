# FIN 0.1.2 S4-T06-A current product 只读投影与 API

时间：2026-08-05

状态：`engineering pass / current backend projection available / T06 product pending T06-B and T06-C`

## 交付结果

T06-A 把 T05 已接受的 DELL、MU、NVDA 产品锚点编译为一份内容寻址 manifest，而不是复制到第二个可变业务库。每案暴露十个只读视图：Case、Run、Evidence、Numeric、Graph、Gap、Workpaper、Report、Trace、quality。总量为 45 Evidence、9 Numeric、9 typed gaps、0 approved Graph edges、27 business Artifacts 和 3 个 Owner acceptances。

Workbench 后端新增独立 current projection service 和三个 GET-only route：

- `GET /api/v1/current-product/cases`
- `GET /api/v1/current-product/cases/{case_key}`
- `GET /api/v1/current-product/cases/{case_key}/{surface}`

所有入口要求 `mode=current` 和 `current_product:read`。默认应用即使没有 fixture root、旧 `CaseService` 不可用，也能只读访问 current 三案。manifest、case projection、view 均验证 canonical digest；service 返回 defensive copy。

## 真值与安全边界

三个 current Evidence Pack 都没有 approved Graph Evidence，所以 Graph 视图明确为 `typed_empty_no_approved_current_graph_evidence`，没有用 candidate、snapshot、fixture 或历史边补齐 UI。Report 只使用 verified final delivery preview。Trace 只投影安全的 node/local receipt 与 lineage 摘要，不暴露模型原始输出、restricted capture、Authorization/Cookie、凭据或 private reasoning。

validator 会拒绝跨案替换、digest 漂移、Graph fabrication、raw/capture/private 字段、未知 surface 和任何 `.codex_runtime` 依赖。tracked runtime registry 是加载权威；manifest 可由生成器确定性重建。

## 验证

- manifest digest：`4ee7df3c46a87939412c6ea4d303590d91622a2f7216367b6a62cbc15f357250`
- implementation digest：`f30c387cfe7c4ae8c999ed75eeb82a18ea83ed7b57c98d6fd4466faa6817617d`
- T06-A focused：`12 passed`
- T06-A + T05 + current Case 选择性回归：`55 passed`
- 历史 fixture RC-P36-127 回归：`1 passed / 10 failed`，失败集合不变
- 新 model/provider/network/source/tool call：`0`
- 新 business runtime write：`0`

RC-P36-126 的根因“没有 digest-bound current read adapter”已由本项关闭。RC-P36-127 没有在本项顺手修复，也没有通过禁用默认 runtime 或放宽 Evidence 状态伪造全绿；它继续由 T06-B 的 current/fixture runtime-mode isolation 负责。

## 未完成与下一步

T06-A 不是 T06 产品验收。前端尚未进入 current mode；旧 fixture workflow 仍有 RC-P36-127；typed return/request-repair 与 replay 尚未实现；qualified Human Review 和 NVDA R3 尚未执行。因此不能声明 S4 closeout、S5、release 或 production。

下一项固定为：

`FIN-0.1.2-S4-T06-B-WORKBENCH-FRONTEND-CURRENT-MODE-CURRENT-FIXTURE-RUNTIME-ISOLATION-AND-BROWSER-MUTATION-ZERO-CALL-IMPLEMENTATION`

T06-B 只负责前端 current mode、current/fixture runtime-mode 隔离、RC-P36-127 和 browser/cross-case mutation；T06-C 的 return/request-repair 与 T07 handoff 不提前并入。
