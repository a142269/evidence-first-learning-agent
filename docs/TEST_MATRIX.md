# 测试分层矩阵（Test Matrix）

> 编写：Qwen · 日期：2026-10-19 · 任务：QWEN-002（Wave 0）· 基线：`main@23766d9`
> 依据：`.github/workflows/ci.yml`、`.github/workflows/nightly.yml` 实测解析 + 全量清单。
> 本轮实测：共 **191** 个 Python 测试文件（`tests/a` 126〔含 `tests/a/benchmarks/` 1〕、`tests/b` 42、`tests/integration` 9、`tests/regression` 5、`tests/benchmarks` 4、`tests/` 根 5）。
> 计数更新：QWEN-101 新增 2 个 `tests/a` 文件（`test_human_agreement_statistics.py`、`test_human_eval_toolkit.py`），189 → **191**（原 189 为 Wave 0 基线，见 §6）。

## 1. 分层定义

| 层 | 运行位置 | 集合 | 门槛/预算 | 目的 |
|---|---|---|---|---|
| **fast** | 每次 push main / PR（CI `quality` job） | 39 个便携 V2 契约文件（下表 `F` 列；QWEN-101 补入 2 个人工评测文件，Wave 0 基线为 37） | job 超时 20 分钟；Wave 0 基线 58.5 s（369 passed / 1 skipped），QWEN-101 后本机等价复跑 54.9 s（396 passed / 1 skipped），QWEN-102 采集器 `--arm` 改动后 55.0 s（398 passed / 1 skipped） | 主线契约回归：权限、学习包、部分完成、结构化输出、评测器、租约/幂等、人工盲评工具包 |
| **contract-pg** | CI `enterprise-contract` job（PG16+pgvector / Redis7 服务容器） | 38 个文件（`E` 列，QWEN-120 补入 `test_v2_retrieval_postgres.py`；首轮统计为 37）+ MCP 协议 1（`M` 列，独立步骤） | job 超时 20 分钟；历史实测 173.6 s（353 passed） | 真实数据库/中间件合同：跨进程恢复、迁移、认证、检索、摄取 |
| **nightly** | 每日 19:20 UTC + 手动 dispatch（`offline` job） | **全量** `pytest tests/`；需外部依赖的用例按设计自动 skip | job 超时 60 分钟；产出核心覆盖率 `build/coverage.xml` | 发现 fast/contract 未覆盖的 V1/算法/演示资产回归 |
| **nightly-lock** | 同上 workflow（`linux-lockfile` job） | 学习包核心 3 文件 | 按哈希安装 `requirements.lock.linux.txt` 后运行 | Linux 锁可安装性冒烟 |
| **manual** | 本地/授权环境 | 见 §4 | 需真人或真实凭据 | 付费云评测、浏览器走查、Docker 冒烟、性能压测 |

**为什么其余文件不进 fast**：fast 层刻意只保留"SQLite + 离线 + 确定性 + <20 分钟"的便携子集；其余文件或依赖 PostgreSQL/Redis/torch/本机媒体工具链，或运行慢（独立 Worker 进程测试），或属 V1/实验面（不阻断 V2 主线）。它们由 nightly 全量收集兜底；现存缺口在 §5 列出。

