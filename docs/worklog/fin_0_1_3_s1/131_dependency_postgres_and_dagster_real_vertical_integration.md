# FIN 0.1.3 单一依赖源、PostgreSQL profile 与 Dagster S2 shadow 纵切

日期：2026-08-31
状态：EXPLICIT NONPRODUCTION CANDIDATE / D127 EXACT ATTEMPT FAILED AT PREEXISTING S2 DIGEST / SAME-STAGE FIX TESTED / NEW CLEAN ATTEMPT PENDING / PRODUCT DELTA 0
分支：`codex/fin013-dell-s1-s2-product-bridge`

## 1. Owner 授权与本工作包边界

Owner 已要求停止继续扩写 R14，并纠正“所有通用能力都由 FIN 自研”的方向。本工作包只完成成熟栈优先重基线中的三个有界工程前置：

1. 把 Python 依赖统一为一个人工维护源和一个机器生成锁；
2. 建立一个可重放的 PostgreSQL 本地支持画像，验证事务、约束、锁、重启、备份恢复与 Dagster run/event storage；
3. 只把现有 S2 CompanyFacts materializer 接成一条 Dagster shadow 纵切，不改写 FIN 业务规则。

明确不在本工作包内：R14 修改或重跑、R15/R16、formal、外源补源、embedding/reranker/4B、Evidence admission、S2 产品 bridge、S3、新报告、产品晋升、production cutover、legacy 删除与发布。`D:\FIN_Insight_Agent\data\indexes` 保持未动。

## 2. 依赖结构

### 2.1 唯一权威与支持 profile

- 人工维护的唯一 Python 依赖源：根 `pyproject.toml`；
- 机器生成的唯一通用锁：根 `uv.lock`，由 uv `0.10.7` 生成并用 `uv lock --check` 验证；
- 旧 `requirements.txt` 与 `requirements-retrieval-eval.txt` 退出，不再作为生产或 CI 权威；
- Docker 与 CI 均使用 `uv sync --locked`；
- build backend 和 uv build constraint 同时固定 `setuptools==84.0.0`，避免构建隔离环境重新选择未审版本；
- `core` 只含 Workbench 当前运行所需依赖；
- `control-plane` 只增加 Dagster `1.13.20`、dagster-postgres `0.29.20`、dagster-webserver `1.13.20` 与 filelock `3.32.4`；
- `qualification` 是测试覆盖层，只增加 psycopg/binary `3.3.4`，不进入 control-plane 镜像；Dagster PostgreSQL runtime 自身使用其上游闭包中的 psycopg2-binary；
- `dev` 使用 pytest `>=9.0.3,<10`、psutil 与 httpx2。Starlette `1.6.0` 的官方 TestClient 已改用 httpx2；本仓用 FastAPI `0.141.1` + Starlette `1.6.0` + httpx2 `2.12.0` 实例化真实 TestClient 并返回 HTTP 200，不是误把旧 `httpx` 模块当依赖；
- `supply` dependency group把 pip-audit `2.10.1`、CycloneDX BOM `7.3.1`、pip-licenses `5.5.5`与build backend `setuptools 84.0.0`纳入同一`uv.lock`，工具运行环境与业务runtime profile分开；当前lock共解析`157`个package records且setuptools已有artifact hash，不能把lock全图数量当作任一运行环境的安装数量。

默认 core 缺少 torch/sentence-transformers 时，learned Qwen retrieval runtime 不再在 Workbench 构造阶段硬崩，而是走既有 deterministic/non-hybrid 路径；显式请求该 learned runtime 时仍返回 typed missing-runtime failure。这个变化属于可选依赖边界修正，不得写成“所有研究输出完全不变”，也不构成 retrieval 质量晋升。

### 2.2 Python 供应链证据

候选实现早期已生成 predecessor manifests：

`Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\manifests\20260831_locked_profiles_v2`

| profile | 实际环境 CycloneDX components | license inventory entries | pip-audit dependency rows / known vulnerabilities |
|---|---:|---:|---:|
| core | 33 | 33 | 33 / 0 |
| control-plane | 86 | 86 | 86 / 0 |
| control-plane + qualification | 88 | 88 | 88 / 0 |

