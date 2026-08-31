# FIN 0.1.3 镜像与原生依赖供应链修复

日期：2026-09-01

状态：EXACT CLEAN BOUNDED NONPRODUCTION QUALIFICATION PASS / PRODUCTION IMAGE SUPPLY BLOCKED

分支：`codex/fin013-dell-s1-s2-product-bridge`

起点：`661145cd8c31ae471acdedb3db32047583e3fb85`

## 1. 本工作包解决什么

S1/131 已完成单一 Python 依赖源、PostgreSQL 支持画像、Dagster S2 shadow、真实容器 job 和 Workbench 有界回归，但最终两张镜像各保留 `236` 条 Grype raw finding；control-plane 的 `psycopg2-binary 2.9.12` 还携带 15 个 scanner 无法识别版本和归属的私有原生文件。因此本工作包只处理 S5 image/native supply：

1. 使用官方更新后的 Python 3.11.16 slim-trixie 镜像消除已有安全更新的 util-linux finding；
2. 不自研 PostgreSQL client，也不 fork Dagster；继续满足 `dagster-postgres 0.29.20` 对 `psycopg2-binary` 的硬依赖，但强制从官方 PyPI sdist 构建，使 `_psycopg` 动态链接 Debian `libpq5`；
3. 继续用成熟的 Syft、Grype、Debian Security Tracker 和 OpenVEX 标准保存、扫描和解释证据；不写自研 scanner 或 suppression engine；
4. exact clean commit 后重建、复扫并重跑真实 PostgreSQL/Dagster job，再决定这一有界修复是否可收口。

明确不在本工作包内：R14 修改或重跑、R15/R16、formal、外源补源、embedding/reranker/4B、Evidence admission、S2 authority bridge、S3、报告、产品或发布晋升。`D:\FIN_Insight_Agent\data\indexes` 未改。

## 2. 采用的成熟栈与没有采用的路线

### 2.1 Python 基础镜像

Dockerfile 从旧 index digest `9c900dea...bfc7` 更新到官方 `python:3.11.16-slim-trixie@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6`。linux/amd64 child manifest 为 `272efc3f...f8fc`。该基础镜像已经包含 Debian trixie 的 util-linux 安全更新 `2.41.5-0+deb13u1`；因此不手工升级九个相关包，也不运行不可控的 full-upgrade。

现有 OpenSSL 精确 overlay `3.5.7-1~deb13u2` 保留。移动 Debian mirror 加精确版本只能固定本次解析，尚不是长期字节级可复现；production 若要求长期复建，仍需 Debian Snapshot 或 artifact proxy。这个边界登记为后续基础设施项，不在本工作包自建镜像仓库。

### 2.2 PostgreSQL Python client

直接迁移 Psycopg 3 当前并不薄：Dagster `0.29.20` 仍硬依赖 `psycopg2-binary`，项目还会遇到异常属性和 URL 行为兼容面。当前最小路线是：

- 锁和 distribution identity 仍为 `psycopg2-binary==2.9.12`；
- 使用 uv `--no-binary-package psycopg2-binary --no-cache`，消费 lock 中已固定 SHA-256=`5ac9444e...294c` 的官方 sdist；
- 构建时临时安装精确 `gcc=4:14.2.0-1`、`libc6-dev=2.41-12+deb13u3`、`libpq-dev=17.11-0+deb13u1`；
- runtime 只保留 `libpq5=17.11-0+deb13u1` 及其 Debian 闭包；
- 同一层内恢复 apt manual marks 并 purge build closure；最终断言 gcc、pg_config、头文件、uv、pip 和 setuptools 均不存在；
- 用 `ldd`、`dpkg-query -S`、compile/runtime libpq version equality 和 vendored directory absence 证明系统链接。

这条路线是成熟组件适配，不引入第二套数据库 client、依赖解析器或供应链协议。Psycopg 3 可在 Dagster 上游支持或兼容面有独立证据后再作为 challenger，不在本轮强迁移。

### 2.3 VEX 工具

OpenVEX 是可采用的标准，Grype 原生支持消费 VEX；但最新稳定 `vexctl v0.4.4` 的官方 Windows binary 用同一 Syft/Grype 数据库自审得到 `19` 条 match，其中 `12 High` 且多项已有修复版本。因此该 binary 只保留为不可变拒绝证据，不进入项目门禁。

