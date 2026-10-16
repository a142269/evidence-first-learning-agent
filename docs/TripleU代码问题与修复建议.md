# Triple U 平台代码问题与修复建议

> 文档用途：内部开发整改与测试验收。  
> 本文不作为项目报告或答辩 PPT 的架构说明。  
> 所有事项均来自当前代码调用关系核验，不包含仅凭猜测提出的问题。

## 1. 整改优先级总览

| 编号 | 优先级 | 问题 | 主要影响 |
| --- | --- | --- | --- |
| FIX-01 | P0 | 聊天生成的学习路径只写旧内存字典 | 路径无法通过标准 Repository 接口稳定读取 |
| FIX-02 | P0 | 聊天评估只写旧内存字典 | 团团评估不进入正式评估与统一学习状态 |
| FIX-03 | P0 | ProfileAgent 和 PathPlanner 使用 session ID 查询认知状态 | 可能读不到真实学生的 BKT/RealDINA |
| FIX-04 | P0 | 主 RAG 返回字段与 RealDINA 回写所需字段不一致 | 普通聊天难以更新涉及的知识点状态 |
| FIX-05 | P1 | 多 Agent 画像更新采用二选一策略 | 团团等业务 Agent 的画像更新可能未合并 |
| FIX-06 | P1 | ConfigurableAgent 读取错误的 RAG 字段 | 教师配置型 Agent 无法获得检索正文 |
| FIX-07 | P1 | 配置型 Agent 的 `allowed_tools` 未进入执行流程 | 配置中的工具能力未产生真实调用 |
| FIX-08 | P1 | 前端没有消费部分 SSE 事件 | 质量、安全、辩论、反思和遥测信息未展示 |
| FIX-09 | P1 | REST ChatResponse 类型与后端字段不一致 | TypeScript 调用方可能读取错误字段 |
| FIX-10 | P1 | Smart Tutor 声明的 used_agents 与真实执行不一致 | 调用追踪和产品展示难以证明真实协作 |
| FIX-11 | P1 | Smart Tutor 的 path_update 未持久化 | Smart Tutor 路径建议无法进入学习路径闭环 |
| FIX-12 | P2 | SafeDeclineAgent 的 reflect 方法签名不兼容 | 团队越界场景产生反思阶段异常日志 |
| FIX-13 | P2 | 编排 YAML 没有加载入口 | YAML 中声明的规则不参与实际运行 |
| FIX-14 | P2 | `depends_on` 未形成可执行任务依赖 | 当前协作只能按优先级分组，不能执行 DAG |
| FIX-15 | P2 | LLM 自动回退 Mock 缺少显式状态 | 外部模型故障可能被当作普通成功结果 |
| FIX-16 | P2 | 多资源工具 Trace 包含固定 warmup 调用 | Trace 可能被误认为 Agent 自主推理工具调用 |
| FIX-17 | P2 | SSE 正文在完整生成后再次切块 | 无法提供真正的模型 token 级输出 |
| FIX-18 | P2 | Reviewer/COVVerifier 已实现但未进入主输出链 | 若产品需要统一审查，需要增加明确编排节点 |

## 2. 建议的实施顺序

```text
第一批：FIX-01 ～ FIX-04
解决学习路径、评估、用户身份和知识点状态的核心闭环。

第二批：FIX-05 ～ FIX-11
解决画像合并、配置型 Agent、前端事件和 Smart Tutor 一致性。

第三批：FIX-12 ～ FIX-18
完善编排能力、运行可观测性、真实流式输出和统一审查。
```

---

## 3. P0：核心学习闭环

### FIX-01：聊天学习路径没有写入 LearningPathRepository

#### 代码证据

- `backend/app/api/v1/chat_pipeline/stages/outputs.py::_save_learning_path()`
- `backend/app/api/v1/learning_path.py`
- `backend/app/repositories/path_repo.py`