工具版本：CycloneDX BOM `7.3.1`、pip-licenses `5.5.5`、pip-audit `2.10.1`。这里的“0”只表示扫描时这些 Python 环境没有被数据库识别出的已知漏洞；不是未来保证，不覆盖 Node、Debian/Alpine、容器镜像、第一方代码或法律审批。license 文件是 inventory，不是法律批准；control-plane 闭包含 LGPL 标识，qualification 还含 psycopg 的 LGPL-3.0-only 标识，部署前仍需项目级 license 决策。仓库自身尚未用本工作包补造 LICENSE。

CI 对本工作包晋升的 core、control-plane、control-plane+qualification 三个 profile增加 locked export、pip-audit、reproducible CycloneDX和第三方 license inventory；工具从独立 locked `supply` 环境运行，并增加 profile间的正/负 import断言。CI 的 requirements-based SBOM会保留 marker 展开，因此组件数可能与单一 Windows/Python 3.11实际安装环境不同；文档不得再把“已安装数量”“export SBOM组件数”和“audit row数”混写成一个数字。既有 `complex-pdf`、`external-search` extras并未在本工作包获得生产晋升或完整供应链签发，不得用这三个 profile的结果覆盖它们。

本工作包当前只签 **CPython 3.11** 的开发、CI与qualification画像。项目元数据仍声明 `requires-python >=3.10`，本轮没有足够证据把全项目兼容面悄悄缩成3.11，也没有为3.10/3.12/3.13建立同等级矩阵；因此“3.11以外兼容”既未被否定，也未被本工作包签发。若后续要发布为多Python版本支持，必须补对应lock resolution、安装、import、测试和供应链矩阵，或另行作出明确的兼容性变更决定。

Python distribution级 SBOM/pip-audit看不到 wheel内捆绑的 `libpq`、OpenSSL等全部原生组件；尤其control-plane由Dagster闭包带入`psycopg2-binary 2.9.12`，qualification另含`psycopg-binary 3.3.4`。所以最终两镜像必须再做OS/image/native层SBOM与CVE扫描并保留原始finding；如果工具仍无法展开wheel内原生库，这个盲区必须作为部署阻断边界留下，不能拿“Python 0 known vulnerabilities”替代。

成熟扫描栈的当前可用主链是：Syft `1.51.1`生成最终runtime filesystem的原生JSON＋CycloneDX＋SPDX SBOM，Grype `0.116.1`消费Syft SBOM做Debian/Python/Node及可识别binary package的CVE匹配；两者均已在Z盘按官方release checksum固定和执行。Docker Scout只作可选交叉验证；本机Scout CVE因Docker ID认证未满足不能出具漏洞结论，这不是PASS。

原计划作为wheel原生库补充检查器的OSSF CVE Binary Tool `3.4`已真实安装到独立hash-locked环境，但其完整闭包自审发现`cryptography 46.0.7`与`httplib2 0.20.4`共6个已知finding；上游`3.4.1rc0`仍无条件依赖legacy `gsutil`，无法解除这条约束链。项目拒绝通过`--no-deps`、手改metadata或强行覆盖版本把它洗成PASS。尚未稳定发布、已移除`gsutil`的上游commit只能作为commit-pinned challenger另测，不能进入正式门禁。因此当前正式状态不是“三个scanner均通过”，而是`Syft + Grype可执行 / CVE Binary Tool稳定版拒绝 / native补充门未满足`。独立复审指出最初只有hash lock、缺原始失败审计收据后，已重新使用pip-audit `2.10.1`对完整lock执行严格审计并持久化：退出码`1`、2个脆弱package／6条vulnerability records，原始JSON SHA-256=`7096a0c99f1463d2277b41df10c948d81f625794bc98e435ade50f183026f924`，receipt SHA-256=`fb86521cbe3b9e6d4636ff3aa4e3b613540ea9e9724649a77d11b802c9614394`，位于`Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\artifacts\scanner-self-audit\cve-bin-tool-3.4`。这补齐拒绝依据，不把该工具转成可用门禁。

Syft能够列出ELF、import关系与部分binary package，但对wheel中hash重命名的`libpq/libssl/libcrypto`没有完整的versioned package classifier保证；Grype没有准确version/PURL/CPE就不能凭空匹配CVE。当前`dagster-postgres 0.29.20`又硬依赖`psycopg2-binary`。因此本轮最多签本地shadow资格，当前control-plane镜像不能被签成production-deployable；production cutover前必须验证source-built psycopg2＋系统libpq/libssl，或上游支持的Psycopg 3 system-linked路径，并重跑native/CVE/并发/恢复门。

