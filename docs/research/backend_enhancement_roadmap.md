# A3 Backend Enhancement Roadmap (Paper-Backed Innovations)

> Author: developer A
> Status: planning doc (Phase 4)
> Scope: backend only (chat / agents / cognitive diagnosis / KG / multimodal / spaced repetition)
> Constraint: each item must have a published reference + concrete API contract + measurable success metric.

---

## 0. Executive summary

After Day 1-10 the system already ships:

* 7-stage chat pipeline + telemetry
* 4-axis Critic + Multi-Agent Debate v3
* Manim DSL / PPTX 7-layout / Mermaid 3-tier / Code Sandbox 3-tier / TTS 8-voice
* DINA + RealDINA AUC 0.80 + DKT AUC 0.91 on ASSISTments-2009
* 20 chapters + 200-question bank + 100-node KG
* CI (ruff + mypy strict on curated set + alembic smoke + pytest)
* 1020+ tests, 285 adversarial-input cases

The next-generation upgrades below target **publishable-grade** innovations
(AIED / EDM / NeurIPS workshop quality). Each follows the same template:

```
H{idx}. {Title}                                         {Paper, Conference, Year}
  Current      : {what we already have}
  Upgrade idea : {concrete delta}
  API surface  : {how chat pipeline / agents consume it}
  Success metric: {numeric target}
  Effort        : {S / M / L / XL}
  Risk          : {what could go wrong}
```

Effort scale (full-time A days, conservative): S = 1-2, M = 3-5, L = 6-10, XL = >10.
Items are independent unless an arrow `→` makes a dependency explicit.

---

## A. Reasoning & Agent quality

### H1. Self-Refine for resource generation                    Madaan et al., NeurIPS 2023
* **Current**: Reflection v1 — single critique pass after generation.
* **Upgrade**: implement the canonical Self-Refine loop: generate → self-critique
  → revise → repeat until a per-axis acceptance threshold is met OR a
  hard max-iter (3-5) is hit. Track AUC of "iteration N quality > iteration N-1".
* **API**: `services/reflection/self_refine.py::iterate(payload, max_iter=5)`.
* **Metric**: hallucination rate (CoV-Edu axis) drops from current 8% to <3%.
* **Effort**: M.
* **Risk**: token budget × iteration; mitigate with early-stopping on critic
  delta < 0.05.

### H2. Tree-of-Thoughts for path planning                     Yao et al., NeurIPS 2023
* **Current**: linear orchestrator picks an agent chain by intent.
* **Upgrade**: explore branching reasoning when the user is stuck. Build a
  k-ary tree with breadth-first expansion, score nodes via Critic, prune
  beam to top-2. Use ToT only when intent classifier flags "complex".
* **API**: `services/planner/tot_planner.py::plan(query, beam=3, depth=3)`.
* **Metric**: on multi-step QA benchmarks, accuracy +5-10 points over CoT.
* **Effort**: L.
* **Risk**: latency × branch factor; cap depth=3, beam=3.

### H3. Reflexion-style episodic memory                         Shinn et al., NeurIPS 2023
* **Current**: agents do not remember failed strategies across sessions.
* **Upgrade**: every Critic-rejected draft writes a `reflexion` entry to
  `data/reflexion_memory.jsonl` keyed by (intent, agent, failure mode). On
  next similar query, prepend the relevant lesson to the system prompt.
* **API**: `services/reflection/reflexion_store.py`.
* **Metric**: same-failure recurrence rate halves after 1000 queries.
* **Effort**: M.

### H4. Constitutional AI safety loop                           Bai et al., Anthropic 2022
* **Current**: 4-axis Critic includes a "safety" axis but no revise loop.
* **Upgrade**: add a constitutional revise step — when safety < threshold,
  ask the same agent to revise against a 9-rule "constitution" (academic
  integrity, age-appropriate, factual, etc.). Store the constitution as
  versioned YAML.
* **API**: `services/safety/constitutional.py`.
* **Metric**: 0 leakage of system prompts in 10k adversarial probes.
* **Effort**: M.

### H5. DSPy-style prompt program with auto-optimization        Khattab et al., 2024
* **Current**: prompts are hardcoded f-strings scattered through agents.
* **Upgrade**: declarative `Signature` + `Module` registry; use bootstrap
  few-shot or MIPRO to optimize prompts against a labeled dev set (~200
  examples from past chat logs).
* **API**: `services/prompt_lab/` package with versioned modules.
* **Metric**: human-rated output quality +0.5 (5-point Likert) on dev set.
* **Effort**: L → enables H6 below.