后续若生成 VEX，只为 exact final image identity 编写标准 OpenVEX JSON，并由现有 Grype `--vex` 验证。raw scan 永远保留；VEX 只表达来源和版本绑定的处置，不删除 finding，也不允许泛化为 package-name ignore。

## 3. dirty candidate 实测

证据根：

`Z:\FIN_Insight_Agent_qualification\20260901_image_native_supply_remediation_v1\artifacts\dirty-candidate-20260831T181128Z-de9bea87`

Dockerfile 的三次递增构建均成功；最后一张带完整 dpkg/build-tool assertion 的 control-plane image ID 为 `7946fa73...1b818`。现有扫描只绑定较早的 dirty control-plane candidate `de43348a...e9364`，Workbench ID 为 `d31431d5...2b134`；不得把 `de433...` 推定为 `7946...` 的等价镜像，后者尚未扫描。dirty 证据只证明方案方向可行，不能签 exact clean commit或最终 VEX。

原生 runtime probe SHA-256=`80f1503674624c4d59fb9579d8134b31f0a01c7f905c3633ca6f0eae733b99f9`；它在 attempt 路径中与 `de433...` 同次执行，但 probe 文本没有内嵌 image ID 或完整命令，因此也只作 dirty 方向证明。结果：

- UID/GID=`10001:10001`；
- `psycopg2-binary=2.9.12`；compile-time/runtime `libpq=170011`；
- `_psycopg` 通过 `/lib/x86_64-linux-gnu/libpq.so.5` 使用系统库；
- 19 个动态库目标全部由 dpkg 拥有；`psycopg2_binary.libs` 不存在；
- `gcc/cc/pg_config/uv/uvx/pip/setuptools` 不存在；
- Dagster `1.13.20` 和 dagster-postgres import 通过；
- probe=`PASS`。

使用 Syft `1.51.1`、Grype `0.116.1` 和冻结 DB schema `v6.1.9`（built `2026-08-30T06:27:52Z`）的 raw 结果：

| image | predecessor | candidate | delta | severity |
|---|---:|---:|---:|---|
| Workbench | 236 | 166 | -70 | 7 Critical / 31 High / 55 Medium / 11 Low / 51 Negligible / 11 Unknown |
| control-plane | 236 | 191 | -45 | 7 Critical / 35 High / 55 Medium / 11 Low / 72 Negligible / 11 Unknown |

Workbench 的 `-70` 与 util-linux 来源簇预期完全一致。control-plane 没有降到 166，是因为系统链接后 Syft 首次看见了 `libpq5 17.11` 及 Kerberos/LDAP 闭包：新增 `25` 条 raw match，其中 `4 High`、`21 Negligible`；`libpq5` 本身为 0 match。这是把过去 scanner 看不见的原生闭包变成 dpkg/PURL 可归责组件；raw 数增加本身不构成实际安全回退的证据，但新旧具体版本和可达性尚未完整比较，实际安全处置仍开放。

新增四条 generic krb5 High 必须继续保留在 raw scan。Debian 资料表明：`CVE-2007-3149` 实际归属 sudo 且 Debian sudo 未链接 krb5；`CVE-2007-5894` 在当前 trixie 已修复且 vendor dispute；`CVE-2026-40355/40356` 在 trixie `1.21.3-5+deb13u1` 已修复。它们是 source-bound OpenVEX 候选，不是当前 production PASS。

scan delta summary SHA-256=`2bf61302115ec76e9ab994910f7ebb60ef8ea1a56af670415097f76330b6ff2b`。两张镜像的三格式 SBOM、完整 Grype JSON、构建日志和 inspect 均保留，未覆盖 S1/131 的旧 raw 证据。

## 4. 当前判断与停止条件

两路作者分离、只读复审已经完成。Docker/code reviewer 的代码 finding 为 `P0/P1/P2/P3=0/0/0/0`，判定允许 nonproduction candidate commit；资格层仍有 `3` 个 P2，正是下列 exact image identity、真实 PostgreSQL/Dagster 和长期 apt reproducibility 缺口。VEX/evidence reviewer 独立复算 `191/166` 与 25 条差值，确认当前只能为最终 clean image 预备 OpenSSL 10 条和 control-plane krb5 4 条 source-bound VEX 候选；Python 17 条、gzip 和全部 Debian residual 继续保留。两份复审都不签 production PASS。

当前可以签的只有：

