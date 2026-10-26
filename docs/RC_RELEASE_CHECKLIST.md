# v1.0.0-rc1 发布检查表（候选，非 GA）

> 状态：**release candidate 草案**。404 独立复核已被用户豁免（**不是复核通过**）；
> 法务/视频/截图/公网部署未完成。完成本表“必须人工”项前，不得发布 GA、不得称“已上线/已验收”。

## 1. 当前基线

- 分支：`main`
- 提交：以 `git rev-parse HEAD` 为准（本文件生成时应记录）
- 全量：**2520 passed / 0 failed / 20 skipped**（Windows + Python 3.12.15，约 1466s）
- CI 快清单：**54 文件 / 649 passed / 1 skipped**
- 版本口径：`v1.0.0-rc1` 候选；app version 仍 `1.0.0`
- 404：**用户豁免，未独立复核**（记录见 `docs/QWEN_LEAD_DIALOGUE.md` §3）

## 2. 发布前自动检查（可执行）

```powershell
git status --short --branch          # 必须干净
git log --oneline -3
$env:A3_OFFLINE_DEMO="true"; $env:LLM_PROVIDER="none"
$env:DATABASE_URL="sqlite:///./output/release-check/db.sqlite"
New-Item -ItemType Directory -Force output/release-check | Out-Null
python -c "from backend.app.core.database import init_db; init_db()"
python -m pytest tests/ --basetemp output/release-check/base -o addopts= --benchmark-disable -q
ruff check --select=F821,F823,E9 backend/app scripts/ tests/
git diff --check
```

预期：全量 2520/0/20、ruff 通过、diff check 干净。若不同，先查环境/未提交改动，不要改文档迎合。

## 3. 必须人工完成（未完成不得 GA）

| 项 | 责任 | 证据 | 状态 |
|---|---|---|---|
| 404 独立复核 | 用户指定独立人/Agent | 复核报告 | **已豁免（不通过）** |
| 法务签署 9 项 | 法务 | 签署件 | 待办 |
| 素材 provenance 121 项 | 设计/产品 | `docs/ASSETS_PROVENANCE.md` 补齐 | 待办 |
| integrated-map bundle 处置 | 产品/法务 | 恢复源码或停止分发 | 待办 |
| 演示视频 7 镜头 | 产品/录制 | 视频文件/链接 | 待办 |
| README 8 张截图 | 产品 | 新截图 | 待办 |
| 公网/TLS/域名/备份/监控/PG 恢复 | 运维 | 演练记录 | 未验证 |

## 4. 版本与 tag（未执行，需用户批准）

当前**没有** git tag；不自动推送 tag。用户确认 rc 后执行：

```bash
git tag -a v1.0.0-rc1 -m "Triple-U v1.0.0-rc1 (release candidate; not GA; 404 waived, legal/deploy pending)"
git push origin v1.0.0-rc1
```

如果 tag 打错（尚未发布）：

```bash
git tag -d v1.0.0-rc1
git push origin :refs/tags/v1.0.0-rc1
```

**注意**：tag 一旦对外发布，不要静默移动；需要新 rc 版本号（如 `v1.0.0-rc2`）。

## 5. Release notes 发布正文

使用 `CHANGELOG.md` 的 `[Unreleased — v1.0.0-rc1 候选]` 段落，并保留 Known limitations 全部条目。
发布正文必须写明：

- 这是 **rc 候选**，不是 GA；
- 404 用户豁免、未独立复核；
- 法务/素材/视频/截图/公网未完成；
- 测试数字的环境口径（Windows + py3.12.15，离线）。

## 6. 发布后检查

1. GitHub Release 是否引用正确 commit/tag；
2. release notes 是否含 Known limitations；
3. 下载/安装包（如有）NOTICE/LICENSE 是否随包；
4. 不把“本地全量绿”写成“公网已验证”；
5. 记录 tag、commit、release URL、时间、操作人。

## 7. 停止条件

出现以下任一，停止发布并回退/修复：

- 全量或 CI 出现非环境性失败；
- 发现 secret/密钥进入仓库或发布物；
- 法务明确拒绝某项分发；
- 发布正文遗漏“rc/未独立复核/未验证”声明；
- 实际发布 commit 与测试 commit 不一致。
