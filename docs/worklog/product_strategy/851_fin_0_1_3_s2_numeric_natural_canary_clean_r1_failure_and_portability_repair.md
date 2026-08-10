# 851 — FIN 0.1.3 S2 numeric canary clean R1 失败与换行可移植性修复

日期：2026-08-11

状态：R1 terminal failed 已保留；零调用 portability 修复完成，待提交后执行 R2

## R1 实际发生了什么

clean proof 从 clean/synced `e2c5e5fa` 建立第一个 Git archive，向临时目录注入两份 digest-bound DELL private Pack 后启动 fresh Python worker。worker 在加载 canary policy 的 immutable bindings 时终止，尚未编译请求，也没有执行任何 fake callback。

前序 clean-proof JSON 在 Windows working tree 中使用 CRLF raw bytes，policy 记录的 raw SHA 为 `85254037...af84`；`git archive` 中相同 UTF-8 文本使用 LF，normalized-text SHA 为 `9c9e8c66...3e0c`。原 helper 按 raw bytes 比较，因而把换行变化误判成内容漂移。model/provider/network/source/retry/fake 全为 0，临时目录已删除，private Pack 未进入仓库。

## 为什么不能忽略

authority binding 如果依赖 checkout 的换行形式，Windows 工作树能通过、clean archive 或 Linux clone 会失败。这不是金融事实错误，但属于可移植性和证明可信度缺陷，必须留在当前 S2 proof 包修复，不能靠手工改 archive 或跳过 SHA。

## 修复

- Git 管理的 UTF-8 JSON／文本改用 universal-newline normalized text SHA；
- PDF、capture bytes 和 private evidence object 仍使用 raw-byte SHA；
- 新增 CRLF 与 LF 内容 digest 相等的测试；
- R1 工件 `f06661f12d79bff091283b8acee4462cfc5fc37bc0cb1040c3d3341e5e13a2b9` 永久保留；
- 更新后的 implementation digest 为 `9d257c4a153dd8cafa219449bfb4029cc6345948a3c926eb46793d93cfbe4a71`，focused=`20 passed`，相邻合计预期=`36 passed`。

下一步是提交并推送修复，然后以新 `clean_proof_r2` 身份重新建立两个 archive。此工作不注册 live scope，不签 admission，不调用 DeepSeek。
