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

## 2. Python 测试文件矩阵（199）

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
| tests/a/test_observation_claim_support.py | F |  |  | ✓ | QWEN-231 统一 Observation + 交付前规则版 claim-support（10 项，离线 scripted）；QWEN-231b 起进 fast/quality 快清单（45→46） |
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
| tests/a/test_run_queue.py |  |  |  | ✓ | QWEN-301 Run 队列/Worker（15 项：领取/心跳/取消/超时/重领/上限/杀进程恢复/API 兼容；离线 stub+subprocess 探针；未进 fast 清单） |
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

## 14. QWEN-104b 延迟投影修复实测摘要（2026-10-23，分支 `qwen/wave1-latency`，零模型调用）

Lead 2026-10-23 12:20 派卡、12:26 `[PERMISSION]` 放行（分支由 Lead 从 `main@dcaf082` 预建）。缺陷来自 §13 最后一条登记（`run_usage.py:22-26` 的 `_count` 只接受非负整数 → 管理端把 **127/127** 条浮点 `result.latency_ms` 显示成未记录）。决定与边界见 §3-47 与 §4 派卡原文：`reported_latency_ms` 走**独立的非负数值投影**（int/float 均收，bool/负数/字符串/None 拒绝），**token、`model_calls`、`tool_calls` 等计数仍必须整数**；只改投影与测试/文档，不改端点语义、不碰 `.env`。改动为 `backend/app/services/run_usage.py`（+8/−1，新 `_number` `:29-33`、调用点 `:92`）与 `tests/a/test_run_usage_admin.py`（+38/−1，用例 9 → **11**）；口径与取舍见 `docs/CLAIMS_LEDGER.md` §17。

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **11** 项（原 9 + 新 2） | **11 passed / 1.34 s**，探针 `outbound attempts=0 unique_hosts=0`；新增两项分别覆盖 int/float/负数/bool/字符串/None 与"分数计数仍算未记录"；日志 `output/qwen104b-2026-10-23/logs/targeted-run3-final.txt`；提交前同一集合复跑 **11 passed / 1.33 s、`attempts=0`**（`logs/targeted-precommit.txt`） |
| **反向验证**（撤掉修复） | 同上 11 项 | `:92` 临时改回 `_count(...)` → **2 failed / 9 passed / 1.67 s**，两处失败同为 `assert None == 5803.27`，证明修复前浮点延迟整条丢弃；改回后转绿。**未用 `git apply -R`**（该命令被权限分类器拦截），改为一次编辑 + 改回，前后各跑 `git diff` 复核；日志 `logs/targeted-negative.txt` |
| 管理端真实响应（`probe_admin_response.py`，`TestClient` + 一次性 sqlite，非断言桩） | 2 条路由各 1 次 | 详情路由 **200**、`reported_latency_ms` = **5803.27**（Python `float`），响应原文含 `"reported_latency_ms":5803.27`（小数未被截成整数）；列表路由同值。同一条响应 `model_calls 1` / `tool_calls 0` / `input_tokens 3715` / `output_tokens 878` / `usage_unknown_calls 0` / `duration_ms 1200` **仍为整数**；`cost_status="unknown"`、`cost.reason="no_cost_amount_recorded"`、`cost_cny=null`、`usage_status="measured"` 与 §7 的 QWEN-104 口径逐项一致；响应不含请求正文；探针 `attempts=0`。延迟取值取自真实评测记录（ablation-full `single` 臂 latency 中位数，同 §2 E3 的 P50 5803.27 ms）；日志 `logs/probe-admin-response.txt` |
| 全量回归 | `pytest tests/`（2300 项） | **2280 passed / 0 failed / 20 skipped / 762.69 s**（Windows + Python 3.12.15），`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen104b-2026-10-23/pytest-full`，探针 **`attempts=0 unique_hosts=0`**；相对上一轮 2278 的 +2 即本卡新增 2 项，既有用例无一转红；日志 `logs/full-suite.txt` |
| CI 可移植子集 | `ci-portable-list.txt` 的 **40** 个文件（与 107c 清单 `diff` 相同） | **409 passed / 1 skipped / 4 warnings / 56.07 s**，探针 `attempts=0 unique_hosts=0`；日志 `logs/ci-portable.txt` |
| 项数口径核对 | `--collect-only` | 安静收集两次**逐字节相同**、各 **2299** 行；非安静收集打印 `collected 2299 items / 1 skipped`（8.75 s，探针 `attempts=0`），集合期那 1 条为 `tests/a/test_mcp_readonly_protocol.py:11` 的 `importorskip("mcp")`（本机无 `mcp`；`torch` 可用故 `tests/b/test_sakt.py` 不跳）。**2299 + 1 = 2300 = 2280 passed + 20 skipped**；文档项数沿用运行时口径（上一轮 2298 = 2278 + 20） |
| 对 QWEN-109 报告的影响（**不重生成已交付报告**） | 同命令只写 scratch | `output/qwen104b-2026-10-23/tmp/eval-cost-report-after-fix.md` 与 `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 的 `diff` = **4 hunk / 6 行**：命令行 `--out` 路径、两处"latency_ms 被投影判为未记录 **127 → 0**"、夹具普查随轮次增长（jsonl 130 → 138 份、排除夹具 122 → 130 份 / 304 → 324 条、归并表新增本目录 20 条）。**127 条记录、442 次调用、1321838/276031 token、2797092 `input_chars`、中位数 14101.54 [2302.41~40332.14]、`cost_status unknown×127` 全部逐项不变**；日志 `logs/eval-cost-delta.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9`（`ci.yml:115`）**All checks passed**；裸 ruff：`run_usage.py` **0 findings**，`test_run_usage_admin.py` **4 findings 与 HEAD 基线逐条相同**（3×E501 + 1×EM101，仅行号位移，基线副本 `tmp/lintbase/`）；`git diff --check` 干净；路由装饰器仍 **189**、测试文件仍 **192** |
| 兼容性核查 | 既有 9 项断言 + 已验收响应 | `_number` **保留原类型**（int 进 int 出），未复用会强转 `float` 的 `_amount`，故整数延迟仍是 `900` 而非 `900.0`，§7 的 QWEN-104 已验收响应取值逐字不变；`aggregate_run_usage` 与 `cost` 分支零改动 |
| 未加项（留给 Lead 裁定） | `math.isfinite` | 唯一写入方 `backend/app/evaluation/ablation_runner.py:100` 是 `round((time.perf_counter()-started)*1000, 2)`，按构造有限，NaN 已被 `value >= 0` 判否；仓库另有两处同类过滤带 `isfinite`（`golden_set.py:178-180`、`learning_package.py:263-266`），若要对齐口径需加 1 行判断 + 1 条断言。**本条已由 QWEN-104c 关闭，见 §15。** |

## 15. QWEN-104c `isfinite` 加固 + 报告措辞更正实测摘要（2026-10-23，分支 `qwen/wave1-finite`，零模型调用）

Lead 2026-10-23 13:40 验收 §14 后派卡，并把 §14 最后一条"留给 Lead 裁定"关闭为必做：(a) `run_usage.py` 的 `_number` 与 `_amount` 加 `math.isfinite`（inf/-inf/nan → `None`，int/float 照旧）+ 补断言；(b) 更正 `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 里"latency 被投影判为未记录 127"的过期说明为"已由 QWEN-104b 修复、127→0"，**统计数字与结论不动**；(c) 零模型、只改投影/测试/文档。Lead 的理由原文：「inf 会让 JSON 序列化失败，不能靠"上游按构造有限"赌」。改动为 `backend/app/services/run_usage.py`（+4/−3，`import math` `:11`、守卫 `:34`/`:40`）、`tests/a/test_run_usage_admin.py`（+52/0，用例 11 → **13**）与三份文档；`_count`、端点、`aggregate_run_usage` 算法一字未动。口径与取舍见 `docs/CLAIMS_LEDGER.md` §18。

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **13** 项（原 11 + 新 2） | 首跑 **13 passed / 2.44 s**、复跑 **13 passed / 2.64 s**，探针 `outbound attempts=0 unique_hosts=0`；两项新增分别钉住"`_number`/`_amount` 对 inf/-inf/nan 全判 `None`、`900`/`5803.27`/`0.0042` 照旧通过、管理端响应正文不含字面 `Infinity`/`NaN`"与"非有限金额绝不进求和（`cost_cny_estimated_sum=0`、`runs_without_estimated_cost=2`）"；日志 `output/qwen104c-2026-10-23/logs/targeted-run1.txt`、`targeted-final.txt` |
| **反向验证**（撤掉守卫） | 同上 13 项 | `math.isfinite(value) and value >= 0` 临时改回 `value >= 0` → **2 failed / 11 passed / 2.38 s**，失败断言 `assert [inf, None, None] == [None, None, None]` 说明**漏网的只有 `+inf`**（`-inf`/`nan` 本就被 `>= 0` 判否），另一处是 `cost` 多出 `amount_cny: None`；改回后转绿。未用被权限分类器拦截的 `git apply -R`，改为一次编辑 + 改回 + `git diff` 复核；日志 `logs/targeted-negative.txt` |
| 为什么必须有这道闸（三条机制实测） | 独立脚本 + 一次性 sqlite，非断言桩 | ① 无守卫时 `_number(inf)` 返回 `inf`；② SQLAlchemy/SQLite 的 JSON 列**原样往返** inf，脏值能一路走到投影输出；③ 同一份 summary 按 Starlette 严格口径 `json.dumps(..., allow_nan=False)` 抛 `ValueError: Out of range float values are not JSON compliant: inf`（端点 500），按 FastAPI/pydantic 响应编码则把 inf **静默写成 `null`**——把"未记录"和"记成了 inf"混成同一个值 |
| 全量回归 | `pytest tests/`（**2302** 项） | **2282 passed / 0 failed / 20 skipped / 873.67 s**（Windows + Python 3.12.15），`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen104c-2026-10-23/pytest-full`，探针 **`attempts=0 unique_hosts=0`**；相对 104b 的 2280 恰好 +2 即本卡新增两项，既有用例无一转红；`--collect-only -q` 收 **2301** + 集合期 1 条 `importorskip("mcp")` = **2302**，与 §14 的 2299+1=2300 同口径；日志 `logs/full-suite.txt`、`logs/collect-quiet.txt` |
| CI 可移植子集 | `ci-portable-list.txt` 的 **40** 个文件（与 107c/104b 清单 `diff` 相同） | **411 passed / 1 skipped / 4 warnings / 83.99 s**（上一轮 409/1，+2 即本卡两项），探针 `attempts=0 unique_hosts=0`；日志 `logs/ci-portable.txt` |
| 报告措辞更正与复跑核对（**不重生成已交付报告**） | 2 行措辞 + 同命令只写 scratch | `docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 只改偏差行与偏差表行 2 行，**127 这个已交付实测值原样保留**、只加注"该说明已过期 / 复跑 127→0"；与交付原件 `diff` 即这 2 行（`logs/report-wording-delta.txt`）。同一条命令复跑到 `tmp/eval-cost-report-final.md`：`sources=8 records=127 cost_status=unknownx127`，两处偏差值实打印 **0**，证明"127→0"不是推断；复跑产物与已交付报告 `diff` = 6 hunk / 23 行，除 `--out` 路径、这两处偏差值、夹具普查随轮次增长（jsonl 130→146 份、排除夹具 122→138 份 / 304→344 条、归并表 +2 行）外**逐字节相同**，127 条记录、442 次调用、1321838/276031 token、2797092 `input_chars`、中位数 14101.54 [2302.41~40332.14] 全部不变；日志 `logs/report-rerun-delta.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9`（`ci.yml:115`）**All checks passed**；裸 ruff：`run_usage.py` **0 findings**，`test_run_usage_admin.py` **4 findings 与 HEAD 基线逐条相同**（3×E501 + 1×EM101，仅行号位移）；`git diff --check` 干净；路由装饰器仍 **189**、测试文件仍 **192**；未 `cat`/提交 `.env`、未重启容器、零模型调用 |
| 登记未修（留给 Lead 裁定） | 两处 | ① `cost.status="estimated"` 而 `amount_cny` 非有限时，投影保留生产者写的 `estimated`、只把金额判未记录 → 响应会出现 `cost_status="estimated"` 且 `cost_cny=null`；降级为 `unknown` 会动到 QWEN-104 已验收语义，本卡不越界，已用测试钉住现状。② `scripts/report_eval_cost.py:380` 的过期解释是硬编码模板串，复跑产物里出现"计数 0 + 说明仍写'小数 latency 全被丢弃'"的自相矛盾行；(c) 范围限定投影/测试/文档，脚本不在其中，故只登记不改（1 行字符串即可修） |

## 16. QWEN-104d 两项裁定落地实测摘要（2026-10-23，分支 `qwen/wave1-finite`，零模型调用）

Lead 2026-10-23 16:05 验收 §15（复跑 `test_run_usage_admin.py` **13 passed / 2.30 s**、全量 2282/0/20 接受、104c 已合并 `main`）后，把 QWEN-104c 交回的两件裁定**全部批准**并派小补丁 QWEN-104d（继续 `qwen/wave1-finite`）：① 改 `scripts/report_eval_cost.py:380` 的硬编码旧说明为"latency 已由 QWEN-104b/104c 修复、复跑 127→0"，**不重生成 tracked 报告**、用 scratch 验证；② `estimated` 而金额非有限/缺失时**保留生产者的 `estimated`、不降级**，在 `cost` 字典补 `reason="no_cost_amount_recorded"`。改动 3 文件 +46/−4：`backend/app/services/run_usage.py`（`:66-69` 新增一支，投影 +4/0）、`scripts/report_eval_cost.py`（`:381-382` 模板 2/2）、`tests/a/test_run_usage_admin.py`（+40/−2，用例 13 → **14**）；`_count`/`_number`/`_amount`、聚合算法、端点与 `COST_STATUSES` 全部不动。口径与语义取舍见 `docs/CLAIMS_LEDGER.md` §19。

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_run_usage_admin.py` **14** 项（原 13 + 新 1） | 落地后首跑 **14 passed / 1.84 s**（`logs/targeted-run1.txt`）；用例补全后的最终代码复跑 **14 passed / 2.64 s**（`logs/targeted-final.txt`，留档凭证）；中间恢复守卫那次 **14 passed / 1.59 s** 只打在终端、未单独存档，故不作为证据行；提交前再跑 **14 passed / 2.44 s**（`logs/targeted-precommit.txt`）；探针一律 `outbound attempts=0 unique_hosts=0` |
| **反向验证**（撤掉裁定 2 的新支） | 同上 14 项 | 条件临时改为永假 → **2 failed / 12 passed / 2.20 s**，两处失败均为 `cost` 字典缺 `reason` 的全等断言（`{'status': 'estimated', 'currency': 'CNY'} != {…'no_cost_amount_recorded'}`）；改回转绿并 `git diff` 复核（`tmp/reason-branch-disabled.patch` / `tmp/reason-branch.patch`）；未用被拦截的 `git apply -R`；日志 `logs/targeted-negative.txt` |
| 新用例覆盖面 | `:288-321` | `estimated` 且投影拿不到可用金额的**五种形态**——**缺 `amount_cny` 键**、`None`、**负数 `-5`**、**字符串 `"0.0042"`**、**`True`**——全部保留 `estimated`、`cost_cny` 仍 `null`、并补 `reason`；对照组 `amount_cny=0.0025` 的 `cost` **不含 reason**；聚合层 `cost_status={"estimated":6,"unknown":0}`、`cost_cny_estimated_sum=0.0025`、`runs_without_estimated_cost=5`，即"补解释"不改变任何金额与计数口径 |
| 模板修正验证（**tracked 报告未重生成**） | 同命令只写 scratch | `--scan-root output --out tmp/eval-cost-report-after-template.md` → `sources=8 records=127 arms=14 cases=127 cost_status=unknownx127`；产物第 79 行改为「… \| 0 \| 已由 QWEN-104b/104c 修复: `_number` 现接受非负 int/float 并要求 math.isfinite, 复跑本计数 127 -> 0 …」，§15 登记的"计数 0 + 旧解释"自相矛盾行消失；`docs/EVAL_USAGE_COST_REPORT_2026-10-22.md` 一字未动；日志 `logs/eval-cost-rerun.txt` |
| 全量回归（**最终代码，记录数**） | `pytest tests/`（**2303** 项 = 收集 2302 + 集合期 1 条 `mcp` `importorskip` skip，口径同 §14/§15） | **2283 passed / 0 failed / 20 skipped / 842.46 s（14:02）**，`--basetemp output/qwen104d-2026-10-23/pytest-full-final`，探针 `outbound attempts=0 unique_hosts=0`；相对 104c 的 2282 恰好 +1（本卡新增项），既有用例无一转红；日志 `logs/full-suite-final.log`。另有一次 16:13 结束的同口径全量 **2283 / 20 skipped / 807.42 s**（`logs/full-suite.txt`），跑的是用例补全前的初版测试文件，项数相同但不作记录数 |
| CI 可移植子集 | 40 个文件（含 `tests/a/test_run_usage_admin.py`） | **412 passed / 1 skipped / 90.29 s**（相对 104c 的 411/1 恰好 +1），`--basetemp output/qwen104d-2026-10-23/pytest-ci`，探针 `attempts=0 unique_hosts=0`；日志 `logs/ci-portable.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9` **All checks passed**；裸 ruff `run_usage.py` 0 findings、测试文件仍 **4 findings 与 HEAD 基线逐条相同**（EM101 行号 `293`→`331`，与 `git show HEAD:` 基线逐条相同）；`git diff --check` 干净；路由装饰器仍 **189**、测试文件仍 **192**；`grep -rln report_eval_cost tests/` 为空 → 脚本模板无测试面 |
## 17. QWEN-201 确认门控长期记忆实测摘要（2026-10-23，分支 `qwen/wave2-memory`，零模型调用）

