# S1 工作记录 106：DELL 03B R9 唯一执行、连接重置根因与作者完整性复证

日期：2026-08-27

状态：`GitHub transport root cause fixed for this repository / R9 exact execution success / raw capture preserved / exact saved-formal replay pass / fresh author-separated engineering and R17 report-quality audit pending`

## 1. 多次连接 reset 的根因与持久修复

R9 authority commit 首先保持在本地 `ahead 1`，没有绕过 runner 的 `HEAD==upstream` 门，也没有提前消费 attempt。多次 push 的症状为 `Recv failure: Connection was reset`、`Could not connect to github.com port 443`。逐层诊断得到：

- Git config、`HTTP_PROXY`／`HTTPS_PROXY`／`ALL_PROXY` 均未配置代理；WinHTTP 也是 direct。
- Windows Internet Settings 已启用 `127.0.0.1:6696`；该端口由 OKZ 的 `AtlasCore_amd64.exe` 监听。
- `github.com` 解析到 `20.205.243.166`，直连 TCP 443 失败，`curl -4 https://github.com` 超时；同机其他 HTTPS 端点以及 GitHub API／object endpoint 可达。这排除凭据、仓库、R9 代码和单纯 HTTP/2 作为最早原因。
- 经 `http://127.0.0.1:6696` 访问 GitHub 主站、API、objects 全部成功；显式代理下连续三次 `git ls-remote` 成功。

根因是：当前网络到 GitHub 主站的直连路径不可达，而 Git 不继承 Windows Internet Settings，因而绕过本机代理并反复 reset／timeout。

最小持久修复只作用于本仓库，没有修改系统或全局 Git：

`git config --local http.https://github.com.proxy http://127.0.0.1:6696`

修复后默认 Git 连续五次 `ls-remote` 成功（`0.85–1.86s`），非强制 push 成功；`HEAD`、upstream、远端 branch 均为 `2c6d7ba526157533770c40ebdbc2f9392c00cc48`，工作树 clean。该配置保存在 `.git/config`，跨当前仓库会话持续生效。外部依赖是本机 6696 listener 必须运行；listener 缺失时应 fail closed，不得移除 sync gate 或改用未验证的直接路径。

## 2. 冻结身份与唯一正式执行

- implementation commit/tree=`3b608ca63631f7c6783443eeb55cae85d111c6b1` / `8d2c65f1288e9b6d6068f38527a57e40c025d7c3`。
- policy-only authority commit/tree=`2c6d7ba526157533770c40ebdbc2f9392c00cc48` / `bda33fb2536cab12ac883c0dd47e8eb0fbc986df`；唯一父提交精确为 implementation，唯一 changed path 为 v1.8 policy。
- policy digest/SHA=`ab50a554fcf65a6c996141016700b47d93fb964b32faf28986fe0a9abdbf1e79` / `ed564b7d5f169c15ee350bb9b81155b5650df62a4651c58809346d104822d9b3`。
- attempt=`dell-rsq-03b-internal-chain-r9`；receipt recorded at=`2026-08-27T04:37:07+00:00`。执行前 public/attempt 均不存在，D 盘 free bytes=`1,245,532,160`，高于 `536,870,912` 策略下限。
- 正式运行执行 `5` 个冻结 request、`1` 个本地 Qwen3-Embedding-0.6B query batch、`338` union、`80` final、`794` target-union occurrences。`network/provider/generation/external/4B/reranker/retry/mutation/promotion/closure=0`。
- 五个请求均为 `material_set_complete`；source=`1,888`、compiled object=`34,199`。

| target | complete source/compiled/union/final | best final rank | R9 disposition |
|---|---:|---:|---|
| ASP bounded quote | 1/1/1/1 | 2 | bounded quote present；company realized ASP/mix remains open |
| capacity release | 0/0/0/0 | — | 03C external route required |
| capacity utilization/yield | 0/0/0/0 | — | 03C external route required |
| HBM→Dell bridge | 0/0/0/0 | — | 03C external route required |
| supplier→Dell | 3/3/2/1 | 2 | relationship present；capacity allocation remains open |
| Dell company-period units | 0/0/0/0 | — | 03C external route required |

