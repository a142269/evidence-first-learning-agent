# ADR-0002：为旗舰 RAG 选择 PostgreSQL + pgvector

- 状态：Accepted（Compose、迁移和 HNSW 索引已接入）
- 日期：2026-10-10

## 背景

SQLite + TF-IDF 是可靠的离线演示退路，但无法覆盖并发写入、文档版本、向量检索审计和
生产化备份需求。单独再维护一套向量数据库会增加本项目的运维面。

## 决策

旗舰环境使用 PostgreSQL + pgvector。文档版本、Chunk、Embedding、检索日志、Agent
checkpoint 和评测结果共用可迁移的关系数据模型；向量列使用 pgvector，并建立 HNSW
余弦索引。检索策略演进为 PostgreSQL 全文检索、稠密检索、RRF 与 reranker 的组合。

## 后果

- Docker Compose 以命名卷持久化 PostgreSQL，首次初始化 `vector` 扩展。
- Alembic 新增 V2 表和 HNSW 索引；SQLite 保留 JSON embedding 回退，确保竞赛演示可运行。
- 当前代码仍保留 TF-IDF 检索作为回退；BGE-M3 embedding 与 reranker 是下一阶段，不虚报为已启用。
