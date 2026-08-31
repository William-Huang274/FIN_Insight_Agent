# FIN 0.1.3 镜像与原生依赖供应链修复

日期：2026-09-01

状态：DIRTY CANDIDATE PROOF PASS / EXACT CLEAN REPROOF PENDING / PRODUCTION IMAGE SUPPLY BLOCKED

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
