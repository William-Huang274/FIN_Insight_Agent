# FIN 0.1.2 S2-T02 双模型 route 与 paired-canary compiler 零调用实现

日期：2026-08-02
状态：`engineering_pass / T03 separate authority next / model calls 0`

## 本轮完成

按 S2 StagePlan 消费唯一一个 T02 零调用实现包：

- 新建 current v1.1 judgment-atom source/binding，旧 v1.0 合同与历史 Pro admission 保持不可变；
- 新建只包含 `deepseek-v4-flash` stable 与 `deepseek-v4-pro` preview 的 S2 candidate registry，冻结同 provider、同 JSON-object transport、thinking disabled、temperature 0、retry/fallback/provider hopping 为 0；
- 新建独立 paired-canary compiler，为 MU 单 Cell 编译 Fact/Claim/WWC × Flash/Pro 六个隔离调用；
- 同一 family 的两模型可见请求逐字节相同，模型身份和 fresh call identity 不参与 equivalence digest；
- full request、final assistant output、allowlisted arguments、finish reason/usage 在本地校验前 capture；credential/header/Cookie/private reasoning 不保存，失败输出不可晋升业务内容；
- 语义失败继续收集其余独立 family，鉴权/transport/security/capture 失败才停止剩余调用。

## 实现中主动发现并修正

1. 旧 wire 要求模型回写 `program_cell_id`，与“identity 归本地所有”冲突。v1.1 Provider schema 完全移除该字段，校验通过后由本地注入。
2. 旧 Fact 可见合同只有 alias/type/role，模型看不到实际 statement/boundary，无法判断证据相关性。v1.1 给模型提供有界 selection context，但 Provider 输出仍只能返回 alias 与 closed enum。
3. 初版把 S2 路径常量放入旧 v1.0 loader，导致 S0 默认资源 detector 发现未登记路径。最终拆出独立 S2 loader 与三资源 registry，不改旧默认 registry，也不放宽 detector。

这三项分别由 RC-P36-098/099/100 的关闭记录约束。它们是项目合同和资源所有权问题，不是 DeepSeek 能力问题。

## 验证

- Python compile：pass；
- S0/S1/S2 组合合同回归：`97 passed / 0 failed`（含 2 项结果与投影闭环）；
- DELL/MU/NVDA 每案：`6 planned / 6 pass / 6 captures / 6 local assemblies`；
- mutation：candidate route/budget、Provider-authored identity、unknown/cross-case alias、Claim kind/support conflict、WWC date alias、6-to-3 selection、transport stop、资源登记与 digest；
- credential/model/provider/network/source/business Run/Artifact：全部 0。

仓库 architecture inventory 为 3654 nodes、18834 edges、0 Python parse error。全局 architecture guard 仍因 5 个既有超大文件失败，错误路径均不在本轮改动内；本轮新 canary 模块没有成为 critical hotspot。`deterministic_judgment_atom_contract.py` 仍是 complexity warning，作为后续共享 Runtime 可维护性债务保留，不阻断本次有界 T02。当前 Python 环境未安装 Ruff，因此没有伪报 lint pass；已执行 Python compile、97 项 pytest 与 `git diff --check`。

## 能力边界

T02 只证明比较器、公平输入和本地安全边界已经可执行。它不证明 Flash 或 Pro 会自然遵循合同，不选择 S3 主线模型，不生成九件套，也不构成 S2 closeout、产品验收或 release readiness。

## 下一项

`FIN-0.1.2-S2-T03-MU-THREE-FAMILY-FLASH-STABLE-VS-PRO-PREVIEW-PAIRED-NATURAL-OUTPUT-CANARY-AUTHORITY-DECISION`

下一项仍为零调用权限审查；只有另行签发后才允许读取凭据并执行六个 DeepSeek 调用。