Lead 2026-10-23 17:20 验收 §16（自行复跑 `test_run_usage_admin.py` **14 passed / 1.70 s**、104d 已合并 `main`）后派 **QWEN-201**，明令「现在开工（允许，不适用交付后 hold）」、分支由 Lead 预建并 fast-forward 到 `main@542d8be`；开工 HEAD = `a312050`，工作树起点干净。DoD 四点原文与逐条交付见 `docs/CLAIMS_LEDGER.md` §20 开头。

| 运行 | 集合 | 结果 |
|---|---|---|
| **迁移真跑（隔离 SQLite，回滚证据）** | `alembic` CLI，库只在 `output/qwen201-2026-10-23/tmp/alembic-memory.db` | `heads` = `20261023_0012 (head)`；空库 `upgrade head` → **12** 个 revision、34 张表含两张新表，DDL 原文 `CREATE UNIQUE INDEX uq_user_memory_active ON user_memories (user_id, kind) WHERE status = 'active'`；`downgrade base` → **12** 步回滚、两张表与全部 **7** 个索引消失、`alembic_version` 归空；**再 `upgrade head`** → 表回归且两张记忆表 0 行。`data/a3_learning.db` mtime `16:18:17` 早于本轮 `17:30:48–17:30:56`，未被写；未读 `.env`。日志 `logs/migration-cli.txt`；首跑的检视片段自身取列出错，另存 `logs/migration-cli-run1-probe-bug.txt` 不删 |
| **CI alembic smoke 同形（`ci.yml:142-147`）** | 独立空库 `tmp/ci_smoke.db`，命令逐字照抄 CI | `upgrade head && downgrade base` → **exit=0 / exit=0**，12 步升级（含 `20261014_0011 -> 20261023_0012` 原文一行）+ 12 步回滚；日志 `logs/ci-alembic-smoke.txt`、`logs/ci-smoke-upgrade.txt`、`logs/ci-smoke-downgrade.txt` |
| **既有现象取证（不属本卡）** | 同一个库文件上先 `init_db()` 再 `alembic upgrade head` | **exit=1**、`sqlite3.OperationalError: table profiles already exists`，红在 baseline `20260618_0001` 的无条件 `create_table`。三条判据与本卡无关：失败日志里 `20261023_0012` 出现 **0** 次；把本卡迁移移出 `alembic/versions/` 后 **HEAD 基线同样 exit=1、同一句错误**（`logs/mixed-head-baseline.txt`，事后已归位并校验 md5）；CI 用两个不同库文件（`ci_smoke.db` vs `ci_tests.db`）故踩不到。归位建议交 Lead 指派 |
| schema 双路径 | 迁移路径 vs `Base.metadata.create_all`（`init_db()` 那条） | 两张表**列集与索引集相同**；部分唯一约束实测撞出 `IntegrityError`；活行改 `revoked` 后新活行可插入；日志 `logs/schema-smoke.txt` |
| 定向（最终代码） | `test_user_memory_migration.py`（3 项）+ `test_user_memory_service.py`（50 项）= **53** 项 | **53 passed / 31.47 s**（`logs/targeted-after-eol-normalise.txt`）。此前 53 passed / 31.57 s（`logs/targeted-final.txt`）与反向验证恢复后 53 passed / 32.03 s（`logs/targeted-after-reverse-proof.txt`）。**首跑 51 passed / 2 failed / 33.62 s**（`logs/targeted-run1.txt`）不作记录数：两处失败都是本卡自己的用例期望写错，改的是测试不是产品代码（台账 §20.4） |
| **反向验证：9 组各禁用一条绑定规则** | 同上 53 项 | M1 撤 run 资格闸门 → **7 failed / 46 passed**；M2 撤人类 actor 守卫 → **6 / 47**；M3 让 revoked 可读 → **2 / 51**；M4 TTL 比较永真 → **1 / 52**；M5 撤服务层 supersede → **2 / 51**；M6 `CONFIRMED` 写成 `SUPERSEDED` → **5 / 48**；M7 撤 revoke 幂等 → **1 / 52**；M8/M9 `downgrade()` 两表分支永假 → 各 **2 / 51**。9 组恢复后与 pristine **md5 逐字节相同**、复跑全绿。补丁 `tmp/rp-M1..M9.patch`、日志 `logs/rp-M*.txt`、汇总 `logs/reverse-proof-summary.txt`。本主机 `git apply -R` 被分类器拦，恢复用本卡自建 pristine 的纯文件复制 |
| 全量回归（**最终代码，记录数**） | `pytest tests/`（**2356** 项 = 收集 2355 + 集合期 1 条 `mcp` `importorskip` skip，口径同 §14/§15/§16） | **2336 passed / 0 failed / 20 skipped / 1156.38 s（19:16）**，`--basetemp output/qwen201-2026-10-23/pytest-full`，探针 **`outbound attempts=0 unique_hosts=0`**；相对 104d 的 2283 恰好 **+53**，全为本卡新增项，既有用例零转红零消失。收集 2355 项用时 11.79 s（`logs/collect-quiet-probe.txt`）。**时长差如实分开**：比 104d 的 842.46 s 长 313.92 s，而本卡 53 项只占 31.47 s，差额不归因于本卡；warnings 22 → 25，新增三条全落在 `tests/integration/test_manim_fallback.py`（1→3）与 `test_artifacts_api.py`（1→2），本卡两个新文件零 warning——是线索不是结论。日志 `logs/full-suite.txt`（去 NUL 副本 `logs/full-suite-clean.txt`） |
| CI 可移植子集 | `ci.yml:172-212` 的 **40** 个文件（**清单未扩**；本轮由 `awk` 从 `ci.yml` 机械重取，与 104d 清单逐行相同） | **412 passed / 1 skipped / 80.92 s**，`--basetemp .../pytest-ci`，探针 `attempts=0 unique_hosts=0`；与 104d 的 412/1 **逐数相同**，正因为本卡两项不在该子集内；日志 `logs/ci-portable.txt` |
| CI 同形口径下的本卡用例 | `--no-cov --benchmark-disable -q`（`ci.yml:213` 同形）+ 前置 `init_db()` | **53 passed / 31.58 s**；`create_all` 确实带出两张记忆表与全部索引；日志 `logs/ci-style-targeted.txt` |
| 静态检查与口径 | `backend/app scripts/ tests/` | CI 口径 `ruff check --select=F821,F823,E9` **All checks passed**；`git diff --check` 干净。裸 ruff（全仓基线 13,647 项，仓库未纳入门禁）：`models.py` **18 → 18** 与 HEAD 基线逐条相同，4 个新文件 **24** 项 = `EM101` 18 + `EM102` 2 + `I001` 2 + `E501` 2，四条规则仓库内已分别有 365/64/514/2907 项同族命中（`run_audit.py`+`run_usage.py` 自己就有 6 项 EM101）；`E501` 两处为 `test_user_memory_service.py:64-65`（106/102 字符），全量跑完后未再动代码，登记为下一卡顺手项。`__tablename__` **37 → 39**；测试文件 **191 → 193**（节点 id 去重口径），含集合期 mcp 文件则是 **192 → 194** |
| 行尾归一（本卡自造噪音，如实登记） | 3 个新文件初写成纯 LF，本仓既有文件是 `i/lf w/crlf` | 归一为 CRLF：转换前后按 LF 归一化 **md5 相同**（纯行尾变换）、孤立 CR/LF **0**；归一后定向复跑 **53 passed / 31.47 s**。**全量 1156.38 s 那一轮跑的是归一前的 LF 形态**，归一不动任何内容字节；旧拷贝在 `tmp/pre-crlf/`。台账 §20.3 末行 |