当前聊天持久化代码直接执行：

```python
lp_api._paths[pid] = record
```

而学习路径的列表、详情和阶段内容接口在 `_repository` 可用时只查询 `LearningPathRepository`。

#### 建议修改

不要直接写 `_paths`。统一调用学习路径公开保存入口或 Repository：

```python
saved = lp_api.save_path({
    "user_id": user_id,
    "title": record["title"],
    "stages": stages,
    "metadata": {
        "source": "chat",
        "agent_name": response.agent_name,
    },
})
```

更推荐将保存逻辑下沉为独立 service，避免 API 模块之间直接访问私有变量：

```text
LearningPathService.save()
→ LearningPathRepository.save()
```

`PersistStage`、`insights.generate_path()` 和学习路径 API 都调用同一个 service。

#### 验收标准

1. 智狐聊天生成路径后，`GET /api/v1/learning-path/list?user_id=...` 能立即查到。
2. 重启应用后路径仍存在。
3. `GET /learning-path/{path_id}` 和阶段内容接口可以读取。
4. 增加聊天路径持久化集成测试。

---

### FIX-02：聊天评估没有写入 AssessmentRepository

#### 代码证据

- `backend/app/api/v1/chat_pipeline/stages/outputs.py::_record_assessment()`
- `backend/app/api/v1/assessment.py`
- `backend/app/repositories/assessment_repo.py`
- `backend/app/services/learner_state.py`

当前代码只执行：

```python
assessment_api._assessments.setdefault(user_id, []).append(record)
```

正式评估接口和 `LearnerStateService` 使用数据库 `AssessmentRecord`。

#### 建议修改

统一通过 Repository 或 assessment service 保存：

```python
AssessmentRepository().add(
    user_id,
    {
        "external_id": response.metadata.get("evaluation_id"),
        "type": "evaluation",
        "score": eval_data.get("overall_score", 0) * 100,
        "topic": eval_data.get("topic", "assessment"),
        "duration": 0,
        "timestamp": time.time(),
        "metadata": eval_data,
    },
)
```

建议新增：

```text
AssessmentService.record_agent_evaluation()
```

由聊天、测验提交和活动记录共同使用。

#### 验收标准

1. 团团完成评估后，`GET /assessment/{user_id}` 能返回该记录。
2. `GET /learner-state/{user_id}` 的 assessment 块包含该评估。
3. 学习时间线出现 assessment 事件。
4. 重启应用后记录仍存在。

---

### FIX-03：认知状态查询混用了 session ID 和 user ID

#### 代码证据

- `backend/app/agents/profile_agent.py`
- `backend/app/agents/path_planner.py`
- `backend/app/api/v1/chat_pipeline/stages/orchestration.py`

编排阶段已经将真实学生 ID 放入：

```python
context.extra["user_id"]
```

但以下代码仍使用 `context.session_id`：

- ProfileAgent 查询 BKT；
- ProfileAgent 查询 RealDINA；
- PathPlannerAgent 查询 BKT。

#### 建议修改

在 `AgentContext` 中增加统一属性：

```python
@property
def user_id(self) -> str:
    return str(self.extra.get("user_id") or self.session_id or "default")
```

所有 Agent 使用：

```python
user_id = context.user_id
```

需要全仓检查以下模式：

```text
get_all_masteries(context.session_id)
snapshot_for(context.session_id)
top_strengths(context.session_id)
top_weaknesses(context.session_id)
```

#### 验收标准

1. 使用不同 `session_id`、相同 `user_id` 发起请求，获得相同的 BKT/RealDINA 基础状态。
2. 使用相同 session、切换 user 时不串数据。
3. ProfileAgent、PathPlannerAgent、EvaluatorAgent 使用同一身份解析函数。
4. 增加 session ID 与 user ID 不同的回归测试。

---

### FIX-04：RAG 输出无法为聊天 RealDINA 回写提供 kp_id