### H6. Society of Minds debate with reviewer pool              Du et al., 2023 (extension)
* **Current**: 3-expert debate + 1 critic.
* **Upgrade**: 5-expert pool with distinct personas (factual / pedagogical /
  empathetic / Socratic / contrarian); reviewer chosen per round; voting
  uses Borda count instead of single Critic.
* **API**: `services/debate/society_of_minds.py`.
* **Metric**: debate convergence rounds drop from current 3.2 avg to <2.5
  with same Critic score.
* **Effort**: L; depends on H5 for clean persona prompt management.

---

## B. Cognitive diagnosis & knowledge tracing

### H7. HO-DINA (Higher-Order DINA)                              Templin & Henson, EM 2006
* **Current**: standard DINA, item × skill independence.
* **Upgrade**: introduce a continuous latent ability θ that *generates* the
  binary skill mastery vector α via an IRT-like link. Lets us share
  statistical strength across skills for sparse learners.
* **API**: replace `cognitive_diagnosis/dina.py` interior; preserve adapter
  signature.
* **Metric**: ASSISTments-2009 AUC moves from 0.6962 (dina_b) to 0.75+;
  fits in 30s/fold.
* **Effort**: L; touches B-owned code → joint task.

### H8. SAKT / SAINT — Attention-based KT                       Pandey 2019; Choi 2020
* **Current**: BKT + DKT (LSTM).
* **Upgrade**: implement self-attentive KT (SAKT) — each next-step
  prediction attends over the student's full history. Replaces DKT in
  research/models/. Adds positional encoding + relation embeddings between
  exercise pairs.
* **Metric**: ASSISTments-2009 AUC moves from DKT's 0.91 to 0.93+;
  ASSISTments-2017 AUC reaches 0.83+.
* **Effort**: L; uses torch.nn.MultiheadAttention.

### H9. 3PL IRT (Three-Parameter Logistic) wrapper                Birnbaum 1968
* **Current**: DINA's per-item slip/guess.
* **Upgrade**: refit slip + guess + discrimination per item as a 3PL model
  using EM on the full responses table; expose as a side channel on top of
  DINA for items where 3PL fits better (BIC < DINA-BIC).
* **API**: `cognitive_diagnosis/irt_3pl.py` parallel adapter.
* **Metric**: AUC + RMSE both improve on the top-30% most-answered items.
* **Effort**: M.

### H10. Active Learning loop for item difficulty calibration   Settles 2009
* **Current**: difficulty hand-labeled in `data/question_bank.json`.
* **Upgrade**: route the next assessment item by uncertainty sampling -
  show students items where the system's current posterior is closest to
  0.5 (highest information gain).
* **API**: `services/active_learning/uncertainty_sampler.py`.
* **Metric**: number of items to reach 95% confidence on a skill mastery
  reduces by 40%.
* **Effort**: M.

---

## C. Spaced repetition

### H11. FSRS-5 with stochastic gradient online update          Ye 2024 (FSRS Open Spaced)
* **Current**: SM-2 fixed parameters; FSRS module exists but offline-trained.
* **Upgrade**: implement FSRS-5 with per-student online parameter updates
  via stochastic gradient. Maintain a personal copy of the 17 weights per
  user, updated after every review.
* **API**: extend `spaced_repetition/fsrs.py` with `online_update()`.
* **Metric**: retention at 30-day horizon improves from current SM-2 baseline
  by 8-15% on the same review effort.
* **Effort**: M.

### H12. Half-Life Regression (HLR)                              Settles & Meeder, ACL 2016
* **Current**: SM-2 / FSRS.
* **Upgrade**: implement HLR as a third scheduler; compare empirically.
* **Metric**: A/B test on 100 students × 2 weeks; primary metric =
  recall@retention.
* **Effort**: M.

---

## D. Retrieval & Knowledge

### H13. GraphRAG complete pipeline                              Edge et al., Microsoft 2024
* **Current**: 2-hop neighbour expansion; community module exists.
* **Upgrade**: complete the Microsoft GraphRAG flow — Leiden community
  detection → LLM-summarized community reports → query-time retrieval
  picks summary level dynamically (local vs global).
* **API**: extend `services/knowledge_graph/community.py` +
  `services/rag/graphrag_pipeline.py`.
* **Metric**: long-form QA (summarize a topic) — recall@5 goes from current
  0.62 to 0.80+.
* **Effort**: L (touches both A and B sides).

