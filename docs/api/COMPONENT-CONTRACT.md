# A3 前端组件契约（Phase 0 框架版）

> 版本：2026-06-25 Phase 0  
> 范围：`/cockpit` 多智能体群聊驾驶舱、`/playground` 像素校园静态页、shared 图表组件  
> 数据源：Phase 0 使用 `frontend/src/mocks/cockpit-fixture.ts` 兜底；Phase 1 接 `GET /api/v1/cockpit/student/{user_id}` 真字段  
> 原则：Cockpit 任一子块带 `error` 时，组件只降级当前区块，不让整页崩溃

---

## 1. 总入口

| 文件 | 路由 / 用途 | 当前状态 |
|---|---|---|
| `frontend/src/views/CockpitView.vue` | `/cockpit`，默认首页，图 1 多智能体群聊主面板 | 已完成三栏框架 + mock 兜底 + demo user 切换 |
| `frontend/src/views/PlaygroundView.vue` | `/playground`，图 2 像素校园加分页 | 已完成一屏静态框架 |
| `frontend/src/router/index.ts` | 路由注册 | `/` 重定向 `/cockpit`，`/chat` 保留原对话页 |
| `frontend/src/App.vue` | 侧边栏导航 | 已新增“群聊驾驶舱”和“像素校园”入口 |

---

## 2. Store / API / 类型

### 2.1 `types/cockpit.ts`

后端契约来源：`docs/api/cockpit-endpoint.md`。

核心类型：

| 类型 | 用途 |
|---|---|
| `CockpitResponse` | Cockpit 顶层响应，含 `profile / kg / forecast / attribution / cov / debate / safety / ledger` |
| `WithError<T>` | 子块降级字段，任一子块可带 `error?: string` |
| `CockpitProfile` | 学习画像、6 维雷达、完整度 |
| `CockpitKg` | 当前知识点、2 跳邻居、图谱边 |
| `CockpitForecast` | 掌握度预测曲线与反事实曲线 |
| `CockpitLedger` | 证据链 claims 与资源来源 |
| `CounterfactualResponse` | P1.4 反事实独立端点响应 |

### 2.2 `api/cockpit.ts`

| 方法 | 后端端点 | 调用者 |
|---|---|---|
| `fetchCockpit(userId, query?)` | `GET /api/v1/cockpit/student/{user_id}` | `stores/cockpit.ts` |
| `fetchCockpitSchema()` | `GET /api/v1/cockpit/schema` | 开发调试 |
| `fetchCounterfactual(params)` | `GET /api/v1/cognitive/counterfactual` | 后续反事实独立页 / Evaluation 展开态 |

### 2.3 `stores/cockpit.ts`

| 字段 / 方法 | 契约 |
|---|---|
| `userId` | 当前 demo user，默认 `demo-student-1` |
| `data` | 完整 `CockpitResponse | null` |
| `profile / kg / forecast / attribution / cov / debate / safety / ledger` | 8 个子块 computed getter |
| `fetchCockpit(uid?, query?)` | 真实接口拉取，失败时设置 `error` |
| `switchUser(uid, query?)` | 切换 demo user |
| `refresh(query?)` | 当前 user 重新拉取 |
| `fetchCounterfactual(kpId, horizonDays?)` | 反事实请求，含本地 cache |
| `loadFixture(fixture)` | Phase 0 离线兜底入口 |

### 2.4 `mocks/cockpit-fixture.ts`

用于无后端、未登录、接口暂时失败时保持页面可视。当前覆盖 8 个 Cockpit 子块和 5 个 demo user ID。

---

## 3. Cockpit 组件契约

### 3.1 页面布局

`CockpitView.vue` 把图 1 拆成：

| 区域 | 组件 |
|---|---|
| 顶部群信息条 | `GroupHeader` |
| 左栏学习空间 | `MyWorkspace` |
| 左栏子块状态 | `BlockHealthPanel` |
| 左栏 Agent 群成员 | `AgentRoster` |
| 中间气泡流 | `ChatStream` + `bubbles/*` |
| 右栏任务进度 | `TaskProgressPanel` |
| 右栏资源列表 | `ResourceListPanel` |
| 右栏学习画像 | `ProfileRadarPanel` |
| 右栏下沉证据 | `MoreDrawer` |

### 3.2 组件明细

| 组件 | Props | 字段来源 | 兜底 |
|---|---|---|---|
| `GroupHeader` | `data`, `loading`, `fixtureMode`, `taskId` | `debate.recent_traces[*].expert/critic`, `generated_at`, `user_id` | Agent 名取不到则写死 6 个 |
| `MyWorkspace` | `profile`, `userId` | `profile.completeness`, `profile.dimensions.learning_goals`, `profile.dimensions.weak_points.topics` | 完整度 0，目标用固定文案 |
| `BlockHealthPanel` | `states`, `fixtureMode`, `transportError` | `cockpitBlockStates(data)` | 显示 pending / empty / error / ready |
| `AgentRoster` | `agents` | Phase 0 静态数组 | 全 mock |
| `ChatStream` | `tasks`, `primaryResource`, `forecast` | Planner mock、`ledger.claims` 转资源、`forecast.curve` | 气泡仍展示静态示例 |
| `StudentBubble` | `text`, `time` | 用户输入示例 | 静态 |
| `PlannerBubble` | `tasks` | Phase 0 mock，后续可由 planner orchestration trace 替换 | 静态 |
| `TutorBubble` | `content` | 后续接 `/api/v1/chat/stream` SSE | 静态 Markdown |
| `ContentBubble` | `resource` | `ledger.claims[].sources` 推断类型 | 无资源则隐藏 |
| `QuizBubble` | `total`, `levels` | W3 题库端点或静态题库 | 静态 |
| `EvaluationBubble` | `forecast` | `forecast.curve`, `forecast.counterfactual.recommended_curve`, `expected_gain` | 曲线为空时显示空图 |
| `TaskProgressPanel` | `tasks` | Phase 0 mock，后续接 planner trace | mock 进度 |
| `ResourceListPanel` | `resources` | `ledger.claims` + `cov.recent_claims` | 空状态 |
| `ProfileRadarPanel` | `profile` | `profile.radar_6d`, `profile.radar_labels` | 空雷达 |
| `MoreDrawer` | `kg`, `attribution`, `safety`, `debate` | 4 个 Cockpit 子块 | 单 Tab 降级，不影响其它 Tab |