## 18. QWEN-201b 把两份记忆测试纳入 CI 快清单实测摘要（2026-10-23，分支 `qwen/wave2-memory`，零模型调用、产品代码零改动）

Lead 2026-10-23 18:50 §4 验收 QWEN-201（自行复跑两份记忆测试 **53 passed / 24.38 s**，全量 2336/0/20 接受；三处读法裁定：admin 不作记忆确认者、`revoke` 同样要求人类 actor、`source_type` 暂留 32 字符自由串）后派 **201b**：把 `tests/a/test_user_memory_service.py`、`tests/a/test_user_memory_migration.py` 加入 `ci.yml` 快清单，文件数 40→42、通过数以实测为准，同步 README/TEST_MATRIX，**不碰产品代码**，跑一遍新清单确认全绿。开工 HEAD = `c28aac4`（= Lead 合并 201 后的 `main` tip，工作树起点干净）。

| 运行 | 集合 | 结果 |
|---|---|---|
| **清单变更（唯一产品外改动）** | `.github/workflows/ci.yml` `quality` job `Pytest (portable V2 contract suite)` | hunk `@@ -212,0 +213,2 @@`：在 `:212 test_deployment_policy.py` 之后追加两行，清单本体 `:173-214`；文件数 **40 → 42**（按 201 既有追加惯例置于尾部，与 `test_conversation_memory_v2.py` 的记忆主题相邻性已在台账 §21.2 说明取舍）。清单由 `sed`+`grep` 从 `ci.yml` **机械重取**存入 `ci-portable-list.txt`，与 201 的 40 行清单逐行比对为 `40a41,42` **恰好 +2**，42 个路径全部存在（逐条 `-f` 检查，缺失 0） |
| **CI 同形全绿（记录数）** | `ci-portable-list.txt` 的 42 个文件，旗标逐字照抄 `ci.yml:215`（`--no-cov --benchmark-disable -q`）+ 前置 `init_db()` | **465 passed / 1 skipped / 0 failed / 96.08 s**（`-rs` 版，`logs/ci-portable-final.txt`）；首跑 **465 passed / 1 skipped / 112.98 s**（`logs/ci-portable-run1.txt`）。相对 201 的 412/1 **恰好 +53** = 本卡纳入的 50 服务项 + 3 迁移项，既有用例零转红零消失；唯一 skip 由 `-rs` 直接点名 `tests\a\test_auth_restart.py:18: Explicit disposable PostgreSQL required`，与该子集历史唯一 skip 同一处；`--basetemp output/qwen201b-2026-10-23/pytest-ci-rs`，前置 `init_db()` **exit=0**（`logs/ci-init-db.txt`），探针 **`outbound attempts=0 unique_hosts=0`** |
| **CI 另两步在同一份配置上复跑** | `ci.yml:141-147` alembic smoke、`ci.yml:113-115` ruff 门 | alembic `upgrade head` → **exit=0**、`downgrade base` → **exit=0**（空库 `output/qwen201b-2026-10-23/ci_smoke.db`，日志 `logs/ci-alembic-smoke.txt`）；`ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **exit=0 / All checks passed**（`logs/ci-ruff.txt`） |
| **workflow 文件本体校验** | `yaml.safe_load(ci.yml)` | 解析 **OK**，4 个 job（frontend / dependency-security / quality / enterprise-contract）；按步骤枚举 pytest 文件数：`quality` 的可移植步 **42**、`enterprise-contract` 仍是 **38**（本卡未动 PG 清单，YAML 里逐 job 打印为证，`logs/ci-yaml-parse.txt`） |
| 静态与行尾 | `git diff --check`、`ci.yml` 字节统计 | `ci.yml` 由 341 行增至 **343 行**（CRLF 343 / 孤立 LF 0 / 孤立 CR 0，改动前后皆然）（编辑器写入未破坏行尾，`git check-attr` 显示该文件无 eol 覆盖，仓库 `core.autocrlf=true`）；`git diff --check` 干净；CI 口径 ruff 见上 |
| 范围与边界 | — | 只改 `.github/workflows/ci.yml`（+2 行）与文档；**产品代码、测试代码、迁移零改动**（`git diff --stat` 只有 `ci.yml`、`README.md`、`docs/TEST_MATRIX.md`、`docs/CLAIMS_LEDGER.md`）；零模型调用、未读 `.env`；未动 `enterprise-contract` 38 文件清单、未动覆盖率门槛步（`ci.yml:221-229`）；全量套件未重跑（本卡不新增用例，2336/0/20 记录数不动，见台账 §21.4） |
## 19. QWEN-202 跨会话摘要实测摘要（2026-10-23，分支 `qwen/wave2-summary`，零模型调用）

Lead 18:55 派 **QWEN-202**，明令「201b 后开工」；分支 `qwen/wave2-summary` 由 Lead 预建，开工 HEAD = `c28aac4` = `origin/main`，工作树起点干净。DoD 原文与逐条交付见 `docs/CLAIMS_LEDGER.md` §22 开头。**编号说明**：§18 属 QWEN-201b，在 `qwen/wave2-memory`（`origin/qwen/wave2-memory = a625adc`）待合并，本节按合并后的最终次序直接编 §19。

| 运行 | 集合 | 结果 |
|---|---|---|
| 定向（最终代码） | `tests/a/test_session_summary.py` = **40** 项 | **40 passed / 13.23 s**（10 组反向验证逐组还原后的复跑，`logs/targeted-after-reverse-proof.txt`）；补守卫后、反向验证前的同字节首跑 40 passed / 12.85 s（`logs/targeted-with-run-read-guard.txt`）。39 项阶段：CRLF 归一后 39 passed / 20.00 s（`logs/targeted-run3-crlf.txt`），归一前 19.79 s（`logs/targeted-run2.txt`）。**首跑 2 failed / 37 passed / 20.38 s**（`logs/targeted-run1.txt`）不作记录数：两处红点都是本卡自己的用例期望写错（TTL 把 `confirm()` 自戳时刻当成注入 `NOW`；手填记忆漏 `run_id=None`），改的是测试、没放宽产品规则。**中途自查返工**：源 run 状态那次 SELECT 起初没有异常守卫，与本模块 docstring 的承诺不一致 → 补守卫 + 1 项用例（39 → 40），反向验证随之从 9 组扩到 10 组，定向/集合/全量/空态证据全部在最终字节上重跑，39 项阶段日志移到 `logs/prev-39items/` |
| **反向验证：10 组各禁用一条绑定规则** | 同 40 项 | R1 读时复核源 run 状态(不被 partial 污染)（禁用 `:127`）→ **8 failed / 32 passed**；R2 窗口截断（禁用 `:117`）→ **1 failed / 39 passed**；R3 token 预算（禁用 `:132`）→ **2 failed / 38 passed**；R4 超长裁剪（禁用 `:94`）→ **1 failed / 39 passed**；R5 空态原因区分（禁用 `:144`）→ **8 failed / 32 passed**；R6 persisted 恒为 False（禁用 `:88`）→ **3 failed / 37 passed**；R7 空内容降级（禁用 `:120`）→ **1 failed / 39 passed**；R8 摘要哈希只覆盖正文（禁用 `:87`）→ **1 failed / 39 passed**；R9 源码静态扫描禁止写回/模型（禁用 `:105`）→ **1 failed / 39 passed**；R10 源 run 那次读也压成稳定 code（禁用 `:175`）→ **1 failed / 39 passed**。 逐组明细见本节末表。逐组跑完即按字节还原，pristine md5 `005986907fd116096b6f831c78fe7160` 全等（`byte_restore_ok=True` ×10）；10 组每次调用都挂探针，`attempts=0 unique_hosts=0` ×10。驱动 `reverse_proofs.py`、日志 `logs/reverse-<组名>.txt`、汇总 `logs/reverse-proof-summary.txt`。**第一轮作废如实登记**：驱动初版未逐轮回滚，R2–R4 的红点为叠加态（9/11/12 failed）且 `restore=False`，发现即停、还原、改驱动，被污染的日志改名 `logs/void-stacked-reverse-*.txt` 保留不删 |
| **空态证据** | 真实 SQLite（`tmp/empty-state-evidence.db`）+ `logs/empty-state-evidence.txt` | 在**最终字节**上跑（守卫前那份在 `logs/prev-39items/empty-state-evidence-pre-guard.txt`，判定逐字相同）。四种空态各自打印完整返回体与其后的两表行数：空库 `empty/no_active_memory`（counts 0/0）、只有未确认候选（counts 仍 0/0）、`token_budget=1` → `empty/no_memory_fit_budget` + `skipped=[token_budget]`（counts 仍 1/1，摘要一次没多写一行）、`revoke` 后 `empty/no_active_memory`（counts 1/2，**这 1 条增量是 `memory.revoke()` 自己的审计，不是摘要写的**） |
| 摘要忠实性与不写回 | 用例逐条 | 固定金句 `- weak_point：分数除法还需要复习`；每一行 `：` 右侧必须命中已存文本；连续三次摘要后 `user_memories`/`memory_events` 仍 `(1, 1)`；`NOW` 与 `NOW+3600` 两次构建除 `generated_at` 外逐字段相同、`summary_sha256` 相同；新增记忆即改哈希 |
| 全量回归（**最终代码，记录数**） | `pytest tests/`（**2396** 项 = 收集 2395 + 集合期 1 条 `mcp` `importorskip` skip，口径同 §14/§15/§16/§17） | **2376 passed / 0 failed / 20 skipped / 993.55 s**，exit 0，`--basetemp output/qwen202-2026-10-23/pytest-full2`，195 个测试文件，探针 **`outbound attempts=0 unique_hosts=0`**；相对 201 的 2336 恰好 **+40**，全为本卡新增项，既有用例零转红零消失；全量 warnings 21（201 那轮 25），warnings summary 里 `session_summary` 命中 **0** 次——是线索不是结论；日志 `logs/full-suite.txt`（去 NUL 副本 `logs/full-suite-clean.txt`）。收集 2395 项用时 8.63 s（`logs/collect-only.txt`） |
| CI 可移植子集 | **本卡未扩清单**：`ci.yml` 在本分支仍是 201 之后的形态（40 文件；42 文件那份改动在 `qwen/wave2-memory`） | 本卡 40 项**不在** portable 清单内，因此该子集计数不因 202 变化；Lead 202 派工条没要求纳入（201b 那句只针对两份记忆测试）。若要纳入，是 `ci.yml` 尾部 +1 行、42 → 43 文件，需另跑一轮同形复现 |
| 静态检查与口径 | `backend/app/services/session_summary.py` `tests/a/test_session_summary.py` | CI 口径 `ruff check --select=F821,F823,E9` **All checks passed**；裸 ruff（未纳入门禁）**15 项** = `RUF001` 7 + `EM101` 4 + `EM102` 2 + `I001` 2，同族规则在本仓 `backend/app`+`tests/a`（含本卡新文件）已有 `E501` 2221 / `RUF001` 3421 / `I001` 319 / `EM101` 252 / `EM102` 56（`logs/ruff-final.txt`、`logs/ruff-family-repo.txt`）；`git diff --check` 干净；`__tablename__` 仍 **39**（本卡零新表）、路由装饰器仍 **194**（本卡零端点）、测试文件 **194 → 195** |
| 行尾 | 2 个新文件写成 CRLF | 180 行 / 307 行，`crlf == 行数`、孤立 LF/CR 各 0；LF 原件 `tmp/pre-lf/`，CRLF pristine `tmp/pristine-crlf/`（10 组反向验证的还原基准）。**归一在反向验证与全量之前完成**，两轮跑的都是最终字节（与 §17 那轮顺序相反，噪音更少） |

### 19.1 10 组反向验证逐组明细（每组只禁用一条绑定规则，跑完立刻按字节还原）

| 组 | 禁用的绑定规则 | 禁用行（原文） | 该组 40 项的结果 | 按字节还原 |
|---|---|---|---|---|
| R1 | 读时复核源 run 状态(不被 partial 污染) | `:127` `if status != MEMORY_ELIGIBLE_RUN_STATUS:` | **8 failed / 32 passed** / 14.41 s | True |
| R2 | 窗口截断 | `:117` `for memory in memories[:window]:` | **1 failed / 39 passed** / 13.91 s | True |
| R3 | token 预算 | `:132` `if used_tokens + cost > token_budget:` | **2 failed / 38 passed** / 13.59 s | True |
| R4 | 超长裁剪 | `:94` `if estimate_tokens(text) > MAX_TOKENS_PER_MEMORY:` | **1 failed / 39 passed** / 13.51 s | True |
| R5 | 空态原因区分 | `:144` `reason = "no_active_memory" if not memories else "no_memory_fit_budget"` | **8 failed / 32 passed** / 13.46 s | True |
| R6 | persisted 恒为 False | `:88` `"persisted": False}` | **3 failed / 37 passed** / 13.63 s | True |
| R7 | 空内容降级 | `:120` `if not isinstance(content, str) or not content.strip():` | **1 failed / 39 passed** / 13.48 s | True |
| R8 | 摘要哈希只覆盖正文 | `:87` `"summary_sha256": _digest([line for line in summary.split("\n") if line]),` | **1 failed / 39 passed** / 13.93 s | True |
| R9 | 源码静态扫描禁止写回/模型 | `:105` `"""Fold readable memories into one bounded summary. Pure: no session, no model."""` | **1 failed / 39 passed** / 14.23 s | True |
| R10 | 源 run 那次读也压成稳定 code | `:175` `except Exception as exc:` | **1 failed / 39 passed** / 13.76 s | True |

每组 `failed + passed = 40`（全量定向集合），转红用例名逐条记在 `logs/reverse-proof-summary.txt` 与 `logs/reverse-<组名>.txt`。

## 20. QWEN-202b 摘要测试纳入 CI 快清单实测摘要（2026-10-23，分支 `qwen/wave2-summary`，零模型、产品零改动）

Lead §4 `[2026-10-23 22:35]`（提交 `bbcc8e0`）派 202b：「把 `tests/a/test_session_summary.py` 加入 `.github/workflows/ci.yml` 快清单，42→43 文件；同形复跑预期 **505/1**（原 465 + 40），更新 README/TEST_MATRIX；产品零改动；完成后 `[DONE]`。」同一节验收 201b 与 202，并关闭我在 §22.4 提请的五处取舍。逐条交付见 `docs/CLAIMS_LEDGER.md` §23。

| 运行 | 集合 | 结果 |
|---|---|---|
| 清单机械重取 | `inspect_ci_list.py` 解析 `ci.yml` → `quality` 步文件行 | **43 个文件**（201b 那份 42 → 本卡 `42a43`），43 条路径 0 缺失；`enterprise-contract` 仍 **38**；`yaml.safe_load` OK |
| **CI 同形子集（记录数）** | 43 文件全量逐文件参数 + `--no-cov --benchmark-disable -q -rs`（旗标逐字抄 `ci.yml:216`） | **505 passed / 1 skipped / 0 failed / 4 warnings / 140.63 s**，exit 0，`--basetemp output/qwen202b-2026-10-23/pytest-ci-rs`，前置 `init_db()` exit=0，探针 **`outbound attempts=0 unique_hosts=0`**；唯一 skip 是 `test_auth_restart.py:18`（要求一次性 PostgreSQL，CI 上同样 skip）。相对 201b 的 465/1 恰好 **+40** = §22 的摘要 40 项，与 Lead 派工条的「预期 505/1」一致 |
| 同命令首跑 | 同上，仅去掉 `-rs`、`--basetemp …/pytest-ci` | 505 passed / 1 skipped / 143.77 s（计数与记录数一致，时长差属主机波动）——`logs/ci-portable-run1.txt` |
| fast job 其余门 | 同库口径 | `alembic upgrade head` exit=0、`downgrade base` exit=0（12 上 + 12 下共 24 条 Running）、`ruff check --select=F821,F823,E9 backend/app scripts/ tests/` All checks passed ——`logs/ci-gates.txt` |
| 行尾与差异 | `.github/workflows/ci.yml` | 343 → **344** 行、`crlf == 行数`、孤立 LF/CR 各 0、md5 `2bf211180ec7435fd70cf711adf6c292`；`git diff --stat` = **1 file changed, 1 insertion(+)**；`git diff --check` 干净 |
| 未跑 | 全量 `pytest tests/` | 本卡零新增用例、零产品改动，§22 的 **2376/0/20 / 2396 项**记录数不动（不擅自改记录数）；PG 清单与覆盖率步未动 |

外推限制：本轮全部是**本机 offline 同形复跑**；GitHub `quality` job 的真实绿灯属 remote 证据，由 Lead 判读（本机无 `gh` CLI）。

## 21. QWEN-211 有界重规划实测摘要（2026-10-24，分支 `qwen/wave2-planning`，零模型调用）

Lead §4 `[2026-10-24 12:25]`（提交 `49910eb`）派 211：「实现**有界重规划**：计划失效检测（工具失败/新证据）→ 允许有限重规划；最大轮数/深度硬上限；保留 checkpoint，超限停止而不是无限循环；测试覆盖超限停止与恢复」，边界「只改 planner/测试/文档，不碰 API/UI；零模型、不读 `.env`」。逐条交付见 `docs/CLAIMS_LEDGER.md` §24。

| 运行 | 集合 | 结果 |
|---|---|---|
| 新用例 | `tests/a/test_learning_package_replan.py` | **15 passed / 0 failed / 7.65 s**，探针 `attempts=0 unique_hosts=0`，`logs/new-file-final.txt` |
| 既有回归面 | 10 个学习包/生命周期文件（不含新文件） | **207 passed / 0 failed / 41.67 s**，`logs/targeted-package.txt` |
| 合并 | 上述 + 新文件 | **222 passed / 0 failed / 48.22 s**，`logs/combined-package.txt` |
| **全量（记录数，最终字节）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen211-2026-10-24/pytest-full2`） | **2391 passed / 0 failed / 20 skipped / 901.89 s / 20 warnings**，`PYTEST_EXIT=0` 记入同一日志，196 个测试文件 / 2411 项，探针 **`attempts=0 unique_hosts=0`**；相对 202 的 2376 恰好 **+15**，既有用例零转红零消失。`logs/full-suite-repeat.txt`（去 NUL 副本 `full-suite-repeat-clean.txt`） |
| 全量首跑（补最后一条交付结果断言之前的字节） | 同命令、`--basetemp …/pytest-full` | 2391 passed / 0 failed / 20 skipped / 1079.94 s / 21 warnings，计数与记录数逐项一致；`logs/full-suite-final.txt` |
| **CI 同形子集（43 文件，最终字节）** | `ci.yml:216` 同形旗标 + 前置 `init_db()` | **505 passed / 1 skipped / 0 failed / 4 warnings / 135.49 s**，`PYTEST_EXIT=0`，探针 `attempts=0`；清单机械重取 43 文件 0 缺失 ——`logs/ci-portable-final.txt`、`logs/ci-list-inspect.txt` |
| 集合 | `--collect-only -q` | 2410 个 node id（收集 13.11 s）+ 收集期 1 条 `mcp` `importorskip` skip = **2411 项**；`logs/collect-only.txt` |
| 失效/上限/审计行为 | 定向日志（`--log-cli-level=INFO`，4 个关键用例） | 4 passed；`logs/replan-evidence-run.txt` |
| 反向验证 | 10 组逐条禁用绑定规则 | **全部转红**，累计 60 个失败用例，产品文件按字节还原（`ALL_10_MUTATIONS_CAUGHT`，`PRODUCT_RESTORED_TO_PRE_ROUND_BYTES=1`）；`logs/reverse-summary.txt` |
| 门 | CI ruff（`--select=F821,F823,E9`）+ `compileall` | All checks passed / COMPILE_OK；`logs/gates-ruff.txt` |
| 未跑 | GitHub `quality` job 真实回执、PG 专项 | 本卡未把新文件纳入快清单（清单仍 43 文件、记录仍 505/1，同形复跑见上一行）；PG 层无专属改动 |