前端 `package-lock.json` 的首次真实 `npm audit --package-lock-only --audit-level=high` 暴露 `nanoid 3.3.17` 高危 finding；没有降级门槛，而是把唯一传递节点升级到 `3.3.18`。同一 pinned Node 22镜像复验为 `122 dependencies / 0 known vulnerabilities`。这仍不代替最终 workbench image扫描。

上述v2 manifests生成于`supply` group进入lock之前，实际runtime profile的33/86/88安装集合仍可作候选历史证据，但其`uv.lock` identity已被`157`-record successor取代。最终qualification必须从全新`control-plane + qualification`环境重建，并由runner收据绑定完整installed-distribution inventory、关键direct version、解释器位置、`pyproject.toml`与`uv.lock` SHA；最终Python supply manifests也必须从提交后的exact lock重建，旧环境或旧manifest不能替代。

## 3. Dagster adapter 的真实责任

`src/sec_agent/adapters/dagster_s2_fact_mart.py` 不复制 CompanyFacts、PIT、period/unit、qrel 或 mutation 业务逻辑；它调用既有 `scripts.data_retrieval.build_s2_company_financial_fact_mart`。但它也不是“67 行、无锁、只传三个路径”的空壳。当前 adapter 的工程 plumbing 明确包括：

- policy/output root containment 与现存目录检查；
- 每个 Dagster native `run_id` 建独立 fresh目录，拒绝不安全 run ID、已有目录和旧 SQLite/JSON覆盖；
- 每个 approved output root 一个成熟 `filelock`，避免同一 builder 临时文件并发冲突；
- 最长 900 秒、不可由调用方放大的 subprocess timeout；
- 子进程环境 allowlist，不向 builder传递数据库 URL、API key 等父进程凭据；
- result self-digest、SQLite存在性和 SQLite byte digest复核；
- Dagster op/job/Definitions，仅作为外层 workflow adapter。

这是“业务逻辑薄、运行边界明确”的 adapter，不是新的 FIN 自研 scheduler、retry engine、数据库、产品状态机或 Evidence authority。

## 4. PostgreSQL / Dagster qualification runner

固定镜像：

`postgres@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`

该 digest 在本机解析为 PostgreSQL `16.15`、Alpine `3.24.1`、linux/amd64。runner 的最终合同包括：

- qualification root 必须真实包含于 `Z:\FIN_Insight_Agent_qualification`；
- Python解释器也必须位于同一 qualification root 下；
- 运行前 Git工作树必须 clean；开始/结束绑定 HEAD、status/diff SHA 与关键文件 SHA，并要求执行期间完全稳定；
- 收据记录完整安装包 inventory 与关键 direct versions，拒绝错误或含已安装第一方 project 的环境；
- container/network 使用完整 UUID 名称和 attempt label；清理前必须验证 exact ownership；
- Windows本地qualification的金融builder与Dagster client运行在宿主进程；Docker Desktop实测中`--internal`会使已发布的loopback端口对宿主不可达，而且不能隔离宿主client。该拓扑改用attempt-labeled dedicated bridge，Engine必须回读`Driver=bridge`、`Internal=false`、默认host binding=`127.0.0.1`、唯一network attachment、创建请求中的loopback binding，以及container启动后`NetworkSettings.Ports`的唯一实际`5432/tcp -> 127.0.0.1:<host-port>`；这只限制数据库的宿主暴露面，不宣称阻断container或host-runner egress；
- CI中的Dagster client与PostgreSQL都在container内，继续使用internal network且不发布数据库host port；本地修正不得扩散成CI网络放宽；
- secret 目录在写密钥前限制 ACL，密码不进入结果；cleanup 必须证明 container、network、secret file 与 secret directory 均已消失，否则不能 PASS；
- PostgreSQL rollback、UNIQUE、advisory lock、stop/start readback；
- Dagster run/event storage 写入、新 instance读回、PostgreSQL再次重启后的读回；
- 要求 PIPELINE_START、STEP_START、STEP_SUCCESS、PIPELINE_SUCCESS 等真实 event；
- `pg_dump --format=custom` 先从容器复制到 host，再由 host artifact复制回不同容器路径并恢复到新数据库；恢复库必须读回相同业务行与同一 Dagster run/event；
- 本纵切没有 schedule/sensor，因此 schedule storage user write/read明确记录为 `not_exercised`，不得冒充已测。

