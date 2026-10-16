# B 模块算法设计文档

> B 角色 · 教学算法层与学情评估流水线 · 2026-06-20

## 1. DINA 认知诊断模型 (Junker & Sijtsma 2001)

### 1.1 模型原理

DINA (Deterministic Input, Noisy "And" gate) 假设学生答对题目需要满足两个条件：
1. **掌握题目考查的所有知识点**（And gate: η = ∏ α_k^{q_{jk}}）
2. **未失误**（slip: s_j）

实际答对概率：

$$P(R_{ij}=1 | α_i, s_j, g_j) = (1-s_j)^{η_{ij}} · g_j^{1-η_{ij}}$$

其中 g_j 是猜测率（未掌握但猜对）。

### 1.2 EM 算法

- **E-step**: 当 K≤6 时精确枚举 2^K 种 α 组合；K>6 时使用**坐标上升 Mean-Field VI**
- **M-step**: 后验加权更新 slip = w_10/(w_11+w_10), guess = w_01/(w_01+w_00)
- **收敛**: ΔLL < 10^-4 或 max_iter=100

### 1.3 工程实现

```python
# backend/app/services/cognitive_diagnosis/dina.py (310 lines)
class DINA:
    def fit(responses, q_matrix, item_ids, kp_ids, student_ids) -> dict
    def _e_step_exact(R, Q, slip, guess, K)  # exact EM for K≤6
    def _e_step_mean_field(R, Q, slip, guess, alpha_prob)  # vectorized MF-VI for K>6
    def _m_step(R, Q, alpha_prob, slip, guess)  # weighted slip/guess update
```

**关键向量化**: log-space batch + np.where 替代四层 Python loop，1556 学生从 474s → 49s (10× 加速)。

### 1.4 ASSISTments-2009 验证

在 CMU 公开数据集上跑四模型对照（DINA/BKT/DKT/Naive），5-fold CV + 统一 next-step KT 协议。因数据集 skill_id 为单值字段（天然 Q 矩阵为 identity），采用 super-attribute 聚类（Liu et al. 2018）让 DINA 在 K=6 exact EM 下运行。

**BKT AUC=0.66** — 坐落在论文报告 0.65–0.75 范围，验证实现正确性。

> 完整数学推导见 `docs/algorithm/dina_derivation.md`

---

## 2. BKT 贝叶斯知识追踪 (Corbett & Anderson 1995)

### 2.1 模型原理

4 参数隐马尔可夫模型：

| 参数 | 含义 | 典型值 |
|------|------|--------|
| P(L₀) | 初始掌握概率 | 0.2 |
| P(T) | 学习转移概率 | 0.1 |
| P(S) | 失误率 (slip) | 0.1 |
| P(G) | 猜测率 (guess) | 0.2 |