外推限制：全部为**本机 offline** 复跑，零计费模型调用；GitHub 真实回执与 PG 侧结论不属本卡主张。重规划阈值 `MAX_REPLAN_ROUNDS=1`/`MAX_REPLAN_DEPTH=2` 是基线常量，**最终取值待 Lead 产品裁定**。

## 22. QWEN-211b 版本 bump + 重规划测试纳入 CI 快清单实测摘要（2026-10-24，分支 `qwen/wave2-planning`，零模型调用、产品逻辑零改动）

| 项 | 口径 | 结果 |
|---|---|---|
| 版本常量 | `backend/app/agent_runtime/learning_package.py:23` | `learning-package-v2.8` → **`learning-package-v2.9`**（1 insertion / 1 deletion，其余 768 行逐字节不动） |
| 文档同步 | Lead 点名的三处 | `LEARNING_PACKAGE_GUIDE.md:93`、`V2_TEN_MODULE_IMPLEMENTATION.md:58`、`CLAIMS_LEDGER.md` R4/T1/S7（`:31`/`:68`/`:98`）；历史行 `:140`、`:901`、`OPTIMIZATION_STATUS_2026-10-18.md:86`、`evals/results/` 两件、对话 `:1859` **未动**；主计划 `:252` 登记未改 |
| CI 清单 | `.github/workflows/ci.yml` `quality` job | **43 → 44 个文件**（新行 `:216`，旗标行 `:216`→`:217`；`enterprise-contract` 仍 38） |
| 版本一致性核对（只读脚本） | `check_version_consistency.py` | `VERSION_CONSISTENT=1`；`logs/version-consistency.txt` |
| CI 门 | ruff（`--select=F821,F823,E9`）+ `compileall` + 前置 `init_db()` | All checks passed / exit 0 / INITDB_EXIT=0；`logs/gates.txt`、`logs/ci-init-db.txt` |
| 新文件单跑 | `tests/a/test_learning_package_replan.py` | **15 passed / 0 failed / 7.62 s**，`logs/new-file.txt` |
| 既有回归面 | 10 个学习包/生命周期文件（不含新文件） | **207 passed / 0 failed / 39.83 s**；合并 **222 passed / 45.86 s**（= 207 + 15）；`logs/targeted-package.txt`、`logs/combined-package.txt` |
| **CI 同形子集（44 文件，最终字节）** | `ci.yml:217` 同形旗标 `-rs` + 前置 `init_db()` | **520 passed / 1 skipped / 0 failed / 4 warnings / 145.34 s**，`PYTEST_EXIT=0`，探针 `attempts=0 unique_hosts=0`；清单机械重取 44 文件 0 缺失；唯一 skip = `test_auth_restart.py:18`；相对 202b 的 505 恰好 +15，与 Lead 预计 **520/1** 吻合 —— `logs/ci-portable.txt`（去 NUL 副本 `ci-portable-clean.txt`）、`logs/portable-list.txt` |
| **全量（记录数，v2.9 字节）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen211b-2026-10-24/pytest-full-suite`） | **2391 passed / 0 failed / 20 skipped / 1308.53 s / 21 warnings**，`PYTEST_EXIT=0`，196 个测试文件 / 2411 项，探针 `attempts=0 unique_hosts=0`；passed / skipped / 项数与 §21 的 211 记录**逐项一致**（本卡零新增用例），warnings 数随轮次波动（§21 记录数轮 20 条、本轮 21 条），不作结论；`logs/full-suite.txt`（去 NUL 副本 `full-suite-clean.txt`） |
| 集合 | `--collect-only -q` | 2410 个 node id + 收集期 1 条 `mcp` `importorskip` skip = **2411 项**（收集 15.97 s）；`logs/collect-only.txt` |
| 字节 | 本卡 8 个改动文件 | 纯 CRLF、孤立 LF/CR 各 0；另 §21 两行的 warnings 数（11）按 pytest summary 行更正为 **20**（记录数轮）/**21**（首跑轮），其余数值与结论一字未动；`ci.yml` 345 行 md5 `3658e9f11738a4633e72551947994080`，产品 769 行 md5 `39365d91586918122d7e72454f1ad498`，新测试文件 md5 不变 `49d2b437e07459ea3af918657892e56b`；`git diff --check` 干净；`logs/bytes-inventory.txt` |
| 未跑 | GitHub `quality` job 真实回执、PG 专项 | 本卡只改清单与版本常量，PG 清单（38 文件）与方言行为未触及 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用；GitHub 真实回执与 PG 侧结论不属本卡主张。**缺口登记**：没有任何测试断言 `PROMPT_VERSION` 的字面值，bump 在测试面上静默，本卡按 Lead 范围未补用例（见台账 §25.2）。

## 23. QWEN-211c 版本防漂移断言实测摘要（2026-10-24，分支 `qwen/wave2-planning`，零模型调用、产品逻辑与 CI 零改动）

| 项 | 口径 | 结果 |
|---|---|---|
| 用例 | `tests/a/test_learning_package_replan.py` | 新增 **1 条**无 fixture 断言 `PROMPT_VERSION == "learning-package-v2.9"`（`:308`）；`git diff --numstat` = **8 / 0**，hunk `@@ -300,0 +301,8 @@` 纯尾部追加；308 行、纯 CRLF，md5 `49d2b437e07459ea3af918657892e56b` → `a530f5a6342dcfa7eb6c145539cccfaa`；条目 **15 → 16** |
| 产品 | `backend/app/agent_runtime/learning_package.py` | **一字未动**：769 行、md5 `39365d91586918122d7e72454f1ad498`（= 211b 交付值） |
| CI | `.github/workflows/ci.yml` | **一字未动**：345 行、md5 `3658e9f11738a4633e72551947994080`；`quality` 快清单仍 **44** 文件（末位仍是重规划测试）、`enterprise-contract` 仍 **38**，`yaml.safe_load` 机械重取 0 缺失、无重复 —— `logs/ci-list-inspect.txt`（`CI_UNTOUCHED=1`） |
| 版本一致性 | 产品 `:23` = 测试 `:308` = 指南 `:93` = 十模块 `:58` | 全部 `learning-package-v2.9`，`PRODUCT_TEST_DOC_AGREEMENT=1`；主计划 `:252` 由 Lead 自行同步（本卡未动）；台账前 200 行仍点名 v2.x 的只剩 `:68`/`:140` 带日期历史行 —— `logs/version-consistency.txt` |
| 门 | ruff（`--select=F821,F823,E9`）+ `compileall` + 前置 `init_db()` | All checks passed / exit 0 / INITDB_EXIT=0；`logs/gates.txt`、`logs/ci-init-db.txt` |
| 新文件单跑 | `tests/a/test_learning_package_replan.py` | **16 passed / 0 failed / 8.45 s** |
| 既有回归面 | 10 个学习包/生命周期文件（不含本卡用例所在文件的既有项） | **207 passed / 43.31 s**；合并 **223 passed / 52.34 s**（= 207 + 16） |
| **CI 同形子集（44 文件）** | `ci.yml:217` 同形旗标 `-rs` + 前置 `init_db()` | **521 passed / 1 skipped / 0 failed / 4 warnings / 148.33 s**，`PYTEST_EXIT=0`，探针 `attempts=0 unique_hosts=0`；相对 211b 的 520 恰好 +1，与 Lead 预计 **521/1** 吻合；唯一 skip = `test_auth_restart.py:18` —— `logs/ci-portable.txt`（去 NUL 副本 `ci-portable-clean.txt`） |
| **全量（记录数）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + `--basetemp output/qwen211c-2026-10-24/pytest-full-suite`） | **2392 passed / 0 failed / 20 skipped / 853.50 s / 23 warnings**，`PYTEST_EXIT=0`，196 个测试文件 / **2412 项**，探针 `attempts=0 unique_hosts=0`；= §25 的 2391 + 本卡 1 项，与 Lead 预计 **2392/0/20** 一致 —— `logs/full-suite.txt`（去 NUL 副本 `full-suite-clean.txt`） |
| 集合 | `--collect-only -q` | 2411 个 node id + 收集期 1 条 `mcp` `importorskip` skip = **2412 项**（收集 14.99 s） |
| 反向验证 | 产品常量临时改回 v2.8（工作树内，未提交） | 整文件 **1 failed / 15 passed / 8.60 s**（红点即新用例）；单跑新用例 **1 failed / 2.31 s**；按字节恢复后 md5 一致、`git diff -- backend/` 为空，复跑 **16 passed / 7.29 s** —— `logs/reverse-*.txt`、`logs/post-restore.txt` |
| 未跑 | GitHub `quality` 真实回执、PG 专项 | 本卡零 CI/PG 面改动，同 §22 口径 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用；GitHub 真实回执与 PG 侧结论不属本卡主张。本节关闭 §25.2 登记的「没有任何测试断言 `PROMPT_VERSION` 字面值」缺口。

## 24. QWEN-221 单一工具目录 + deny-by-default + 统一审计实测摘要（2026-10-24，分支 `qwen/wave2-tools`，零模型调用）

| 项 | 口径 | 结果 |
|---|---|---|
| 单一来源 | `backend/app/services/tool_catalog.py`（新增） | **9 个工具 = V2 四个只读 + V1 五个**，一条 `ToolSpec` 同时给出工具名、来源、描述、权限键、允许角色、只读/副作用、版本、超时与超时类、参数模型或 JSON schema、截断上限、MCP 暴露；`ROLE_PERMISSIONS` 给角色→权限键；215 行、纯 CRLF、md5 `3c13c4490298567bf34b6986e6c86656` |
| 运行时 deny-by-default | `decide_access()` 三层：目录注册 → 角色列出 → 权限键持有 | 未知工具 `unknown_tool`、未列角色 `role_not_allowed`、矩阵自相矛盾 `permission_not_granted`、无权限键角色 `unknown_role`（含 `student`/`teacher`/`admin` 主体角色）一律拒；`practice`/`reviewer` 基线 0 键 0 工具 |
| 散落注册点替换 | V2 broker + V1 registry | `ROLE_TOOLS`/`SCHEMAS`/三个 pydantic 参数模型**删除**（broker 171 行、md5 `e17a28b1da38837f4b983e51b5635233`、`git diff --numstat` 46/−55）；V1 的 5 个 `ToolSchema` 字面量改由 `source_specs("v1")` 循环构造（503 行、md5 `8b6844c70c32fd516d9ff4ef62b9693a`、47/−71），`_traced_call` 入口加闸门 |
| 行为保留 | 错误面与导出 | 六态 `success/no_data/denied/invalid_args/timeout/failed`、`ToolResult` 六字段、`audit()` 六键、V1 `{success,error,tool}` 三键全部逐字钉住；`to_openai_tools()` 与 `git show HEAD:` **逐字节相同**（`OPENAI_EXPORT_IDENTICAL=1`、`ORDER_SAME=True`、`OWNER_SAME=True`） |
| 统一审计 | `backend/app/services/tool_audit.py`（新增） | 14 个固定键、环形 500、`counts()`（total/granted/refused/by_status/by_decision/by_tool）；**每个结局各写一条**，拒绝也写；事件不收参数值（`query=` 传入即 `TypeError`），只存摘要哈希与异常类名；123 行、md5 `7cb62306d6677cbb980000240b5bab39` |
| 基线矩阵 | `matrix_dump_221.py` 从目录机械导出 | `logs/permission-matrix.txt`（`MATRIX_DUMP_OK=1`）；`matrix_violations()` 为空；测试内嵌 221 之前 `ROLE_TOOLS` 字面 dict 做等值比对 |
| 新用例 | `tests/a/test_tool_registry_permissions.py`（新增） | **18 条**、395 行、md5 `af49171bb284a43725e312b8571d8ef2`；含 4 角色 × 9 工具 = **36 对越权扫**（逐对核对结论、拒绝理由、`data is None`、`result_count=0`、执行面 `calls == []`）；单跑 **18 passed / 0.93 s** |
| 既有工具面 | 3 个既有文件 + 本卡新文件 | **32 passed / 1 skipped / 5.17 s**（前三个文件 14 项；唯一 skip = `mcp` 未装的 `importorskip`） |
| 学习包/运行时面 | 5 个文件 | **60 passed / 0 failed / 23.77 s** |
| **CI 同形子集（44 文件，未纳入本卡新文件）** | `ci.yml:217` 同形旗标 + `-rs` + 前置 `init_db()` | **521 passed / 1 skipped / 0 failed / 4 warnings / 147.78 s** —— 与 211c 记录**逐数相同**，即本卡对既有行为零改变；`ci.yml` 一字未动（md5 `3658e9f11738a4633e72551947994080`、快清单仍 44、`enterprise-contract` 仍 38，`CI_UNTOUCHED=1`） |
| 候选 45 文件清单（**仅证据，未采纳**） | 同形旗标 | **539 passed / 1 skipped / 0 failed / 4 warnings / 143.83 s**（= 521 + 18），顺序见 `logs/candidate-list.txt` |
| **全量（记录数）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + 全新 `--basetemp`） | **2410 passed / 0 failed / 20 skipped / 1067.30 s / 23 warnings**（2026-10-24 QWEN-221 最终字节复跑，Windows + Python 3.12.15；口径不变：`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 仓库默认 SQLite + 全新 `--basetemp output/qwen221-2026-10-24/pytest-measure-221-full-suite`，挂同一个 fail-closed socket 探针，探针 **`outbound attempts=0 unique_hosts=0`**，零计费模型调用、未读 `.env`、无用例因阻断转红，`PYTEST_EXIT=0` 记入日志）＝ **2430 项**（passed + skipped）/ 197 个测试文件 = 211c 的 2412 项 + 本卡新增 18 项；既有 3 个工具文件 14 项与 5 个学习包/运行时文件 60 项在本卡最终字节上全部照旧通过（`32 passed, 1 skipped in 5.17s`、`60 passed in 23.77s`） |
| 集合口径 | `--collect-only -q` | `--collect-only -q` 得 **2429** 个 node id，分布在 **196** 个文件（`2429 in 13.35s`）；node id 2429 + 收集期整文件跳过的 `test_mcp_readonly_protocol.py`（本机未装 `mcp` 的 `importorskip`）1 条 = **2430 项**，与全量 passed + skipped 逐数相同；因此全量那一轮实际触达 **197** 个文件（有 node id 的 196 + 那 1 个只贡献收集期 skip 的），与 211c 的 195 + 1 = 196 同口径 |
| 门 | ruff（`--select=F821,F823,E9`）+ `compileall` + 前置 `init_db()` + `git diff --check` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed!**（exit 0）、`compileall backend/app tests/` exit 0、CI 前置 `init_db()` INITDB_EXIT=0、`git diff --check` 干净 |
| 反向验证 | 11 组单层破坏（工作树内临时改、按字节恢复、断言 md5 相同） | **全部 `RED_OK`**：权限键层 5 failed / 两层一致的扩权 4 / 工具改名脱登记 5 / 未知角色层 2 / V1 闸门不看名字 1 / `extra=ignore` 2 / 拒绝不写审计 3 / 审计丢 attempted 名 4 / 截断回字面量 1 / MCP 改名 1 / OpenAI 导出丢 `required` 1；每组收集均为 `18 = failed + passed`，无 ImportError，探针 `attempts=0 unique_hosts=0` —— `logs/reverse-proofs.txt`（`ALL_PROOFS_VALID=1`） |
| 未跑 | GitHub `quality` 真实回执、PG 专项 38 文件 | 本卡零 CI/PG 面改动，同 §22/§23 口径 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用、零 `.env` 读取；GitHub 真实回执与 PG 侧结论不属本卡主张。**待裁定登记**（详见台账 §27.4）：`mcp_readonly.py:25` 固定 `role="planner"` 而 `search_course_evidence` 基线只给 `tutor`，MCP 侧该工具恒 `denied`（221 前后一致）；`agent_config_service.allowed_tools` 与 `contracts.RunPolicy.allowed_tools` 两处声明运行时不消费；统一审计仍是进程内环形缓冲，未持久化。