## 5. 真实数据纵切与 Docker 运行合同

输入不是手工 fixture，而是 policy用 digest固定的本地 DELL、MU、NVDA SEC companyfacts/submissions captures。它们位于 ignored `data/raw_private`，不进 Git，也不进镜像。可重放者必须预先具备 policy列出的 12 个 capture/metadata对象且 digest匹配。

Docker control-plane target：

- 固定运行身份 `WORKBENCH_IMAGE_KIND=control-plane`、`WORKBENCH_RUNTIME_PROFILE=dagster-postgres-shadow`；
- Workbench和control-plane两个 final target都以固定非 root UID/GID `10001:10001`运行；默认 Workbench `data` mount改为只读，数据构建只能由显式外部 job完成；
- 镜像写入不可由 runtime env伪造的 OCI source/revision、image kind与runtime profile labels；build时必须把 clean commit同时传入 `WORKBENCH_RELEASE_ID`与OCI revision；
- control-plane `ENTRYPOINT`是极薄的 secret-file launcher，默认 `CMD`参数仍为官方 Dagster `dev`；launcher只从 `DAGSTER_POSTGRES_URL_FILE`读取 PostgreSQL URL，在进程内设置 Dagster所需 env、移除 file pointer并 `exec`官方 `dagster` CLI，不打印 secret；
- `compose.yaml` 的 opt-in `control-plane` profile把宿主 `raw_private` 只读挂载到 `/app/data/raw_private`，把输出写到独立 state volume；
- `configs/control_plane/s2_fact_mart_shadow.run_config.example.yaml` 给出成熟 Dagster CLI所需的最小 run config；
- Compose使用官方 environment-backed secret source：宿主只提供 `DAGSTER_POSTGRES_URL`，Compose把值物化为容器内 `/run/secrets/dagster_postgres_url`，resolved model只保留变量名；验证一律用 `docker compose --profile control-plane config --quiet`。CI另用无敏感性的占位URL真实执行`docker compose run`，要求容器UID 10001可读且文件owner/group/mode为`10001:10001/0400`；直接 `docker run`资格使用attempt-scoped只读secret file并做同类证明。只通过手工bind文件不能替代Compose路径本身的证明。

CI只有仓库内容，没有 private captures，因此 Docker CI只能证明镜像身份、adapter import和 PostgreSQL-backed默认控制面启动；不能宣称 CI跑过真实 job。最终本地资格必须额外用只读 `D:\FIN_Insight_Agent\data\raw_private` mount真实执行 job并保存独立收据。

安全事件：旧 Compose曾把宿主 provider API key直接映射进 service environment；一次普通 `docker compose config`因此把一枚真实 EIA credential展开到诊断输出。当前仓库已删除 FMP/EIA默认映射，数据库 URL也不再通过 Compose interpolation进入resolved model；但仓库修复无法撤销已暴露的外部 credential，Owner仍必须在提供方轮换该 key。禁止为了清日志读取或修改旧 Codex live SQLite/JSONL。

## 6. 不可变失败与历史结果

以下 attempt 保留为历史调试证据：

1. `20260831T032558Z-2300a528`：只看 `pg_isready`，误把 official image initdb 临时 server当最终 server；
2. `20260831T032728Z-2c296ed6`：错误把 psycopg 3 `executemany` 当 connection API；
3. `20260831T032838Z-*`：修正 readiness/API 后继续暴露早期 runner边界；
4. `20260831T034026Z-a8700e1b` 与 `20260831T040515Z-eb3bd7b5`：当时代码可得到 bounded PASS，但没有绑定后续 adapter、lock、cleanup、runtime inventory与 backup round-trip hardening。
5. exact clean commit `4817a556...`首次preflight被仓库ignored的`src/finsight_agent.egg-info`元数据影子拒绝；失败收据保存在`final-clean-4817a556/preflight-failures/20260831T174102+0800-first-party-metadata-shadow.json`，该生成目录已可恢复地移到Z盘quarantine，未删除用户源码或索引；
6. `20260831T094310Z-ac7fd1d9`：official PostgreSQL最终PID 1、container-local `SELECT 1`、clean implementation binding、secret scan和ownership cleanup均通过，但Windows宿主`psycopg`连接`127.0.0.1:55432`超时。结果/日志SHA-256分别为`ce6be960...f729a`／`af6260a1...545d9`。同Engine无secret A/B证明ordinary bridge+loopback可达、`--internal`+同loopback publish不可达，最早错误因此是host-runner网络拓扑合同；失败attempt保持不可变，修复后只能用新attempt ID。独立诊断收据保存于`artifacts/network-topology-diagnostics/20260831T181951+0800/receipt.json`，SHA-256=`ddf8a4e3...db7d0`，记录Docker Engine 29.5.2／Docker Desktop linux-amd64、两组精确命令、inspect、localhost结果与四个对象cleanup；明确`diagnostic_only=true / final_qualification=false`且不向其他host/Engine泛化。

