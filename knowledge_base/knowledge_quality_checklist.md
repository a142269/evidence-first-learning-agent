# Knowledge Base Quality Checklist

> **范围**：`knowledge_base/artificial_intelligence/` + `knowledge_base/python_programming/`
> **目的**：锁住章节 / KP / 题库 / 配套资源的一致性，防止后续编辑引入"知识孤岛"
> **配套**：`scripts/check_kb_quality.py`（CI 钩子）

---

## 一、章节 frontmatter 必须满足

### 1.1 必备字段（缺失即 FAIL）

| 字段 | 类型 | 说明 |
|------|------|------|
| `chapter_id` | str | 两位零填充，必须等于文件名 `00~19` 前缀 |
| `slug` | str | 等于文件名去掉 `xx_` 前缀 |
| `title` | str | 人类可读标题 |
| `kp_ids` | list[str] | 至少 1 个 KP ID（来自 `knowledge_map.yaml`）|
| `bloom_focus` | list[str] | 子集 ∈ {Remember, Understand, Apply, Analyze, Evaluate, Create}，非空 |
| `prerequisites` | list[str] | 章节 ID 列表，必须是已存在的章节 |
| `estimated_minutes` | int | 20 ≤ x ≤ 120 |

### 1.2 推荐字段（缺失降级，标注 WARN）

| 字段 | 类型 | 说明 |
|------|------|------|
| `summary` | str | 一句话导览 ≤ 80 字 |
| `learning_outcomes` | list[str] | 至少 3 条可观测产出 |
| `code_refs` | list[str] | 关联到 `code_examples/*.py` 相对路径 |

---

## 二、KP 三方一致性（核心闭环）

```
knowledge_map.yaml  ─┐
                    ├─→ 知识图谱 (PathPlanner / Dual Graph)
chapter frontmatter ─┤
                    ├─→ 章节渲染 (Resources / KG 可视化)
data/question_bank  ─┘
                    └─→ 题库检索 (Practice / Quiz Generation)
```

### 2.1 必须满足（FAIL 即阻断 CI）

1. `knowledge_map.yaml` 中每个 KP 至少被 1 个章节 frontmatter 引用，**或**被显式标记为 `orphan_ok: true`（如 python_basics / data_structures 为基础学科，可豁免但需注释原因）
2. 每个章节 `question_kp_ids`（由 chapter→bank_kp 映射推导）必须在 `data/question_bank.json` 存在
3. `question_bank.json` 的 KP 集合 ⊆ `chapter→bank_kp` 映射的并集 ∪ 显式豁免集合
4. `question_bank.json` 的 KP 集合 ⊆ `knowledge_map.yaml` KP 集合（避免题库出现"图谱外"知识点）

### 2.2 推荐（违反仅 WARN）

- 每个 KP 至少有 1 章 + 至少 5 道题
- 章节→KP 映射为 1:N 时（多对多），确保 N ≤ 3，避免一对多导致学习路径混乱

---

## 三、配套资源覆盖

### 3.1 `code_examples/` 实操代码（覆盖率目标 ≥ 80%）

| 类型 | 必备示例数 | 验收标准 |
|------|-----------|---------|
| 监督学习入门 | ≥ 1（linear_regression） | 可 `python xxx.py` 直接跑、断言通过 |
| 决策树/集成 | ≥ 1（random_forest） | 同上 |
| 神经网络基础 | ≥ 1（mlp_mnist） | 同上 |
| CNN | ≥ 1（cnn_cifar10） | 同上 |
| RNN/LSTM | ≥ 1（rnn_text） | 同上 |
| Transformer | ≥ 1（transformer_toy） | 同上；至少跑通一次 demo |

每份代码必须包含：
- 文件级 docstring（说明对应 KP / 章节）
- `if __name__ == "__main__":` 入口
- 跑通断言（`assert` 或 doctest）

### 3.2 `references/` 扩展阅读（覆盖率目标 ≥ 50%）

| 章节 | 推荐数量 | 验收标准 |
|------|---------|---------|
| 机器学习基础 (04) | ≥ 1 | 中文摘要 ≥ 200 字、附原文链接 |
| 深度学习 (06) | ≥ 2 | 同上 |
| Transformer/大模型 (05) | ≥ 1 | 同上 |
| 多智能体 (06 多智能体章) | ≥ 1 | 同上 |

每篇摘要必须有 frontmatter：

```yaml
---
title: 论文原标题或资源原标题
authors: [...]    # 留空 = 非论文类
year: YYYY
url: https://...
kp_refs: [KP_ID]  # 至少 1
summary_zh: 一句话中文摘要
---
```

### 3.3 `exercises/` 章节练习 markdown（覆盖率目标 ≥ 30%）

| 章节 | 推荐数量 | 验收标准 |
|------|---------|---------|
| 04 机器学习基础 | ≥ 1 | 选择 + 简答 + 编程各 ≥ 2 |
| 06 神经网络与深度学习 | ≥ 1 | 同上 |
| 05 Transformer | ≥ 1 | 同上 |

每套练习必须有：
- frontmatter `chapter_ref`、`kp_refs`、`bloom_focus`
- 至少 1 道编程题
- 至少 1 道分析/评估级（≥ Analyze）开放题

---

## 四、题库覆盖度

### 4.1 当前基线（2026-07-04）

- 主库 `question_bank.json`：240 题 / 24 KP / 每 KP 10 题
- 增量 `question_bank_extra_0703.json`：高质量选择题（多智能体 / Agent / MCP / 多模态）
- 题型分布：multiple_choice / short_answer / open_ended

### 4.2 扩展目标（本次提交前完成）

| 类型 | 当前 | 目标 | 来源 |
|------|------|------|------|
| multiple_choice | 184 | ≥ 200 | 已有 + 0703 增量 |
| short_answer | 28 | ≥ 36 | 主库 + 增量 |
| open_ended | 28 | ≥ 36 | 主库 + 增量 |
| **fill_blank (新增)** | 0 | ≥ 24 | `data/question_bank_fill.json` |
| **programming (新增)** | 0 | ≥ 16 | `data/question_bank_programming.json` |
| **总计** | **240** | **≥ 312** | 合并加载后 |

### 4.3 验收

每种题型必须满足：
- KP 覆盖率 ≥ 80%（每个 KP 至少有 1 道）
- Bloom 分布：Remember ≥ 10%、Analyze+Evaluate+Create ≥ 30%

---

## 五、CI 钩子脚本

`scripts/check_kb_quality.py` 一键跑全部检查：

```bash
python -m scripts.check_kb_quality            # 全量
python -m scripts.check_kb_quality --strict   # WARN 也阻断
```

输出示例：

```
[PASS] 20 chapter frontmatter
[PASS] knowledge_map.yaml KP count = 27 (matches chapter frontmatter)
[PASS] question_bank KP union ⊆ chapter KP union
[PASS] code_examples present: 5/6 expected
[WARN] references coverage 50% (target 80%)
[FAIL] questions bank missing programming type — run scripts/expand_question_bank.py
```

任意 FAIL 退出码 1，阻断 commit。

---

## 六、维护节奏

| 时机 | 操作 |
|------|------|
| 新增章节 | frontmatter 补全 + KP 双向引用 + 加进 tests |
| 新增 KP | YAML + 至少 1 章引用 + 题库至少 5 题 |
| 新增题型 | 更新 `QuestionBank._ALLOWED_TYPES` + tests |
| 季度 | 重跑 `check_kb_quality.py --strict`，把 WARN 收敛到 0 |

---

> 最后更新：2026-07-04
> 关联：DELIVERY.md § P0-1、P0-2、P0-3
