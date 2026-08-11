# FIN 0.1.2 S0C-T03 corrective hermetic proof terminal honest block

日期：2026-08-01

任务：`FIN-0.1.2-S0C-T03-INDEPENDENT-TWO-DISPOSABLE-CORRECTIVE-HERMETIC-PROOF-AND-CLOSEOUT`

结果：`terminal failed / unique proof package consumed / no T04 or retry / S2 and model canary deferred`

## 1. 唯一正式执行结果

在 clean/synced `codex/layered-data-source-expansion@47ed2584` 上完成 host preflight 后，唯一 S0C-T03 package 按冻结 manifest 执行一次。包位于：

`D:/FIN_Insight_Agent_recovery/packages/fin_0_1_2_s0c_t03_corrective_hermetic_proof_20260731T191455Z_head_47ed2584`

`verification.json` SHA-256=`4bdfa028...0d80`，`package_manifest.json` SHA-256=`3b96871b...00c1`。两套 disposable 都在 pytest collection 期以 exit code 2 失败，各有 1 个 collection error、0 个测试实际执行。仓库运行期间未变化；terminal、collection detail、process stdout/stderr 与语义投影均保留内容寻址引用。credential environment names 被移除，但失败包仍只允许 restricted audit，不得自动分享、重放或业务晋升。

## 2. 首个可信失败

两套 disposable 的同一 import chain 最终进入 `apps/workbench/backend/application/integrity_service.py:105`，尝试读取：

`configs/releases/fin_ia_0_1_vt2_three_cell_integrity_workpaper_contract_v1_0.json`

该文件在 host 上受 Git 跟踪，SHA-256=`2cb328eb...ab79`，但两份 package 中均为 0 份；消费它的 Python 文件却已入包。当前 closure 能处理 manifest seed、Python prefix、JSON ref 和既有显式 Runtime resource inventory，却不能发现 Python 代码直接声明的静态非 Python 资源。登记 `RC-P36-092`。这是项目内 hermetic dependency compiler 缺口，不是 DeepSeek、Provider、金融方法或新的金融 Runtime L1。

## 3. 次级语义投影失败

两份 collection traceback 各保留 1 个不属于三个 allowlisted disposable roots 的绝对宿主 Python/site-packages 路径。semantic projection 正确 fail closed，但 `normalization_valid=[false,false]`，semantic parity=false。登记 `RC-P36-093`。未来只能对稳定 interpreter/distribution 路径做 typed normalization，不能通过广泛删路径制造 parity，也不能删除业务值、nodeid 或 failure code。

## 4. 对 RC-P36-090/091 的判断

新包 inventory 为 `746 paths / 746 tracked / 0 explicit allowlist`，`.git=0`、`.codex_runtime=0`，repository unchanged=true。因此旧 `.git` 自反和 ignored Runtime 越界在 package construction 层没有复发。由于 collection 在任何选中测试执行前停止，不能把这部分正面信号升级成正式关闭；RC-P36-090/091 继续 open/full-chain blocker。

## 5. 停止线与产品真值

S0C implementation/proof budget 已全部消耗为 `1/1`。按冻结规则：

- 不修补后重跑 S0C-T03；
- 不创建第二 proof package、T04 或 R-number；
- 不建立 S2 StagePlan；
- 不调用 DeepSeek V4 Flash stable 或 Pro preview；
- DELL R2、MU R2、post-transfer NVDA、NVDA R3、S2 entry 与 FIN 0.1 release qualification 均保持 false。

当前下一项只允许一个零调用归属决策：

`FIN-0.1.2-S0C-TERMINAL-HONEST-BLOCK-AND-REPAIR-OWNER-VERSION-DISPOSITION-DECISION`

它需要决定 RC-P36-090–093 是进入 FIN 0.1.2 的新版本化共同 Runtime/hermetic contract stage，还是后传到更晚版本；不得把该决策偷换成 S0C 重跑。