## 2. Python 测试文件矩阵（192）

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
| tests/a/test_human_agreement_statistics.py | F |  |  | ✓ | QWEN-101 人工一致性统计（κ/Wilson/bootstrap），纯 stdlib、毫秒级 |
| tests/a/test_human_eval_toolkit.py | F |  |  | ✓ | QWEN-101 `scripts/human_eval/` 五个入口的端到端门禁，fixtures 全合成、不落真实题面 |
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
| tests/a/test_run_usage_admin.py | F |  |  | ✓ | QWEN-104 新增（管理端只读用量/成本摘要，9 用例）；仅进 portable V2 contract suite，未扩 pg/enterprise 清单 |
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
3. ~~**前端 34 个 `.mjs` 单元**未进任何 CI~~ —— **QWEN-121 已接（方案 A，Lead 2026-10-19 [DECISION]）**：`ci.yml` frontend job 增加 `node --test tests/*.test.mjs`（cwd=frontend，shell 展开 glob，**无** `|| true`）。17 个依赖本仓库未提交源码（`frontend/integrated-map-src/` 或 `frontend/src/views/CockpitView.vue`）的用例 `git mv` 到 `frontend/tests/_orphaned/`（只移不删，附逐文件缺失路径清单），glob 单层 `*` 不跨目录所以不会被命中；另 4 个过期断言按当前源码修正，其中 2 个语义被改写（见台账 S8）。本机：17 文件 / 21 顶层结果 **0 failed、exit 0**（node v24.13.0）；CI 用 node 20——合并后 `main` run **#21** 的 Frontend unit tests step **已通过**（Lead 2026-10-19 14:55 报告；证据等级 `remote`，本机无 `gh` CLI 未能程序化自查）。注意 `node --test tests/`（目录形式）在 node 24 会当模块加载并报 `MODULE_NOT_FOUND`，必须用 glob 形式。
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
| QWEN-121 方案 A 执行后：`git mv` 17 个孤儿测试进 `_orphaned/`（只移不删）+ 修正 4 个过期断言 | 17 文件 | **21 顶层结果 passed / 0 failed / exit 0**（430.9 ms，offline，node v24.13.0）；已接入 CI frontend job（无 `|| true`）；CI node 20 由 main run #21 复验通过（`remote`） |
| QWEN-121 追加：本机 node 20 预检（尝试） | 0 | **无法执行，非跳过**（offline 阻塞）：本机只有 `node v24.13.0`（`which -a node` → 仅 `/d/node.js/node`，无 nvm/fnm 等其他版本），`docker pull node:20-slim` 失败（Docker Desktop 无 HTTPS 代理，`registry-1.docker.io:443` 连接超时），本地 `evidence-first-learning-agent-frontend:latest` 镜像内无 `node`（静态托管镜像）。改为代码层核对：`node --test <显式文件列表>` 自 node 18.13 起支持；唯一第三方依赖是 `learningStream.test.mjs` 的 `typescript`，属 devDependency，CI `npm ci` 会安装。node 20 真实绿/红仍只能由合并后 main 的 fast 作业给出——**已补齐，见下一行** |
| Wave 0 合并后远端 CI（main run **#21**） | 4 个 job | Lead 2026-10-19 14:55 报告 **success**，含 `Frontend unit tests (node:test)` 在 **node 20** 上 21 个顶层结果通过。**证据等级 `remote`，非本机复核**：本机无 `gh` CLI，Docker Hub 不可达，无法自建 node 20 环境；此行只转述远端结论 |
| Wave 0 数字自检（合并前复核） | 16 项复现命令 | 逐项重跑台账/矩阵/状态文档引用的数字：2235-0-20/612.61s、2-2234-19/650.31s、369-1/58.54s、110/92.44%、CI 清单 37/38/5、Python 189（5+123+1+42+9+5+4）、前端 17+17、node:test 21/0 exit 0、pg 1 passed、README L56、T1/E1/D1/D2 行引用、`BaseAgent` 子类 16、路由装饰器 187、Linux 锁 144 包、素材 30+2 —— **全部一致**；唯一修正为口径精确化：S9"14 个空目录"→ 14 个目录 / 12 个叶子空目录 / 0 个文件。明细见 `OPTIMIZATION_STATUS_2026-10-19.md` §六 |
| QWEN-101 新工具包定向测试（`test_human_agreement_statistics.py` + `test_human_eval_toolkit.py`） | 2 文件 / 27 用例 | **27 passed / 0 failed**（0.76 s，offline；`--basetemp output/qwen-wave1-2026-10-19/*`、合成 fixtures、无模型调用） |
| QWEN-101 后 fast 清单本机等价复跑 | 39 文件 | **396 passed / 1 skipped / 0 failed**（54.90 s，offline；独立 SQLite `output/qwen-wave1-2026-10-19/ci_fast.db`；skip 仍是 `test_auth_restart.py`）；对 Wave 0 的 369/1：+27 全来自新增两文件，无既有用例转红 |
| QWEN-102 采集器 `--arm` 改动后复跑 | 39 文件 | **398 passed / 1 skipped / 0 failed**（55.04 s，offline；同一 SQLite `output/qwen-wave1-2026-10-19/ci_fast.db`；`--basetemp output/qwen-wave1-2026-10-19/base-fast102`）；+2 来自 `tests/a/test_ablation_collect.py` 新增的单臂选择与非法臂前置校验两例，既有用例（含 `test_v2_retrieval_postgres.py` 之外的便携子集）无一转红 |
| QWEN-103 全量复跑（本轮 README:56 数字来源） | 191 个 `test_*.py` | **2263 passed / 1 failed / 20 skipped**（679.38 s，offline；独立 SQLite `output/qwen103-2026-10-19/full.db`、`--basetemp output/qwen103-2026-10-19/base-full`、TEMP/TMP 迁入 `output/`）；较 Wave 0 收口的 2235/0/20：+29 项 = QWEN-101 的 27 + QWEN-102 的 2，总数 2255 → 2284 一致；**唯一红点**为 `tests/a/test_embedding_provider.py:39`（用例未 monkeypatch `EMBEDDING_BATCH_SIZE`，读到本机 `.env` 的 `20` 而非默认 `10`；宿主配置期望缺口，非产品回归，CI 无 `.env` 时全绿），详见台账 §8 |
| QWEN-101 静态检查 | `backend/app/evaluation/human_agreement.py` + `scripts/human_eval/` | `mypy --config-file mypy.ini backend/app/evaluation/human_agreement.py` **0 error**；`ruff check --select F821,F823,E9`（CI 同口径）通过；覆盖率门禁清单**未扩**（Lead 裁决 6，仍 5 文件） |
| QWEN-106 ①：`tests/a/test_embedding_provider.py` 补 `monkeypatch.delenv("EMBEDDING_BATCH_SIZE")` 后定向复跑 | 1 文件 / 1 用例 | **1 passed**（0.19 s，offline，本机带真实 `.env` 仍绿；provider 在构造时 `os.getenv`，见 `backend/app/services/embedding_provider.py:34`） |
| QWEN-106 ②：`test_manim_fallback.py::TestFallbackAssets::test_code_only_skips_fallback` 离线态复核 | 1 用例 | **1 passed**（45.57 s；`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + fail-closed socket 探针 `output/qwen106-2026-10-21/qwen_net_probe.py`，**探针 `outbound attempts=0`**） |
| QWEN-106 ②对照实验：**漏设**上述两个环境变量时同一用例 | 1 用例 | **1 failed**（50.71 s；探针记录 **3 次外联尝试 / 3 个 IP**，其中含 `api.deepseek.com:443 /v1/chat/completions` 端点类别；断言新加的失败消息给出 `reason='manim_render_failed'`）。结论：该用例的绿/红由**外联可用性**决定，非顺序依赖；离线开关下稳定通过 → 未改产品、未放宽断言，语义矛盾登记台账 §9.2 待 Lead 派代码卡 |
| QWEN-106 测量自误（如实登记，非产品结论）：`DATABASE_URL="sqlite:///$PWD/..."` | 3 文件 / 97 用例 | 首轮全量多出 **6 红**（`no such table: profiles/knowledge_points`：`test_cockpit_endpoint.py` ×4、`test_cockpit_branches.py` ×1、`test_collaboration_resource_regressions.py` ×1）。归因实验：同一批文件**去掉该覆盖**后用默认 DB **97 passed / 34.99 s**，探针 `outbound attempts=0` → 与网络无关，纯因 Git Bash `$PWD` 拼出的 `sqlite:////d/...` 使 SQLite 落在仓库外 `D:\d\...`（3 个游离 `.db` 已由 Lead 于 2026-10-21 删除，见台账 §9.3/§9.5） |
| QWEN-106 全量复跑（**本轮 README 数字来源**） | 191 个 `test_*.py` / 2284 项 | **2264 passed / 0 failed / 20 skipped**（834.21 s，offline；`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 默认 SQLite + `--basetemp output/qwen106-2026-10-21/base-official` + TEMP/TMP 迁入 `output/` + socket 探针）；探针汇总 **6 次外联尝试 / 2 个 IP（101.201.58.201、47.94.20.201）全部阻断**，本轮无失败用例，**未逐条归属这 6 次尝试的调用方**（探针只在会话末尾汇总，需逐条归属时应加 per-attempt 记录再跑）。对 QWEN-103 的 2263/1/20：+1 passed 恰为 ① 的修复，0 红点；679.38 s → 834.21 s 为探针阻断等待所致，非用例增减。日志 `output/qwen106-2026-10-21/logs/pytest-full-official-guarded.log` |
| QWEN-106 静态检查 | `backend/app scripts/ tests/` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（CI `ci.yml:115` 同口径）**All checks passed**；`git diff --check` 干净。附带事实：`test_manim_fallback.py` 全文裸 `ruff check` 有 20 条 RUF002/RUF003/I001/B007/EM101 历史告警，**均不在 CI 口径内且不在本轮新增行上** |
| QWEN-106 CI 便携清单复跑（`ci.yml`  portable V2 contract suite，39 文件） | 39 文件 | **398 passed / 1 skipped / 0 failed**（83.92 s，offline；`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 探针 **`outbound attempts=0`**；skip 仍是 `test_auth_restart.py`）；与 QWEN-102 后的 398/1 逐项一致，本轮两处测试改动未使既有用例转红 |

