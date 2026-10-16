# B 角色后端质量核心设计

## 1. 目标

本轮完成角色 B 可离线验收的后端核心，使现有 B 测试归零失败，并把规划 v6 中最关键的持久化、算法服务、API 和可观测性能力落到可重复验证的工程实现。

本轮不修改前端，不下载 ASSISTments/KDD Cup 数据集，不训练 DKT，不开展真实用户研究。

## 2. 验收边界

### 必须完成

1. `tests/b/` 全部通过。
2. DINA 的 exact EM 与 mean-field VI 均可运行，100 学生 × 50 题性能验收不崩溃。
3. BKT、SM-2、DINA 状态可通过统一 repository 持久化并在新实例中恢复。
4. GraphRAG 存储和子图遍历在临时数据库与正式数据库中行为一致。
5. Learner Archetype 的 9 种类型有稳定公共接口，聚类验证可运行。
6. PathPlanner 使用真实 Thompson Sampling 输出 `arm_pulls`，不保留错误类型或拼写。
7. 学习时光机满足 Kalman 平滑、置信区间传播、反事实分析和目标倒推。
8. 错题本支持 8 类归因、规则/LLM 可降级双通道、Bloom 变式题、热力统计和 SM-2 入队。
9. API 路由顺序正确，固定路由不会被 `/{user_id}` 吞掉；请求/响应使用 Pydantic 模型。
10. 建立 Alembic 基线迁移、关键索引、数据库备份与恢复脚本。
11. 提供无需额外服务即可工作的 Prometheus 文本指标端点。
12. 更新 `开发日志/B2026-6-18.md`，记录根因、修改、测试和剩余工作。

### 本轮不做

- Vue 页面和其他前端代码。
- ASSISTments、KDD Cup 等外部数据下载。
- DKT/PPO 等需要长时间训练或新数据集的研究实验。
- Grafana 部署、线上 CI 执行和真实用户研究。
- A 角色拥有的 Agent、chat pipeline 和多模态模块重构。

## 3. 架构

### 3.1 状态持久化

`StateRepository` 是 DINA、BKT、SM-2 的唯一数据库读写边界。算法类接受可选 repository，实现：

- 内存计算不依赖数据库；
- 配置 repository 后每次关键状态变化可持久化；
- 新实例可以显式恢复状态；
- 测试使用独立 SQLite session factory，不污染全局数据库。

数据库初始化必须在访问 repository 前建立 schema。不存在表时不能在热路径重复抛异常或刷屏日志。

### 3.2 算法服务

- DINA 内部统一使用参数 `q_matrix`，exact EM 和 mean-field 共享相同的输入验证、M-step 与似然计算。
- BKT 趋势使用完整近期窗口首尾差判断；个性化转移率不改变标准 BKT 的基本单调行为。
- SM-2 评分低于 3 时进入立即复习队列，之后由复习结果重新安排间隔。
- GraphRAG store 不缓存过期 session factory；每次操作从当前数据库配置创建会话。
- Thompson Sampling 对每个候选输出 Beta 后验参数、抽样值和奖励分解。

### 3.3 学习时光机

`BKTForecaster` 负责纯算法，API 负责输入验证和序列化：

- Kalman 仅平滑历史观测，不篡改原始数据；
- 更高练习率不得产生更低的最终掌握度；
- 预测步数增加时置信区间不缩窄；
- reverse plan 使用有界搜索求满足目标所需的最小 daily practice rate，并给出每日题量建议；
- 不可达目标返回明确状态，不伪造成功计划。

### 3.4 错题复盘

错题服务分为 repository、attribution、variant generator 和 API 四层：

- 规则通道始终可用；
- LLM 通道可选，失败时回退规则通道并标记 attribution source；
- 每道变式题含 Bloom 层级、题干、参考答案和解析；
- 记录错题后自动加入 SM-2 队列；
- 热力图返回知识点 × 错因的稳定矩阵。

### 3.5 迁移与监控

- Alembic 初始迁移覆盖当前模型，并显式创建高频查询组合索引。
- backup 脚本使用 SQLite backup API，restore 在覆盖前验证备份可读。
- metrics registry 使用进程内 counters/histograms，输出 Prometheus text exposition format；缺少第三方 Prometheus 包时仍可运行。

## 4. 错误处理

- 禁止新增静默 `except Exception: pass`。
- 可降级路径必须记录结构化 warning，并返回可辨识的 fallback/source 字段。
- 输入错误返回 4xx；内部不可用返回稳定错误码，不把堆栈暴露给 API 调用者。
- 算法输入中的空矩阵、全零 Q 行、非法概率和不可达目标均有明确行为和测试。

## 5. 测试策略

严格使用测试驱动：

1. 为每个现有失败保留或补充最小复现测试并确认失败。
2. 每次只修复一个根因，运行对应测试确认变绿。
3. 新增持久化、reverse plan、错题复盘、metrics、backup/restore 测试。
4. 每批完成后运行整个 `tests/b/`。
5. 最终运行：

```powershell
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m pytest tests/b -q
& 'D:\Anaconda3\envs\dxtorch\python.exe' -m compileall -q backend/app
```

若覆盖率工具可用，再运行 B 模块覆盖率；若不可用，在日志中如实记录环境限制，不虚报覆盖率。

## 6. 实施顺序

1. 修复现有 14 个失败及数据库测试隔离。
2. 完成三算法持久化和恢复。
3. 完成时光机与错题本 API。
4. 加入 Alembic、索引、metrics、backup/restore。
5. 全量验证并更新 B 开发日志。

## 7. 完成定义

只有当 `tests/b/` 全绿、关键性能测试通过、迁移和备份恢复有自动化测试、开发日志记录了真实验证结果时，本轮才算完成。
