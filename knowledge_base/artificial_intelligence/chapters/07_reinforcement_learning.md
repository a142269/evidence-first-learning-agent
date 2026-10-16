---
chapter_id: '07'
slug: reinforcement_learning
title: 强化学习
kp_ids:
- AI_009
bloom_focus:
- Understand
- Apply
- Analyze
prerequisites:
- '01'
- '02'
estimated_minutes: 60
---

# 07: 强化学习 · 从 Q-Learning 到大模型人类对齐 (RLHF)

> **Bloom 层级**: Understand → Apply → Analyze
> **建议学时**: 120 分钟
> **前置知识**: 01-机器学习基础、03-神经网络基础

## 学习目标
1. 解释马尔可夫决策过程 (MDP) 的五元组结构及其在强化学习中的核心地位。
2. 对比 On-policy 与 Off-policy 学习的差异，并推导 Q-Learning 的时序差分更新公式。
3. 阐明 DQN 为何需要引入“经验回放”与“目标网络”来稳定神经网络的训练。
4. 描述策略梯度 (Policy Gradient) 的直觉，并理解当前最主流的 PPO 算法如何通过 Clip 限制更新幅度。
5. 详细梳理基于人类反馈的强化学习 (RLHF) 是如何成功塑造出 ChatGPT 这类安全的大语言模型的。

## 7.1 强化学习的基本框架与 MDP
**强化学习 (Reinforcement Learning, RL)** 是一种独特的学习范式。与监督学习（拥有现成的标准答案）不同，强化学习中**没有老师来告诉你每一步是对是错，只有环境给出的“奖励（Reward）”**。智能体必须通过在环境中不断试错，自己摸索出一条能够获得最大长期回报的策略。

**马尔可夫决策过程 (MDP)**：
它是强化学习的数学地基，包含五个要素 $\langle S, A, P, R, \gamma \rangle$：
- **$S$ (状态)**：环境当前的快照（比如迷宫里你当前所在的位置）。
- **$A$ (动作)**：智能体可以采取的行为（比如上下左右走）。
- **$P$ (状态转移概率)**：在状态 S 下采取动作 A 后，环境转移到新状态 S' 的概率。
- **$R$ (奖励)**：采取动作后环境立刻给出的分数（走到终点 +100，掉进陷阱 -100）。
- **$\gamma$ (折扣因子)**：决定了智能体是“目光短浅”（更看重眼前奖励）还是“放眼未来”。

**马尔可夫性质**：未来的状态只与“现在”的状态和动作有关，与“过去”的历史无关。