- util-linux 可修来源簇在 dirty candidate 中关闭；
- `psycopg2-binary` 私有原生库盲区改为系统 `libpq` 的方案实测可行；
- control-plane 新增 raw finding 来自可见依赖闭包，不是隐藏或删除告警；raw delta 本身不用于推断实际风险升降；
- 没有新增自研 scanner、client、scheduler 或供应链格式。

当前不能签：

- exact clean image qualification；
- 最后 asserted dirty image `7946...` 的 SBOM/scan，或 dirty probe 的 image-ID 自证；
- system-linked control-plane 对真实 PostgreSQL 的握手、Dagster run/event readback和真实只读 source job；旧 binary-wheel image 的成功纵切不能继承；
- image/native supply PASS 或 production deployable；
- 7 Critical、其余 High、Python source provenance 和 glibc/perl reachability 的最终处置；
- repository license/legal approval；
- 长期 Debian 字节级可复现；
- R14、S1 research quality、S2 authority、Evidence、产品或 release 的任何增量。

下一执行顺序固定为最小工程闭环，而非新规划阶段：

1. 独立复审当前 Docker diff 和 dirty evidence；
2. 通过后提交并推送明确的 nonproduction candidate；
3. 从该 exact clean commit 以 linux/amd64、`--pull --no-cache` 重建两张镜像，绑定 OCI revision/release ID；
4. 对 exact image IDs 重跑 runtime ownership probe、Syft 三格式和 raw Grype；
5. 用 fresh qualification root 重跑 PostgreSQL/Dagster full vertical、control-plane 真实只读 private-source job 和 Workbench smoke；
6. 只对有官方来源和 exact product/version identity 的项形成 OpenVEX，再由 Grype 原生消费并保留 raw/filtered 双结果；
7. fresh 独立复核后更新最终结论。任一 runtime、扫描、真实 job 或复核出现 P0/P1，保留失败并停在本 S5 工作包，不开新产品版本。

## 5. exact clean 重建与原生运行时复证

上述候选已经提交并推送为精确提交 `e965f235e41b219e38ff8d01783fa5df4eeaf2e9`。随后没有修改仓库，使用 `linux/amd64 + --pull + --no-cache + --load` 从该提交重建两张镜像，并把 OCI revision 与 `WORKBENCH_RELEASE_ID` 都绑定到完整提交：

| image | exact ID |
|---|---|
| Workbench | `sha256:e2ce7bdc9a8c347ec85d93f4cb8d37cc2e21e0a9fef57baadf1eb653ce03dcc3` |
| control-plane | `sha256:d76bf851c5e35f3a0a0b7c1dce69baf04d1d90a15f2df9ef4d8773cb02c7ebea` |

identity receipt 为 `exact-clean-e965f235/images/image-identity-receipt.json`，SHA-256=`7e128cad...72696`。Docker build check 为 0 warning。

control-plane 原生 probe 的第一次执行在全部实质断言已经打印 `probe=PASS` 后，因为 Windows CRLF 令尾部空行成为无效 shell command 而以 `127` 退出；该失败保留为 `control-native-probe.txt`、SHA=`99a207d7...5082`。同一 exact image ID 的 LF-only successor 没有弱化任何断言，退出码 0，probe SHA=`9d6a5184...f8d1`、receipt SHA=`e680c832...7299`。最终证明：

- `psycopg2-binary=2.9.12`，compile/runtime libpq 均为 `170011`；
- `_psycopg` 使用系统 `/lib/x86_64-linux-gnu/libpq.so.5`；
- 19/19 动态目标均由 dpkg 拥有；
- 私有 `psycopg2_binary.libs` 不存在；
- gcc、cc、pg_config、uv、uvx、pip、setuptools 和开发头文件均不在 runtime；
- Dagster `1.13.20` 与 dagster-postgres import 通过。

这关闭的是旧 wheel 原生闭包对 scanner 不可见的问题，不是 production CVE 门。

## 6. exact SBOM、Grype 与 OpenVEX

扫描绑定 exact image ID，工具为 Syft `1.51.1`、Grype `0.116.1`，使用冻结数据库 schema `v6.1.9`（built `2026-08-30T06:27:52Z`）。每张镜像都保存 Syft JSON、CycloneDX、SPDX、raw Grype 和 VEX-filtered Grype；raw 永不覆盖。