#### 代码证据

- `backend/app/services/rag_service.py::retrieve()`
- `backend/app/api/v1/chat_pipeline/stages/outputs.py::_maybe_update_learner_state()`

RAG 标准返回字段为：

```text
content, source, course, score, chunk_id, title_hint
```

PersistStage 提取：

```text
metadata.kp_id
metadata.knowledge_point
hit.kp_id
```

两个字段契约没有对齐。

#### 建议修改

方案 A：在 RAG chunk 建索引时保留知识点元数据。

```python
{
    "content": c.content,
    "source": c.source,
    "course": c.course,
    "score": c.score,
    "chunk_id": c.chunk_id,
    "title_hint": c.title_hint,
    "kp_id": c.metadata.get("kp_id"),
    "metadata": c.metadata,
}
```

方案 B：增加 `KnowledgePointResolver`，根据 `course + title_hint + source` 映射知识点 ID。

建议优先采用 A，并用 B 兼容历史知识库。

#### 验收标准

1. 对课程知识点提问时，RAG 命中至少能返回一个可验证的 `kp_id`。
2. PersistStage 能收到去重后的 kp ID。
3. 对话后对应用户的 RealDINA/BKT 状态产生预期记录。
4. 无法映射时不写错误知识点，并记录可观测日志。

---

## 4. P1：多智能体与前后端一致性

### FIX-05：画像更新需要从“二选一”改为“受控合并”

#### 代码证据

`backend/app/api/v1/chat_pipeline/stages/outputs.py::_merge_profile()`

当前逻辑优先采用 ProfileAgent 更新；只有 ProfileAgent 没有更新时才采用 primary Agent 更新。

EvaluatorAgent 同样可能返回：

```python
profile_updates=eval_data.get("profile_updates", {})
```

#### 建议修改

按可信来源和字段权限合并所有成功响应：

```text
ProfileAgent：兴趣、偏好、目标、互动模式
EvaluatorAgent：薄弱点、自我效能、掌握度相关证据
其他 Agent：仅允许白名单字段
```

实现建议：

```python
ProfileUpdateMerger.merge(
    current_profile,
    updates=[
        ("profile_agent", profile_updates),
        ("evaluator_agent", evaluator_updates),
    ],
)
```

同时在画像快照中记录每个字段的来源。

#### 验收标准

1. 同一轮 ProfileAgent 和 EvaluatorAgent 都返回更新时，两类允许字段均被保存。
2. 冲突字段按明确优先级处理。
3. 非白名单 Agent 不能覆盖关键诊断字段。
4. 快照能追踪更新来源。

---

### FIX-06：ConfigurableAgent 应读取 RAG 的 `content`

#### 代码证据

`backend/app/agents/configurable_agent.py`

当前代码：

```python
text = str(item.get("text", ""))[:600]
```

主 RAG 返回字段为 `content`。

#### 建议修改

```python
text = str(item.get("content") or item.get("text") or "")[:600]
```

同时加入来源：

```python
source = item.get("source", "")
rag_block += f"\n---\n来源：{source}\n{text}"
```

#### 验收标准

1. 配置型 Agent 的最终 LLM messages 中包含 RAG 正文。
2. 有来源时带 source。
3. 同时兼容旧 `text` 字段。

---

### FIX-07：接通或移除 `allowed_tools`

#### 代码证据

`allowed_tools` 出现在：

- 数据模型；
- agent config service；
- 教师端 API 类型。

`ConfigurableAgent.execute()` 没有读取该字段。

#### 建议修改

若要接通：

1. 根据 `allowed_tools` 从 `ToolRegistry` 获取白名单 schema；
2. 将 tools 传给支持 function calling 的 LLM；
3. 解析 tool call；
4. 校验工具名仍在白名单；
5. 执行工具并记录 trace；
6. 将工具结果返回 LLM 生成最终答案；
7. 设置最大调用轮数和超时。