因此 `034026`/`040515` 不再是当前实现的“最终证据”，不能用于关闭当前工作包。失败与旧 PASS均不覆盖、不删除。

## 7. 截至候选实现冻结前的验证

- `uv lock --check`：PASS，lock解析`157`个package records；独立`supply` env与build backend精确版本可执行；Z盘Syft/Grype通过版本与发布checksum校验，CVE Binary Tool稳定版因自身闭包6个known findings被明确拒绝，不能计为工具门PASS；
- `git diff --check`、YAML parse、`docker compose --profile control-plane config --quiet`：PASS；
- active baseline=`213 Python / 8 frontend / 0 forbidden`、archive redirect=`6059 / PASS`、repository secret scan=`8325 files / 0 findings`；
- runner/adapter/launcher/S1/CUDA/EvidencePack最新作者短门：`37 passed, 2 skipped`；作者分离代码／安全review另跑`60 passed, 1 skipped`。skip是缺可选 CUDA/torch或环境条件，不被伪装成 PASS；
- qualification adapter/runner/secret launcher直接短门：`36 passed`，覆盖路径逃逸、run-scoped replay、锁、timeout、digest、缺 SQLite、凭据剥离、secret不回显、module origin、cleanup ownership、secret scan、固定uv locked-profile check、首尾HEAD/branch绑定，以及最终summary写盘前的内存敏感值扫描；
- exact-clean首次失败后的同阶段网络修正短门先为`tests/qualification=51 passed`，补入credential/proxy、启动后effective port mapping和CI database无host-publish回归后最新为`59 passed`；另用临时Docker对象真实回读dedicated bridge为`Driver=bridge / Internal=false / host_binding_ipv4=127.0.0.1`，container为唯一attempt network且`5432/tcp`精确绑定loopback，探针对象结束后均已移除。该结果只验证修正合同，不替代新的完整qualification attempt；
- Workbench只读数据／可写状态分离针对性回归：`10 passed`；镜像现在从`/app/data/workbench_private`读取产品私有输入，并把运行SQLite写到`/app/state/workbench.sqlite`，修复了默认只读data mount下启动即报`unable to open database file`或空state缺readiness对象的问题；
- Workbench EvidencePack route targeted：`9 passed`；
- FastAPI/Starlette/httpx2真实 TestClient：HTTP 200；
- 前端 npm audit首次 `1 high`，升级 nanoid后复验 `0 critical / 0 high / 0 moderate / 0 low`；typecheck/build/E2E仍需最终门；
- 当前候选全量回归：`2630 passed, 5 skipped in 2112.20s`，退出码0。运行前fresh审查曾发现`LazyLocalQwenHybridCandidateRuntime.retrieve_many`被错误缩进成依赖probe内的不可达嵌套函数；作者主动中止旧全量、恢复类方法、加入无模型加载的接口/参数委托回归，再从零复验。两位作者分离reviewer最终均确认当前提交门P0/P1=`0/0`；治理review发现的“candidate与bounded adoption混写”已修成`implementation candidate=true / final bounded adoption=false`，未使用且未精确pin的`INSTALL_OS_PACKAGES` bash/git逃生路径已删除。剩余两个P2只属于production hardening：可信builder/provenance与Debian snapshot／artifact mirror；不在本候选内自研替代系统。
- 当前dirty-candidate Workbench与control-plane镜像均从源码真实构建，locked Python安装、前端1,676模块production build、UID10001、revision和Dagster import通过；本机真实Compose environment-backed secret物化为`10001:10001/0400`且非root可读。镜像基础已从Python 3.11.15 successor切到官方`python:3.11.16-slim-trixie@sha256:9c900dea...bfc7`；三个OpenSSL Debian包精确固定并升级到`3.5.7-1~deb13u2`，没有执行浮动全系统upgrade；uv依赖下载采用官方建议的BuildKit cache mount，runtime移除uv、system pip/setuptools/ensurepip。v6内真实运行身份为Python 3.11.16、Expat 2.8.3、OpenSSL 3.5.7。它们仍绑定dirty candidate，只证明提交前可构建，不替代clean commit最终镜像与真实job。
- 候选镜像供应链失败证据没有被覆盖：v1两个镜像各有Grype raw `352` matches（`11 Critical / 94 High`）；Python 3.11.16与初步runtime清理后的v5为`281`（`8 Critical / 60 High`）；精确OpenSSL修复后的v6为`236`（`7 Critical / 31 High`）。v6完整Syft三格式SBOM与Grype JSON保存在`Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\artifacts\image-supply-candidate-v6`，Grype JSON SHA分别为Workbench `29df26c8...bb8`、control-plane `2eb768c7...74aa`。raw OpenSSL Critical已归零；剩余Critical来自Debian stable的glibc/perl，当前stable仓库无可安装修复版。generic binary catalog仍会把Debian回补信息丢失后的`/usr/bin/openssl 3.5.7`和Python CPE单列，必须用来源绑定triage/VEX而非静默ignore；Python 3.11.16官方发布说明已包含CVE-2026-4224、CVE-2026-3644与Expat hash-flooding修复。未经triage的raw数字、wheel native盲区与stable无修复项共同阻止image supply PASS和production结论。

