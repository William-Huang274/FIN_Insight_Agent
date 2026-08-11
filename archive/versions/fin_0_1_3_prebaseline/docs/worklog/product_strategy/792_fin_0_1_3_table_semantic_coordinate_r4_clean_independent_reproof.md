# 792 — FIN 0.1.3 表格语义坐标 R4 clean independent reproof

日期：2026-08-10

阶段：S1／留出案例对象形状泛化独立复证

状态：通过；只准入 CandidateBundle-only sparse／dense manifest 重定基

## 1. 最终证明结果

从已推送提交 `25286d109c8ee070fef48e79eee3402d8403a4da` 导出两个独立 Git archive。每个 archive 只复制 R4 policy 所绑定公开 source result 精确引用的三份不可变响应对象：ORCL `3bf5b666…ade4`、ASML `2036be81…7e7`、ANET `fd327ed8…57cf`；复制前后均校验文件 SHA，凭据类环境变量被剔除，socket 被封锁。

两个 fresh Python process 各自执行 Project OS reparse scope preflight、加载 R4 policy、重建表格／Metric／Claim／CandidateBundleV2、执行 9 类 mutation，并与已提交 R4 result 做 canonical byte comparison。两次结果完全相同：

- R4 result digest：`924c656e32e5e279c12883a6374f53b7e424d5e3046c2ed18e6a4d2f11878ffc`；
- ORCL／ASML／ANET admitted metrics=`1249／18／470`；
- typed rejects=`236／0／238`；
- projected bundles=`27／13／27`，Slots=`8／5／7`；
- mutation=`9／9`；
- network／Provider／model／embedding／rerank／Evidence promotion=`0`。

A3 public proof digest：`0d8531aa4d98c8882061da69f9c6354ed701c55402c936601d48999aa94736e4`。

## 2. 前序失败保留

- A1 在 Git archive 提取器使用本机 Python 不支持的 `filter=` 参数时失败；尚未复制 capture、尚未启动 worker，所有调用为 0。failure digest=`593eb297…c820`。
- A2 在第一个 clean archive 中已逐字节重现 R4，但 proof reporter 使用旧摘要字段 `projected_bundles`，在公开终态物化前失败。单 archive 的业务复现为真，但不能冒充要求的双 archive proof；failure digest=`31ae3cc0…5b4d`。
- A3 只修兼容提取和 reporter 字段映射，从第一份 archive 重新开始；没有修改 parser、policy、R4 result、质量门或调用预算。

## 3. 处置

旧 R1 clean proof 继续是“旧代码可复现”的历史证据，但其 index authority 正式失效。R4 clean proof 现可作为 CandidateBundle-only manifest 的新输入。manifest 必须：

1. 绑定 R4 result／proof digest；
2. 每个 Metric spec 保留 `metric_period／period_role／metric_unit`；
3. `metric_period_missing`、`metric_unit_mismatch`、duplicate、cross-case、wrong period、unknown bundle、unselected claim 与 partial build 全部 fail closed；
4. 仅生成 fake sparse／fake BGE-Milvus 结果和私有 spec CAS，不执行真实 embedding 或 Milvus 写入。

真实 Ubuntu build、同矩阵 ranking、Evidence Pack、外源 residual supplement、DeepSeek 动态研究和报告验收仍需依次独立完成。