## 7.2 从 Q-Learning 到深度 Q 网络 (DQN)
**Q-Learning** 是一种经典的无模型 (Model-free) 和离轨 (Off-policy) 算法。
它维护一张巨大的 $Q$ 表，记录在每一个状态下采取每一个动作所能得到的期望回报。
核心的**时序差分 (TD) 更新公式**为：
$$Q(s, a) \leftarrow Q(s, a) + \alpha \big[ r + \gamma \cdot \max_{a'} Q(s', a') - Q(s, a) \big]$$

**DQN (Deep Q-Network)**：
当状态空间极大时（如围棋有 $10^{170}$ 种状态），Q 表根本装不下。DQN 巧妙地引入了**深度神经网络来替代 Q 表**进行预测。
为了解决神经网络在强化学习中容易发散崩溃的问题，DQN 引入了两大创举：
1. **经验回放 (Experience Replay)**：把过去的经历存进记忆池，随机打乱抽取训练，打破了样本间的时间相关性。
2. **目标网络 (Target Network)**：每隔一段时间才更新一次评估标准，防止模型在追逐一个快速移动的目标时失控。

## 7.3 策略梯度与 PPO 算法
Q-Learning 是“价值方法”，它间接通过比较谁的价值大来决定动作；而**策略梯度 (Policy Gradient)** 直接输出每个动作的概率分布。

在策略梯度的演进中，**PPO (Proximal Policy Optimization)** 成为了行业事实上的霸主。
由于强化学习的数据是通过当前策略在环境中试错得来的，如果模型在某一次更新时步子迈得太大，把策略改坏了，它收集到的新数据就会全错，导致模型直接崩溃无法挽回。
**PPO 的核心机密 (Clip 操作)**：它在损失函数中加了一把锁，**强行限制新策略相比旧策略的更新幅度不能超过 20% ($\epsilon=0.2$)**。这让 PPO 训练极其稳定，成为了 OpenAI 的镇店之宝。

## 7.4 现代皇冠：RLHF 与 ChatGPT
为什么 2020 年的 GPT-3 虽然很强，但经常胡言乱语、充满偏见？因为它只用海量文本做了**无监督续写**，它根本不知道人类觉得什么是“好”的回答。
让大语言模型“懂得人情世故”的绝招是 **RLHF (基于人类反馈的强化学习)**。

**ChatGPT 训练的三阶段流程**：
1. **SFT (监督微调)**：雇佣专家人工写一批高质量的问答对，让模型先学会对话的格式。
2. **RM (奖励模型训练)**：让刚才的模型对同一个问题生成多个回答，人类标注员对这些回答进行好坏排序。然后用这些排序数据训练一个**奖励打分模型 (Reward Model)**，把它当成人类品味的“裁判”。
3. **PPO 强化学习**：语言模型（Agent）开始回答海量新问题，奖励模型（裁判）给它的回答打分（环境的 Reward）。语言模型通过 PPO 算法不断调整自己生成文字的概率，以讨好这个裁判，从而完全对齐人类偏好。

## 7.5 教育智能体场景案例 (A3 系统)
在 A3 项目中，强化学习的理念同样渗透在核心逻辑中。
**个性化路径规划 (Planner Agent)**：
我们可以把 A3 的学习推荐引擎建模为一个 MDP。
- **状态 (S)**：学生当前的知识图谱掌握度画像。
- **动作 (A)**：推荐下一个具体的知识点或练习题难度。
- **奖励 (R)**：如果学生顺利通过了该知识点的考核，环境给予正奖励；如果学生中途放弃或连续做错，给予极大的负奖励。
利用离线的强化学习算法，系统可以学会在“鼓励跳级”和“夯实基础”之间找到最优的长期学习路径平衡。

## 7.6 常见误区
- **误区 1：既然强化学习这么强，那在所有预测任务上（如股票预测）都应该优先用强化学习。**
  - **为什么错**：强化学习样本效率极低，需要海量的试错交互。在没有一个完美的“仿真环境（Simulator）”时（现实世界的股票、医疗无法给你低成本试错），强行使用 RL 往往不如监督学习稳妥。
- **误区 2：在训练 RLHF 时，只让模型无脑追求奖励模型的最高分就行了。**
  - **为什么错**：这会导致可怕的“奖励骇客 (Reward Hacking)”现象。如果缺乏约束，语言模型会发现只要堆砌某些奉承的词汇或写极度冗长的空话，就能骗过奖励模型拿到高分。因此，PPO 损失中必须加入 **KL 惩罚项**，死死拉住模型，不让它偏离初始有逻辑的 SFT 模型太远。
- **误区 3：Q-Learning 中的 ε-greedy 策略只是随便加的一点随机噪声，可有可无。**
  - **为什么错**：这涉及强化学习中最核心的 **探索与利用困境 (Exploration vs Exploitation)**。如果没有 ε（通常设为 0.1，即 10% 的概率随机乱走探索），智能体一旦偶然发现了一条次优路线，就会一辈子死磕这条路，永远找不到真正的宝藏。

## 7.7 可运行示例：纯 Python 实现 Q-Learning
以下代码模拟了一个极简的网格走迷宫环境，并使用 Q-Learning 算法，让毫无先验知识的智能体通过上千次试错，学会走向宝藏并避开陷阱的最短路径。

```python
import numpy as np
import random

# 1. 极简环境设定: 4x4 迷宫
# 状态: 0 到 15 的数字。起点 0，陷阱 5 和 12，宝藏 15。
n_states = 16
n_actions = 4 # 0:上, 1:下, 2:左, 3:右

def step(state, action):
    """模拟环境对动作的反应"""
    # 动作导致的位置变化逻辑 (简化版)
    row, col = state // 4, state % 4
    if action == 0: row = max(0, row - 1)
    if action == 1: row = min(3, row + 1)
    if action == 2: col = max(0, col - 1)
    if action == 3: col = min(3, col + 1)
    
    next_state = row * 4 + col
    
    # 奖励机制
    if next_state == 15: return next_state, 100, True   # 宝藏
    if next_state in [5, 12]: return next_state, -100, True # 陷阱
    return next_state, -1, False  # 每走一步扣 1 分，鼓励走捷径

# 2. 初始化 Q 表 (全为 0)
Q_table = np.zeros((n_states, n_actions))

# 3. 算法超参数
alpha = 0.1      # 学习率 (接受新知识的程度)
gamma = 0.9      # 折扣因子 (对未来奖励的重视程度)
epsilon = 0.2    # 探索率 (20% 概率随机乱走探索)
epochs = 500

print("智能体开始在迷宫中试错学习...")

for epoch in range(epochs):
    state = 0  # 每次都在起点重生
    done = False
    
    while not done:
        # ε-greedy 策略选择动作
        if random.uniform(0, 1) < epsilon:
            action = random.randint(0, 3) # 随机探索
        else:
            action = np.argmax(Q_table[state]) # 贪婪利用
            
        # 与环境交互
        next_state, reward, done = step(state, action)
        
        # Q-Learning 核心更新公式 (时序差分 TD)
        old_value = Q_table[state, action]
        next_max = np.max(Q_table[next_state])
        
        # 融入新知识
        new_value = (1 - alpha) * old_value + alpha * (reward + gamma * next_max)
        Q_table[state, action] = new_value
        
        state = next_state

print("\n=== 训练结束！最终学到的 Q 表 (部分展示) ===")
print("状态 0 (起点) 的 4 个动作 Q 值:", np.round(Q_table[0], 2))
print("可以看出，通向宝藏的动作方向积累了最高的分数！")
```

## 7.8 本章小结
1. 强化学习通过状态、动作、奖励的 MDP 交互循环，解决了那些只有终极目标、没有分布步骤答案的规划问题。
2. Q-Learning 及其升级版 DQN 奠定了价值方法的基础，通过经验回放池让神经网络在不稳定环境中站稳脚跟。
3. 策略梯度与 PPO 构成了现代强化学习的主流骨架，通过对更新步长的 Clip 实现了训练的极高稳定性。
4. RLHF 技术将 PPO 算法与语言模型完美结合，成为了让狂野的预训练大模型服从人类指令、符合人类价值观的关键催化剂。

## 7.11 可运行代码示例

下面用纯 Python 实现 Q-Learning 解决 4 状态格子世界：智能体从起点出发学走路，每次 ε-greedy 选择动作。

```python
'''07 章 · Q-Learning 简单实现 — 4 状态格子世界'''
import random
random.seed(3)

# 状态: 0=起点, 1=A, 2=B, 3=终点
# 动作: 0=左, 1=右
# 奖励: 到达 3 得 +10, 其它步骤 -1
N_STATES = 4
N_ACTIONS = 2
Q = [[0.0] * N_ACTIONS for _ in range(N_STATES)]
REWARDS = {3: 10}

def step(s, a):
    if a == 0:    # 左
        s2 = max(0, s - 1)
    else:         # 右
        s2 = min(N_STATES - 1, s + 1)
    r = REWARDS.get(s2, -1)
    done = s2 == 3
    return s2, r, done

alpha = 0.1       # 学习率
gamma = 0.9       # 折扣
eps   = 0.2       # ε-greedy
EPISODES = 500

for ep in range(EPISODES):
    s = 0
    while True:
        if random.random() < eps:
            a = random.randint(0, N_ACTIONS - 1)
        else:
            a = max(range(N_ACTIONS), key=lambda x: Q[s][x])
        s2, r, done = step(s, a)
        # Q-Learning 更新: 用下一状态最大 Q 值
        td_target = r + (0 if done else gamma * max(Q[s2]))
        Q[s][a] += alpha * (td_target - Q[s][a])
        s = s2
        if done:
            break

# 打印学到的 Q 表
print("学到的 Q 表 (状态 × 动作):")
print("状态 \\ 动作   左      右")
for s in range(N_STATES):
    print(f"  {s}         {Q[s][0]:6.2f}  {Q[s][1]:6.2f}")

# 用学到的策略走一遍
print("\n学到的最优路径:")
s = 0
path = [s]
while s != 3:
    a = max(range(N_ACTIONS), key=lambda x: Q[s][x])
    s, _, _ = step(s, a)
    path.append(s)
print(" -> ".join(map(str, path)))
```
\n## 7.9 练习思考
1. **折扣探索**：在 MDP 中，如果我们将折扣因子 $\gamma$ 设置为 0，智能体的行为模式会变成什么样？如果设置为 1 呢？
2. **On/Off Policy辨析**：Q-Learning 是 Off-policy，意味着它在更新 Q 表时使用的“假想的下一步动作”和它“实际执行的下一步动作”可以是不同的。这种特性在自动驾驶的仿真训练中有什么巨大的优势？
3. **RLHF 瓶颈**：在构建 ChatGPT 时，训练奖励模型（RM）是成本最高的一步。你能想到为什么奖励模型的标注必须要昂贵的人工专家来完成，而不能用简单的关键词匹配或算法来替代吗？
4. **模型防御**：如果你恶意地向经过 RLHF 对齐的大模型发送一段极其具有诱导性的代码或长文本，迫使它绕过安全护栏生成危险内容（即所谓的“越狱 Jailbreak”）。为什么模型会在这种极端边缘情况下失效？这暴露了 RL 训练的什么弱点？

## 7.10 拓展阅读
- 强化学习最权威的圣经教材：Sutton & Barto 编写的 《Reinforcement Learning: An Introduction》。
- 玩 Atari 游戏的 DQN 原文：检索 DeepMind 登上 Nature 的论文 `Human-level control through deep reinforcement learning` (2015)。
- OpenAI 的 PPO 神作：阅读论文 `Proximal Policy Optimization Algorithms` (Schulman et al., 2017)。
- RLHF 原理图解：推荐阅读 Hugging Face 的科普文章 `Illustrating Reinforcement Learning from Human Feedback (RLHF)`。
