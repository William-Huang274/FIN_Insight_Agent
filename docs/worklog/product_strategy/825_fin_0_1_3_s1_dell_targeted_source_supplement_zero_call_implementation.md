# 825 — FIN 0.1.3 S1 DELL 定向补源零调用实现

日期：2026-08-10

状态：working-tree engineering pass；clean proof／真实 source authority 待执行

## 业务问题

旧 DELL Pack 有 15 条 Evidence，但估值、AI server 产品利润、订单时点、供应与竞争反证仍弱。审计发现问题并不全是“国内搜索 API 搜不到”：本地 corpus 已经保存 HPE、Supermicro、Microsoft、Micron 的相关官方披露，只是旧 query／evidence-owner 路由没有把它们选进 DELL Pack。继续 broad search 会重复花费，并可能把第三方事实误写成 Dell 事实。

## 实现内容

本地 exact-select 五条材料：HPE 订单消化；HPE 内存短缺与 AI 客户验收周期；SMCI AI GPU 增长、ASP 与毛利；Microsoft AI 基础设施 capex；Micron HBM 封装扩产。每条均绑定 corpus SHA、source record、exact anchor 和中文 claim boundary。

外部只保留四个已知高价值来源：Dell Q1 FY27 法说、Micron Q3 FY26 slides、TSMC Q1 2026 法说、Nasdaq DELL 2026-08-06 历史收盘行。它们使用 allowlisted HTTPS、capture-first、parse-after-capture、每路一次、0 retry、0 model。搜索 snippet 和 Provider 日期没有 Evidence 权限。

成功 fixture 在原 DELL Pack 上新增 12 条 Evidence，形状为 `15→27 Evidence／16→14 gaps`。AI server 产品利润和单点估值基础只有在对应 issuer／market target 实际出现后才关闭；HBM、CoWoS、pull-forward 和 price-in gap 只收窄为 Dell-specific allocation／量化／相对估值缺口。客户、竞争对手和供应商全部为 bounded read-through；Nasdaq 行为独立市场 PIT，不能自动生成目标价。

## 验证与停止规则

focused=`6 passed`：正向、缺 issuer margin anchor、corpus SHA mutation、exact-once ledger、authority budget mutation、registered-scope fail-closed。Project OS scope `FIN_0_1_3_S1_DELL_TARGETED_SOURCE_SUPPLEMENT_EXACT_ONCE` 已注册，当前 scoped preflight=`pass／0 blocker`。真实 network/model/provider=`0/0/0`。

下一步必须先 committed/synced，由两个 fresh Git archive worker重现本地选择、fixture parser、gap disposition 和六案 pack 物化；proof 通过后才签发一次 4-call source authority。真实 source 若缺 anchor，保留 capture 与 typed gap，不自动重试，也不进入模型 live。