## 25. QWEN-221b MCP scope 角色回归 + 权限测试纳入 CI 快清单实测摘要（2026-10-24，分支 `qwen/wave2-tools`，零模型调用、产品角色零改动）

| 项 | 口径 | 结果 |
|---|---|---|
| 产品角色（**不改**） | `backend/app/mcp_readonly.py` | **一字未动**：70 行、md5 `6eea05e5fef4622ae314f9e1e1654e03`（= 221 交付值）；`_scope()` 固定 `role="planner"` 只服务 profile/mistakes/prereqs，`search_course_evidence` 自建 `tutor_scope` 调用 broker（`:56-64`）。Lead 2026-10-24 19:35 `[CORRECTION]` 已撤回“把全局 scope role 改成 tutor”，本卡按更正版只补测试钉住现状 |
| 新增断言 | `tests/a/test_tool_registry_permissions.py`（**扩展现有 MCP 用例，0 新增用例项**） | 静态半：`_scope()` 内 `ToolContext(role=...)` 字面量 = `planner`、`search_course_evidence` 内 = `tutor`、search 把 `tutor_scope` 交给 `broker.call(..., "search_course_evidence", ...)`、三个 planner 工具各 `_call("<自身工具名>", ...)`；动态半：`sys.modules` 注入假 `mcp`/`mcp.server`（保留 `mcp_readonly.py` 的 import 期依赖检查）后用录制 broker 跑全部 4 个工具，`(role, tool)` 序列 = `("tutor", "search_course_evidence")`、`("planner", "get_learning_profile")`、`("planner", "get_recent_mistakes")`、`("planner", "get_prerequisites")`，且 run/user/course 三个标识全程一致、`knowledge_point_id` 原样转发；另断言 `decide_access("tutor", "search_course_evidence").allowed is True` 而 `planner` 为 `False`（角色是承重墙，不是装饰） |
| 本机无 `mcp` | `tests/a/test_mcp_readonly_protocol.py` | 既有 `importorskip` 行为**保留**：模块仍整文件 skip（`could not import 'mcp'`），本卡未装依赖、未改该文件 |
| CI 清单 | `.github/workflows/ci.yml` `quality` job | **44 → 45 个文件**（新行 `:217`，旗标行顺延 `:218`）；`yaml.safe_load` 机械重取 45 条、0 缺失、无重复、末位即本卡文件；`enterprise-contract` 仍 **38**、MCP 协议独立步骤仍保留（`CI_LIST_OK=1`） |
| 门 | ruff + `git diff --check` + 前置 `init_db()` | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` → **All checks passed!**（exit 0）、`git diff --check` 干净、`init_db()` INITDB_EXIT=0 |
| 定向 | 4 文件（本卡文件 + `test_v2_learning_tools.py` + `test_agent_tools.py` + `test_mcp_readonly_protocol.py`） | **32 passed / 1 skipped / 2.67 s**（本卡文件单跑 **18 passed / 1.04 s**；唯一 skip = `test_mcp_readonly_protocol.py:11` 的 `mcp` `importorskip`） |
| **CI 同形子集（45 文件）** | `ci.yml:218` 同形旗标 `--no-cov --benchmark-disable -q -rs` + 前置 `init_db()` | **539 passed / 1 skipped / 0 failed / 4 warnings / 121.79 s**，`PYTEST_EXIT=0`；= 44 文件记录的 521 + 该文件既有 **18**，与 Lead 预计 **539/1** 逐数一致；唯一 skip 仍是 `test_auth_restart.py:18` —— `logs/ci45.txt`、`logs/portable-list.txt`、`logs/ci-list-inspect.txt` |
| **全量（记录数）** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 隔离 SQLite + 全新 `--basetemp output/qwen221b/base-full`） | **2410 passed / 0 failed / 20 skipped / 20 warnings / 893.78 s**，`PYTEST_EXIT=0`，197 个测试文件 / **2430 项**；与 221 记录的 2410/0/20 **逐项相同**（本卡 0 新增用例项、产品零改动）；**本轮未挂 fail-closed socket 探针**，故不主张探针 `attempts=0` 值（见台账 §28.5）—— `logs/full-suite.txt` |
| 集合 | `--collect-only -q` | **2429** 个 node id + 收集期 1 条 `test_mcp_readonly_protocol.py:11` 的 `mcp` `importorskip` = **2430 项**（14.90 s），与 221 同口径 —— `logs/collect-only.txt` |
| 反向验证 | 4 组单层破坏 `mcp_readonly.py`（工作树内临时改、每组后按字节恢复） | **全部 `RED_OK`**（每组 `1 failed / 17 passed`）：rp01 `_scope` planner→tutor / rp02 search tutor→planner / rp03 search 改把 base scope 交给 broker / rp04 planner 工具转发错名；恢复后 md5 = 原始 `6eea05e5fef4622ae314f9e1e1654e03`、`git diff -- backend/app/mcp_readonly.py` 为空（`ALL_PROOFS_VALID=1`）—— `logs/reverse-proofs.txt` |
| 未跑 | GitHub `quality` 真实回执、PG `enterprise-contract` 38 文件 | 本卡零 PG 面改动，同 §22–§24 口径 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none`）、未读 `.env`；GitHub 真实回执与 PG 侧结论不属本卡主张。本节关闭 §24 结尾登记的「`mcp_readonly.py` 固定 `planner` 而 search 只给 `tutor`」的待裁定项——结论是**现状无误**：search 本就用 `tutor_scope`，无需改产品，已由用例钉住。

