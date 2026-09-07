# FIN 0.1.3 S1 VS4 DELL Coverage 驱动补证纵切

日期：2026-08-18
状态：`DELL_VS4_vertical_slice_integrated / MU_NVDA_equivalent_paths_pending / S1_qualification_false`

## 1. 这轮解决的不是“再搜几份网页”

VS4 要验证的是：当研究命题仍有缺口时，系统能否从现有 Coverage 和候选账本出发，形成有方向的第二轮检索，区分真正可用的证据与语义相近的噪声，把通过来源、身份、期间和引用复核的对象加入当前 Evidence Pack，并说明结论究竟被补强、被收窄，还是仍应保持 gap。

DELL 选择三种不同业务问题：

1. AI 订单是否占用更多营运资金；
2. 强订单是否也可能伴随价格、取消、延期和库存风险；
3. 上游先进封装和测试瓶颈能否构成供给反方，以及它能否直接证明 Dell 获得的分配量。

本轮复用已保存的 Dell 与 TSMC 官方法说 capture，0 网络、0 生成模型调用。它证明的是“当前资料库内的命题驱动补证、审阅、晋升和 Coverage delta”，不是开放网络补源完成，也不是完整动态 Agentic Research。

## 2. 不可变失败与根因

所有失败均保留为新版本结果，没有覆盖历史：

1. `query/policy v1.0` 在 Provider／向量执行前 fail closed：上游反方被编译到不允许 transcript 的 facet。根因是 source-role 路由合同不一致，不是没有资料。
2. `ranking v1.1` 已通过 CUDA 召回全部三类正例，但 Evidence Role 只保留一半开发正例，并接受了实际候选池中的 hard negative。问题是分析师提问、IR 主持人复述和同页句子可错误继承管理层事实权限。
3. `ranking v1.2` 关闭实际候选池 hard negative，但完整已审集合仍只有 5/7 被抑制。
4. `ranking v1.3` 采用通用 speaker-authority 与 claim-local 规则：6/6 正例 compatible，7/7 hard negative rejected／abstained；没有使用 ticker、对象 ID、答案 URL 或标准答案专用分支。

这几轮说明，早期错误不能笼统归为“Embedding 不行”。正例早已进入候选池，真正断点是 transcript 说话人权限、Evidence Role 与同页兄弟片段的授权继承。

## 3. 实现

### 3.1 通用金融角色边界

- transcript 中只有分析师提问、IR 主持人转述或没有管理层回答的片段，不得成为 management fact；
- working-capital 必须包含库存、应收、应付、现金转换等主体锚点，不能因为位于财务报表附近就获得相应角色；
- upstream capacity 识别 packaging、tester、shortage、bottleneck 等机制，但跨公司资料只授予 ecosystem context，不授予 Dell 分配量或产品归属。

### 3.2 精确对象绑定

`CandidateDecision` 现在检查 Evidence 明确绑定的 `compiled_object_id`。同一原始 capture、同一页或同一 parent 下的兄弟 claim 不能借用另一条已复核 Evidence 的权限。

### 3.3 Capture-bound supplement vertical

新增 provider-neutral `src/retrieval/supplement_vertical.py`：

- 从 compiled object 反查 source record、parent document 和 immutable capture；
- 校验 source digest、parent digest、capture SHA、公司身份、日期、locator 和原文包含关系；
- Candidate 仍不是 Evidence；只有显式人工／规则审阅的对象可形成精确 claim Evidence；
- 支持 retire／add／reuse、gap narrow／close 和确定性审阅顺序；
- gap 不能因为发现一条定性材料而被静默关闭；
- Workbench 投影持续显示 `S1=false`、`NumericFact=false`。

DELL policy 显式退役三条宽片段／整页 Evidence，并以五条精确 claim 继任；这不是本地“超级拼装”观点，而是把已有官方原文切到正确的命题与权限边界。

## 4. DELL 业务结果

### 营运资金

Dell 已明确说，FY2025 的营运资金受到 AI 动态影响，库存、应收和应付上升；同时，大额订单需要更多营运资金，并面临价格、延期、取消和过时库存风险。

这使原来的“完全不知道 AI 是否影响营运资金”收窄为：方向和机制已知，但 AI 产品级金额、周转天数桥和各科目具体增量仍未披露。系统只 narrow gap，没有 close gap，也没有授予 NumericFact。

