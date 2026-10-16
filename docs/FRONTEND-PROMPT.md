# 前端开发启动提示词 v2（A3 ）

> **用途**：新窗口开 Claude Code 时把下面 PROMPT START → PROMPT END 之间整段贴进去作为第一条消息
> **角色**：开发者 A（前端主线 + 演示门面）
> **当前真实日期**：2026-06-25
> **演示日**：2026-07-23（剩 28 天）
> **历史 v1**：6/24 写，覆盖 Phase 0 启动；v2 覆盖 v5.1 计划 + 已完成现状 + 宠物化创新点

---

## ⬇️ 复制下面整段（含 PROMPT START → PROMPT END）

```
===PROMPT START===

你是项目「A3 智学领航 / 个性化学习多智能体系统」的开发伙伴。我是开发者 A，负责前端主线 + 演示门面，队友 B 负责后端算法。最终交付物是第十五届中国软件杯演示日（2026-07-23）的前端 + 一键 docker 部署 + PPT/视频。

# 0. 真实时间线（必读）

* 今天：2026-06-25
* 距演示日：28 天
* 当前进度：今日 6/25 一日内已提前完成 v4 计划的 11 个 day 产出（Phase 0 框架 + W2 6 天 + W3 Day 1）
* 当前指导计划：`开发日志/2026-06-25-A-前端启动双人开发计划.md`（v5.1 版本）
* 距 7/22 晚提交：27 天（节奏舒缓，user 要求"细细打磨"）

# 1. 项目背景速览

* 赛题：第十五届中国软件杯 A3「基于大模型的个性化资源生成与学习多智能体系统」，出题企业科大讯飞
* 团队：A（前端 + 演示）+ B（算法 + benchmark）
* 后端态势：100% 完成（13 创新点 / 84 v1 API / 1338 测试 / 14/14 演示资产健康检查 / Cockpit 聚合端点就绪 / 16 模块 mypy strict）
* 后端 6/29 起已修了 P0-2 counterfactual + P1-1 KG 13 节点 + P1-2 attribution 9 题 + P1-3 ledger 5 来源；P0-1 radar_labels 编码部分修但仍有 4/6 mojibake（前端 safeRadarLabels 兜底）
* 演示日：约 2026-07-23

# 2. 必读文档（开工前 1h 看完）

按优先级：

1. **`开发日志/2026-06-25-A-前端启动双人开发计划.md`** — v5.1 计划，含 28 天细排 + 宠物化创新点（§十六）+ 字段对账 + B 协作清单。**最重要**。
2. **`docs/api/CONTRACT-FROZEN-2026-06-30.md`** — 6/30 接口冻结后的 84 路由 + 字段；任何后端字段变更必须走 §6.2 流程（A+B 双签）。已签字 A，B 待补。
3. **`docs/api/cockpit-endpoint.md`** — Cockpit 9 字段契约，CockpitView 的"圣经"。
4. **`docs/api/COMPONENT-CONTRACT.md`** — 199 行前端组件契约（14 cockpit + 5 shared + 5 playground + 字段映射 + 兜底）。
5. **`开发日志/A-框架交付清单.md`** — 给 B 看的 8 子块 P0/P1/P2 优先级。
6. **`开发日志/2026-07-04-A-前端Day6.md`** — Day 6 战报，最近实测发现 + B 修复验证。
7. **`docs/10-学术与工程创新对照表.md`** — 13 创新点答辩弹药。
8. **`docs/06-演示视频脚本与答辩准备.md`** — 7 分钟演示路径 + 20 页 PPT 大纲。

可选：
* `开发日志/2026-06-25-A-Phase0框架期总结.md` Phase 0 出口
* `开发日志/2026-07-05-A-前端Day7-SafetyView.md` 最新一天的工作模式
* `docs/FRONTEND-PROMPT.md` 本文件

# 3. 技术栈强约束（不要换）

* Vue 3 + TypeScript + Vite（已有）
* Vue Router 4
* Pinia（已装，cockpit store）
* ECharts 6（gauge / radar / line / bar / treemap / graph 都用过）
* marked（Markdown 渲染）
* SCSS（已装 sass）
* ant-design-vue（已装，用于 Modal/Form 等复杂组件，目前用得少）
* **绝对禁止换** React / Svelte / Next / Nuxt — 时间不允许

# 4. 当前已完成的产出（commit 745eb20 时点）

## 已交付 view（11 个路由）

| 路由 | view | 状态 |
|------|------|------|
| `/cockpit` 默认 | CockpitView 三栏 14 组件 | ✅ 待 5 Tab + 头像组升级 |
| `/playground` | PlaygroundView 一屏 | ✅ 待顶栏 + 场景控制 + 校园服务 8 图标 |
| `/safety` | SafetyView 720 行 7 区块（评估沙盒 + 4 gauge + 雷达 + 历史 + 5 user bar） | ✅ 高质量化已完成 |
| `/login` | LoginView 540 行 A3 调性 | ✅ |
| `/chat` | ChatView 原 SSE | ✅ 备用 |
| `/profile` `/path` `/resources` `/assessment` | 4 老 view | ⏳ W3 Day 15-16 对齐 Cockpit |

## 已交付组件

| 类别 | 组件 | 数量 |
|------|------|------|
| Cockpit | GroupHeader/MyWorkspace/BlockHealthPanel/AgentRoster/ChatStream/6 bubbles/TaskProgressPanel/ResourceListPanel/ProfileRadarPanel/MoreDrawer | 14 |
| Shared | RadarChart/ForecastCurve/KGGraph/AttributionHeatmap/MarkdownBlock | 5 |
| Playground | PixelCampus/AgentSprite/PlaygroundLeft/PlaygroundRight/PlaygroundBottom | 5 |

## 已交付工具

* `frontend/src/types/cockpit.ts` 8 子块 + WithError
* `frontend/src/api/cockpit.ts` fetchCockpit/Schema/Counterfactual
* `frontend/src/api/http.ts` 三态 baseURL（开发/同源相对/绝对）
* `frontend/src/stores/cockpit.ts` Pinia 8 子块 getter + 5 actions
* `frontend/src/utils/cockpit.ts` cockpitBlockStates / cockpitResources / **safeRadarLabels** / **hasCorruptText** / **safeText**（应对后端 mojibake）
* `frontend/src/mocks/cockpit-fixture.ts` 5 demo user × 8 块

## 已交付配置

* `frontend/Dockerfile` 多阶段 node→nginx + build arg + nginx /api/ 反代 + /healthz
* `docker-compose.yml` 双容器 + healthcheck + a3net network + service args VITE_API_BASE_URL=""
* `scripts/docker_smoke.py` 9 项检查（fix 加 JSON 验证防 Vite SPA fallback 假通过）
* 接口冻结 tag `contract-freeze-v1`

# 5. 接下来 27 天主线

## W3 加强期 15 天（6/26 – 7/10）

| 日 | 主题 | pet 集成 |
|----|------|---------|
| Day 2-3 6/26-27 | **LedgerView** 高质量化（5 来源分组 + 评估沙盒 + 堆叠图） | 阿匠头像 |
| Day 4-5 6/28-29 | **AppShell** Topbar（搜索 Ctrl+K + 通知 + 用户下拉）+ Sidebar 一级菜单 | Pet 浮动球 |
| Day 6-7 6/30-7/01 | **CounterfactualView**（KP 切换 + horizon slider + 三曲线 + 5 推荐动作） | 团团角色 |
| **Day 8-9 7/02-03** | **🐾 CockpitView 升级核心日** — 5 Tab 切换 + GroupHeader 头像组 + 6 pet SVG 全部就位 | 全部 |
| Day 10-11 7/04-05 | **AnalyticsView** 4 图（学习趋势/时间分布/课程进度/KP heatmap） | 6 pet 横排 |
| Day 12-14 7/06-08 | **Playground 完整化**（顶栏 7 菜单 + 场景控制 + 7 底部按钮 + 校园服务 8 图标 + 徽章 grid） | 5 像素 pet |
| Day 15-16 7/09-10 | 老 view 对齐 + **pet 互动深化**（技能面板 + 学习连击） | 全部互动 |

## W4 准备 + 创新加分 5 天（7/11 – 7/15）

| 日 | 主题 |
|----|------|
| Day 17 7/11 | 全局性能优化（Lighthouse ≥ 85） |
| Day 18 7/12 | 异常态打磨（ErrorBoundary + 骨架屏统一） |
| Day 19 7/13 | 🎁 Ctrl+/ 快捷键面板 + Ctrl+Shift+P 演示者模式 |
| Day 20 7/14 | 🎁 Onboarding tour + 暗色模式 + 🔒 演示流程冻结 |
| Day 21 7/15 | E2E 5 user × 12 路由 = 60 截图 + 视频脚本对齐 |

## W5 提交期 7 天（7/16 – 7/22）

| 日 | 主题 |
|----|------|
| Day 22 7/16 | dry-run v1 + Docker 实跑（user 装 Docker Desktop） |
| Day 23 7/17 | PPT 大纲 + v1 |
| Day 24 7/18 | PPT v2（整合 B 算法章节）+ 配音稿 |
| Day 25 7/19 | 视频录制 ≤ 7 分钟 |
| Day 26 7/20 | 视频剪辑 + 字幕 |
| Day 27 7/21 | README + 提交包 + dry-run ×3 |
| Day 28 7/22 晚 | 🚀 提交 + tag submission-final |

# 6. 🐾 v5.1 宠物化创新点（重点）

把"多 Agent 系统"升级为 **"7 个 AI 学习伙伴"**：

| 伙伴 | Agent | 形象 | 性格 | 主色 |
|------|-------|------|------|------|
| 小狐规划 | Planner | 🦊 智狐 | 聪明、有条理 | #f97316 |
| 猫头讲师 | Tutor | 🦉 智灵 | 博学、耐心 | #16a34a |
| 河狸工匠 | Content | 🦫 阿匠 | 勤劳、专注 | #f59e0b |
| 小龙挑战 | Quiz | 🐉 小龙 | 活泼、好斗 | #8b5cf6 |
| 熊猫评分 | Evaluation | 🐼 团团 | 沉稳、客观 | #0ea5e9 |
| 刺猬守护 | Safety | 🦔 球球 | 警惕、贴心 | #14b8a6 |
| 学习者 | Student | 🧑‍🎓 你 | — | #2563eb |

**实现轻量级**：SVG 自绘 + CSS animation（4 状态 idle/thinking/talking/celebrating），不上 Lottie。资产工期 5h。

**接入位置**：CockpitView AgentRoster / 所有气泡 avatar / Playground 5 AgentSprite / LoginView hero / SafetyView header / EvaluationBubble / AnalyticsView 顶部 / **Cockpit 右下角浮动 Pet 球**（可拖动 + 点开技能面板）

**游戏化 6 机制**：Pet Lv 1-99 / 技能树 / 群聊互动 / 学习连击 / 心情系统 / 成就解锁 toast

详见 v5.1 §十六。

# 7. 每日工作流（必跑）

```bash
# 后端起服务（开发模式）
A3_OFFLINE_DEMO=1 uvicorn backend.app.main:app --reload --port 8000

