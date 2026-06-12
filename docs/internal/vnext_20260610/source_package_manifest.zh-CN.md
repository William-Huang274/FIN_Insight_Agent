# 源文件清单与吸收映射

## 来源

- 源目录：`D:\finsight_agent_升级方案_20260610`
- 吸收日期：2026-06-10
- 吸收方式：摘要、合同化和边界映射；不把规划稿全文复制进公开文档。

## 文件哈希

| 源文件 | SHA256 | 吸收位置 | 备注 |
| --- | --- | --- | --- |
| `README.zh-CN.md` | `12AFBC11EE82C057FD80BA08F10E464FB9F0AFEC0503EAA4C455069889734C30` | `README.md` | 文档包结构、使用方式和实施优先级。 |
| `00_skill_playbook_overview.zh-CN.md` | `D3D989C7408B4C07D18A9719172EE4350A9F985BF2B7F6A23F4BB9D3FE697626` | `skill_playbook_eval_contract.zh-CN.md` | Skill / Playbook / Eval Gate 分工和 runtime 组装方式。 |
| `01_core_agent_role_skills.zh-CN.md` | `0133DBDF5A35013B3EC8B5707978478E1E58348A811F609E1B031C37BCA6A836` | `skill_playbook_eval_contract.zh-CN.md` | Research Lead、Coverage、Memo Writer、Verifier 等核心 role skill。 |
| `02_specialist_agent_skills.zh-CN.md` | `2676A751AB4966DA404373845F1CBE138CE18A89C6F344178D3B3D9448F1CF6D` | `skill_playbook_eval_contract.zh-CN.md` | Fundamental、Market、Industry、Product、Risk、Ownership specialist 合同。 |
| `03_fundamental_analysis_playbook.zh-CN.md` | `6EC891B6F15E81C2487A69ABBB86B6213BFC8491F99E3D3FBF69C665990FE3DD` | `skill_playbook_eval_contract.zh-CN.md` | 基本面六层框架、claim 强度和行业适配规则。 |
| `04_industry_playbooks.zh-CN.md` | `7551C01AD6B1AC9B503CBAB8C0BAE3AF6A8EB24F818F9BF02611A76DBFA788FA` | `skill_playbook_eval_contract.zh-CN.md` | 半导体、云软件、医疗、能源、银行、消费制造行业 playbook。 |
| `05_eval_gate_framework.zh-CN.md` | `CF80F3CA8CBA8FB723DE23F02DCE0F1638A09688102CC29E4F5481EB6A9F71BC` | `skill_playbook_eval_contract.zh-CN.md` | G0-G14 gate 框架；当前先采用 G0-G8 作为后续第一阶段候选。 |
| `06_reference_sources.zh-CN.md` | `D04127E0DB086419B9C1CD3E026D24E70101B5CB9ECB0A769C4D32EC1CB2BF76` | `skill_playbook_eval_contract.zh-CN.md`, `public_data_source_coverage_audit.zh-CN.md` | 外部方法论、合规边界和行业数据参考。 |
| `Agent_Graph更新方案.docx` | `36C8DA6306F7C53582F6F4C25322533EE057B0404E8F212FA2B4A42074A1276E` | `agent_graph_contract.zh-CN.md` | Graph 节点、状态、工件、门控和 replay ledger 方案。 |
| `数据扩容方案——2026.6.10.docx` | `D568CA58D01234477CBB2CC7BC966101B2B87AFD0E0610D26F2377C9EBF5FBBD` | `public_data_source_coverage_audit.zh-CN.md` | 数据源扩容、source registry、raw collector、normalizer、entity resolution 和 tool adapter 方案。 |

## 吸收原则

- 这些文件是 vNext 输入，不是当前系统已发布能力。
- 与现有代码或评测文档冲突时，以当前已验证实现为准；新规划必须通过 source coverage、schema、gate 和小批真实运行后才能进入主线。
- 公开数据源覆盖审计优先于 Graph 和 Skill 的 prompt 级改造。
