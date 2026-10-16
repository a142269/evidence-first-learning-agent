# 学习时光机：BKT 掌握度预测器设计文档

> **Innovation #4** · B-P3-1 交付物 · `services/cognitive_diagnosis/bkt_forecaster.py`
> 算法设计文档（B-P5-1）

## 1. Motivation

传统知识追踪系统（BKT/DKT）只回答"学生**现在**掌握了多少"，却无法回答学生和家长最关心的问题：

- "照目前节奏，**30 天后**我能掌握这个知识点吗？"
- "如果想 30 天后达到 95% 掌握，**每天该练几道题**？"
- "如果每天多练 1 题，结果会差多少？"（反事实分析）

"学习时光机"把 BKT 从**事后估计**升级为**事前预测**，并量化预测的不确定性，
为个性化学习计划提供可解释的、带置信区间的未来推演。

### 现有方案局限

| 方案 | 局限 |
|------|------|
| 标准 BKT (Corbett & Anderson 1995) | 只做一步更新，无多步预测 |
| DKT (Piech 2015) | 黑盒 LSTM，无法给出置信区间，难解释 |
| 性能预测器 (Khajah 2016) | 仅预测整体正确率，不分解到知识点 + 无反事实 |

### 我们的假设

> 将 BKT 的单步贝叶斯更新封装为**日级状态转移函数**，迭代推演未来 $H$ 天，
> 并用 Beta 分布近似每日掌握度的后验，即可得到带 90% 置信区间的预测曲线；
> 进一步对练习强度做参数扫描，可实现反事实分析与目标倒推。

## 2. Related Work

1. **Corbett & Anderson 1995** — BKT 四参数模型（P(L0)/P(T)/P(S)/P(G)），本文的转移基础。
2. **Piech et al. NIPS 2015** — DKT，LSTM 替代隐马尔可夫，本文作为对照基线（benchmark）。
3. **Yudelson 2013** — BKT+，per-student 个性化参数，本文的个性化方向。
4. **Kalman 1960** — 线性高斯状态空间滤波，本文用于历史观测去噪平滑。
5. **Settles & Meeder 2016** — HLR (Half-Life Regression)，间隔重复预测，对照 FSRS。
6. **Khajah et al. 2016** — 预测学生表现，多步推演思想相近但无 Beta CI。

## 3. Method

### 3.1 形式化定义

记学生在知识点 $k$ 上的掌握度为 $\ell_t \in [0,1]$（$t$ 为天）。BKT 四参数：

| 参数 | 含义 |
|------|------|
| $P(L_0)$ | 初始掌握概率 |
| $P(T)$ | 单次练习后"未掌握→掌握"的转移概率 |
| $P(S)$ | 已掌握但答错的概率（slip） |
| $P(G)$ | 未掌握但蒙对的概率（guess） |

**日级状态转移**：设每日练习强度为 $r \in [0,1]$（当日练习概率）。

1. 不练习（概率 $1-r$）：掌握度保持 $\ell_{t+1}^{(\text{no})} = \ell_t$（无遗忘假设）。
2. 练习（概率 $r$）：
   - 答对概率 $P(C) = \ell_t(1-S) + (1-\ell_t)G$
   - 答对后贝叶斯后验：$P(L|C) = \dfrac{\ell_t(1-S)}{P(C)}$
   - 答错后贝叶斯后验：$P(L|\bar C) = \dfrac{\ell_t S}{1-P(C)}$
   - 练习后掌握度（含转移）：$\ell_{t+1}^{(\text{prac})} = P(\text{post}) + (1-P(\text{post}))T$
     其中 $P(\text{post}) = P(C)\cdot P(L|C) + (1-P(C))\cdot P(L|\bar C)$
3. 日级混合：$\ell_{t+1} = r\cdot\ell_{t+1}^{(\text{prac})} + (1-r)\cdot\ell_{t+1}^{(\text{no})}$

迭代 $H$ 天即得预测曲线 $\{\ell_0, \ell_1, \dots, \ell_H\}$。

### 3.2 不确定性传播（Beta 置信区间）

掌握度后验用 $\text{Beta}(\alpha, \beta)$ 近似，其中：

$$\alpha = \max(0.5,\ \ell_t \cdot n_{\text{eff}}),\quad \beta = \max(0.5,\ (1-\ell_t)\cdot n_{\text{eff}})$$

有效样本量 $n_{\text{eff}}$ 随练习天数递增（每练习一天 $+r$），反映信息累积。
90% 置信区间取 $\text{Beta.interval}(0.90, \alpha, \beta)$。

为防止远期 CI 过窄（高估确定性），引入**不确定性下界**：

$$\text{width}_{\min}(t) = \text{width}_0 + 0.01\sqrt{t}$$

即 CI 宽度至少随 $\sqrt{t}$ 增长，体现长期预测的固有不确定性。

### 3.3 Kalman 平滑历史

真实历史观测含噪声（单次答题运气）。`forecast_with_kalman` 先用 Kalman Filter
（过程噪声 $Q=0.02$，观测噪声 $R=0.05$）平滑历史 $\{\ell_{-n}, \dots, \ell_0\}$，
再以平滑后的 $\ell_0$ 为起点做多步预测，降低起点噪声对远期预测的放大效应。

### 3.4 反事实分析

对一组练习强度 $\{r_1, \dots, r_m\}$（默认 $[0.3, 0.5, 0.7, 0.9]$）分别推演 $H$ 天，
对比最终掌握度与 80%/90%/95% 里程碑达成时间，输出推荐文案：

> 当前节奏（70%）下，30 天后预计掌握 82%。若提高到每天 90% 练习，可达 91%。

### 3.5 目标倒推（reverse_plan）