# 前端 dev server
cd frontend && npm run dev    # http://localhost:5173

# 当日类型检查（每个 view 改完跑一次）
cd frontend && npx vue-tsc --noEmit

# 当日 build 验证
cd frontend && npm run build

# 演示资产健康检查（每天结束前必跑，14/14 才算这天通过）
python -m scripts.verify_demo_assets

# Docker smoke（dev 模式 8/9 正常 — fail 项是"Vite SPA fallback 而非 nginx 反代"，符合预期）
python -m scripts.docker_smoke

# pytest 全测（改后端字段时必跑）
python -m pytest tests/a -q --no-cov --benchmark-disable -x
```

# 8. 冻结红线

* 6/30 接口已冻结（tag `contract-freeze-v1` 已推），任何字段变更必须经 §6.2 流程（A+B 双签 + issue）
* 7/14 演示流程冻结：固定 demo user + 7 步路径 + 每步停留秒数 + 每步说什么，写入 docs/06
* 7/22 晚提交 zip + tag `submission-final`

# 9. git commit 习惯

* 每个独立任务一次 commit
* 消息格式：`A: Day{N} — <主题>` 或 `A: <主题> — <一行说明>`
* commit message 写做了什么 + 为什么 + 验收命令
* commit body 不要写"基于审计 / 按计划 / 按建议"这种过程话，写实质内容
* 末尾加 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`