### H14. RAG-Fusion with reciprocal rank                         Raudaschl 2023
* **Current**: hybrid retrieval (BM25 + dense).
* **Upgrade**: generate 4 query variants → retrieve from each → fuse with
  Reciprocal Rank Fusion (RRF). Surfaces queries with rare but precise
  vocabulary.
* **API**: `services/rag/rag_fusion.py`.
* **Metric**: NDCG@10 +0.04-0.07 on internal eval set.
* **Effort**: S.

### H15. HyDE — Hypothetical Document Embeddings                Gao et al., ACL 2023
* **Current**: query text → embedding → search.
* **Upgrade**: ask LLM to draft a hypothetical answer → embed that →
  search. Bridges question/document vocabulary gap.
* **API**: `services/rag/hyde.py`.
* **Metric**: recall@5 +0.03-0.05 for cold-start queries.
* **Effort**: S.

---

## E. Pedagogy & path planning

### H16. ZPD-aware Contextual Bandit path planner               Li et al., LinUCB; Auer 2002
* **Current**: heuristic difficulty matching.
* **Upgrade**: LinUCB on per-(student, skill) reward = engagement × mastery
  gain. Context features = current mastery, time-of-day, recent fatigue.
* **API**: `services/planner/linucb_planner.py`.
* **Metric**: per-session mastery improvement +20% over heuristic baseline.
* **Effort**: M.

### H17. PPO-based curriculum sequencer                          Schulman et al., 2017
* **Current**: not implemented.
* **Upgrade**: train a small PPO policy on logged student trajectories;
  reward = long-term mastery + engagement minus item cost. Stable-Baselines3.
* **API**: `services/planner/ppo_sequencer.py`.
* **Metric**: 7-day mastery improvement over LinUCB.
* **Effort**: XL; offline training required.

### H18. Cognitive Load Theory aware resource selector          Sweller, 1988
* **Current**: 5 resource types selected by intent classifier.
* **Upgrade**: model intrinsic + extraneous + germane load; pick resource
  type to keep total < threshold given student's working memory capacity
  (derived from interaction history).
* **API**: `services/pedagogy/cognitive_load.py`.
* **Metric**: reduces dropout rate in a study by 15%.
* **Effort**: M.

### H19. Bloom 6×3 sub-level grading + auto-generation          Anderson & Krathwohl 2001
* **Current**: 6 Bloom levels (basic).
* **Upgrade**: expand to 6 × 3 = 18 sub-levels (Cognitive Process × Knowledge
  dimension). Re-tag the 200 questions automatically by a fine-tuned
  classifier; add a constraint solver that picks a balanced set per
  practice session.
* **API**: `services/cognitive_diagnosis/bloom_6x3.py`.
* **Metric**: inter-rater agreement (vs human teacher) Cohen's kappa > 0.7.
* **Effort**: M.

---

## F. Safety, calibration, observability

### H20. CoV-Edu extended axes                                   our work + Dhuliawala 2023
* **Current**: 5-axis verification (claim → evidence → contradiction).
* **Upgrade**: add 2 axes: (a) age-appropriateness, (b) curriculum-alignment
  to the official PRC course standards (loaded as YAML).
* **API**: `agents/cov_verifier.py::verify(claim, axes=...)`.
* **Metric**: parental approval rating in user study > 4.5/5.
* **Effort**: S.

### H21. Platt + Isotonic dual calibration                       Niculescu-Mizil & Caruana 2005
* **Current**: Platt scaling (Day 7).
* **Upgrade**: also fit isotonic regression on the held-out probabilities;
  pick whichever has lower Brier score on a separate validation slice.
  Already wired into `CalibratedAdapter`; add the isotonic branch.
* **Metric**: Brier score -0.01 on ASSISTments.
* **Effort**: S.

### H22. Per-stage cost / latency Prometheus dashboards
* **Current**: chat telemetry exposes 7-stage times.
* **Upgrade**: add Histogram for LLM tokens / latency per stage, surface
  in Grafana via the existing `/metrics` endpoint. Alert when P99 > SLO.
* **API**: `core/metrics.py` (B-owned) — extend with token Histograms.
* **Metric**: ops team can reproduce demo behaviour from dashboard alone.
* **Effort**: S.

---

## G. Multimodal & content

### H23. PPTX SVG embedding (carry-over Day 12)
* **Current**: 7 PPTX layouts + Mermaid PNG; no native SVG.
* **Upgrade**: extend `PPTXBuilder` to accept SVG (e.g., from B's
  svg_visualization) and embed via `add_picture` after SVG→EMF conversion
  (or `python-pptx-svg` if available).