## 26. QWEN-231 统一 Observation + 交付前规则版 claim-support 实测摘要（2026-10-24，分支 `qwen/wave2-observation`，零模型调用）

| 项 | 口径 | 结果 |
|---|---|---|
| Observation schema | `backend/app/agent_runtime/observation.py` | `Observation`：`node` / `status`（success/partial/failed/skipped）/ `error_class` / `retryable` / `evidence_strength`（0..1）/ `citation_support`（0..1）/ `detail`；`classify_failure()` 映射既有稳定错误码；`failure_observation()` 不写异常文本 |
| 观察接入 | `backend/app/agent_runtime/learning_package.py` | `_observed` 失败时发 `observation.recorded`、成功时把 `_observation_events` 并入 `delivery_observations`；`_tool` 的检索投影与 `claim_check` 的交付前校验共用同一 schema；既有 `observations` 搜索载荷、事件名、错误码、checkpoint 结构与交付包形状不变 |
| claim_check 节点 | `compose → claim_check → approval/verify` | 只读最终交付包与本次证据；`claim_support_checked` 保证每运行最多一次；无模型/工具调用、不增加预算；失败 fail-closed 用既有 `learning_package_invalid_citation` / `learning_package_quality_failed`，不新增重试 |
| 规则实现 | `backend/app/evaluation/claim_support.py` | `evaluate_rule_based_support()`：引用 ID 必须指向本次检索证据且内容非空；证据 ≥40 字符时用字符二元组重叠；支持率 <0.5 或任一缺失/非法引用即失败；短证据标为“未判定” |
| 新文件单跑 | `tests/a/test_observation_claim_support.py` | **10 passed / 0 failed / 7.16 s**，`PYTEST_EXIT=0` |
| 定向 5 文件 | 新文件 + `test_claim_support` + `test_learning_package` + `test_learning_package_replan` + `test_learning_package_partial` | **96 passed / 0 failed / 60.92 s**，`PYTEST_EXIT=0` |
| 相关面 | collection / evaluator / structured_output / ablation / lifecycle / retry_guidance / reconciliation | **150 passed / 0 failed / 38.77 s**，`PYTEST_EXIT=0` |
| **全量** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + `DATABASE_URL=sqlite:///./output/qwen231/full-clean.db`（先 `init_db()`）+ 全新 `--basetemp output/qwen231/base-full-clean2`） | **2424 passed / 0 failed / 20 skipped / 24 warnings / 1431.51 s (0:23:51)**，`PYTEST_EXIT=0`，198 个测试文件 / **2444 项** |
| 门 | `ruff check --select=F821,F823,E9 backend/app scripts/ tests/` + `git diff --check` | **RUFF_EXIT=0（All checks passed）；DIFFCHECK_EXIT=0**（仅 CRLF 归一化 warning） |
| 提示词 | `PROMPT_VERSION` | **未 bump**：仍 `learning-package-v2.9`；本卡没有新增模型可见固定文本（规则失败即停，不向模型追加 Reviewer 反馈）；行号因两行 import 由 `:23` 后移到 `:25`，文档已同步 |
| CI 清单 | `.github/workflows/ci.yml` | **未改**：快清单仍 45 文件；`test_claim_support.py` 规则用例 +4 → **543 passed / 1 skipped / 0 failed / 4 warnings / 288.83 s**，`CI45_EXIT=0`；新测试文件未纳入（沿用 201b/202b/211b/221b 的“CI 纳入另卡”先例） |
| 失败路径 | 支持不足 / 引用不足 / 失败即停 | 支持不足 → `learning_package_quality_failed`、`answer.delta` 不出现、`observation.recorded` 带 `error_class=claim_support`；引用不足 → `learning_package_invalid_citation`、`error_class=citation`；两者 `retryable=false`，且落 `agent_checkpoints` |
| 未跑 | GitHub `quality` 真实回执、PG `enterprise-contract` | 本卡零 PG 面改动，同 §22–§25 口径 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none`）、未读 `.env`；规则版是词面启发式，不证明语义蕴含，也不替代人工审核。**本轮未挂 fail-closed socket 探针**，故不主张 `attempts=0` 探针值。

## 27. QWEN-231b Observation 测试纳入 CI 快清单实测摘要（2026-10-24，分支 `qwen/wave2-observation`，零模型调用、产品与测试逻辑零改动）

| 项 | 口径 | 结果 |
|---|---|---|
| CI 清单 | `.github/workflows/ci.yml` `quality` job | **45 → 46 个文件**：在 `tests/a/test_tool_registry_permissions.py` 后加 `tests/a/test_observation_claim_support.py`（新行 `:218`，旗标行顺延 `:219`）；`enterprise-contract` 仍 **38**、MCP 协议独立步骤仍在 |
| 清单机械重取 | 脚本用 `yaml.safe_load` 读 `ci.yml` | **46** 条、无重复、0 缺失、末位即本卡文件（`output/qwen231b/logs/portable-list.txt`） |
| 门 | `git diff --check` | exit 0（仅 CRLF 归一化 warning） |
| **CI 同形子集（46 文件）** | `ci.yml:219` 同形旗标 `--no-cov --benchmark-disable -q -rs` + 前置 `init_db()`，`DATABASE_URL=sqlite:///./output/qwen231b/ci.db`（全新） | **553 passed / 1 skipped / 0 failed / 4 warnings / 281.02 s (0:04:41)**，`CI46_EXIT=0`；= 231 记录的 543/1 + 该文件既有 **10** 项，与 Lead 预计 **553/1** 逐数一致；唯一 skip 仍是 `test_auth_restart.py:18` —— `output/qwen231b/logs/ci46.txt`、`ci46-exit.txt` |
| 全量 | 未重跑 | 本卡 0 新增用例项、产品零改动，全量记录数仍为 231 的 **2424/0/20 / 2444 项**（§26） |
| 未跑 | GitHub `quality` 真实回执 | 本地同形复跑属 offline 证据，remote 回执由 Lead 判读 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用、未读 `.env`；本卡只改 CI/文档，未跑探针故不主张 `attempts=0` 探针值。