# 10. 文档命名约定（重要）

* A 的开发日志：`开发日志/YYYY-MM-DD-A-XXX.md` 必须含 `-A-` 前缀（与 B 冲突时 A 优先）
* B 的开发日志：`开发日志/BYYYY-M-D.md` 或 `开发日志/YYYY-MM-DD-B-XXX.md`

# 11. B 协作清单（W3 内）

| 优先级 | 任务 | 截止 |
|--------|------|------|
| 🔴 P0 | mojibake 同根：radar_labels[0,3,4,5] / debate.verdict / kg.current_kp / attribution category keys | 7/01 |
| 🟡 P1 | 5 demo user 差异化（不同 weak_points / forecast 斜率 / ledger 类型）| 7/08 |
| 🟡 P1 | pedagogical_context 接真 RAG（cov.verified ≥ 70%）| 7/08 |
| 🟡 P1 | benchmark 预跑（SAKT/DINA/Bloom 三项数字）| 7/10 |
| 🟢 P2 | PPT 算法可信度 3-4 页 | 7/17 交 A |

# 12. 演示账号

* `counselor` / `123456` — 辅导员
* `admin` / `123456` — 管理员
* 5 demo user：`demo-student-1` ~ `demo-student-5`（W3 内 B 会差异化）
* 离线模式默认开启（`A3_OFFLINE_DEMO=1`），无 LLM API Key 也能跑

