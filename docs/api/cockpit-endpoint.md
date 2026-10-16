# Cockpit 聚合端点字段契约

> 路径：`GET /api/v1/cockpit/student/{user_id}`
> 文档版本：2026-06-24
> 冻结日期：2026-06-30（冻结前如需改字段必须 A+B 双方同意）
> 用途：前端 CockpitView 一次调用拿齐聚合数据

## 1. 设计目标

- 一次请求返回 cockpit 需要的主要面板数据，避免前端拆成多个零散调用。
- 保留 A 侧 `safety` / `ledger` 聚合能力。
- 保留 B 侧 `learning_goals` 映射、KG/forecast 修正、demo seed 回退。
- 任一子块失败时，整体仍返回 `200`，失败信息放在对应字段的 `error` 内。

## 2. Query 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `horizon_days` | int 1-90 | 7 | forecast 预测天数 |
| `focus_kp` | string | `""` | 可选：指定关注的知识点 |
| `sample_response` | string | 引导式示例句 | `safety` 评估用 tutor 响应样本 |
| `sample_text` | string | CNN 示例句 | `ledger` 证据链评估用文本样本 |

## 3. 顶层响应

```json
{
  "user_id": "demo-student-1",
  "generated_at": "2026-06-24T12:00:00+00:00",
  "profile": {...},
  "kg": {...},
  "forecast": {...},
  "attribution": {...},
  "cov": {...},
  "debate": {...},
  "safety": {...},
  "ledger": {...}
}
```

## 4. 字段说明

### 4.1 `profile`

```json
{
  "dimensions": {
    "knowledge_base": {"level": "中级", "score": 0.72},
    "cognitive_style": {"primary": "视觉型"},
    "learning_preference": {"mode": "项目驱动"},
    "weak_points": {"topics": ["RNN", "注意力机制"]},
    "learning_goal": {"target": "AI工程师就业"},
    "learning_goals": ["AI工程师就业"],
    "self_efficacy": {"confidence": 0.75}
  },
  "radar_6d": [0.72, 0.7, 0.7, 0.7, 0.7, 0.75],
  "radar_labels": ["知识基础", "认知风格", "学习偏好", "薄弱环节", "学习目标", "自我效能"],
  "completeness": 75.0
}
```

- `dimensions` 以仓库当前画像为主，并额外暴露稳定字段 `learning_goals`
- 内部 `learning_goal` 在 cockpit 对外统一映射为 `learning_goals`
- `radar_6d` 长度恒为 6，可直接喂雷达图
- `completeness` 为 8 维画像填充率（0-100）

### 4.2 `kg`

```json
{
  "current_kp": "CNN",
  "current_kp_meta": {"id": "kp-cnn", "name": "CNN", "course": "AI 入门"},
  "neighbors_1hop": [
    {"kp_id": "kp-rnn", "relation_type": "related_to", "weight": 0.8}
  ],
  "neighbors_2hop": [
    {"id": "kp-rnn", "name": "RNN", "distance": 1},
    {"id": "kp-lstm", "name": "LSTM", "distance": 2}
  ],
  "edges_2hop": [
    {"source": "kp-cnn", "target": "kp-rnn", "type": "related_to"}
  ]
}
```

- `current_kp` 为当前展示用名称
- `current_kp_meta` 为结构化节点信息
- `neighbors_2hop` 兼容 B 侧 `distance` 需求
- 若运行时 KG 不可用，该子块会返回空列表并附 `error`

### 4.3 `forecast`

```json
{
  "kp_id": "kp-cnn",
  "horizon_days": 7,
  "current_mastery": 0.62,
  "curve": [
    {"day": 0, "mastery": 0.62},
    {"day": 1, "mastery": 0.65}
  ],
  "milestones": [],
  "counterfactual": {
    "baseline_curve": {...},
    "recommended_curve": {...},
    "expected_gain": 0.12,
    "risk_warning": "..."
  }
}
```

- `curve` 已统一映射成 `day/mastery`
- `TimeMachineService.forecast(...).forecast` / `curve` 两种内部结构都能适配
- 若可用，会附带 B 侧反事实 `counterfactual`

### 4.4 `attribution`

```json
{
  "latest_mistakes": [
    {
      "id": "m-1",
      "question": "CNN 池化层作用",
      "category": "concept_confusion",
      "confidence": 0.85,
      "resolved": false
    }
  ],
  "category_distribution": {"concept_confusion": 1},
  "total": 1
}
```

### 4.5 `cov`

```json
{
  "recent_claims": [
    {
      "claim": "CNN 通过卷积核共享权重",
      "verified": true,
      "sources": ["ai/04_cnn.md#L23"]
    }
  ],
  "total_demo_cases": 3
}
```

### 4.6 `debate`

```json
{
  "recent_traces": [
    {
      "round": 1,
      "expert": "CNN 的优势是参数共享...",
      "critic": "建议加入复杂度对比...",
      "verdict": "accept"
    }
  ],
  "total": 1
}
```

### 4.7 `safety`

由 A 侧教学安全评估器返回，典型字段包括：

- `scaffolding_score`
- `answer_leak_risk`
- `misconception_reinforcement_risk`
- `student_uptake_prompt`

### 4.8 `ledger`

由 A 侧证据链服务返回，典型字段包括：

- `claims`
- `total_claims`
- `supported_claims`
- `support_rate`
- `source_distribution`

## 5. 错误兜底约定

任一子块失败时，整体仍返回 `200`，对应子块结构中附带：

```json
{
  "error": "ExceptionType: 具体错误信息"
}
```

前端应按 `error` 做降级渲染，而不是把整页判为失败。

## 6. 调用示例

```bash
curl http://localhost:8000/api/v1/cockpit/student/demo-student-1

curl "http://localhost:8000/api/v1/cockpit/student/demo-student-1?horizon_days=14&focus_kp=kp-cnn"
```

## 7. 自描述端点

```bash
GET /api/v1/cockpit/schema
```

返回 query 参数与 response 字段说明，供前端开发和测试使用。

## 8. 实现备注

- `demo-student-*` 若运行时 profile 仓为空，会只读回退到 `data/seed.json` / `data/seed_extended.json`
- `kg` 复用 A 侧聚合思路，同时保留 B 侧 `distance` 结果
- `forecast` 保留 A 侧反事实能力，同时兼容 B 侧 `curve/mastery` 契约