* **Metric**: support 100% of B's existing SVG figures.
* **Effort**: S.

### H24. Manim DSL expansion + asset library
* **Current**: 5-template DSL + 20 pre-rendered videos.
* **Upgrade**: 15 templates (added: sliding window, beam search,
  back-propagation, convolution, attention head, RNN unroll, ...);
  pre-render 60 clips.
* **API**: `services/multimodal/manim/templates.py`.
* **Metric**: 95% of chapter-level concepts have a canned animation.
* **Effort**: L (content-heavy).

### H25. Textbook OCR multi-modal QA upgrade                     GPT-4o vision / Qwen-VL
* **Current**: text-only OCR + LLM QA.
* **Upgrade**: replace single-page OCR with a vision-LLM that accepts an
  uploaded photo + free-form question. Auto-write the parsed equations
  back to KG.
* **API**: `agents/textbook_qa_agent.py` extension.
* **Metric**: equation extraction accuracy 95% on math textbook pages.
* **Effort**: M; depends on Spark Vision API access.

---

## H. Engineering infrastructure

### H26. LLM token cost dashboard + budget alerts
* **Current**: cost endpoint exists (B's Day 2).
* **Upgrade**: per-user / per-feature / per-day cost rollup; alert if any
  user exceeds threshold; cache hit-rate observability.
* **Effort**: S.

### H27. PromptCache + semantic retry
* **Current**: no LLM-call cache.
* **Upgrade**: cache key = SHA-1(prompt + model + temperature=0); semantic
  retry: on transient failure, re-run with adjusted temperature.
* **API**: `core/llm_cache.py`.
* **Metric**: 30% LLM call cost reduction in demo workloads.
* **Effort**: S.

### H28. Sandbox hardening — DoS defense
* **Current**: AST → RestrictedPython → Subprocess; AST mode lacks resource
  caps (Day 9 xfail).
* **Upgrade**: wrap AST mode execution in a `resource.setrlimit` (CPU + AS)
  on Linux; use Job objects on Windows.
* **Metric**: tests/regression/test_sandbox_resilience xfailed → passing.
* **Effort**: M.

### H29. End-to-end performance regression suite
* **Current**: per-component benchmarks.
* **Upgrade**: scripted full demo journey (login → 5 resources → assess);
  collect P50 / P95 / P99 latency + token cost; CI fail if regression > 15%.
* **Metric**: regression caught in CI within 1 hour of merge.
* **Effort**: M.

### H30. Multi-tenant + RLS isolation                            v6 P4 stretch
* **Current**: single-user demo.
* **Upgrade**: SQLAlchemy session-scoped row-level security; per-user data
  isolation in seed + tests.
* **Metric**: no data leak across 1000 simulated parallel users.
* **Effort**: L.

---

## Recommended Phase ordering

1. **Quick wins (S, 1-2 weeks total)**: H14 (RAG-Fusion), H15 (HyDE),
   H20 (CoV axes), H21 (isotonic), H22 (dashboards), H23 (SVG embed),
   H26 (cost dashboard), H27 (LLM cache).
2. **Core upgrades (M, 4-6 weeks total)**: H1 (Self-Refine), H3 (Reflexion),
   H4 (Constitutional), H9 (3PL), H10 (Active learning), H11 (FSRS-5),
   H16 (LinUCB), H18 (CLT), H19 (Bloom 6×3), H25 (vision OCR),
   H28 (sandbox), H29 (regression).
3. **Algorithm research (L, 8-12 weeks total)**: H2 (ToT), H5 (DSPy),
   H6 (Society of Minds), H7 (HO-DINA), H8 (SAKT), H13 (GraphRAG complete),
   H24 (Manim templates), H30 (multi-tenant).
4. **Experimental (XL, write-up only)**: H17 (PPO sequencer).

Total enhanced surface area: 30 distinct papers / techniques wired into
the existing stack. Even doing Phase-1 alone (8 quick wins) takes the
system past the v7 acceptance ceiling and into AIED-2027 paper territory.

---

## Tracking

Every adopted item gets:
* an entry in `docs/research/` with the same template
* a feature flag in `backend/app/core/config.py`
* one or more benchmarks under `tests/benchmarks/`
* one or more adversarial tests under `tests/regression/`

A's continued role: build, test, and document. B's continued role:
authenticate the algorithmic core, ship the algorithm modules under
`services/cognitive_diagnosis/` and `services/knowledge_graph/`.

End of roadmap.