## 7. QWEN-104 成本/用量可见性实测摘要（2026-10-22，分支 `qwen/wave1-cost`，零模型调用）

| 运行 | 集合 | 结果 |
|---|---|---|
| QWEN-104 定向（新增 `tests/a/test_run_usage_admin.py`） | 1 文件 / 9 用例 | **9 passed**（1.33 s；`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 探针 `output/qwen104-2026-10-22/qwen_net_probe.py`，**`outbound attempts=0`**）。覆盖：measured/partial/unknown/not-recorded 四态投影、聚合只加实测并单列未测数、分页窗口与 `total`、teacher/admin 200 / 学生 403 / 无 token 与坏 token 401、未知 run 404、持久层故障 503、响应不含请求正文 |
| QWEN-104 全量复跑（**本轮 README 数字来源**） | 192 个 `test_*.py` / 2293 项 | **2272 passed / 1 failed / 20 skipped**（731.42 s，offline；`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen104-2026-10-22/base-official` + TEMP/TMP 迁入 `output/` + 探针）。日志 `output/qwen104-2026-10-22/logs/pytest-full-official-final.log`。对 QWEN-106 的 2264/0/20：**+9 项全绿**（2264+9=2273，本轮 2272+1=2273 一致），唯一红点是既有的 manim 用例（见下一行），**与本轮代码改动无关** |
| manim 红点复核（**推翻 QWEN-106 的"离线开关下稳定绿"结论**） | `test_manim_fallback.py::TestFallbackAssets::test_code_only_skips_fallback` | 本轮两次全量（重构前 782.22 s、最终 731.42 s）**在已设 `A3_OFFLINE_DEMO=true LLM_PROVIDER=none` 且挂探针的情况下都失败**，断言诊断给出 `manim_success=False error='画面与旁白时长偏差 2.09s，超过允许的 2.00s'` 与 `'… 2.17s …'`（阈值固定 2.00 s，抖动值逐轮变化）；而同一用例单独离线复跑是 **1 passed / 45.57 s / attempts=0**（QWEN-106 §6），**本轮 2026-10-22 再单独复跑仍 1 passed / 46.33 s / `attempts=0`**（两次独立取证同结论）。结论：该用例由**质量门时长抖动**决定，既不是顺序依赖也不是外联依赖；Lead 2026-10-21 裁定的方案①（测试显式设离线开关）**不足以**给出确定性，QWEN-107 需要额外处理（本轮未改产品、未放宽断言，如实登记） |
| QWEN-104 CI 便携清单复跑（`ci.yml` portable V2 contract suite，**40 文件**，含本轮新增文件） | 40 文件 | **407 passed / 1 skipped / 0 failed**（56.35 s，offline，探针 `attempts=0`；skip 仍是 `test_auth_restart.py`）；398+9=407 与定向数逐项吻合，新增文件已进 CI 清单（`ci.yml` 便携段 +1 行；pg/enterprise 段**未扩**） |
| QWEN-104 静态检查 | `backend/app services scripts tests` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（CI `ci.yml:115` 同口径）**All checks passed**；`mypy --config-file mypy.ini backend/app/services/run_usage.py backend/app/api/v2/run_usage_admin.py` **0 error**（注意：本机 mypy 需 `PYTHONUTF8=1`，否则 `configparser` 以 GBK 读 `mypy.ini` 直接 UnicodeDecodeError；该两文件未进 CI 的 mypy 清单，属本轮额外自检）；`git diff --check` 干净 |
| QWEN-104 口径重测（公共文档数字来源） | 路由装饰器 / 表 / 章节 | `grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l` = **189**（QWEN-103 核定的 187 + 本轮 `/api/v2/admin/run-usage` 只读 2 条）；`__tablename__` 仍 **37**、章节仍 **38**（本轮未加模型、未动知识库） |
| QWEN-104 数据可见性事实（重要限制） | 本机仓库默认 SQLite `data/a3_learning.db` | 只读查询 `agent_runs` = **0 行**，因此新端点在本机**没有任何真实 Run 可展示**；其正确性目前只有测试构造数据这一级证据（offline）。QWEN-102 付费跑的用量写在评测 JSONL（`runs.jsonl` 的 `budget`）而非 `agent_runs`，故评测战役的成本可见性需要另做一张卡，本轮未扩范围 |

## 8. QWEN-107 manim 方案②产品修正实测摘要（2026-10-22，分支 `qwen/wave1-manim`，零模型调用）

| 运行 | 集合 | 结果 |
|---|---|---|
| QWEN-107 抖动机器第一手取证（离线只读探针脚本 `output/qwen107-2026-10-22/probe_manim_envelope.py`，直接调 `generate_manim(render=False)` + `_gen_manim(include_manim=False)`，脚本自身不写仓库文件） | 同一脚本 3 次运行；**只有第 3 次已存档** `logs/probe-manim-run3.txt`，前 2 次的读数当时打印在终端、未单独落盘 | 第 1 次（产品改动落地前）：脚本态 `success=False`、`error='画面与旁白时长偏差 2.25s，超过允许的 2.00s，已阻止发布'`、`video_status='script_only'`（视频 94.19 s / 旁白 91.94 s）。第 2、3 次（改动落地后，走的是不受本改动影响的 Level-1 成功路径）：质量门放行（第 3 次存档读数 `av_duration_drift_seconds=1.61`）→ `video_status='ready'` + MP4。**同一台机器、同一离线开关、同一段脚本三次两种结果 → 红绿由媒体时长抖动决定**。另经存档实测：`generate_manim(render=False)` 返回 `type='manim_code'`、`filepath=''`、`success=True`，**顶层没有 `script`/`code` 字段**，讲稿正文只在 `metadata.generated_code`（3002 字符），故 `_gen_manim` 的 `content` 恒为空 |
| QWEN-107 定向（`tests/integration/test_manim_fallback.py`，含新增 5 项回归）第 1 轮 | 1 文件 / 14 用例 | **14 passed**（277.40 s，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 探针 `output/qwen107-2026-10-22/qwen_net_probe.py`，**`outbound attempts=0`**）；日志 `output/qwen107-2026-10-22/logs/manim-file-run1.log` |
| QWEN-107 定向 第 2 轮（确定性复核） | 同上 14 用例 | **14 passed**（343.17 s，探针 `attempts=0`）；两轮均绿，此前"单独跑绿 / 全量跑红"的抖动被产品语义修正消除；日志 `logs/manim-file-run2.log` |
| QWEN-107 全量复跑（**本轮 README 数字来源**） | 192 个 `test_*.py` / 2298 项 | **2278 passed / 0 failed / 20 skipped**（1095.22 s，offline；同口径 + `--basetemp output/qwen107-2026-10-22/base-full` + 探针，`outbound attempts=6 unique_hosts=2`，两个 IP 全部阻断、无用例因阻断转红）。对 QWEN-104 的 2272/1/20：既有红点转绿 + 新增 5 项 = 2273+5=**2278**，与实测逐项吻合；日志 `logs/pytest-full-official.log` |
| QWEN-107 静态检查 | `backend/app scripts/ tests/` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（CI `ci.yml:115` 同口径）**All checks passed**；`git diff --check` 干净。附带事实（实测计数）：`tests/integration/test_manim_fallback.py` 全文裸 `ruff check` 由 main 版本的 **20** 条增至 **42** 条，增量分解 RUF002 +15 / RUF003 +3 / RUF001 +3 / EM101 +1，全部是中文全角标点与异常字面量风格类，**均不在 CI 口径内**，未为此改写既有用例风格；日志 `output/qwen107-2026-10-22/logs/`（含 `git show 5ffec8f:` 版本对照） |
| QWEN-107 口径复核 | 路由装饰器 / 测试文件数 | `grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l` = **189**（本轮未加端点）；`find tests -name 'test_*.py'` = **192**（本轮只改既有用例文件，未新增文件） |
| QWEN-107 全量第二跑（per-attempt 归属探针 `qwen_net_probe_attempts.py`） | 192 文件 / 2298 项 | **2278 passed / 20 skipped**（1198.51 s，同口径），探针 `attempts=6 unique_hosts=2` 与官方跑逐项一致 → 增强探针未改变红绿。**归属结论**：6 次全部来自 `tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip`（`setup` 阶段，`asyncio-portal-*` 线程），调用栈落在 `embedding_provider.embed_documents` 的 `{base_url}/embeddings` 重试路径（每 IP 3 次 = `min(max_attempts,3)`），**embeddings 端点类别、非聊天模型**，6 次 connect 全被阻断（0 出网字节），用例仍 passed。详见 `docs/CLAIMS_LEDGER.md` §11.5 |
| QWEN-107 CI 便携清单复跑（`ci.yml:164-220` portable V2 contract suite，**40 文件**，与 QWEN-104 同清单） | 40 文件 | **407 passed / 1 skipped / 0 failed**（95.54 s，offline，探针 `outbound attempts=0`；`-rs` 点名唯一 skip 仍是 `tests/a/test_auth_restart.py:18 Explicit disposable PostgreSQL required`，日志 `logs/pytest-ci-portable-rs.log`；同清单首跑 100.32 s → `logs/pytest-ci-portable.log`，两次计数一致）——与 QWEN-104 的 407/1 逐项一致，本轮产品语义修正未使便携层回归。`tests/integration/test_manim_fallback.py` 属手工层（单文件 277 s），**未扩进 CI 清单，本轮未改 `ci.yml`** |

## 9. QWEN-107b 脚本态 `content` 交付实测摘要（2026-10-22，分支 `qwen/wave1-manim`，零模型调用）

Lead 2026-10-22 裁定：脚本态 `success=True` 时 `content` 必须携带可编辑讲稿（来源 `metadata["generated_code"]`），缺失/为空要显式失败给稳定错误；只扩既有用例、**不新增测试项**，保持 2278/0/20。

| 运行 | 集合 | 结果 |
|---|---|---|
| QWEN-107b 定向（`tests/integration/test_manim_fallback.py`） | 1 文件 / 14 用例（**用例数与扩展前一致**，证明未新增测试项） | **14 passed**（451.60 s，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + per-attempt 探针，**`outbound attempts=0 unique_hosts=0`**）；日志 `output/qwen107b-2026-10-22/logs/targeted-run1.txt` |
| QWEN-107b 全量复跑（**本轮 README 数字来源**） | 192 个 `test_*.py` / 2298 项（2278+20） | **2278 passed / 0 failed / 20 skipped**（756.16 s，offline，`--basetemp output/qwen107b-2026-10-22/base`，探针 `outbound attempts=6 unique_hosts=2`，两个 IP 全阻断、无用例因阻断转红）——**与 QWEN-107 官方跑计数逐项相同**，本轮只改断言与一处返回体，未增删用例；日志 `logs/full-suite.txt` |
| QWEN-107b 外联归属（同一 6 次尝试） | `distinct tests with outbound attempts=1` | 6 次全部归属 `tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip (setup)`，线程 `asyncio-portal-*`，栈 `knowledge_admin.py:247 ← knowledge_ingest.py:384 ← knowledge_ingest.py:191 ← embedding_provider.py:63`（embeddings 端点类别，非聊天模型）——与 QWEN-107 §8 归属完全一致；**本轮按 Lead 范围未动该用例**，离线化属 QWEN-108 |
| QWEN-107b CI 便携清单复跑（`ci.yml:164-220`，40 文件，同 QWEN-107 清单） | 40 文件 | **407 passed / 1 skipped / 0 failed**（81.34 s，offline，探针 `outbound attempts=0`；`-rs` 唯一 skip 仍是 `tests/a/test_auth_restart.py:18 Explicit disposable PostgreSQL required`）——与 QWEN-104/QWEN-107 的 407/1 逐项一致；日志 `logs/ci-portable.txt` |
| QWEN-107b 静态检查 | `backend/app scripts/ tests/` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（`ci.yml:115` 同口径）**All checks passed**；`multi.py` 不在 mypy 白名单，类型门不受影响。附带事实（实测计数，非 CI 口径）：裸 `ruff check` 对 `tests/integration/test_manim_fallback.py` 由 `HEAD` 版 **42** → **49**（全为 RUF001/RUF002/RUF003 中文全角标点类），`multi.py` 由 **884** → **889**（同类）；对照文件留在 `output/qwen107b-2026-10-22/tmp/lintbase/` |
| QWEN-107b 口径复核 | 路由装饰器 / 测试文件数 | `grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l` = **189**（未加端点）；`git ls-files 'tests/**test_*.py' \| wc -l` = **192**（未新增文件） |
| QWEN-107b 真链路只读探针（`output/qwen107b-2026-10-22/probe_content_delivery.py`，非 monkeypatch，直接调 `generate_manim(render=False)` + `_gen_manim(include_manim=False)`，导入 `qwen_net_probe` 做 fail-closed） | 真实离线链路 1 次 | `generate_manim` → `type='manim_code'`、`filepath=''`、`success=True`、`metadata.generated_code` **3002 字符**；`_gen_manim(include_manim=False)` → `success=True`、`error=None`、`video_status='script_only'`、`rendered=False`、`playback_status='unavailable'`、`downloads=[]`，**`content` 是 `str`、len=3002、`content == metadata.generated_code`（`content_equals_generated_code=True`）**。本轮日志还第一手复现了抖动：Level 1 被质量门以"画面与旁白时长偏差 **2.01s** > 2.00s"拒绝（Kimi 与讯飞凭据未配置 → 本地脚本），脚本态仍 `success=True` → QWEN-107 方案②在真链路上生效。探针 **`outbound attempts=0 unique_hosts=0`**，零出网；日志 `logs/probe-content.txt` |

## 10. QWEN-108 摄取用例显式离线实测摘要（2026-10-22，分支 `qwen/wave1-manim`，零模型调用、产品代码零改动）

| 运行 | 集合 | 结果 |
|---|---|---|
| QWEN-108 改动前基线（同口径，直接引用本轮已有存档） | 全量 192 文件 / 2298 项 | `outbound attempts=6 unique_hosts=2`，`distinct tests with outbound attempts=1`，全部归属 `tests/a/test_knowledge_platform.py::test_upload_index_hit_test_roundtrip (setup)`，栈 `knowledge_admin.py:247 ← knowledge_ingest.py:384 ← knowledge_ingest.py:191 ← embedding_provider.py:63`；见 §9 与 `output/qwen107b-2026-10-22/logs/full-suite.txt` |
| QWEN-108 定向第 1 轮（含我的错误断言） | `tests/a/test_knowledge_platform.py` 14 用例 | **1 failed / 13 passed / 25.99 s**，失败点是新增的 `document["embedding"]` 断言 `KeyError`；**同一轮探针已 `attempts=0`** → 离线化本身已生效。日志 `output/qwen108-2026-10-22/logs/kp-targeted.txt` |
| QWEN-108 定向第 2 轮（修正后） | 同上 14 用例（**用例数未变**） | **14 passed / 22.21 s**，`outbound attempts=0 unique_hosts=0`；日志 `logs/kp-targeted2.txt` |
| QWEN-108 全量复跑（**本轮 README 数字来源**） | 192 个 `test_*.py` / 2298 项 | **2278 passed / 0 failed / 20 skipped / 764.23 s**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + per-attempt 探针 → **`outbound attempts=0 unique_hosts=0`、`distinct tests with outbound attempts=0`**：套件不再依赖探针阻断，**真离线**。计数与 QWEN-107/107b 逐项一致（只加 fixture 与断言，未增删用例）；日志 `logs/full-suite.txt` |
| QWEN-108 CI 便携清单复跑（40 文件，同 QWEN-107/107b 清单） | 40 文件 | **407 passed / 1 skipped / 0 failed / 77.83 s**，`attempts=0`，唯一 skip 仍是 `tests/a/test_auth_restart.py:18`；日志 `logs/ci-portable.txt` |
| QWEN-108 静态检查与边界 | `backend/app scripts/ tests/` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/`（`ci.yml:115` 同口径）**All checks passed**；`git diff 755454f..912d9b5 --stat -- backend/` 实测为空（QWEN-108 提交在 `backend/` 下相对 107b 零差异，产品未动）；`grep -rhoE '@router\.(get\|post\|put\|delete\|patch)\(' backend/app \| wc -l` = **189**。裸 ruff（非 CI 口径）：该文件 15 → **30**，增量全为 `RUF001/RUF002/RUF003` 中文全角标点类，`I001` 仍 1 条与 HEAD 相同 |