## 28. QWEN-301 Run 队列/Worker 实测摘要（2026-10-24，分支 `qwen/wave3-queue`，零模型调用、零迁移）

| 项 | 口径 | 结果 |
|---|---|---|
| 队列载体 | `agent_runs.status='queued'` + `metadata.queue` 簿记 | **零新增表/列**；行级原子 UPDATE 定胜者（`run_leases` 模式）；队列专属审计 `run.queued` / `run.claimed` / `run.cancelled` / `run.queue_exhausted` |
| 状态机 | `run_queue.py` | `queued→running→终态`；`queued/running→cancelled`；`running/interrupted` 租约过期→重领（attempts+1）；`attempts>2` 判 `failed("run_queue_attempts_exhausted")`（新增队列专属稳定码） |
| Worker | `run_worker.work_once/work_forever` | 与 `/stream` 同一图/运行时、同心跳（`run_leases.renew`）、同超时（60/180s）、同交付契约（`apply_settled_state`）；守卫 finish（fence + `status=='running'`，无 `run.reconciled` 污染）；不声称 exactly-once |
| API | `POST /enqueue`、`POST /{run_id}/cancel` | 创建返回 `run_id+queued`；取消仅限队列来源且 `queued/running`（409 `run_not_cancellable` / `run_not_queued`）；既有 `/stream`/GET/`resume`/`continue`/`reconcile` 一字未改 |
| 新文件单跑 | `tests/a/test_run_queue.py` | **15 passed / 0 failed / 19.88 s**，`NEW_FILE_EXIT=0` |
| 稳定性 | 同文件连续 3 轮 | **15 / 15 / 15 passed**（20.16 / 19.55 / 20.29 s） |
| 定向相关面 | 10 文件（run_leases/lifecycle/learning_runs_v2/reconciliation/learning_package/partial/observation/unfinished_resume/event_idempotency/checkpoint_lifecycle） | **137 passed / 0 failed / 84.79 s**，`RELATED_EXIT=0` |
| **CI 同形子集（46 文件，清单未改）** | `ci.yml` 同形旗标 + 前置 `init_db()` | **553 passed / 1 skipped / 0 failed / 4 warnings / 343.87 s**，`CI46_EXIT=0`；`test_run_queue.py` 未纳入（沿用“CI 纳入另卡”先例） |
| **全量** | `pytest tests/`（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none` + 全新 `sqlite:///./output/qwen301/full2.db`（先 `init_db()`）+ `--basetemp output/qwen301/base-full2`） | **2439 passed / 0 failed / 20 skipped / 21 warnings / 1434.35 s (0:23:54)**，`PYTEST_EXIT=0`，199 个测试文件 / **2459 项**；首跑有 1 个 `test_demo_journey` 30 s 墙钟贴边抖动（30.07 s，单跑复验 5 passed，见台账 §31.3） |
| 杀进程恢复 | `tests/helpers/run_queue_probe.py`（hang→kill→quick 两进程） | attempts 1→2、`run.claimed×2`、唯一 `run.completed`、API 可查询 |
| 门 | ruff + `git diff --check` | **RUFF_EXIT=0（All checks passed）；DIFFCHECK_EXIT=0** |
| 未跑 | GitHub `quality` 真实回执、PG `enterprise-contract` | 本卡零 PG 面改动；PG 行锁使序号重试按设计不触发 |

外推限制：全部为**本机 offline** 同形复跑，零计费模型调用（`A3_OFFLINE_DEMO=true LLM_PROVIDER=none`）、未读 `.env`、未装依赖；崩溃恢复为 **at-least-once**（重领重跑），不声称 exactly-once；`MAX_ATTEMPTS=2` 为基线常量待 Lead 裁定；未跑探针故不主张 `attempts=0` 探针值。
