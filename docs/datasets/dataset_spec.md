# 数据集说明文档

> B 角色 · 2026-06-20

## 1. 知识库结构

### 1.1 课程覆盖

```
knowledge_base/
├── artificial_intelligence/     ← A 维护
│   ├── 人工智能导论.md
│   ├── 实验指导.md
│   └── chapters/
│       ├── 03_neural_network_basics.md
│       ├── 04_cnn_and_vision.md
│       ├── 05_transformer_and_llm.md
│       └── 06_multi_agent_systems.md
└── python_programming/          ← B 维护
    ├── Python程序设计.md
    ├── 01_python_basics.md       (变量/控制流/函数)
    ├── 02_data_structures.md      (列表/字典/集合/collections)
    ├── 03_oop.md                  (类/继承/魔术方法/上下文管理器)
    └── 04_file_io_exceptions.md   (文件读写/Json/CSV/异常处理)
```

### 1.2 统计

| 课程 | 章节数 | 每章字数 | 含练习 | Bloom 标注 |
|------|--------|---------|--------|-----------|
| AI (A 维护) | 10 章 | 1500-3000 | ✅ | ⏳ 待标 |
| Python (B 维护) | 4 章 | 1800-2500 | ✅ | ✅ |

### 1.3 RAG 索引

- 114 个知识块 (chunk) 按 Markdown `##`/`###` + 1200 字硬切
- 三级降级后端: DB(SQLite) > jieba JSON > sklearn > keyword
- 每块含 title_hint, source, course 元数据
- content_hash (SHA256 前 16 位) 增量更新

---

## 2. 题库结构

### 2.1 `data/quiz_bank.json`

| 维度 | 统计 |
|------|------|
| 题目总数 | 200 |
| 题型 | 选择(choice) / 填空(fill_blank) / 简答(short_answer) / 编程(programming) / 推理(reasoning) |
| 覆盖章节 | 20 章 |
| Bloom 层级 | remember / understand / apply / analyze / evaluate / create |
| 每章题目 | 8-12 题 |

### 2.2 字段说明

```json
{
  "id": "q001",
  "type": "choice|fill_blank|short_answer|programming|reasoning",
  "chapter": "所属章节",
  "bloom_level": "remember|understand|apply|analyze|evaluate|create",
  "kp_id": "对应知识点 ID",
  "question": "题目文本",
  "options": ["仅 choice 类型有"],
  "answer": "正确答案",
  "explanation": "解析说明"
}
```

### 2.3 章节覆盖

| # | 章节 | 题数 | KP ID |
|---|------|------|-------|
| 1 | 机器学习基础 | 10 | kp_ml_basics |
| 2 | 神经网络基础 | 10 | kp_neural_networks |
| 3 | CNN 与计算机视觉 | 10 | kp_cnn |
| 4 | RNN 与序列模型 | 6 | kp_rnn |
| 5 | Transformer 与大语言模型 | 9 | kp_transformer |
| 6 | RAG 检索增强生成 | 5 | kp_rag |
| 7 | 多智能体系统 | 6 | kp_multi_agent |
| 8 | 强化学习 | 4 | kp_rl |
| 9 | Python 数据科学 | 4 | kp_python_data |
| 10 | 模型评估与调优 | 6 | kp_model_eval |
| 11 | 正则化与优化 | 5 | kp_regularization |
| 12 | 计算机视觉进阶 | 5 | kp_cv_advanced |
| 13 | NLP 自然语言处理 | 5 | kp_nlp |
| 14 | 推荐系统 | 5 | kp_recommend |
| 15 | 图神经网络 | 4 | kp_gnn |
| 16 | 模型部署与 MLOps | 5 | kp_mlops |
| 17 | Python 程序设计 | 5 | kp_python_prog |
| 18 | AI 安全与伦理 | 5 | kp_ai_ethics |
| 19 | 综合能力 | 2 | kp_synthesis |
| 20 | 其他专题 | 88 | kp_* |

---

## 3. 知识图谱数据

### 3.1 数据模型

**表结构** (SQLite):
- `knowledge_points`: id (PK), name, course, description, bloom_level, metadata (JSON)
- `kp_relations`: source_id (FK→KP), target_id (FK→KP), relation_type, weight

### 3.2 关系类型

| 类型 | 含义 | 示例 |
|------|------|------|
| prerequisite | 前置依赖 | Python基础 → 机器学习 |
| part_of | 组成部分 | CNN → 深度学习 |
| analogous | 类比/相似 | LSTM ↔ GRU |

### 3.3 构建方式

1. 正则通道: 从 Markdown 标题/加粗/代码标签/书名号提取实体，从"前提""依赖"等关键词推断关系
2. LLM 通道 (可选): 抽取隐含实体 + analogous 类比关系

### 3.4 规模

- 当前: ~80 知识点 + ~120 关系边
- 目标 (v7 Day 4): ≥ 100 节点 + ≥ 300 边

---

## 4. ASSISTments-2009 基准数据集

### 4.1 数据源

- 名称: ASSISTments 2009-2010 "skill builder" data (corrected version)
- 来源: USTC EduData mirror → `http://base.ustc.edu.cn/data/ASSISTment/2009_skill_builder_data_corrected.zip`
- 许可: 学术研究用途（CMU 开放）

### 4.2 原始统计

| 维度 | 数值 |
|------|------|
| 原始交互 | 401,756 |
| 学生数 | 4,217 |
| 知识点 (skills) | 123 |
| NaN skill_id | 63,755 (过滤) |

### 4.3 预处理

- 过滤: min_interactions=5, min_skill_freq=50
- 过滤后: ~3,000 学生 / ~100 skills
- 评估: 5-fold CV，按学生划分防止数据泄漏

### 4.4 本地缓存

```
data/benchmarks/
├── skill_builder_data_corrected.csv (63 MB)
└── assist2009.zip (9 MB)
```

---

## 5. 演示种子数据

### 5.1 `data/seed.json`

| 学生 | 画像 | 路径 | 评估 |
|------|------|------|------|
| demo-student-1 (小明) | 8 维完整 (中级/视觉/项目驱动) | AI 工程师 6 阶段 | 2 条 quiz 记录 |
| demo-student-2 (小红) | 8 维 (初级/听觉/视频) | 考研 408 4 阶段 | 2 条记录 |
| demo-student-3 (小刚) | 8 维 (高级/动手/论文) | 多智能体研究 5 阶段 | 2 条记录 |

### 5.2 `scripts/seed_b_extended.py`

幂等补充 B 域演示数据:
- 错题本: 5 学生 × 4-6 条 × 8 类错因
- 游戏化: 5 学生差异化 XP/level/streak/achievements
- BKT 历史: 每 KP 补 20 个历史点（让预测曲线有真实形状）

---

## 6. 开源协议合规

| 依赖 | 版本 | 协议 | 用途 |
|------|------|------|------|
| numpy | 1.25+ | BSD-3 | 矩阵运算 |
| scipy | 1.10+ | BSD-3 | 统计分布 |
| SQLAlchemy | 2.0+ | MIT | ORM |
| FastAPI | 0.110+ | MIT | Web 框架 |
| scikit-learn | 1.3+ | BSD-3 | CV/metrics |
| jieba | 0.42+ | MIT | 中文分词 |
| PyTorch | 2.0+ | BSD | DKT |
| igraph | 1.6+ | GPL-2 | Leiden 聚类 |
| Alembic | 1.12+ | MIT | 数据库迁移 |
| pytest | 8.0+ | MIT | 测试 |
