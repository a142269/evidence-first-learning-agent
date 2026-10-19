# 测试分层矩阵（Test Matrix）

> 编写：Qwen · 日期：2026-10-19 · 任务：QWEN-002（Wave 0）· 基线：`main@23766d9`
> 依据：`.github/workflows/ci.yml`、`.github/workflows/nightly.yml` 实测解析 + 全量清单。
> 本轮实测：共 **189** 个 Python 测试文件（`tests/a` 124〔含 `tests/a/benchmarks/` 1〕、`tests/b` 42、`tests/integration` 9、`tests/regression` 5、`tests/benchmarks` 4、`tests/` 根 5）。

## 1. 分层定义

| 层 | 运行位置 | 集合 | 门槛/预算 | 目的 |
|---|---|---|---|---|
| **fast** | 每次 push main / PR（CI `quality` job） | 37 个便携 V2 契约文件（下表 `F` 列） | job 超时 20 分钟；本轮实测 58.5 s（369 passed / 1 skipped） | 主线契约回归：权限、学习包、部分完成、结构化输出、评测器、租约/幂等 |
| **contract-pg** | CI `enterprise-contract` job（PG16+pgvector / Redis7 服务容器） | 38 个文件（`E` 列，QWEN-120 补入 `test_v2_retrieval_postgres.py`；首轮统计为 37）+ MCP 协议 1（`M` 列，独立步骤） | job 超时 20 分钟；历史实测 173.6 s（353 passed） | 真实数据库/中间件合同：跨进程恢复、迁移、认证、检索、摄取 |
| **nightly** | 每日 19:20 UTC + 手动 dispatch（`offline` job） | **全量** `pytest tests/`；需外部依赖的用例按设计自动 skip | job 超时 60 分钟；产出核心覆盖率 `build/coverage.xml` | 发现 fast/contract 未覆盖的 V1/算法/演示资产回归 |
| **nightly-lock** | 同上 workflow（`linux-lockfile` job） | 学习包核心 3 文件 | 按哈希安装 `requirements.lock.linux.txt` 后运行 | Linux 锁可安装性冒烟 |
| **manual** | 本地/授权环境 | 见 §4 | 需真人或真实凭据 | 付费云评测、浏览器走查、Docker 冒烟、性能压测 |

**为什么其余文件不进 fast**：fast 层刻意只保留"SQLite + 离线 + 确定性 + <20 分钟"的便携子集；其余文件或依赖 PostgreSQL/Redis/torch/本机媒体工具链，或运行慢（独立 Worker 进程测试），或属 V1/实验面（不阻断 V2 主线）。它们由 nightly 全量收集兜底；现存缺口在 §5 列出。

## 2. Python 测试文件矩阵（189）

图例：`F`=fast CI quality 清单；`E`=enterprise 合同清单；`M`=enterprise 内 MCP 可选步骤；`N` 列 `✓`=nightly 全量中实跑，`s`=nightly 收集但缺外部依赖（显式 PG / MCP SDK 等）时自动 skip。