| image | SBOM components | raw | raw Critical / High | OpenVEX exact statements | filtered |
|---|---:|---:|---:|---:|---:|
| Workbench | 137 | 166 | 7 / 31 | 10 | 156 |
| control-plane | 197 | 191 | 7 / 35 | 14 | 177 |

OpenVEX 文档绑定最终 OCI IDs 和组件 PURL，使用 OpenVEX spec commit `d29fab0c...39ac` 的 schema 验证；文档 SHA=`34735e51...111f`。第一次 CLI quoting 失败、第二次 runtime profile 缺 locked supply group 均保留；successor 使用仓库已有 locked `supply` group 验证通过，没有临时安装包。Grype 对 ignored 结果逐项证明 namespace=`vex` 且只命中 10/14 个精确 allowlist ID；两张镜像的 7 个 Critical、Python generic 17 项、gzip 4 项和其他 Debian residual 都原样保留。

scan summary SHA=`ae787aae...74fa`，`conservation_and_allowlist=PASS`，但 `production_gate=BLOCKED`。VEX 不是“安全通过”或 suppression；它只把官方来源已经能证明的 generic 误配/已修复项从精确镜像的处置视图中标明。

## 7. exact clean 真实功能资格

### 7.1 fresh 宿主 PostgreSQL + Dagster vertical

第一次 preflight 因错误使用 D 盘仓库 `.venv` 被 `qualification_interpreter_must_be_under_qualification_root` 正确拒绝；随后两个 attempt 因 `PYTHONPATH` 没有同时包含 `src` 被导入门拒绝。三份失败日志均保留。successor 在 Z 盘创建 88-distribution locked env，显式绑定 `D:\FIN_Insight_Agent\src` 和仓库根，再运行完整 vertical。

attempt `20260831T192751Z-b379e7b1` 为 `bounded_engineering_pass`，result SHA=`a8a76d16...0d9`：

- PostgreSQL `16.15` transaction、UNIQUE、advisory lock、两次 restart readback 和 dump/restore 全部通过；
- Dagster run `SUCCESS`，11 个事件跨新 instance、重启和恢复后可回读；
- 1,319 observations，24/24 qrels；legacy、Dagster 与 tracked business projection SHA 都为 `794977ca...ca28`；
- 新生成 legacy/Dagster SQLite 物理 SHA 相等，均为 `363780c0...5ac4`；
- 临时口令扫描 1,890 个文件，0 match；容器、网络、secret 均清理；
- start/end 均绑定 clean `e965f235`，运行期间 implementation stable。

现有 current-bound S2 v1.1 的 self-digest 仍不合法；本 run 只作 immutable compatibility baseline，不修改、修复或迁移 S2 authority。

### 7.2 exact control-plane image 真实 job

旧外部 runner 的已知 P2/P3 没有被照搬。Z 盘 successor runner SHA=`732b35c9...79cc` 做了三项最小修正：

1. 复用现有 `fact_mart_semantic_projection`，除 `result_digest` 与三个 SQLite path/physical 字段外，未知顶层/storage 字段默认进入 exact 比较；
2. SQLite 先读取一次 bytes 并写入 attempt-owned snapshot，file SHA、header、integrity、schema 与 SQL 查询全部来自同一 snapshot；
3. 无 `ORDER BY` 的 natural-row digest 只作诊断，硬门只比较 columns、row count、sorted rows、schema 与完整 logical content。

runner 同时按 SHA 绑定 fresh host summary/result/SQLite、旧失败 summary 和旧失败 runner snapshot，没有改写 `SQLite 3.50.4 vs 3.46.1` 物理 SHA 假门的失败历史。

attempt `20260831T194006Z-86bca107...` 在 exact control image `d76bf...c7ebea` 内连接 PostgreSQL 16.15 并真正执行 Dagster job：run `48debabe-f84b-415f-8648-6c38d6c64e5c`、status=`SUCCESS`、16 events、1,319 observations、24/24 qrels。host/container 完整 semantic projection 均为 `794977ca...ca28`；SQLite physical SHA 不同但 snapshot-bound schema、sorted logical rows 与 logical content exact。secret match=0，container/network/volume/secret cleanup 全部成立。summary SHA=`49d44970...d580`。

### 7.3 exact Workbench 真实数据 smoke

没有重新发明 Workbench runtime 框架；新 thin runner 复用 S1/131 已验证的 `network none` 表示、三路 readonly bind、attempt state volume 和 default CMD/USER 合同，并按 SHA 绑定旧失败与已修正 successor。runner SHA=`997583d1...5787`。

