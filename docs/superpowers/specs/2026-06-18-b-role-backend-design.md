# B 角色后端开发设计

## 目标

在不破坏 A/B 协作边界的前提下，完成 B 负责的教学算法层和学情评估流水线。第一阶段先建立稳定的契约、SQLite 持久化和种子数据底座，随后依次实现 GraphRAG、DINA、BKT、Bloom、SM-2、ZPD、错题本、Agent 学术化升级、游戏化与一致性检查。

## 实施顺序

1. Day 1：契约、数据库模型、Repository、现有 API 持久化、种子数据。
2. Day 2：知识图谱构建、2-hop 检索、TF-IDF 与图检索融合。
3. Day 3：DINA、BKT、Bloom 分类及认知诊断 API。
4. Day 4：SM-2、遗忘曲线、ZPD、学习者类型接入、错题本。
5. Day 5：PathPlanner、Evaluator、Profile 三个 Agent 学术化升级。
6. Day 6：游戏化、防幻觉一致性检查、B 侧测试覆盖。
7. Day 7：契约测试、端到端联调、Docker 验证和答辩材料。

每个阶段必须产生可独立运行、可测试的增量，不提前依赖尚未实现的后续模块。

## 所有权边界

B 可以修改：

- `backend/app/agents/profile_agent.py`
- `backend/app/agents/path_planner.py`
- `backend/app/agents/evaluator_agent.py`
- B 负责的 service、API、repository、数据库表和测试
- `knowledge_base/python_programming/`
- `data/seed.json`
- `data/ads/rag/`
- `开发日志/B2026-6-18.md`

共享面包括 `agents/base.py`、`agents/orchestrator.py`、`core/database.py`、`core/models.py`、`core/llm_client.py`、契约文档和契约测试。共享面只做完成 B 目标所必需的最小修改，并在开发日志中记录原因和兼容性影响。

A 独占的 Chat、多媒体、资源生产、Artifacts 和人工智能课程知识库不由 B 修改。跨域读取必须通过稳定的 Service 或 Repository 接口完成。

## 契约

`AgentResponse.metadata` 保留以下跨域字段：

- `bloom_level: str`
- `kp_ids: list[str]`
- `archetype_code: str`
- `zpd_kps: list[str]`
- `reflection_trace: list`

`AgentContext.extra` 保留以下字段：

- `strategy_prompt: str`
- `dina_snapshot: dict`
- `archetype: dict`
- `rag_mode: "tfidf" | "graph" | "hybrid"`

`AgentOrchestrator.process_turn()` 的参数签名保持不变。新增上下文只能写入 `context` 字典。

## 数据持久化

使用项目现有 SQLAlchemy 和 SQLite 配置，不引入第二套 ORM。业务数据通过 Repository 访问，API 不直接操作 SQLAlchemy Session。

B 拥有的表：

- `profiles`
- `realtime_states`
- `learner_archetypes`
- `knowledge_points`
- `kp_relations`
- `dina_states`
- `bkt_states`
- `sm2_schedule`
- `learning_paths`
- `assessments`
- `mistakes`
- `gamification_profiles`

为了兼容当前前端，画像、路径和评估 API 的 URL、请求体和响应体保持不变。内存字典迁移后，进程重启不得丢失数据。

种子数据通过显式脚本幂等导入。重复执行不得产生重复用户、路径或评估记录。

## 教学算法边界

GraphRAG：

- 知识点实体和关系持久化到数据库。
- 支持 `prerequisite`、`part_of`、`analogous` 三类关系。
- 检索按实体命中、2-hop 扩展、关联 chunk 汇总执行。
- Hybrid 模式使用图得分 0.6、TF-IDF 得分 0.4。

认知诊断：

- DINA 输出每个知识点的 mastery、slip 和 guess。
- 数据不足或 EM 不收敛时使用 BKT 先验，不返回空结果。
- BKT 使用 P(L0)、P(T)、P(S)、P(G) 四参数增量更新。
- Bloom 分类使用确定性关键词规则为主，LLM 为可选增强。

复习与推荐：

- SM-2 使用标准 quality 0-5 更新间隔、重复次数和 easiness。
- ZPD 选择 mastery 0.5-0.8 的知识点，以及前置已掌握的下一知识点。
- PathPlanner 将 ZPD 结果写入 `metadata.zpd_kps`。

## Agent 集成

ProfileAgent：

- 将非数值画像转换成稳定的 0-1 评分快照。
- 调用 LearnerArchetypeService。
- 在 metadata 写入 `archetype_code` 和完整 archetype。

EvaluatorAgent：

- 优先使用 DINA 掌握状态和 BKT 趋势。
- 用 NarrativeGenerator 生成确定性报告段落。
- 用 SVGVisualizer 生成评估图表 data URI。
- LLM 仅用于补充个性化建议，失败时报告仍完整可用。

PathPlannerAgent：

- 使用知识图谱拓扑约束。
- 优先推荐 ZPD 知识点。
- 使用 epsilon=0.1 的策略在探索和利用间选择。
- 输出 `confidence_score` 和 `zpd_kps`。

## 错误处理

- 数据库操作失败必须回滚事务，并由 API 返回明确错误。
- 算法输入不足时返回带 `fallback_reason` 的降级结果。
- RAG、LLM 或图检索不可用时回退到现有 TF-IDF 或规则路径。
- SVG、叙事和学习者类型服务不得因单个异常阻断主评估流程。
- 所有 API 返回 JSON 可序列化数据，不暴露内部异常堆栈。

## 测试与验收

采用 TDD，每项新行为先编写失败测试。

测试目录为 `tests/b/`，至少覆盖：

- 数据库重启后画像、路径和评估仍存在。
- Seed 重复执行保持幂等。
- GraphRAG 关系扩展和 Hybrid 排序。
- DINA 正常收敛与 BKT 降级。
- BKT 正误答后的掌握度方向变化。
- Bloom 六层分类。
- SM-2 各 quality 分支。
- ZPD 前置约束。
- 学习者类型评分转换与类型输出。
- Agent metadata 契约。
- SVG 与叙事输出完整。

Day 6 时 B 模块覆盖率目标不低于 65%。Day 7 运行契约测试和完整端到端流程。

## 日志规范

`开发日志/B2026-6-18.md` 按阶段持续追加：

- 当日目标
- 修改文件
- 共享面修改及原因
- RED/GREEN 测试证据
- 已完成能力
- 风险和降级方案
- 下一步

日志只记录实际完成和实际验证结果，不提前把计划项标记为完成。