| 文件 | F | E | M | N | 备注（依赖 / 为何不进 CI / 已知状态） |
|---|---|---|---|---|---|
| tests/a/benchmarks/test_chat_bench.py |  |  |  | ✓ |  |
| tests/a/test_ablation_collect.py | F |  |  | ✓ |  |
| tests/a/test_ablation_dataset.py | F |  |  | ✓ |  |
| tests/a/test_ablation_report.py | F |  |  | ✓ |  |
| tests/a/test_ablation_review_packets.py | F |  |  | ✓ |  |
| tests/a/test_ablation_runner.py | F |  |  | ✓ |  |
| tests/a/test_adversarial_leakage.py |  |  |  | ✓ |  |
| tests/a/test_agent_tools.py |  |  |  | ✓ |  |
| tests/a/test_assistments_q_matrix.py |  |  |  | ✓ |  |
| tests/a/test_auth_migration.py |  | E |  | s |  |
| tests/a/test_auth_restart.py | F | E |  | s |  |
| tests/a/test_backfill_enterprise_corpus_summary.py |  |  |  | ✓ |  |
| tests/a/test_base_agent.py |  |  |  | ✓ |  |
| tests/a/test_calibrated_adapter.py |  |  |  | ✓ |  |
| tests/a/test_campus_assets.py | F |  |  | ✓ |  |
| tests/a/test_celery_worker_process.py |  |  |  | ✓ | 独立 Celery solo worker 子进程；慢，不进 fast |
| tests/a/test_chapter_frontmatter.py |  |  |  | ✓ |  |
| tests/a/test_chat_pipeline.py |  |  |  | ✓ |  |
| tests/a/test_checkpoint_lifecycle.py | F |  |  | ✓ |  |
| tests/a/test_claim_ledger.py |  |  |  | ✓ |  |
| tests/a/test_claim_support.py | F |  |  | ✓ |  |
| tests/a/test_cockpit_branches.py |  |  |  | ✓ |  |
| tests/a/test_cockpit_endpoint.py |  |  |  | ✓ |  |
| tests/a/test_code_sandbox.py |  |  |  | ✓ |  |
| tests/a/test_collaboration_resource_regressions.py |  |  |  | ✓ |  |
| tests/a/test_convergence_tracker.py |  |  |  | ✓ |  |
| tests/a/test_conversation_memory_v2.py | F | E |  | ✓ |  |
| tests/a/test_cov.py |  |  |  | ✓ |  |
| tests/a/test_cov_demo_api.py |  |  |  | ✓ |  |
| tests/a/test_critic.py |  |  |  | ✓ |  |
| tests/a/test_debate.py |  |  |  | ✓ |  |
| tests/a/test_debate_sse_events.py |  |  |  | ✓ |  |
| tests/a/test_deepseek_model_alias.py |  |  |  | ✓ |  |
| tests/a/test_demo_journey.py |  |  |  | ✓ |  |
| tests/a/test_deployment_policy.py | F | E |  | ✓ |  |
| tests/a/test_diagnosis_reporter.py |  |  |  | ✓ |  |
| tests/a/test_dina_real_adapter.py |  |  |  | ✓ |  |
| tests/a/test_dual_graph.py |  |  |  | ✓ |  |
| tests/a/test_embedding_provider.py |  |  |  | ✓ |  |
| tests/a/test_embedding_provider_resilience.py | F | E |  | ✓ |  |
| tests/a/test_enterprise_retriever.py |  | E |  | ✓ |  |
| tests/a/test_fix_p0_closures.py |  |  |  | ✓ |  |
| tests/a/test_golden_set_evaluator.py | F | E |  | ✓ |  |
| tests/a/test_golden_set_runner.py | F | E |  | ✓ |  |
| tests/a/test_golden_set_v2.py | F | E |  | ✓ |  |
| tests/a/test_hyde_rrf.py |  |  |  | ✓ |  |
| tests/a/test_ingestion_staging.py |  |  |  | ✓ |  |
| tests/a/test_intent_classifier.py |  |  |  | ✓ |  |
| tests/a/test_knowledge_extras.py |  |  |  | ✓ |  |
| tests/a/test_knowledge_index.py |  |  |  | ✓ |  |
| tests/a/test_knowledge_ingest_enterprise.py |  | E |  | ✓ |  |
| tests/a/test_knowledge_map_consistency.py |  |  |  | ✓ |  |
| tests/a/test_knowledge_platform.py |  |  |  | ✓ |  |
| tests/a/test_learner_endpoints.py |  |  |  | ✓ |  |
| tests/a/test_learner_state.py |  |  |  | ✓ |  |
| tests/a/test_learning_checkpoint_postgres.py |  | E |  | s |  |
| tests/a/test_learning_graph_safety.py | F | E |  | ✓ |  |
| tests/a/test_learning_package.py | F | E |  | ✓ |  |
| tests/a/test_learning_package_collection.py | F | E |  | ✓ |  |
| tests/a/test_learning_package_evaluator.py | F | E |  | ✓ |  |
| tests/a/test_learning_package_online_collector.py |  |  |  | ✓ | 在线采集器的离线契约测试 |
| tests/a/test_learning_package_partial.py | F | E |  | ✓ |  |
| tests/a/test_learning_package_partial_postgres.py |  | E |  | s |  |
| tests/a/test_learning_package_retry_guidance.py | F |  |  | ✓ |  |
| tests/a/test_learning_run_reconciliation.py | F | E |  | ✓ |  |
| tests/a/test_learning_runs_v2.py | F | E |  | ✓ |  |
| tests/a/test_learning_runs_v2_lifecycle.py | F | E |  | ✓ |  |
| tests/a/test_learning_runtime_retrieval.py | F | E |  | ✓ |  |
| tests/a/test_llm_client.py |  |  |  | ✓ |  |
| tests/a/test_manim.py |  |  |  | ✓ | 依赖本机 manim 工具链；不稳定处需手动复跑 |
| tests/a/test_mcp_readonly_protocol.py |  |  | M | s | 需 requirements-mcp.txt；nightly 未安装该依赖时按 importorskip 跳过 |
| tests/a/test_mermaid_studio.py |  |  |  | ✓ |  |
| tests/a/test_mistake_course_filter.py |  |  |  | ✓ |  |
| tests/a/test_mobile_student_api.py |  |  |  | ✓ |  |
| tests/a/test_multimodal_dashboard_recommendations.py |  |  |  | ✓ |  |
| tests/a/test_ocr.py |  |  |  | ✓ |  |
| tests/a/test_orchestrator.py |  |  |  | ✓ |  |
| tests/a/test_orchestrator_dm.py |  |  |  | ✓ |  |
| tests/a/test_path_course_scope.py |  |  |  | ✓ |  |
| tests/a/test_pedagogical_bridge.py |  |  |  | ✓ |  |
| tests/a/test_pedagogical_safety.py |  |  |  | ✓ |  |
| tests/a/test_persistent_auth.py | F | E |  | ✓ |  |
| tests/a/test_postgres_api_recovery.py |  | E |  | s |  |
| tests/a/test_pptx_builder.py |  |  |  | ✓ |  |
| tests/a/test_profile_extractor.py |  |  |  | ✓ |  |
| tests/a/test_profile_schema.py |  |  |  | ✓ |  |
| tests/a/test_prompt_cache.py |  |  |  | ✓ |  |
| tests/a/test_question_bank.py |  |  |  | ✓ |  |
| tests/a/test_question_bank_merged.py |  |  |  | ✓ |  |
| tests/a/test_realdina_service.py |  |  |  | ✓ |  |
| tests/a/test_reflection.py |  |  |  | ✓ |  |
| tests/a/test_registered_account_persistence.py |  |  |  | ✓ |  |
| tests/a/test_registration_onboarding.py |  |  |  | ✓ |  |
| tests/a/test_resource_course_filter.py |  |  |  | ✓ |  |
| tests/a/test_resource_ownership.py |  |  |  | ✓ |  |
| tests/a/test_run_lease_migration.py |  | E |  | s |  |
| tests/a/test_run_leases.py | F | E |  | ✓ |  |
| tests/a/test_seed_extended.py |  |  |  | ✓ |  |
| tests/a/test_smart_tutoring.py |  |  |  | ✓ |  |
| tests/a/test_spaced_repetition.py |  |  |  | ✓ |  |
| tests/a/test_startup_log_redaction.py | F |  |  | ✓ |  |
| tests/a/test_static_and_ws_safety.py | F | E |  | ✓ |  |
| tests/a/test_structured_output_robustness.py | F | E |  | ✓ |  |
| tests/a/test_student_data_deletion.py |  |  |  | ✓ |  |
| tests/a/test_teacher_collaboration.py |  |  |  | ✓ |  |
| tests/a/test_tts_xunfei.py |  |  |  | ✓ | 讯飞 TTS 边界用桩；不发真实请求 |
| tests/a/test_v1_production_access.py | F | E |  | ✓ |  |
| tests/a/test_v2_access.py | F | E |  | ✓ |  |
| tests/a/test_v2_auth_throttle.py | F | E |  | ✓ |  |
| tests/a/test_v2_eval_cost_guard.py | F | E |  | ✓ |  |
| tests/a/test_v2_event_idempotency.py | F | E |  | ✓ |  |
| tests/a/test_v2_ingestion_idempotency.py |  | E |  | ✓ |  |
| tests/a/test_v2_ingestion_postgres.py |  | E |  | s |  |
| tests/a/test_v2_learning_tools.py | F |  |  | ✓ |  |
| tests/a/test_v2_model_usage.py | F |  |  | ✓ |  |
| tests/a/test_v2_retrieval_comparison.py |  |  |  | ✓ |  |
| tests/a/test_v2_retrieval_postgres.py |  | ✓ |  | s | 需显式一次性 PG；QWEN-120 已补入 enterprise 清单（本机 pg 实测 1 passed） |
| tests/a/test_v2_unfinished_postgres.py |  | E |  | s |  |
| tests/a/test_v2_unfinished_resume.py |  | E |  | ✓ |  |
| tests/a/test_variant_generator.py |  |  |  | ✓ |  |
| tests/a/test_vector_reindex.py |  | E |  | ✓ |  |
| tests/a/test_verify_demo_assets.py |  |  |  | ✓ |  |
| tests/a/test_video_demo_account.py |  |  |  | ✓ | 视频回归使用桩执行器 |
| tests/a/test_video_quality_regressions.py |  |  |  | ✓ |  |
| tests/b/test_active_learning.py |  |  |  | ✓ |  |
| tests/b/test_algorithm_state_persistence.py |  |  |  | ✓ |  |
| tests/b/test_archetype_narrative_svg.py |  |  |  | ✓ |  |
| tests/b/test_assistments_benchmark.py |  |  |  | ✓ |  |
| tests/b/test_attribution_engine.py |  |  |  | ✓ |  |
| tests/b/test_b_evidence_reporting.py |  |  |  | ✓ |  |
| tests/b/test_benchmarks.py |  |  |  | ✓ |  |
| tests/b/test_bkt_forecaster.py |  |  |  | ✓ |  |
| tests/b/test_bkt_persisted_demo_state.py |  |  |  | ✓ |  |
| tests/b/test_bkt_plus_and_hlr.py |  |  |  | ✓ |  |
| tests/b/test_bloom_6x3.py |  |  |  | ✓ |  |
| tests/b/test_bloom_forgetting.py |  |  |  | ✓ |  |
| tests/b/test_bloom_relabel.py |  |  |  | ✓ |  |
| tests/b/test_build_kg_extended.py |  |  |  | ✓ |  |
| tests/b/test_cockpit_endpoint.py |  |  |  | ✓ |  |
| tests/b/test_cognitive_diagnosis.py |  |  |  | ✓ |  |
| tests/b/test_contract_document.py |  |  |  | ✓ |  |
| tests/b/test_database_models.py |  |  |  | ✓ |  |
| tests/b/test_forecast_api.py |  |  |  | ✓ |  |
| tests/b/test_gamification_api.py |  |  |  | ✓ |  |
| tests/b/test_graph_rag_hybrid.py |  |  |  | ✓ |  |
| tests/b/test_kg_builder.py |  |  |  | ✓ |  |
| tests/b/test_kg_neighbors.py |  |  |  | ✓ |  |
| tests/b/test_learning_path_loop.py |  |  |  | ✓ |  |
| tests/b/test_llm_cost_endpoint.py |  |  |  | ✓ |  |
| tests/b/test_mistake_attribution.py |  |  |  | ✓ |  |
| tests/b/test_mistake_review.py |  |  |  | ✓ |  |
| tests/b/test_operations_infrastructure.py |  |  |  | ✓ |  |
| tests/b/test_pedagogical_context.py |  |  |  | ✓ |  |
| tests/b/test_peer_matching.py |  |  |  | ✓ |  |
| tests/b/test_persistence_api.py |  |  |  | ✓ |  |
| tests/b/test_persistence_repositories.py |  |  |  | ✓ |  |
| tests/b/test_phase23_algorithms.py |  |  |  | ✓ |  |
| tests/b/test_profile_schema.py |  |  |  | ✓ |  |
| tests/b/test_rag_persistence.py |  |  |  | ✓ |  |
| tests/b/test_sakt.py |  |  |  | ✓ | 需要 torch（nightly 显式安装 CPU wheel） |
| tests/b/test_seed_b_extended.py |  |  |  | ✓ |  |
| tests/b/test_seed_demo.py |  |  |  | ✓ |  |
| tests/b/test_sm2_and_kg.py |  |  |  | ✓ |  |
| tests/b/test_spaced_repetition_benchmark.py |  |  |  | ✓ |  |
| tests/b/test_telemetry.py |  |  |  | ✓ |  |
| tests/b/test_timemachine_service.py |  |  |  | ✓ |  |
| tests/benchmarks/test_bench_code_sandbox.py |  |  |  | ✓ |  |
| tests/benchmarks/test_bench_mermaid.py |  |  |  | ✓ |  |
| tests/benchmarks/test_bench_pipeline.py |  |  |  | ✓ |  |
| tests/benchmarks/test_bench_pptx.py |  |  |  | ✓ |  |
| tests/integration/test_artifacts_api.py |  |  |  | ✓ |  |
| tests/integration/test_b_api_validation.py |  |  |  | ✓ |  |
| tests/integration/test_b_journey.py |  |  |  | ✓ |  |
| tests/integration/test_chat_e2e.py |  |  |  | ✓ |  |
| tests/integration/test_five_resources_e2e.py |  |  |  | ✓ |  |
| tests/integration/test_graph_bkt_hover.py |  |  |  | ✓ |  |
| tests/integration/test_manim_fallback.py |  |  |  | ✓ |  |
| tests/integration/test_multi_evidence.py |  |  |  | ✓ |  |
| tests/integration/test_spaced_priority.py |  |  |  | ✓ |  |
| tests/regression/test_mermaid_resilience.py |  |  |  | ✓ |  |
| tests/regression/test_pptx_resilience.py |  |  |  | ✓ |  |
| tests/regression/test_question_bank_resilience.py |  |  |  | ✓ |  |
| tests/regression/test_sandbox_resilience.py |  |  |  | ✓ |  |
| tests/regression/test_sandbox_security_p0.py |  |  |  | ✓ | V1 沙箱安全 P0：建议 nightly 独立步骤（§5.2） |
| tests/test_demo_bkt_variation.py |  |  |  | ✓ |  |
| tests/test_demo_business_data.py |  |  |  | ✓ |  |
| tests/test_demo_data_unification.py |  |  |  | ✓ |  |
| tests/test_enrich_demo_mistakes.py |  |  |  | ✓ |  |
| tests/test_mistake_list_limit.py |  |  |  | ✓ |  |
注：`N=s` 之外不排除个别用例因平台/数据状态 skip；今日 Windows 全量复跑的实际 skip/fail 清单见
`output/qwen-baseline-2026-10-19/report.md`，与 nightly（Ubuntu）存在平台差异。

