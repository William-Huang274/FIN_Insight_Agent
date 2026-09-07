# S1 工作记录 126：DELL 03B R14 revision 1 fresh plan 审计失败与 lifecycle bootstrap 修正

日期：2026-08-28
状态：`exact commit 46cccb10 fresh read-only review PLAN_FAIL 0/1/0/0 / implementation still false / revision 2 required`

## 1. 结果先说

第二名全新`fork_turns=none`、作者分离、只读reviewer严格审查pushed commit `46cccb104281b54aa51177399d511f785ff37bc2`，没有审查之后的工作区。它独立验证：

- plan SHA-256=`78ac2464e3636345d474042cd3664290160a7e6c12a6ff739640c79813c6ddf7`；
- plan bytes=`65,552`；
- Git blob=`4c190884b838082eeafaa60a206c674648e8c151`；
- reviewer writes／commits／pushes／formal／pytest／dynamic probe／network/model/external/embedding/4B/reranker均为0。

最终=`PLAN_FAIL`，`P0/P1/P2/P3=0/1/0/0`。初审`0/3/2/1`中的authority主体链、grammar/topology、mutation denominator、vector编码、Windows transaction、4B和下游质量顺序均已在plan层关闭；只剩一个lifecycle/bootstrap P1。

## 2. 唯一P1是什么

revision 1存在三段互相冲突的文字：

1. pre-formal `A=FAIL`后，可以直接在同一R14创建`I′→B′→A′`；
2. “任一审查或formal材料失败”都进入`R14_STOP_OWNER_DECISION_REQUIRED`，只有OwnerDecisionReceipt才能返回实现；
3. hard-stop又说pre-formal失败直接在同一R14修复，只有formal后失败才需要Owner决定。

机器validator无法同时执行“直接返修”和“必须OwnerDecision”两条转换。

此外，revision 1把`G`定义成当前计划/R13 audit治理基线，允许首个`I.parent=G`；但真正解锁implementation的条件是fresh plan review PASS。若PASS receipt没有先进入一个后继治理commit并成为`I`的exact parent，`PLAN_PASS才可实现`仍只是Markdown承诺。

## 3. revision 2唯一修正方向

不改初审已关闭的其余架构，只把状态机改成一条路：

### 3.1 Plan bootstrap

```text
candidate plan commit C
  -> fresh read-only plan review
  -> FAIL: failure receipt F -> new candidate C′
  -> PASS: PASS receipt governance commit G
           -> first implementation I, with I.parent == G
```

`G`必须只含原样物化的plan PASS receipt和append-only governance状态；receipt绑定`C` commit/tree/parent、plan blob/SHA/bytes、reviewer payload digest、verdict/counts。`PLAN_FROZEN→IMPLEMENTATION_FROZEN` preflight必须验证这些exact bytes和`G` changed-path allowlist。这样没有self-reference：reviewer审`C`，PASS进入后继`G`，实现以`G`为parent。

### 3.2 Pre-formal failure

```text
I -> B -> A=FAIL
  -> PREFORMAL_FAIL_REVISION_REQUIRED
  -> same R14 new I′ -> B′ -> A′
```

由于没有消费attempt，不要求OwnerDecision；但此状态禁止P、attempt、R15、03C、模型、Evidence、S2、S3和Writer。

### 3.3 Post-attempt failure

```text
... -> P -> ATTEMPT_CONSUMED
      -> formal/post-formal material FAIL
      -> R14_STOP_OWNER_DECISION_REQUIRED
```

只有这里需要OwnerDecisionReceipt，选择同一R14更换parser/IR、永久`partial＋human`或终止03B。失败attempt保持immutable，不复用ID。

## 4. 当前authority

- 允许：物化本次失败回执、Project OS更新、revision 2 plan、fresh exact-commit plan re-review；
- 禁止：R14 implementation、policy、attempt、R15、03C、0.6B/4B、reranker、Evidence、Pack/Readiness、S2、S3、Writer、report、product、publication、release；
- 磁盘门独立保持：`518,934,528 < 536,870,912 bytes`，即使未来implementation eligible也不等于policy/formal eligible。

## 5. 下一门

revision 2必须成为新的exact pushed candidate plan commit `C′`，再由第三名fresh、作者分离、只读reviewer给出`PLAN_PASS`且P0/P1/P2=`0/0/0`。PASS payload必须先进入后继治理commit `G`；只有首个`I.parent==G`时才真正解锁implementation。