attempt `20260831T194804Z-7b714d...` 在 exact Workbench image `e2ce...03dcc3` 上通过：

- 使用镜像默认 CMD 和 `10001:10001`，没有用 `--user` 或自定义 command 帮助通过；
- `/api/health` 200；`/api/readiness` 200、`all_ready=true`，DELL/MU/NVDA 三项均 ready；`/workspace` 200 且前端 root 存在；
- `/app/configs`、`/app/data`、`/app/reviewed-evidence` 为 readonly bind，只有 attempt state volume 可写；
- `network=none`，IP/gateway/IPv6 均空，无 host-published port；
- 容器内与 image/container inspect 中均没有已检查的 provider credential 名；pip/uv/uvx 均不存在；
- 容器和 state volume 清理成功。

summary SHA=`23dbd254...0cdeb`，状态严格为 `bounded_nonproduction_workbench_smoke_pass`。

### 7.4 全仓回归

在同一 clean commit 上执行：

`uv run --locked --extra control-plane --extra qualification python -m pytest -q`

结果为 `2671 passed, 5 skipped in 796.19s`，失败 0；log SHA=`ef070cd2...862d`。26% 附近的长停顿来自冻结 R14 mutation regression 的隔离子进程，不是继续开发或执行 R14 产品阶段。

## 8. fresh 独立复核

control-plane runner/attempt 的 finding 为 `P0/P1/P2/P3=0/0/0/1`。reviewer 独立复算 runner、summary、7 份 selected artifact、host/container result self-digest、default-closed projection、SQLite schema/row digests、image identity、旧失败链、secret 和 cleanup，允许 exact image 真实 PostgreSQL/Dagster `bounded nonproduction engineering PASS`。唯一 P3 是 future cleanup helper 必须区分明确 not-found 与 Docker daemon/transport error；本 attempt 的四类对象已被 reviewer 逐条原生 inspect 复核为明确不存在，因此不重跑。

Workbench runner/attempt 的 finding 为 `0/0/0/3`，允许本 attempt 的 bounded smoke PASS。三个 P3 只约束 future reuse：runner 应硬编码 DELL/MU/NVDA exact case set；敏感环境名应扩大或把 claim 缩窄为 known-provider prefixes；cleanup absence 也应区分 not-found 与 daemon error。reviewer 已直接核实当前 raw readiness 包含三家公司、完整 Env 无其他常见 secret 名、删除命令成功且对象不存在，所以不改写或重跑当前 attempt。

两个 reviewer 都明确拒绝 production、S2 authority、Evidence、R14/R15/R16、产品或 release 推广。

## 9. 最终收口判断

统一 qualification summary 位于：

`Z:\FIN_Insight_Agent_qualification\20260901_image_native_supply_remediation_v1\exact-clean-e965f235\qualification-summary.json`

SHA-256=`80f5121dc0a4186d59aaa41991262d5f6c12f332bce1e9365b0700194751943b`。

本工作包现在可以关闭的缺口：

- 官方更新 base 在 exact clean image 中消除了 70 条 util-linux 可修来源簇；
- `psycopg2-binary` 从 opaque vendored native 变成可由 Debian/dpkg/SBOM 归责的系统 libpq 闭包；
- exact control-plane image 已跑真实 PostgreSQL/Dagster job；
- exact Workbench image 已用真实只读产品对象通过 health/readiness/workspace smoke；
- raw/VEX 双结果守恒，完整回归不退化。

因此，`exact-clean nonproduction qualification=PASS`。但 `image/native supply production gate=BLOCKED`，原因仍为：每张镜像 7 个 raw Critical 与 residual High；Python generic、gzip 与 Debian residual 尚未完成 production disposition；发布时需最新 DB 复扫；license/legal 未签；长期 Debian 字节级复建仍缺 Snapshot/artifact proxy；production container hardening/operations 未做。

下一合法动作不是 R14、R15/R16 或下游产品阶段。应先由 Owner 决定：继续在 S5 做 production supply remediation，还是把当前成果冻结为非生产架构可行性证据并回到全产品技术栈迁移路线的下一个已批准能力面。无论选择哪条，current-bound S2 authority、Evidence、S3、报告、产品和 release 都不因本工作包自动变化，`D:\FIN_Insight_Agent\data\indexes` 仍未改。
