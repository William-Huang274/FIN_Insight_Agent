# 870 — FIN 0.1.3 S3 小判断原子与确定性 cell 投影

日期：2026-08-11

阶段：S3 targeted repair

状态：working-tree engineering pass；clean proof 待执行

## 为什么不是继续改 DS 字段

唯一自然 canary 已经证明 DS 能正确识别 `E021` 的 issuer-direct 角色、`E002／E008／E023` 的边界、三个残余 gap 和 Numeric authority，但不能稳定管理内部 cell 状态：target changed flag 自相矛盾，并从经营盈利证据越推到 price-in。继续增加四行 Prompt 仍会把模型绑在项目内部状态机上，也会形成 DeepSeek 专用分支。

## 新分工

模型输出面缩成五类研究语义：Evidence disposition、盈利方向、产品／分部归因边界、residual-gap enums、短 mechanism／boundary atoms。它不再返回 affected cells、state、changed flag、每 cell refs 或 WWC。

本地 Runtime 只做控制投影：根据已冻结的 dependency graph 生成四个 affected cells；固定无估值 Evidence 时 price-in=`cannot_infer`；绑定 Evidence／NUM／WWC；本地渲染 `mid-single-digit`；把 Writer admission 当报告控制而不是业务证据。Runtime 不替模型发明 thesis、机制、反方解释或完整研报。

## 项目侧修复

内部 `E021`／NUM alias 的数字现在与真正金融数字分型；atom 中重复的 alias 会被替换成不改变含义的中性引用短语，而不是机械删除成残句；`mid-single-digit`、金额、百分比和拼写数字仍 fail closed。JSON 成功解析后先写 `parsed/repair_output.json`；只有合同通过并实际写出文件后 terminal 才给 `validated_output_ref`。旧失败 terminal 不改写，原 capture 继续不可变。

新 request 为 `8,854` 字符，旧 request 为 `17,343`；减少的是状态表和数值表面，不是 Evidence 语义。DELL 实际 projection 与 DELL／MU／NVDA 三案 shape、cross-case、错误方向、数字越权和 state 注入 mutation 已通过；focused／terminal=`27 passed`，相邻 S3 合计=`42 passed`。下一步是提交推送后两个 clean Git archive／fresh process，注入既有私有 Pack 与本次失败 capture，完成零网络 replay 和 byte-equivalent proof。任何第二次自然调用与完整报告仍未授权。
