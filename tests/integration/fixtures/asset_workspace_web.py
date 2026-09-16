"""Readable synthetic asset workspace; real BFF/SQLite and no model dispatch."""
import os
from pathlib import Path
from tests.integration.fixtures.project_library_web import app  # noqa: F401
from sec_agent.research_foundation.asset_workspace import AssetWorkspace

workspace=AssetWorkspace(Path(os.environ['FINSIGHT_LOCAL_STATE_ROOT'])/'project-library')
project='00000000-0000-4000-8000-000000000053'
if not workspace.library.index('local-pilot')['projects']:
    workspace.library.save('local-pilot',0,{'projects':[{'id':project,'name':'AI 基础设施 · 研究笔记'}],'assignments':{},'pinned':[]})
    scope=workspace.library.scope('local-pilot',project)
    workspace.library.documents.add(scope,'资本开支与现金创造.md', '''# 从投资规模，走向回报质量

> 界面演示资料，以下是研究问题与假设，不是真实公司的财务结论。

## 我们真正想回答的问题

当基础设施投入持续增加，收入增长是否足以覆盖新增折旧、营运资本占用与维护性投入？需要将投资规模和现金创造能力放在同一期间比较。

## 先把三个口径分清

| 观察维度 | 应核对的内容 |
| --- | --- |
| 资本开支 | 现金支出、融资租赁与管理层指引的口径差异 |
| 经营现金流 | 营运资本变动和一次性收付款的影响 |
| 投资回报 | 投入兑现的时间、利用率与收入转化 |

## 还缺哪些依据

- 同期现金流量表与固定资产附注。
- 投资计划的原始表述，以及期间和范围限定。
- 能够挑战当前假设的经营数据与管理层解释。

下一步：先核对原始披露，再判断投入是否转化为持续回报。
'''.encode())
    workspace.library.documents.add(scope,'阅读线索与来源核查.md','''# 下一次阅读的清单

这是一份可自行维护的合成笔记。

- 原始披露说了什么，哪些是我们的推断？
- 指标是否保持相同期间、主体和单位？
- 当前结论最容易在哪个假设上失效？
'''.encode())