## 3. 前端与桌面测试

| 集合 | 数量 | 当前覆盖 | 分层 |
|---|---|---|---|
| `frontend/tests/*.test.mjs`（node:test 单元，含 `learningStream.test.mjs`） | 17（另有 17 个移入 `_orphaned/`） | **已进 CI**：`ci.yml` frontend job 新增 `node --test tests/*.test.mjs`（无 `|| true`）；本机 node v24.13.0 实测 21 顶层结果 **0 failed / exit 0** | fast（QWEN-121）；`_orphaned/` 17 个 = 已知缺口，等 `integrated-map-src`/`CockpitView.vue` 来源结论（QWEN-401/343），**不是"已覆盖"** |
| `tests/desktopPackaging.test.mjs` | 1 | 不在 CI | manual（Electron 打包检查） |

## 4. manual 层清单（不进自动化）

| 项 | 需要 | 说明 |
|---|---|---|
| `scripts/evaluate_golden_set.py` 全量在线评测 | 付费授权 + 企业栈 | cloud；已跑两轮 76 条（2026-10-16），复跑属 QWEN-102/105 范畴 |
| `scripts/collect_learning_package.py` 在线采集 24 条 | 付费授权 | 13 条 standard 已采集；其余 11 条故障注入应继续走受控离线 Provider |
| 真实浏览器端到端（学生续跑/教师审核） | Docker + 在线模型 | 现为模拟 API/桩模型走查；Playwright 化 = QWEN-331 |
| `docker compose ... up --build` 生产栈冒烟 | Docker Desktop | 2026-10-18 已做（本机 prod）；公网 = QWEN-403 |
| `scripts/load_test` 完整压测 | — | CI 已有 light 步骤（5 并发×30）；cockpit p95 ~112.7 s 历史观察，无门槛定义 |
| `tests/a/benchmarks/test_chat_bench.py`、`tests/benchmarks/*` | 手动 | `--benchmark-disable` 下仅收集断言；性能结果不入发布门禁（当前无门槛） |