### 3.3 数据归一化工具

`frontend/src/utils/cockpit.ts` 负责把后端响应转成页面稳定可用的数据形态：

| 方法 / 类型 | 用途 |
|---|---|
| `cockpitBlockStates(data)` | 统计 8 个子块的 ready / empty / error / pending 状态 |
| `cockpitResources(ledger, cov)` | 合并 `ledger.claims` 与 `cov.recent_claims`，输出资源卡数据 |
| `asArray(value)` | 防止后端子块 `error` 时数组字段缺失 |
| `blockError(block)` | 标准化子块错误文案 |
| `CockpitResourceItem` | 右侧资源列表和 Content 气泡共用资源形态 |

### 3.4 Cockpit 字段映射顺序

Phase 1 接真数据建议顺序：

1. `profile`：先驱动 `MyWorkspace` 和 `ProfileRadarPanel`。
2. `ledger + cov`：驱动 `ResourceListPanel`、`ContentBubble`。
3. `forecast`：驱动 `EvaluationBubble` 和 `ForecastCurve`。
4. `kg + attribution + safety + debate`：驱动 `MoreDrawer` 4 个 Tab。
5. `/api/v1/chat/stream`：替换 `TutorBubble` 静态 Markdown。
6. 题库端点：替换 `QuizBubble` 静态题库。

---

## 4. Shared 组件契约

| 组件 | Props | 用途 | 注意事项 |
|---|---|---|---|
| `RadarChart` | `labels: string[]`, `values: number[]`, `title?`, `height?` | Cockpit 学习画像、Playground 左栏画像 | `values` 支持 0-1 或 0-100 |
| `ForecastCurve` | `baseline: ForecastPoint[]`, `recommended?`, `expectedGain?`, `height?` | Evaluation 气泡、后续反事实页 | `mastery` 支持 0-1 或 0-100 |
| `KGGraph` | `nodes: KgNeighbor2Hop[]`, `edges: KgEdge[]`, `height?` | MoreDrawer KG Tab | `distance=0` 作为中心节点 |
| `AttributionHeatmap` | `distribution: Record<string, number>`, `height?` | MoreDrawer 错题归因 Tab | Phase 0 用 treemap 表达错因占比 |
| `MarkdownBlock` | `content: string` | TutorBubble / 后续 LLM 输出 | 做了基础 script/on* 清理 |

---

## 5. Playground 组件契约

`/playground` 是纯静态加分页，不接后端。当前目标是评委开场吸睛和 PPT 截图素材。

| 组件 | Props | 数据源 | 说明 |
|---|---|---|---|
| `PixelCampus` | 无 | 静态数组 + `assets/playground/campus.svg` | 中央像素校园地图 + 5 个 Agent |
| `AgentSprite` | `name`, `title`, `x`, `y`, `color` | `PixelCampus` 内部静态配置 | CSS 像素人物 + 浮动动画 |
| `PlaygroundLeft` | 无 | 静态课程 / 雷达值 | 学生信息、学习画像、课程列表 |
| `PlaygroundRight` | 无 | 静态进度 / 路径 / 徽章 | 学习进度、学习路径、学习成果 |
| `PlaygroundBottom` | 无 | 静态对话 / 资源 / 饼图 | 底部多智能体对话、资源中心、数据分析 |

Agent 命名保持与 Cockpit 一致：

| 英文 | 中文 |
|---|---|
| Planner | 学习规划师 |
| Tutor | 知识讲师 |
| Content | 资源生成师 |
| Quiz | 实践辅导师 |
| Evaluation | 测评分析师 |

---

## 6. 验收命令

```powershell
cd frontend
npx vue-tsc --noEmit
npm run build
```

后端演示资产健康检查建议指定仓库内临时目录，避免 Windows TEMP 权限影响：

```powershell
$tmp=(Resolve-Path '.tmp').Path
$env:TEMP=$tmp
$env:TMP=$tmp
python -m scripts.verify_demo_assets
```

当前验收结果：

- `npx vue-tsc --noEmit`：通过
- `npm run build`：通过，仅 Vite chunk size warning
- `python -m scripts.verify_demo_assets`：14/14 通过（设置 `TEMP/TMP=.tmp` 后）

---

## 7. 未接真字段清单

| 项 | 当前状态 | 后续动作 |
|---|---|---|
| Planner 任务拆解 | mock | 若后端提供 orchestration trace，则替换 `tasks` computed |
| Tutor Markdown | 静态 | 接 `/api/v1/chat/stream` SSE |
| Quiz 题库 | 静态 | W3 接题库端点或从资源端点筛题库 |
| Content 文件大小 / 类型 | 从 claims 粗略推断 | 后续由 ledger/resource 元数据提供 |
| Playground | 纯静态 | W3 末若有时间再打磨视觉，不接真数据 |