若本阶段不实现，应暂时从教师配置 UI 中隐藏该字段，避免产生能力误解。

#### 验收标准

1. 配置只允许 `lookup_knowledge_point` 时不能调用代码执行。
2. 工具调用被 trace 记录。
3. 工具异常不会绕过白名单。
4. 无 allowed tools 时保持纯文本 LLM 行为。

---

### FIX-08：补齐前端 SSE 事件消费

#### 代码证据

后端 `chat.py` 会发送：

```text
saved_resources, quality, safety, debate, reflection, telemetry
```

`frontend/src/api/chat.ts` 的 `StreamEvent` 联合类型和 switch 没有这些分支。

#### 建议修改

扩展类型：

```typescript
| "saved_resources"
| "quality"
| "safety"
| "debate"
| "reflection"
| "telemetry"
```

为 `StreamCallbacks` 增加：

```typescript
onSavedResources
onQuality
onSafety
onDebate
onReflection
onTelemetry
```

在 ChatView 中决定展示位置：

- safety：回答安全状态；
- quality：质量分；
- debate/reflection：折叠的推理与校验面板；
- telemetry：AgentTracePanel；
- saved_resources：资源归档状态。

#### 验收标准

1. 每种后端事件都有 TypeScript 类型。
2. switch 全部分发。
3. 不需要展示的事件也应显式记录或忽略，不能静默遗漏。
4. 增加 SSE parser 单元测试。

---

### FIX-09：统一 REST ChatResponse 字段

#### 代码证据

后端返回：

```text
primary_agent
```

前端 `ChatResponse` 定义：

```typescript
agent: string;
```

#### 建议修改

前端改为：

```typescript
primary_agent: string;
```

如需兼容旧响应：

```typescript
primary_agent: string;
agent?: string;
```

并补充后端实际返回但类型缺少的字段：

- `saved_resources`
- `profile_meta`
- `realtime_state`
- `rag_hits`
- `agents_invoked`
- `quality`
- `safety`
- `debate`
- `reflection`
- `telemetry`

#### 验收标准

1. `sendMessage()` 返回类型与后端 JSON 完全一致。
2. TypeScript 严格模式无字段错误。
3. REST 与 SSE 的 Agent 命名规则一致。

---

### FIX-10：Smart Tutor 的 used_agents 应来源于真实执行

#### 代码证据

`backend/app/services/smart_tutoring.py`

当前 `used_agents` 是固定类变量，`ask()` 实际没有实例化这些 Agent；其中 `derivation_agent` 和 `example_agent` 也未注册。

#### 建议修改

两种方案二选一：

方案 A：改为真实调用主编排器。

```text
Smart Tutor 请求
→ 构造 AgentContext
→ AgentOrchestrator.process_turn()
→ 从实际 AgentResponse 生成 used_agents
```

方案 B：保留轻量 Smart Tutor，但将字段改名为：

```text
planned_roles / response_components
```

并只在 `used_agents` 中返回真实调用的 LLM/service 名称。

#### 验收标准

1. `used_agents` 中每个名称都有对应的本轮执行记录。
2. Agent trace 与响应字段一致。
3. 未注册 Agent 不出现在 used_agents。

---

### FIX-11：Smart Tutor 的 path_update 应进入正式路径服务

#### 代码证据

`SmartTutoringEngine.ask()` 构造并返回：

```python
path_update = {
    "next_kp": kp,
    "reason": "smart_tutor_question_loop",
    ...
}
```

但没有调用学习路径 Repository。

#### 建议修改

增加：

```text
LearningPathService.apply_smart_tutor_update()
```

处理策略：

- 用户已有活动路径：将 next_kp 写入调整记录或当前阶段建议；
- 没有路径：只创建“建议草稿”，由用户确认后生成完整路径；
- 将来源标记为 `smart_tutor`；
- 保留原始 question_id 作为证据。

#### 验收标准