## 5. 缺口与 nightly 计划（QWEN-343 的输入）

按"应当先补"排序：

1. **nightly 远端实际运行记录未核验**：workflow 已定义（cron `20 19 * * *` + dispatch），本轮无 gh CLI，无法确认最近一次运行结论。第一步：触发一次 `Nightly offline suite` 并把 run 编号/耗时/skip 清单记入状态文档。
2. **`tests/regression/test_sandbox_security_p0.py` 等 V1 安全专项**只被 nightly 全量收集，无独立步骤：建议 nightly 加独立步骤并单列失败注解——P0 语义不应埋在 60 分钟全量里。
3. ~~**前端 34 个 `.mjs` 单元**未进任何 CI~~ —— **QWEN-121 已接（方案 A，Lead 2026-10-19 [DECISION]）**：`ci.yml` frontend job 增加 `node --test tests/*.test.mjs`（cwd=frontend，shell 展开 glob，**无** `|| true`）。17 个依赖本仓库未提交源码（`frontend/integrated-map-src/` 或 `frontend/src/views/CockpitView.vue`）的用例 `git mv` 到 `frontend/tests/_orphaned/`（只移不删，附逐文件缺失路径清单），glob 单层 `*` 不跨目录所以不会被命中；另 4 个过期断言按当前源码修正，其中 2 个语义被改写（见台账 S8）。本机：17 文件 / 21 顶层结果 **0 failed、exit 0**（node v24.13.0）；CI 用 node 20，待合并后由 main 的 CI 复验。注意 `node --test tests/`（目录形式）在 node 24 会当模块加载并报 `MODULE_NOT_FOUND`，必须用 glob 形式。
4. ~~**`tests/a/test_v2_retrieval_postgres.py`** 不在 enterprise 清单~~ —— **QWEN-120 已修**：补入 `.github/workflows/ci.yml` enterprise 清单（37 → 38 文件），本机一次性 pgvector 容器实测 1 passed（pg 级）。
5. **`tests/b`（42，依赖 torch）与 `tests/integration`（9）**：nightly 全量收集但无分文件通过报表；建议 nightly 步骤输出 `-rf` 短摘要并上传日志 artifact。
6. **覆盖率门禁仅学习包两模块 ≥80%**：主计划 §7 还要求扩展核心（memory/tools/scheduler）≥70%——nightly 已有 coverage.xml，但无判定；建议在 QWEN-343 中加阈值步骤。