## 11. QWEN-105 企业契约子集本机 PG 实测摘要（2026-10-22，分支 `qwen/wave1-pg`，零模型调用、产品代码零改动）

**证据等级：pg**。镜像用的是本机**已存在**的 `pgvector/pgvector:pg16`（ID `7b822b0aac60`，server 16.15）与 `redis:7-alpine`（ID `858f009f9709`，server 7.4.11），**未执行 pull**；Docker 引擎 29.8.2。宿主机 Python 3.12.15 / psycopg 3.3.6 / redis-py 8.1.0 / SQLAlchemy 2.1.5 / alembic 1.20.0 / pytest 9.1.1。

容器只绑环回、用独立端口避开既有服务：`qwen105-pg-20261022` → `127.0.0.1:55432`，`qwen105-redis-20261022` → `127.0.0.1:56379`；健康核验 `pg_isready` = accepting connections、`redis-cli ping` = PONG。

| 运行 | 集合 | 结果 |
|---|---|---|
| 迁移 + 扩展校验（照 `ci.yml:290-293`） | `alembic upgrade head` | 最终 revision `20261014_0011`（11 个 revision）；`SELECT extname FROM pg_extension WHERE extname='vector'` → `('vector',)`。日志 `output/qwen105-2026-10-22/logs/alembic.txt` |
| run1（URL 用 `localhost`） | CI `enterprise-contract` 38 文件 | **349 passed / 10 failed / 12 errors / 1698.19 s**，`attempts=0`。失败面全是 `tests/a/test_postgres_api_recovery.py:13-18` 的 60 s 子进程超时：本机 `localhost:55432` 建连实测 **5.02 s**（IPv6 优先回落）vs `127.0.0.1` **0.01 s**。日志 `logs/enterprise-run1.txt` |
| 同批复验（5 个跨进程恢复文件，URL 改 `127.0.0.1`） | 5 文件 | **16 passed / 116.83 s** → 证实 run1 红点纯属本机建连延迟口径 |
| run2（**本卡 PG 层数字来源**） | 38 文件全量 | **364 passed / 0 failed / 0 skipped / 162.58 s**，`outbound attempts=0 unique_hosts=0`。日志 `logs/enterprise-run2.txt` |
| run3（确定性复跑） | 同 run2 命令与清单 | **364 passed / 0 failed / 0 skipped / 159.53 s**，`attempts=0`。日志 `logs/enterprise-run3.txt` |
| PG 写入旁证（清理前查同一实例） | 容器内 `triple_u` 库 | `tables=36`、`chunk_vectors=1372`、`knowledge_chunks=1372`、`checkpoint_migrations=10`、`alembic_version=1`；业务表 0 行 = 用例 `finally` 自清理 |
| Redis 边界（**不计入通过**） | 38 文件子集 | 服务可用（`PING`/`SET`/`GET` 往返成功），但子集跑完 `dbsize=0`；唯一 redis 引用点 `tests/a/test_v2_eval_cost_guard.py:17-22` 是 `FakeRedis` + `sys.modules` 打桩。真 broker 路径 `tests/helpers/celery_ingestion_worker_probe.py:26` 未执行 |
| 清理 | 只删本卡容器 | `docker rm -f qwen105-pg-20261022 qwen105-redis-20261022`；`docker ps -a` 18 → **16**、`qwen105-*` 计数 **0**（`logs/docker-ps-before-cleanup.txt` / `logs/docker-ps-after-cleanup.txt`）。`echomind-*`/`a3-*`/`devtrace-*` 逐个 diff 未动；唯一非本卡差异是 `a3-backend` uptime 文本（其自身 RestartCount=537、`failed to resolve host 'postgres'`），与本卡无因果 |