当前真实 candidate pool 的 4B embedding eligibility=`0`、same-pool reranker eligibility=`0`。这不是删除混合方案或重排器；必须先由四条 03C 外源产生真实新增 candidate pool，再按 eligibility 对 0.6B／4B 和 reranker 做受控对照。

## 3. Artifact 完整性与 exact replay

- receipt digest/SHA=`a38f4c383cdfccf1a4835a0803cb66c22bd27ff4d465ad2191099743dc2f243b` / `2b60e9884c8dda527d84c575b360e1593e1773074b3133afdd78ebe21d95fb0b`。
- raw capture digest/file SHA=`cad1ad51a3a2d5ed7b64ac166a1f668bee35b1fdd132e875b8c9f8376ccb3657` / `2105aced925042fdef18fda4bdf2433d5d978cf0b77c4175078bd0d8ad3db6e3`。
- raw execution projection SHA=`0e9e4456ba75ecd07bc2e3bd6d5deddafc1972ba19700b029b2e6793e99f7458`；它不是 raw capture 文件 SHA，两者语义不同。
- private digest/SHA=`7531b4947803422acb76d64d9151cc9d35b2f7fc4aabbbb7ec00279be8f61533` / `8a774e436ca7e80349d0fda338336ac5c400dca7e5189b83d2b7272e4a1d8c52`。
- public digest/SHA=`b60fd48482855ff85c3ad46b00fe68433ed4a170532284534bf01522881b32ae` / `8be3ea0dd8a5223818f8cbbf689b8804aba7a87cb28cbc0f16682d12b57f07a4`。
- `terminal_failure_receipt.json` absent。saved-formal replay 返回 `private_dict_and_bytes_equal=true`，private digest 精确为上述值；未再次调用 embedding/model/network。

## 4. 风险分层验证

- formal 后 R9 direct=`56 passed in 7.66s`。
- Project OS preflight=`82 passed in 30.40s`；8 个 Project OS JSONL=`1,324 rows / all parse`，public result JSON parse pass。
- repository secret scan=`8,183 files / 0 findings`；`git diff --check` pass。
- active baseline=`213 Python / 8 frontend / 5 detectors / 28 resources / 0 forbidden`。
- exact saved-formal replay pass；private canonical dict/bytes 全等。
- implementation freeze 的 T2=`153`、T3=`93`、compile/static/import isolation、active baseline、JSONL 和 secret evidence 继续绑定未变的 implementation tree。
- result 阶段只新增 public result、账本和治理文档，不修改 production/test/shared validator/active consumer；T4 trigger 仍为 false，故不重复约 20 分钟的 full pytest。审计若提出具体 material suspicion，再升级到对应 targeted/mutation 或 T4。

## 5. 研报与产品边界

R9 成功证明的是 S1 03B 当前候选链的 frame/scope/anchor/transformation 工程闭环，不是 source closure 或研报通过。四条 residual 外源仍未执行，CandidateDecision、Evidence admission、02B `0/16` qualified-human decisions、Pack/Readiness、S2 数值桥、受影响 S3 单元和新报告均未开始。

R17 固定 14 文件仍是 `FAIL_GATE_OPEN_NOT_ASSESSABLE`：读者可见 citation/source appendix、EV→exact passage/URL/locator、14/9/4/10 crosswalk、六 WWC、事实去重/密度、formal 8D 与 qualified-human 全未通过。下一名 fresh reviewer 必须同时给出 R9 工程 verdict 与 R17 研报质量 carry-forward verdict，不能用工程零 finding 代替报告质量。

## 6. 下一合法顺序

1. 提交并推送 public R9 result、model-run、本工作记录和 Project OS successor。
2. 在 immutable result commit 上创建 hash-bound fixed audit manifest，提交并推送。
3. 启动 fresh、作者分离、只读 subagent；审计 R9 工程和 R17 研报质量，不运行 formal/model/network，不默认跑 full pytest。
4. 只有 R9 engineering fresh PASS 后，才进入四条 residual 03C 外源梯子；随后重建真实 candidate pool，条件式运行 0.6B/4B mixed shadow 和 reranker。
5. 再依次完成 Evidence/human admission、Readiness、S2、受影响 S3、non-overwriting report successor，以及工程／研报／qualified-human 三重验收。