最终 clean qualification、最终 Docker真实 job、两个最终镜像SBOM/CVE/native扫描、frontend E2E与最终治理/供应链复审仍待后续收据填写。本节状态因此是implementation candidate，不是已完成adoption。

## 8. 完成门与停止条件

只有同时满足以下条件，才把本工作包改为 bounded engineering PASS：

1. 提交当前同阶段的 S2 producer digest composition、qualification harness signed-payload 与 private output 修正，使 receipt v1.2 runner 从新的 clean commit 运行；网络拓扑修正已由 `d127e327...` 冻结，不得把旧修正冒充为当前待提交项；
2. 新建空 qualification env，精确执行 `uv sync --locked --no-dev --extra control-plane --extra qualification --no-install-project`；
3. runner PASS，repository/runtime/start-end binding、cleanup、restart、host-roundtrip backup/restore、Dagster run/event与 1,319 observations / 24 of 24 qrels全部可独立复算；
4. 最终 control-plane image从同一 commit构建，默认 CMD启动，并以只读 private source mount真实执行 Dagster job；
5. 生成 Python与镜像 SBOM/CVE证据，任何 finding都如实保留并决定隔离/修复；
6. 最终全仓回归、active baseline、archive redirect、secret scan、frontend门按风险通过；
7. fresh作者分离 reviewer对代码、供应链和治理文档复审，P0/P1/P2/P3归零或留下明确阻断。

任一核心门失败时，只在本工作包内形成新 attempt并修最早责任层；不借失败开启 R15/R16，不弱化 validator，不改变 R14、Evidence、S2 bridge或产品权限。

## 9. 当前权限结论

- 单一依赖/lock implementation：candidate，等待 clean commit与最终回归；
- PostgreSQL本地支持画像：旧 attempt提供可行性证据，当前 hardened runner最终复证待跑；
- Dagster S2 shadow adapter：代码 candidate，尚未用最终 commit签发 bounded adoption；
- production PostgreSQL/Dagster cutover：false；
- schedule/sensor、daemon/operator、HA、TLS、secret manager、PITR、多租户：未资格；
- LangGraph：HOLD，当前确定性数据纵切没有 inner-agent checkpoint/HITL需求；
- legacy deletion：0；
- product/research authority delta：0；
- R14和全部下游门：不变。

## 10. d127 exact-clean attempt 与结果摘要根因