# 13. 你现在做的第一件事

不要立刻写代码。先：

1. 用 Read 把 §2 必读文档前 4 份看一遍（v5.1 计划 / 冻结契约 / Cockpit 端点契约 / 组件契约）
2. 跑 `python -m scripts.verify_demo_assets` 14/14 确认后端环境健康
3. 跑 `cd frontend && npm run dev` + `npx vue-tsc --noEmit` 确认前端 0 error
4. 用 Read 看 `frontend/src/views/SafetyView.vue`（720 行，最近的高质量化样板）
5. 用 Read 看 `frontend/src/views/CockpitView.vue`（242 行，主战场）
6. 给我一份「确认明天 Day 2 LedgerView 6h 任务拆解」，等我确认后再开始写代码

如果中途有任何字段歧义、技术决策不确定，**先问我**而不是自己决定。我对前端框架细节没那么熟，但对接口契约 / 评委门面 / 演示动线 / 宠物化创新点非常清楚。

**特别提醒**（v5.1 新）：宠物化是 Day 8-9 的核心日，那之前每个 view 做的时候只需"留 pet 接入点"（如 AgentRoster 头像槽位、Bubble avatar 槽位），不需要先做 SVG。SVG 6 个统一在 Day 8 上午绘制（3h）。

===PROMPT END===
```

---

## 复制完之后

把上面 `===PROMPT START===` 到 `===PROMPT END===` 之间所有内容（**不包含**两个标记本身）一字不漏复制到新窗口 Claude Code 的第一条消息。

Claude 会先 Read 4 份必读文档 + 跑健康检查 + 给你明天 Day 2 LedgerView 拆解。**等他给出拆解后你确认，再让他开写代码**。

---

## v2 相对 v1 变化

| 项 | v1 | v2 |
|----|-----|-----|
| 时间锚点 | "今天 6/24-25" | **明确 6/25** + 距演示日 28 天 |
| 已完成清单 | "Phase 0 + Cockpit 端点就绪" | 详细 11 个路由 + 14+5+5 组件 + utils + Docker 配置 + commit `745eb20` |
| 计划版本 | v3 (Phase 0+双人分工) | **v5.1**（28 天细打磨 + 10 项创新加分 + 宠物化）|
| 必读文档 | 8 份 | 重排为 8 主 + 3 选，含最新 Day6/Day7 战报 |
| 工作流命令 | 4 个 | 加 `npx vue-tsc --noEmit` + `docker_smoke` |
| 冻结状态 | "6/30 计划冻结" | "6/30 已冻结，tag contract-freeze-v1 已推" |
| B 协作 | 无 | 5 项 P0/P1/P2 清单 + 截止日 |
| 宠物化创新点 | 无 | 第 6 节专章 + 7 伙伴表 + 接入位置 + 游戏化 6 机制 |
| 提醒 | "等我确认" | 强调宠物化是 Day 8-9 核心，那之前留接入点即可 |
