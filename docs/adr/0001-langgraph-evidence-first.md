# ADR-0001：以 LangGraph 迁移一条可审计学习问答链路

- 状态：Accepted（首条链路已接入，持久化 Checkpointer 待后续接入）
- 日期：2026-10-10

## 背景

原项目的自研多 Agent 编排支撑了十余种资源生成能力，但状态、人工审核、重放和流式事件
没有统一契约。一次性替换全部 Agent 风险高，也不利于证明生产化能力。

## 决策

只迁移“有证据的个性化学习问答与推荐”这条高频链路。LangChain 负责模型、Prompt、
结构化输出、工具与 Retriever 集成；LangGraph `StateGraph` 负责检索、生成、引用校验、
流式事件与人工审核边界。旧 Agent 继续通过适配层运行。

RunContext、RunPolicy、RunResult 是框架外的 Harness 契约：调用方必须明确用户、课程、
会话、权限、预算、超时和 trace；运行结果必须带回答、证据、质量、成本、延迟和审计事件。

## 后果

- 新接口以 SSE 稳定输出 `run.started` 至 `run.completed`/`run.failed` 事件。
- 无证据时不生成事实性断言；有证据的答案必须返回引用。
- 本地离线演示仍可回退到确定性实现；生产部署下一步接入 `AsyncPostgresSaver` 保存线程状态。
- 新功能先进入旗舰链路，旧功能不被“大重写”阻塞。