**贝叶斯更新**（每次答题后）:
- P(L|correct) = P(L)(1-S) / [P(L)(1-S)+(1-P(L))G]
- P(L|wrong) = P(L)S / [P(L)S+(1-P(L))(1-G)]
- P(L') = P(L|obs) + (1-P(L|obs))·P(T)（学习转移）

### 2.2 BKT+ 个性化

`_personalized_transit()` 根据学生该知识点近 5 次答题正确率动态调整 P(T):
```
P(T)_{personalized} = P(T)_base × (0.7 + 0.6 × correct_rate)
```
答对率高的学生 → 更高的学习效率假设。

### 2.3 工程实现

```python
# backend/app/services/cognitive_diagnosis/bkt.py (180 lines)
class BKT:
    def update(student_id, kp_id, correct) -> float  # 增量贝叶斯更新
    def get_mastery(student_id, kp_id) -> float       # 当前 P(L)
    def get_all_masteries(student_id) -> dict          # 所有 KP P(L)
    def trend(student_id, kp_id) -> str                # improving/declining/stable
    def get_transit_rate(student_id, kp_id) -> float   # BKT+ personalized
```

**持久化**: 每 5 次 update `_maybe_persist()` → `state_repository.save_bkt_state()`. 重启恢复 via `load_all_from_db()`.

---

## 3. SM-2 间隔重复 (Wozniak 1990)

### 3.1 核心算法

| 输入 | 含义 |
|------|------|
| quality (0-5) | 学生自评回忆质量 |
| EF | 难度因子 (1.3-2.5) |
| interval | 下次复习间隔 (天) |
| repetitions | 连续正确次数 |

**更新规则**: quality<3 → 重置; quality≥3 → EF' = EF+(0.1-(5-q)(0.08+(5-q)0.02)) → 间隔 ×= EF → repetitions++

### 3.2 FSRS-4.5 对照

同时对 FSRS-4.5 (Ye 2023, Anki 23.10+ 默认) 做 benchmark:
- 17 参数三分量模型 (Stability/Difficulty/Retrievability)
- 论文数据表明比 SM-2 提升 ~30% 调度精准度
- 实现: `backend/app/services/spaced_repetition/fsrs.py`

---

## 4. GraphRAG 知识图谱

### 4.1 系统架构

**双通道构建** + **2-hop 检索** + **Leiden 社区聚类**

```
知识库 Markdown
    ↓
[正则通道: 标题/加粗/代码标签/书名号 → 实体 + prerequisite/part_of 推断]
    ↓
[LLM 通道(可选): 隐含实体 + analogous 关系]
    ↓
knowledge_points + kp_relations 表 (SQLite)
    ↓
[检索]: query → 实体匹配 → 2-hop BFS → graph_score + TF-IDF 融合 (0.6:0.4)
    ↓
[社区]: Leiden 聚类 → 社区摘要
```

### 4.2 关键模块

| 模块 | 文件 | 行数 | 核心能力 |
|------|------|------|---------|
| Store | `knowledge_graph/store.py` | 200 | KP/关系 CRUD + get_neighbors() + get_subgraph() BFS |
| Builder | `knowledge_graph/builder.py` | 250 | 双通道抽取实体 + 关系推断 |
| Retriever | `knowledge_graph/retriever.py` | 190 | 2-hop 子图 + hybrid score 融合 |
| Community | `knowledge_graph/community.py` | 150 | Leiden(igraph) → NetworkX greedy 降级 |

### 4.3 API 端点

- `GET /knowledge-graph/kps` — 知识列表
- `GET /knowledge-graph/search?q=&mode=hybrid` — GraphRAG 检索
- `GET /knowledge-graph/3d?user_id=&course=` — 3D 力导向图数据（含 mastery + Bloom 颜色）
- `GET /knowledge-graph/zoom?kp_id=&hops=2` — 子图详情

---

## 5. 学习时光机 BKT 预测 (Innovation #4)

### 5.1 数学模型

BKT 多步推演 + Beta CI + Kalman 平滑 + 反事实 + 目标倒推。

**日级状态转移**:
```
p_{t+1} = practice_rate × posterior_update(p_t, correct) + (1-practice_rate) × (p_t + (1-p_t)·P(T))
```

**90% 置信区间**: Beta(α=p·n_eff, β=(1-p)·n_eff) 的 90% 区间。

**Kalman Filter**: process noise=0.02, obs noise=0.05, 平滑历史观测后跑 BKT 预测。

**反事实分析**: 对比 4 种 daily_practice_rate (0.3/0.5/0.7/0.9) 下的 30 天预测曲线。

**目标倒推**: 二分搜索最小 practice_rate 使 30 天内达到目标 mastery。

### 5.2 实现位置

- `bkt_forecaster.py` — 核心预测器
- `kalman_smoother.py` — Kalman Filter 平滑
- `svg_visualization.py:mastery_forecast_svg()` — SVG 图表（实线=历史，虚线=预测，阴影=90%CI，里程碑标注）
- API: `GET /cognitive/forecast?user_id=&kp_id=&horizon_days=30`

> 完整设计文档见 `docs/algorithm/forecaster_design.md`

---

## 6. 学习者 Archetype 9 种类型

### 6.1 类型列表

| 类型代码 | 类型名称 | 昵称 | 策略 |
|---------|---------|------|------|
| high_achiever | 自驱引领者 | 笃行的探路人 | 挑战性项目 + 前沿论文 |
| effort_chaser | 努力的追赶者 | 勤恳的赶路人 | 结构化基础 + 增量练习 |
| rhythm_broken | 疲惫的夜行者 | 昼夜颠倒的孤勇者 | 灵活时间 + 碎片化学习 |
| habit_breakdown | 走神的旁观者 | 困在习惯漩涡里的人 | 习惯重建 + 小步激励 |
| introverted_explorer | 低调的独行者 | 追问本质的思考者 | 深度阅读 + 独立项目 |
| social_learner | 校园社交达人 | 以群为镜的同行者 | 小组讨论 + Peer tutoring |
| stable_average | 规律的常驻生 | 稳重的守望者 | 边际稳步提升 |
| exam_oriented | 应试专精型 | 只问结果的行动者 | 高频刷题 + 考点聚焦 |
| concept_explorer | 概念探索者 | 刨根问底的追问者 | 跨领域类比 + 元认知 |

### 6.2 聚类验证

用 K-means (k=9) + GMM (n_components=9) 在合成数据上验证: silhouete ≥ 0.25 表明 9 种类型在 8 维特征空间可分离。

> 实现: `learner_archetype_validation.py` + `validate_archetypes()`

---

## 7. 错题本 8 分类 (Innovation #5)

### 7.1 错因体系

| 类别 | 判定规则 |
|------|---------|
| 知识缺漏 | 空答案 / 与正确答案字符重叠度低 (< 40%) |
| 计算失误 | 数值偏差 5%-30% |
| 概念混淆 | 符号相反 / 字符重叠 40-75% |
| 阅读理解 | 回答过短 (< 正确答案 30% 长度) |
| 审题不清 | 回答中含反问 ("?" / "？") |
| 方法选择错 | 数值偏差 > 30% |
| 计算粗心 | 数值偏差 < 5% / 完全一致但被标注为错 |
| 概念边界混淆 | 字符重叠 > 75% 但不完全相同 |

### 7.2 变式题生成

按 Bloom 3 层（记忆→理解→应用）生成结构化变式题: `{question, answer, explanation, difficulty}`

### 7.3 实现位置

- `services/mistake_review.py` — 错因分类 + 变式生成
- `api/v1/mistakes.py` — `POST /{id}/analyze` + `POST /{id}/variants` + `GET /heatmap`
- SM-2 自动入队: `record_mistake()` → `get_sm2().add_to_review_queue()`

---

## 8. Peer Matching 协同过滤 (Innovation #6)

### 8.1 互补匹配算法

不找"相似"而是找"互补"——符合 Johnson & Johnson 合作学习理论。

**互补度**: `mutual = 2 × a_high × b_low / (a_high + b_low)` 调和均值（双向互利）

**混合权重**: 0.6 × 画像互补度 (content-based) + 0.4 × 学习行为协同 (CF — 共享 topic Jaccard)

**隐私**: 返回仅含 user_id + 互补维度 + 自然语言理由，原始画像分数永不外泄。

### 8.2 实现位置

- `services/social/peer_matching.py` — PeerMatcher class
- `services/social/recommendation_engine.py` — 高层封装 + 脱敏
- `api/v1/social.py` — `GET /peer-suggestions` + `GET /tutor-suggestions`

---

## 9. RAG 三级降级 (jicba + sklearn + keyword)

### 9.1 降级链

```
DB (SQLite knowledge_chunks+chunk_vectors) → jieba JSON (data/ads/rag/) → sklearn TfidfVectorizer → keyword overlap
```

- DB: 增量更新 + crash-safe (content_hash 比对), 仅重算变更块
- jieba: char-bigram + 持久化 TF-IDF JSON 索引，冷启动秒级
- sklearn: TfidfVectorizer(char_wb, 2-3 gram), 缺 jieba 时降级
- keyword: 中英 regex tokenize + 字符重叠（最终兜底）

### 9.2 实现位置

- `services/rag_service.py` — RAGService (415 lines)
- `services/rag/index_manager.py` — DB 持久化索引
- `alembic/versions/20260620_0002_rag_index_persistence.py` — 迁移

---

## 10. 状态持久化体系

| 算法 | 持久化位置 | 容错 |
|------|----------|------|
| SM-2 | `sm2_schedule` 表 | `state_repository.load_sm2_state()` |
| BKT | `bkt_states` 表 (JSON 历史) | `state_repository.load_all_bkt()` |
| DINA | `dina_states` 表 | `state_repository.save_dina_state()` |
| RAG | `knowledge_chunks` + `chunk_vectors` | content_hash 增量去重 |

---

## 11. 基础设施

| 组件 | 文件 | 能力 |
|------|------|------|
| Alembic | `alembic/` (2 migrations) | 12+2 表 DDL + upgrade/downgrade |
| Prometheus | `core/metrics.py` | 14 指标 (Counter/Histogram), `GET /metrics` |
| Telemetry | `core/telemetry.py` | Timer/Counter/Gauge/Histogram, `GET /metrics/llm-cost` |
| Backup/Restore | `scripts/backup_database.py` + `restore_database.py` | sqlite3.backup + PRAGMA integrity_check + 安全确认 |

---

## 附录: 算法 vs 论文对照

| 算法 | 论文出处 | 实现文件 | 数据集验证 |
|------|---------|---------|----------|
| DINA | Junker & Sijtsma 2001 | `dina.py` (310 lines) | ASSISTments-2009 |
| BKT | Corbett & Anderson 1995 | `bkt.py` (180 lines) | ASSISTments-2009 |
| BKT+ | Yudelson 2013 | `bkt.py:_personalized_transit()` | — |
| SM-2 | Wozniak 1990 | `sm2.py` (193 lines) | — |
| FSRS-4.5 | Ye 2023 | `fsrs.py` | — |
| DKT | Piech et al. NIPS 2015 | `dkt.py` (248 lines) | ASSISTments-2009 |
| Thompson Sampling | Thompson 1933 | `path_planner.py` | — |
| ZPD | Vygotsky 1978 | `path_planner.py:_compute_zpd_bandit()` | — |
| Bloom 6×3 | Anderson & Krathwohl 2001 | `bloom_taxonomy.py` | — |
| GraphRAG | Microsoft 2024 | `knowledge_graph/retriever.py` | — |
| Leiden Community | Traag 2019 | `knowledge_graph/community.py` | — |
| Collaborative Filtering | Burke 2002 | `social/peer_matching.py` | — |
| Cooperative Learning | Johnson & Johnson 1999 | `social/peer_matching.py` | — |
