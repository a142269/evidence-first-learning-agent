# ADR-0003：以 OpenTelemetry + Phoenix 建立可观测性

- 状态：Accepted（OTLP 初始化与 Phoenix 容器已接入）
- 日期：2026-10-10

## 背景

仅有应用日志无法回答“某次回答使用了哪些证据、为什么失败、耗时和成本在哪里”的问题。
而将追踪绑定到特定 LLM 云服务会限制模型供应商选择。

## 决策

业务代码使用 OpenTelemetry API 输出 trace；本地通过 Phoenix 接收 OTLP HTTP trace 并可视化。
Phoenix 使用独立数据库，避免观测数据的保留策略影响业务数据。LangSmith 只作为未来可选的
云端适配器，而非运行时强依赖。

## 后果

- `OTEL_EXPORTER_OTLP_ENDPOINT` 未配置或 SDK 不可用时安全降级，不阻塞离线演示。
- 学习问答运行会产生顶层 span；后续补充模型、retriever、工具、审核、token 与成本子 span。
- 生产部署必须为 Phoenix 增加认证、TLS、保留策略和访问控制；本地 Compose 默认只面向开发机。