### 发行人反方

Dell 自身风险披露足以否定“订单强就必然高质量兑现”的简单推断。它支持竞争定价、营运资金占用、订单变化和库存风险等反方；发生概率和已实现损失金额仍未知。

### 上游反方

TSMC 管理层确认先进封装产能紧张、部分瓶颈工具和测试设备短缺。这可支持行业供给反方，但不能证明 Dell 的具体分配、产品映射或产能释放时点。分析师问题和主持人语句已被拒绝，不再冒充管理层事实。

### Pack delta

| 项目 | 前序 | successor | 含义 |
| --- | ---: | ---: | --- |
| Evidence | 20 | 22 | 退役 3 条宽 Evidence，新增 5 条精确 claim |
| residual gaps | 14 | 14 | 1 条被窄化，0 条被关闭 |
| candidate text 自动晋升 | 0 | 0 | 排名不能授权 Evidence |
| NumericFact 新授权 | 0 | 0 | 文本补证不替代 S2 数值权威 |
| hard-negative false accept | — | 0 | 说话人／同页权限边界保持 |

三个命题均达到本轮有界 readiness，但 `complete_research_ready=false`、`complete_s1_ready=false`。

## 5. 当前消费者与回退

- Runtime Registry 升为 R18，新增 `application.result.current_s1_vs4_supplement_vertical`；
- Operations 新增 `/api/operations/s1/supplement-quality`；
- 当前 Evidence result v1.2、anchor catalog v1.1 与 Workspace catalog v1.2 已共同绑定 DELL successor；`/workspace`、Evidence API 和 Retrieval API 现在都返回同一条 successor canonical spine，不再出现 Operations 看见 22 条而产品面仍读 20 条的双轨状态；
- Workbench 展示三命题已知／未知、Evidence 替换、gap delta 和权限边界；
- 首次全仓回归自然暴露 56 failures／36 errors：旧 S3 fixed-Pack 测试通过活动 `current` 指针重建历史输入，导致合法 S1 Pack 更新改写旧证明。根因已修为“当前产品读 v1.2；历史 authority／attempt 显式读其绑定的 v1.1”，没有批量修改历史模型输出或质量答案；
- 前序 Pack、anchor、workspace、v1.1/v1.2/v1.3 排名结果和所有失败 attempt 保持不可变；回退通过恢复 R17 的三项 current pointer 并移除 VS4 resource 完成，不需要改写历史 Pack。

## 6. 验证

- supplement、canonical lineage、candidate binding、Evidence Role、Workbench 与 Runtime Registry 定向测试通过；
- 全仓 Python：`581 passed`；
- TypeScript typecheck 与 Vite production build：pass；
- Playwright desktop Operations 定向：`1 passed`；桌面／移动真实数据产品面：`6 passed`。默认 4173 被本机其他程序占用，使用隔离端口 43173／43174 后通过，未修改产品逻辑；
- S1 program foundation：pass（10 axes、20 open gaps、资格仍 false）；active baseline：143 Python／8 frontend／16 Runtime resources／0 forbidden reference；
- CUDA 边界保持：Embedding 与 Cross-Encoder 均显式使用 CUDA／FP16，CUDA 不可用时 fail closed，不允许 CPU fallback；CPU 只承担 BM25、硬过滤、JSON、稳定排序和账本编排。

## 7. 未关闭事项与下一步

1. DELL 只证明当前对象库与已有 capture 上的有界补证，不代表开放式网络补源覆盖充分；
2. DELL 其余 residual gaps 尚未逐项形成 typed stop；
3. MU／NVDA 尚未从自然命题走等价 Coverage→query→candidate→review→capture→Pack→Workbench 路径；
4. valid temporal、frozen test、新异质留出、性能阈值和双 clean replay 仍属 VS5；
5. S1、完整用户链、研报内容质量、S4 与 release 均未通过。

下一步先用相同通用模块审计 MU、NVDA 的自然命题和真实 residual gaps。若对象已经存在，走 capture-bound 晋升；若路线未执行，保留 `not_yet_searched`；只有本地对象、适用路线、排序、审阅和来源可达性都留有凭证后，才允许形成真实信息边界。三案稳定后才进入 VS5，不为单一公司增加核心分支。
