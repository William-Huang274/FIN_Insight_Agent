# FIN 0.1.3 S1-C BGE Reranker v2 M3 / Evidence Role Shadow R2

- 日期：2026-08-12
- 用途：离线候选重排和 Evidence Role 资格判断
- 模型：`BAAI/bge-reranker-v2-m3`（Apache-2.0）
- 模型文件 SHA256：`d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286`
- 设备：CUDA
- 评测 pair：631
- 最大长度：1024；batch：2
- 耗时：25.141 秒；峰值 GPU：2,280,719,360 bytes
- 网络调用：0；生成模型调用：0；训练步骤：0

结果：

- 三案 Cross-Encoder Recall@10=`0.944444`、MRR=`0.608480`。
- BM25 Recall@10=`0.944444`、MRR=`0.559392`。
- 规则 Evidence Role gate Recall@10=`0.722222`，禁止晋升。
- ORCL／ASML／ANET 留出明确正负 pairwise=`0.790698`，Cross-Encoder top1=`0.823529`、top3=`1.0`；规则角色 gate top1=`0.764706`。

处置：模型与角色门均未注册为 Runtime route。Cross-Encoder 有真实但不稳定的排序增益；规则角色门跨对象泛化不足。微调和 S1-D 均未授权执行。

机器结果：`configs/retrieval/fin_ia_0_1_3_s1c_cross_encoder_role_shadow_result_v1_1.json`，result digest=`89163f5ef2a51341135d8dcb864a655ea1a4fe215ab796ac51075e84a969e88a`。