## 6. 本轮（Wave 0）实测摘要

| 运行 | 集合 | 结果 |
|---|---|---|
| fast 清单（本机等价，SQLite/离线） | 37 文件 | **369 passed / 1 skipped / 0 failed**（58.54 s）；skip=`test_auth_restart.py`（需显式一次性 PG） |
| 覆盖率门禁（本机等价） | 5 文件 | **110 passed**；learning_package 94%、claim_support 83%、合计 92.44%（≥80） |
| 全量 `pytest tests/`（本机 Windows，Python 3.12.15） | 189 文件 | **2 failed / 2234 passed / 19 skipped**（650.31 s）；两个失败已定位为本机环境依赖（pywin32）与测试期望过期（edge-tts 回退），见台账 R11 与 `output/qwen-baseline-2026-10-19/report.md` |
| 同上（QWEN-004 收口后复跑，新 `--basetemp` + 独立 SQLite） | 189 文件 | **2235 passed / 0 failed / 20 skipped**（612.61 s，offline）；+1 passed = TTS 断言补 `edge-tts`，+1 skipped = Celery 在 Windows 缺 `pywintypes` 条件跳过；未装 pywin32 |
| QWEN-004 定向复跑（`test_artifacts_api.py` + `test_celery_worker_process.py`） | 2 文件 | **24 passed / 1 skipped（expected）/ 0 failed**（58.37 s，offline）；`ruff --select F,E9` 与 `tests/ --select F821,F823,E9` 通过 |
| QWEN-120：`test_v2_retrieval_postgres.py` 加入 enterprise 清单后的本机验证 | 1 文件 | **1 passed**（1.56 s，pg：一次性 pgvector/pg16 容器，tmpfs、仅 `127.0.0.1:55432`，跑完 `--rm` 删除） |
| QWEN-120 首测：`node --test tests/*.test.mjs`（cwd=frontend） | 34 文件 | **17 passed / 21 failed**（offline，node v24.13.0）；失败原因见台账 S8 |
| QWEN-121 方案 A 执行后：`git mv` 17 个孤儿测试进 `_orphaned/`（只移不删）+ 修正 4 个过期断言 | 17 文件 | **21 顶层结果 passed / 0 failed / exit 0**（430.9 ms，offline，node v24.13.0）；已接入 CI frontend job（无 `|| true`）；CI node 20 待 main 复验 |
| QWEN-121 追加：本机 node 20 预检（尝试） | 0 | **无法执行，非跳过**（offline 阻塞）：本机只有 `node v24.13.0`（`which -a node` → 仅 `/d/node.js/node`，无 nvm/fnm 等其他版本），`docker pull node:20-slim` 失败（Docker Desktop 无 HTTPS 代理，`registry-1.docker.io:443` 连接超时），本地 `evidence-first-learning-agent-frontend:latest` 镜像内无 `node`（静态托管镜像）。改为代码层核对：`node --test <显式文件列表>` 自 node 18.13 起支持；唯一第三方依赖是 `learningStream.test.mjs` 的 `typescript`，属 devDependency，CI `npm ci` 会安装。node 20 真实绿/红仍只能由合并后 main 的 fast 作业给出 |