1. Smart Tutor 返回的 path_update 有可查询的持久记录 ID。
2. LearnerState timeline 能看到该调整。
3. 重复请求具备幂等策略。

---

## 5. P2：编排、可观测性与质量能力

### FIX-12：修复 SafeDeclineAgent.reflect 签名

#### 代码证据

基类：

```python
async def reflect(self, content, context, ...)
```

SafeDeclineAgent：

```python
def reflect(self, ctx)
```

#### 建议修改

最简单方式是不覆盖 `reflect()`，并在 `DebateReflectionStage._should_reflect()` 中跳过：

```python
if resp.agent_name == "safe_decline":
    return False
```

或保持覆盖但使用完全一致的异步签名。

#### 验收标准

越界团队请求不产生 TypeError，且不进入无意义的反思流程。

---

### FIX-13：决定编排 YAML 的真实地位

#### 代码证据

`configs/agents/orchestration.yaml` 声明了 profile first、依赖和自动重规划等规则，但后端没有加载该文件。

#### 建议修改

选择一种架构：

1. 以 Python 为唯一真源：删除或标记 YAML 为示例文件；
2. 以 YAML 为配置真源：实现 `OrchestrationConfigLoader`，启动时加载并校验，再生成路由表。

不建议长期保留两个不一致的真源。

#### 验收标准

- 修改 YAML 后能通过测试证明运行行为变化；或
- 项目文档明确声明 Python 路由表是唯一运行配置。

---

### FIX-14：实现真正的任务依赖 DAG

#### 代码证据

`AgentTask` 定义 `depends_on`，但 `_plan_tasks()` 不填充，执行器也不读取。

#### 建议修改

如果需要画像先更新、评估消费练习结果等动态协作，可实现：

1. 任务图构建；
2. 拓扑排序；
3. 无依赖节点并发；
4. 将上游 `AgentResponse` 映射到下游 context；
5. 失败传播和降级策略；
6. 环检测。

示例依赖：

```text
profile → tutor/path/resource
quiz → evaluator
evaluator → adaptive_strategy
```

#### 验收标准

1. 下游 Agent 能读取上游结构化结果。
2. 独立任务仍并发。
3. 环依赖被启动前拒绝。
4. 单任务失败按策略跳过或降级。

---

### FIX-15：显式标记 LLM fallback

#### 代码证据

`LLMClient.achat()` 在空输出或 API 错误时直接返回 `_mock_chat()`，上层无法知道发生过回退。

#### 建议修改

将返回值改为结构化结果：

```python
LLMResult(
    text=...,
    provider=...,
    model=...,
    fallback_used=True,
    error=...,
    latency_ms=...,
)
```

或至少在请求级 context/telemetry 写入：

```text
llm_provider
llm_model
llm_fallback_used
llm_error
```

正式环境可配置：

```text
LLM_ALLOW_MOCK_FALLBACK=false
```

#### 验收标准

1. 外部 LLM 故障时监控能识别。
2. 前端可选择提示“当前使用降级模式”。
3. 正式环境可禁止 Mock。
4. Agent success 与 provider 状态不再混淆。

---

### FIX-16：区分工具 Trace 的 warmup 与真实任务调用

#### 代码证据

`_record_trace_for_multi()` 会执行：

```python
code="print('multi warmup')"
```

并主动进行知识点查询和资源搜索。

#### 建议修改

为 Trace 增加：

```text
call_origin: agent_decision | pipeline_support | warmup | user_action
```

固定 warmup 默认不计入“Agent 自主工具使用次数”。

更进一步，可把 warmup 改为健康检查，不写任务 Trace。

#### 验收标准

1. UI 能区分真实任务调用与系统预热。
2. 工具使用率统计只统计约定来源。
3. 研究评测不会把 warmup 当作 Agent 推理证据。

---

### FIX-17：实现真正的 LLM token 流式输出