与 CI 的口径差异（4 条，详见 `docs/CLAIMS_LEDGER.md` §14.5）：端口/主机改写、额外 `-o addopts=` 与 `LLM_PROVIDER=none`、额外只读探针插件、**未跑** `ci.yml:338-341` 可选 MCP stdio 步骤（本机未装 `requirements-mcp.txt`，未擅自 pip）。

完整可复现命令与环境写在 `output/qwen105-2026-10-22/report.md`（`env.sh` + `enterprise-list.txt` 在同目录）。

## 12. QWEN-107c 脚本态审计交付正文实测摘要（2026-10-22，分支 `qwen/wave1-content`，零模型调用）

Lead 2026-10-22 18:40 裁定：脚本态的 CoV/Safety 必须审计**实际交付正文**（`metadata.generated_code`），`include_manim=true` 渲染分支的 enrichment 语义不变；扩既有用例捕获 `_enrich_with_safety_cov` 输入，**不新增测试项**。产品 +6 行、测试 +18 行，改动位置与实现取舍见 `docs/CLAIMS_LEDGER.md` §15。

| 运行 | 集合 | 结果 |
|---|---|---|
| 单用例（正向） | `-k test_script_only_is_success_when_render_not_requested` | **1 passed / 5.89 s**，探针 `attempts=0 unique_hosts=0`；日志 `output/qwen107c-2026-10-22/logs/single-test-positive.txt` |
| 单用例（**反向验证**：`git apply -R` 撤掉产品 6 行） | 同上 | **1 failed / 3.44 s**，`AssertionError: 脚本态交付正文未进入审计：['']` —— 修复前该分支唯一的审计输入就是空串，断言确实钉住行为；日志 `logs/single-test-negative.txt`，之后 `git apply` 恢复并 `git diff --stat` 复核 |
| 定向整文件 | `tests/integration/test_manim_fallback.py` 14 用例（**用例数不变**） | **14 passed / 270.02 s**，`attempts=0`，per-attempt 归属 0 条；日志 `logs/targeted-run2.txt`。首轮 **1 failed / 13 passed / 276.58 s** 是我多加的那条断言前提写错（rich 端点在 manim 失败后仍会为 mindmap/tts 兜底资源各自调 enrichment，与被测分支无关），收窄后转绿；失败轮存档 `logs/targeted-run1.txt` |
| 全量复跑（**本轮 README 数字来源**） | 192 个 `test_*.py` / 2298 项 | **2278 passed / 0 failed / 20 skipped / 649.18 s**，`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + `qwen_net_probe` → `outbound attempts=0 unique_hosts=0`；计数与 107/107b/108 逐项相同（只加断言，未增删用例）；日志 `logs/full-suite.txt` |
| CI 便携清单（40 文件，本轮从 `ci.yml:164-220` 机械重取） | 40 文件 | **407 passed / 1 skipped / 0 failed / 56.90 s**，`attempts=0`，唯一 skip 仍是 `tests/a/test_auth_restart.py:18 Explicit disposable PostgreSQL required`；日志 `logs/ci-portable.txt`，清单 `ci-portable-list.txt` |
| 真链路（`probe_audit_input.py`，非 monkeypatch 生成器） | 真实 Level-2 脚本态 1 次 | 本机媒体链路这一轮**真的渲染出了 MP4**，第一次探针走的是渲染分支（`video_status='ready'`、`content len=62`、审计输入 1 条 1256 字符），无脚本态证据，存档 `logs/probe-audit-input.txt`；第二次把 Level 1 钉为不可用后：`success=True`、`video_status='script_only'`、`content len=3002`，**审计输入 `[(0, ''), (3002, '# Auto-generated by Mani…')]`、`delivered_content_audited=True`**，`cov={checked: True, score: 0.0, passed: False, missing_terms: […]}`。对照 107b 同参存档（`output/qwen107b-2026-10-22/logs/probe-content.txt`）：审计空文本时 `cov` 反而 `{score: 1.0, passed: True}`，即**空文本虚过**；本卡后 `cov` 才真正反映交付正文。两次均 `attempts=0`；日志 `logs/probe-audit-input2.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | `ruff check --select=F821,F823,E9 ...`（`ci.yml:115` 同口径）**All checks passed**；`git diff --check` 干净；路由装饰器 **189**、测试文件 **192**（均不变）。裸 ruff（非 CI 口径）：测试文件 49 → **54**（RUF003 +4 / RUF001 +1），`multi.py` 889 → **893**（RUF003 +4），基线副本 `tmp/lintbase/` |
| 末次注释措辞改动后复验 | 单用例 + lint | **1 passed / 7.62 s**、`attempts=0`、CI 口径 ruff 仍 All checks passed、裸 ruff 仍 893；全量未为此重跑（注释不参与执行路径）；日志 `logs/single-test-final.txt` |
| 影响面核查 | 兜底与红绿判定 | `_detect_manim_needs_fallback` 只读 `envelope.success` 与质量门（`multi_with_fallback.py:56-68`），`resource_generator_agent.py:131` 仅透传 `cov`；脚本态 `cov.passed` 由虚过 `True` 变为可能 `False` **不翻转 success、不触发兜底**，14 用例与全量 2278/0/20 不变即其实测支撑 |