给定目标掌握度 $\ell^*$ 与期限 $H$，求**最小**日练习强度 $r^*$：

1. 上界检查：$r=1.0$（每日全练）下若 $\ell_H < \ell^*$ → 标记 `unreachable`。
2. 二分搜索：$r \in [0,1]$，24 次迭代收敛到 $r^*$（精度 $10^{-4}$）。
3. 换算每日题数：$n_{\text{questions}} = \lceil r^* \cdot N_{\text{full}} \rceil$（默认每日满练 10 题）。

### 3.6 算法伪代码

```
function forecast(ℓ₀, H, r, history):
    n_eff ← 5 + len(history)
    points ← [Point(0, ℓ₀, Beta.CI(ℓ₀, n_eff))]
    w₀ ← points[0].ci_width
    for t ← 1 to H:
        P_C ← ℓ·(1−S) + (1−ℓ)·G
        post_C ← ℓ·(1−S)/P_C          # P(L|correct)
        post_W ← ℓ·S/(1−P_C)          # P(L|wrong)
        post ← P_C·post_C + (1−P_C)·post_W
        ℓ_prac ← post + (1−post)·T
        ℓ ← r·ℓ_prac + (1−r)·ℓ        # 日级混合
        n_eff ← n_eff + r
        w_min ← w₀ + 0.01·√t
        points.append(Point(t, ℓ, Beta.CI(ℓ, n_eff, floor=w_min)))
    return points
```

### 3.7 复杂度分析

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| `forecast(H)` | $O(H)$ | 每天 $O(1)$ 贝叶斯更新 |
| `find_milestones` | $O(3H)$ | 3 个目标 × 扫描曲线 |
| `counterfactual(m)` | $O(mH)$ | $m$ 个场景各跑 $H$ 天 |
| `reverse_plan` | $O(24H)$ | 24 次二分 × 每次 $O(H)$ |
| `forecast_with_kalman(n)` | $O(n + H)$ | Kalman 平滑 $O(n)$ + 预测 $O(H)$ |

$H=30$ 时全部操作均在毫秒级，满足实时 API（P99 < 3s）SLO。

## 4. Implementation

### 4.1 模块结构

```
services/cognitive_diagnosis/
├── bkt.py                 # 4 参数 BKT 单步更新（Corbett & Anderson 1995）
├── bkt_forecaster.py      # ★ 学习时光机：多步预测 + CI + Kalman + 反事实
├── kalman_smoother.py     # Kalman Filter 历史平滑
└── state_repository.py    # BKT 状态持久化
```

### 4.2 关键设计权衡

| 决策 | 选择 | 理由 |
|------|------|------|
| 不练习时的遗忘 | 不建模（$\ell$ 保持） | 简化；遗忘由 SM-2 单独负责，职责分离 |
| CI 分布族 | Beta | 支持域 [0,1]，与掌握度语义一致，闭式区间 |
| 远期不确定性 | $\sqrt{t}$ 下界 | 防止 CI 过窄误导；与随机过程扩散相符 |
| 目标倒推 | 二分搜索 | 单调性保证全局最优，24 次迭代足够 |
| 平滑 vs 预测解耦 | Kalman 仅平滑历史 | 预测用 BKT（可解释），平滑用 Kalman（去噪） |

### 4.3 数值稳定性

- 掌握度钳制到 $[0.01, 0.99]$，避免贝叶斯后验退化到 0/1 吸收态。
- Beta 参数 $\alpha,\beta$ 加 0.5 下界，防止极端值导致 `scipy.stats.beta.interval` 失败。
- `scipy` 不可用时降级为 $\ell \pm 0.2$ 区间。

## 5. API

| 端点 | 功能 |
|------|------|
| `GET /api/v1/cognitive/forecast?user_id=&kp_id=&horizon_days=30` | 30 天预测曲线 + 里程碑 + SVG + 自然语言摘要 |

（反事实与目标倒推端点在 `bkt_forecaster.py` 内提供方法，可按需暴露 API。）

## 6. Discussion

### 优势
- **可解释**：每步更新遵循贝叶斯规则，里程碑与 CI 都有概率语义。
- **可操作**：反事实与目标倒推直接给出"每天练几题"的可执行建议。
- **轻量**：纯数值迭代，无神经网络依赖，毫秒级响应。

### 局限
- 无遗忘建模：长期不练习的衰减需结合 SM-2 间隔重复数据修正。
- 参数固定：$P(T)/P(S)/P(G)$ 未做 per-student 个性化（BKT+ 在 `bkt.py` 层补充）。
- Beta 近似：对极端掌握度（接近 0 或 1）CI 可能偏窄，已用 $\sqrt{t}$ 下界缓解。

### 未来工作
- 引入 per-student $P(T)$（BKT+），让预测因人而异。
- 用真实学生留存数据校准 $r \to$ 实际练习量的映射。
- 与 DKT 预测曲线对比，验证 BKT 预测的准确性。

## 7. References

```bibtex
@article{corbett1995knowledge,
  title={Knowledge tracing: Modeling the acquisition of procedural knowledge},
  author={Corbett, Albert T and Anderson, John R},
  journal={UMUAI},
  year={1995}
}
@inproceedings{piech2015deep,
  title={Deep knowledge tracing},
  author={Piech, Chris and others},
  booktitle={NIPS},
  year={2015}
}
@article{kalman1960new,
  title={A new approach to linear filtering and prediction problems},
  author={Kalman, Rudolph E},
  journal={J. Basic Eng.},
  year={1960}
}
@inproceedings{yudelson2013individualized,
  title={Individualized bayesian knowledge tracing models},
  author={Yudelson, Michael V and Koedinger, Kenneth R and Gordon, Geoffrey J},
  booktitle={AIED},
  year={2013}
}
```