网络修正已提交并推送为 `d127e32715abe76abfd326be173c627bfd061bbe`。随后从新的 Z 盘根创建 Python 3.11.14、uv 0.10.7、88 个实际 distribution 的 fresh locked 环境，并以新 attempt `20260831T110518Z-a77be8f5`运行完整纵切。该 attempt 已通过：

- dedicated bridge 的 requested/effective `127.0.0.1`绑定；
- PostgreSQL 16.15 transaction rollback、UNIQUE、advisory lock、三行 readback与 restart readback；
- clean start/end implementation binding；
- container/network/secret cleanup；
- secret scan `1275 files / 0 matches`；
- 0 model、0 provider、0 financial-source network call。

它在启动 legacy/Dagster S2 builder之前以 `tracked_s2_result_self_digest_invalid`终止。失败 result SHA-256=`ef14bfa4...54e23`，container log SHA-256=`49eabad8...80cf`。该失败不可变保留于：

`Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\final-clean-d127e327\artifacts\postgres-dagster-s2\20260831T110518Z-a77be8f5`

后续只读诊断证明这是两个不同责任层的缺陷：

1. **S2 producer envelope**：`build_company_fact_mart()`返回的内层对象已有 `result_digest`；CLI 将它展开到外层 unsigned，再以同名外层字段覆盖。tracked v1.1 文件 SHA=`4dd68cb1...e6c22`，历史 claimed digest=`0c25c917...95a1`，正常 canonical recompute=`e3f955dc...05fd`。从持久化正文恢复内层 digest=`a7094622...656ce` 后，能精确重建历史 claimed outer digest，证明不是随机损坏。
2. **S5 qualification harness**：`run_fact_mart_builder()`读回已签名 JSON 后又注入 `qualification_cli_stdout`，会再次破坏任何正确新结果的自摘要；stdout 从未被其他消费者使用。

同阶段最小修正没有创建 corrected S2 result v1.2／current S2 authority successor，没有改 current-bound v1.1，也没有迁移 S2 authority；这里的 qualification receipt schema v1.2 只是本纵切的收据合同版本，不是 S2 result 版本或产品版本：

- producer 先校验内层摘要并从外层 preimage移除；外层 finalizer禁止 `result_digest`再入口以及除 `status`外的保留字段覆盖；
- v1.0 与 current-bound v1.1 都进入精确 protected output集合；builder与Workbench默认写私有可变 result；
- qualification reader不再修改 signed payload，读回即走正常 self-digest validator；Dagster adapter继续独立验证 result与SQLite digest；
- current-bound v1.1只允许 canonical path + exact file SHA + claimed/canonical三元组 + runtime registry R39／policy v1.14／receipt v1.15 绑定的 shadow parity兼容；receipt明确 `self_digest_valid=false`、`current_s2_authority_self_integrity_pass=false`、`current_s2_authority_migration_authorized=false`；
- semantic projection默认比较所有顶层字段，只排除 result digest和路径相关SQLite字段；`schema_version`、`recorded_at`、`research_as_of`、`authority`、`policy_ref`任一漂移都会失败；
- producer、Dagster adapter与qualification三份 canonical JSON实现用中文、嵌套和乱序键做交叉回归。

21:57诊断patch的定向组合为`80 passed`；作者分离复核随后补齐同一bytes快照、现有current-runtime policy/receipt validator复用、registry重复ID拒绝、receipt/registry identity交叉绑定以及未来未知storage语义字段fail-closed。最终增量后的qualification、S2 builder、Workbench catalog、current registry/binding与S1d相邻组合为`123 passed in 19.82s`。最终 patch fresh rebuild保存于：

`Z:\FIN_Insight_Agent_qualification\20260831_production_dependency_and_vertical_v1\artifacts\tracked-s2-result-integrity-diagnostic\20260831T215722+0800-final-patch`

fresh result file SHA=`eccd53b1...e5b17`，claimed/recomputed digest均为`fda4b03e...cb90`，SQLite SHA=`363780c0...5ac4`，1,319 observations、24/24 qrels、mutations all pass，完整 semantic projection与current-bound artifact exact，projection SHA=`794977ca...ca28`。诊断 receipt SHA=`d0647343...54fc`。这些是 working-tree root-cause evidence，不是 final clean PostgreSQL/Dagster qualification；下一合法动作是提交同阶段修正，从新 clean commit、新 locked env和新 attempt ID重跑完整纵切。