## 13. QWEN-109 评测用量/成本只读汇总实测摘要（2026-10-22，分支 `qwen/wave1-evalcost`，零模型调用、产品代码零改动）

Lead 2026-10-22 23:05 开卡：**只读**汇总评测产物 `runs.jsonl` 的 `budget`（每臂/每题的调用数、输入/输出 token、latency、cost），`unknown` 不写 0、缺失样本单列计数、不编造单价、不读 `.env`、不新增对外端点、不改产品。交付 `scripts/report_eval_cost.py`（461 行）+ 脱敏报告 `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md`（257 行，与 `output/qwen109-2026-10-22/eval-cost-report.md` 逐字节相同）；口径与登记见 `docs/CLAIMS_LEDGER.md` §16。

| 运行 | 集合 | 结果 |
|---|---|---|
| 生成命令（可复现） | 8 份真实评测产物 / 127 条记录 | `PYTHONUTF8=1 python output/qwen109-2026-10-22/run_report_guarded.py output/qwen109-2026-10-22/eval-cost-report.md`（等价于 `python scripts/report_eval_cost.py --scan-root output --out …`，外面套 fail-closed 探针）→ `sources=8 records=127 arms=14 cases=127 cost_status=unknownx127 runs_without_token_data=1 excluded_fixtures=122`；日志 `output/qwen109-2026-10-22/logs/run5-final.txt` |
| 零外联 | 同上一次运行 | 探针 `outbound attempts=0 unique_hosts=0 blocked=[]`；脚本**不 `import os`**，结构上无法读环境变量或 `.env`；`--out` 强制落在 `output/` 下且拒绝覆盖 |
| 样本边界 | 扫描根 `output/` | 含 `result.budget` 的 `.jsonl` 共 **130** 份 → 计入 **8** 份 / **127** 条，按"路径组件以 `test_` 开头"排除 pytest 夹具 **122** 份 / **304** 条，逐目录计数写进报告第 1 节 |
| 独立复算（第二套代码路径，不复用产品模块/聚合器/发现规则） | `output/qwen109-2026-10-22/crosscheck_independent.py` | 127 / 442 / 1321838 / 276031 / 2797092 / 有 token 126 / `result.error` 28 / 跨来源题号 25 / 14 组，**14 行每臂数字逐行一致**；日志 `logs/crosscheck.txt`（两侧数字并排留档） |
| 与 §2 **E3** 行交叉验证（cloud 级已接受结论） | `evals/results/ablation-fixed-evidence-20261017.md` | 该表"任务完成 23/24、13/24、13/24"= 实测 `completed=True` single 23 / without_reviewer 13 / full 13；"平均模型调用 1.00/3.58/4.96"= 调用数合计 24/86/119 ÷ 24 题；"P50 5.80/15.91/21.41 秒"= latency 中位数 5803.27/15912.39/21411.53 ms；正文"有 1 次运行缺少 token 用量"= `runs_without_token_data` 1；"费用为未知"= `cost_status unknown×127`。**逐项一致**（P95 本卡未算，三者均落在实测 max 之内，不矛盾） |
| 与 §2 **E5** 行交叉验证 | `evals/results/structured-output-20261018.md` | 该行"44/43 次调用；输出 25,384/25,286 tokens"= `stability-20261018/dev-retest` 44/25384、`holdout-retest` 43/25286，**一致** |
| CLI 分支与错误路径 | 5 种输入 | `--source` 限定单来源 → 12 条 / 1 臂（排除清单仍报 122 份）；`--out` 不在 `output/` 下、`--out` 已存在、`--source` 缺 `=`、`--source` 路径不存在 → **均 exit 2 且零写出**；日志 `logs/cli-branches.txt` |
| 静态检查 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9`（`ci.yml:115` 同口径）**All checks passed**；裸 ruff（`pyproject` 全集）对新文件 **0 findings**（`scripts/` 既有 2382 条基线未增加）；`git diff --check` 干净（曾报 ledger 末尾多余空行，已修） |
| 脱敏复核 | 报告全文 | grep `sk-`/`api_key`/`bearer`/`password`/`secret`/URL/≥32 位十六进制/`deepseek.com` → 仅命中"不读取 .env"这句自述；出现的只有模型名 `deepseek-flash`、路径与计数；`dataset_sha256`/`evidence_sha256` 取值一律不复现 |
| 测试项与产品改动 | 全仓 | **未新增测试项、未改任何产品/测试代码**：`git status` 只有 2 个新文件（脚本 + 报告）与 2 份登记文档改动（ledger §16、本 §13）。无用例枚举 `scripts/` 或 `docs/`（`test_campus_assets.py:9` 枚举前端 assets，`test_diagnosis_reporter.py:293` / `test_human_eval_toolkit.py:111-113` 枚举 `tmp_path`），故 README 的 **2278 / 0 / 20** 按构造不变；按"已交付数字不为好看而重跑"未重跑全量 |
| 产品侧观察（**只登记，本卡不改**） | `backend/app/services/run_usage.py:22-26` | `_count` 只接受非负整数，而 `result.latency_ms` 是小数 → `summarize_run_usage` 对 **127/127** 条返回 `reported_latency_ms=None`（`model_calls` 是整数，被丢弃 **0** 条）。报告改为直接读原始 `result.latency_ms` 并单列该偏差条数；是否放宽由 Lead 裁定，**归属 QWEN-104** |
| 迭代过程留档（不删） | `output/qwen109-2026-10-22/tmp/` | v1 自写成本判定的脚本、排除清单归并键错写版、改走产品投影后 latency 全丢的中间版、补 `completed` 列之前版、`--source` 分支验证报告、重新生成前的已交付副本，共 7 份；日志 `logs/run1~run4`（迭代）、`logs/run5-final.txt`（交付数字）、`logs/run6-reproducibility.txt`（提交前复现核对）、`logs/cli-branches.txt`、`logs/crosscheck.txt` |
| 提交前可复现性核对 | 待提交的同一份脚本重新生成到同一路径 | run5 之后只做了一次**纯删死代码**收尾（删 `Bucket.cases` 及其两行赋值；题号分组实际用 `main()` 的 `per_case`，`cases=127` 取自 `len(per_case)`，`report_eval_cost.py:453`）。删后两个 lint 门复跑仍 All checks passed；把已交付报告挪到 `tmp/eval-cost-report-run5-final.md` 后重新生成 → 摘要行逐字段相同、`cmp` 三方（run5 存档 / 重新生成 / `docs/` 副本）**全部逐字节相同**、探针仍 `attempts=0 unique_hosts=0`；`git diff --check` 干净。脚本无 `datetime`/`time` 依赖，输出确定，**交付数字未因这次收尾变化**。日志 `logs/run6-reproducibility.txt` |