#### 代码证据

`chat_stream()` 等 `_process_turn()` 完成后，再把完整文本按固定字符数切成 chunk。

#### 建议修改

需要把 streaming callback 下沉到 Agent 与 Pipeline：

```text
LLMClient.chat_stream
→ BaseAgent streaming execute
→ task_id 级 EventBuffer
→ SSE agent_chunk
```

同时保留：

- Agent 开始/结束事件；
- 多 Agent 并发时按 task_id 分流；
- 最终聚合结果；
- 断线重放；
- 对非流式生成器的兼容回退。

#### 验收标准

1. 首个正文 token 在完整回答完成前到达前端。
2. 多 Agent chunk 不串 task_id。
3. 最终拼接文本与持久化文本一致。
4. 断线重连不会重复或丢失事件。

---

### FIX-18：按产品要求接入 Reviewer/COVVerifier

#### 代码证据

- `ReviewerAgent` 和 `COVVerifierAgent` 已实现并注册；
- 主聊天聚合只调用 `quick_quality_score()` 和 `ContentSafetyChecker`；
- 多资源 `cov` 使用 `ConsistencyChecker`；
- CoV Demo 使用 `CoVDemoService`。

#### 建议修改

只有在产品确实要求“所有最终回答统一经过 Reviewer/CoV Agent”时接入，建议增加独立 Stage：

```text
DebateReflection
→ VerificationStage
   ├─ ReviewerAgent
   ├─ COVVerifierAgent
   └─ ContentSafetyChecker
→ Aggregation/Persist
```

需要定义：

- 哪些内容类型必须验证；
- 超时与降级；
- RAG 无证据时的处理；
- 修订次数；
- 用户是否可见验证报告；
- token 与延迟预算。

#### 验收标准

1. 被要求验证的回答有 Reviewer/CoV trace。
2. 失败或低分时按策略修订、警告或阻断。
3. 多模态资源和聊天正文的验证口径统一。
4. 不要求验证的轻量请求不增加不必要延迟。

---

## 6. 建议新增的测试文件

| 测试文件建议 | 覆盖内容 |
| --- | --- |
| `tests/integration/test_chat_path_persistence.py` | 智狐聊天路径写入 Repository、重启可读 |
| `tests/integration/test_chat_assessment_persistence.py` | 团团评估进入 AssessmentRepository 与 LearnerState |
| `tests/a/test_agent_user_identity.py` | session ID 与 user ID 分离 |
| `tests/a/test_rag_kp_contract.py` | RAG 返回 kp_id 与学习状态回写 |
| `tests/a/test_profile_update_merge.py` | 多 Agent 画像更新合并和字段权限 |
| `tests/a/test_configurable_agent_rag_tools.py` | RAG content、allowed_tools 白名单 |
| `frontend/src/api/chat.spec.ts` | SSE 全事件解析与 REST 类型 |
| `tests/a/test_smart_tutor_trace.py` | used_agents 与真实调用一致 |
| `tests/a/test_safe_decline_reflection.py` | 安全拒答不进入错误反思 |
| `tests/integration/test_true_sse_stream.py` | token 级流式、task_id 隔离和重放 |

## 7. 完成定义

本整改文档全部完成时，应满足：

1. 聊天产生的路径、评估、画像、资源和学习状态都通过正式 Repository 或 service 形成一致闭环。
2. 所有认知状态服务统一使用真实 `user_id`。
3. RAG、AgentContext、PersistStage 的知识点字段契约一致。
4. 前端 REST/SSE 类型与后端响应完全对齐。
5. 配置型 Agent 展示的能力与真实执行能力一致。
6. Smart Tutor 的 Agent 追踪和路径更新均可由持久化记录证明。
7. LLM 降级、工具来源、Reviewer/CoV 和 SSE streaming 均具备明确可观测性。
8. 每项修复均有自动化测试，不依赖人工演示判断是否成功。
