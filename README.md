# FinSight

FinSight 是一个金融研究工作台。你可以围绕一个项目积累资料，发起研究，跟踪调查进度，再从报告回到引用的原文。研究记录和知识库保存在自己的部署中。

[中文使用指南](docs/public/quickstart.zh-CN.md) · [English quickstart](docs/public/quickstart.en.md) · [架构](docs/public/architecture.zh-CN.md)

## 开始使用

在仓库根目录运行以下命令。需要 Docker Compose 和 Python 3.10 或更高版本。

```sh
python scripts/deployment/initialize.py
docker compose up -d --build
```

打开 [本机工作台](http://127.0.0.1:8765/workspace/projects)。项目、资料与账户服务使用本机数据库。启用模型研究还需要配置原生执行服务、模型访问权限和预算，具体步骤见使用指南。

| 入口 | 用途 |
| --- | --- |
| [项目](http://127.0.0.1:8765/workspace/projects) | 管理项目、资料和研究成果 |
| [研究会话](http://127.0.0.1:8765/workspace/session) | 设置研究问题、模型、附件和执行方式 |
| [对话](http://127.0.0.1:8765/workspace/assistant) | 就已有材料提问，追踪对话与交接 |
| [资料库](http://127.0.0.1:8765/workspace/assets) | 管理资料及可检索的版本 |

[方法示例](examples/skills/source-comparison/SKILL.md) · [本地快捷测试](scripts/dev/verify_public_checkout.py)
