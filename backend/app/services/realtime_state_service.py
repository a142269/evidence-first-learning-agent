"""
实时学情感知服务
借鉴自: NPUYUN/LearnPath 的 realtime_state_service.py 设计理念

核心能力：通过规则引擎 + LLM 增强分析，实时感知学生当前的学习状态。
与长期画像（Profile）的区别：
- 长期画像：你是谁、基础怎样（慢变）
- 实时学情：你现在怎样 —— 困惑、投入、负荷（快变）

应用场景：
- 驱动对话回答的语气和策略（困惑高时放慢节奏）
- 触发教学干预（连续困惑 → 主动询问是否需要帮助）
- 辅助路径重规划决策
"""
from __future__ import annotations

import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ================================================================
# 数据模型
# ================================================================
@dataclass
class RealtimeLearningState:
    """实时学情状态"""
    # 情绪维度
    emotion: str = "neutral"            # confused / frustrated / excited / tired / bored / neutral
    implicit_emotion: str = ""          # 自然语言情绪描述
    confidence_level: float = 0.5       # 学习信心 0-1

    # 投入与负荷
    engagement: str = "medium"          # low / medium / high
    confusion_level: float = 0.0        # 困惑度 0-1
    curiosity_level: float = 0.0        # 好奇度 0-1
    cognitive_load_level: float = 0.3   # 认知负荷 0-1
    fatigue_level: float = 0.0          # 疲劳度 0-1

    # 主题检测
    stuck_topics: List[str] = field(default_factory=list)      # 卡点主题
    curiosity_topics: List[str] = field(default_factory=list)   # 好奇主题

    # 策略建议
    preferred_reply_style: str = ""     # 偏好的讲解方式
    next_best_action: str = ""          # 建议的下一步教学动作
    evidence: List[str] = field(default_factory=list)           # 判断依据

    def summary(self) -> str:
        """人类可读的摘要"""
        parts = []
        if self.emotion != "neutral":
            parts.append(f"情绪: {self.emotion}")
        if self.confusion_level > 0.3:
            parts.append(f"困惑度: {self.confusion_level:.0%}")
        if self.curiosity_level > 0.3:
            parts.append(f"好奇度: {self.curiosity_level:.0%}")
        if self.cognitive_load_level > 0.5:
            parts.append(f"认知负荷较高: {self.cognitive_load_level:.0%}")
        if self.fatigue_level > 0.5:
            parts.append("可能疲劳")
        if self.stuck_topics:
            parts.append(f"卡点: {', '.join(self.stuck_topics[:3])}")
        return "; ".join(parts) if parts else "状态正常"


# ================================================================
# 规则引擎 —— 基于关键词和模式的实时分析
# ================================================================
class RealtimeStateAnalyzer:
    """
    实时学情分析器

    设计原则（借鉴 LearnPath）：
    1. 规则引擎先做快速分析（毫秒级）
    2. 深度分析可选（调用 LLM，秒级）
    3. 分析结果同时考虑当前消息和历史上下文
    """

    # ---- 困惑信号 ----
    CONFUSION_PATTERNS = [
        # 强信号（困惑度高）
        (r"(?:完全|根本|一点都|实在)(?:不懂|不理解|没懂|没理解|不会|搞不懂)", 0.9),
        (r"(?:太难|好难|太复杂|看不懂|听不懂)", 0.7),
        (r"(?:什么意思|为什么|怎么会|咋回事|搞不明白)", 0.6),
        (r"(?:不太懂|不太理解|不是很懂|不是很理解|有点难)", 0.5),
        (r"(?:能再.*一遍|能重新.*一下|没听清|没看懂)", 0.4),
        # 中信号
        (r"(?:可以.*解释|能.*解释|帮我.*解释|麻烦.*解释)", 0.3),
        (r"\?{2,}|？{2,}", 0.2),  # 多个问号
    ]

    # ---- 挫败/沮丧信号 ----
    FRUSTRATION_PATTERNS = [
        (r"(?:算了|不学了|放弃了|搞不定|学不会|心态崩)", 0.9),
        (r"(?:烦死了|好烦|崩溃|头大|头疼|脑壳疼)", 0.8),
        (r"(?:每次都|老是|总是|一直)(?:错|做错|搞错)", 0.6),
    ]

    # ---- 兴奋/好奇信号 ----
    EXCITEMENT_PATTERNS = [
        (r"(?:原来如此|懂了|明白了|理解了|恍然大悟|终于)", 0.7),
        (r"(?:有意思|有趣|好厉害|太强了|牛|!,{2,})", 0.6),
        (r"(?:想学|想了解|感兴趣|好奇|探索)", 0.5),
    ]

    # ---- 疲劳信号 ----
    FATIGUE_PATTERNS = [
        (r"(?:累了|困了|好累|好困|不想动了|想休息)", 0.8),
        (r"(?:太多了|很长|内容好多|学不完|看不完)", 0.5),
        (r"(?:先到这|今天就|下次|改天|回头再)", 0.4),
    ]

    # ---- 认知负荷信号 ----
    COGNITIVE_LOAD_PATTERNS = [
        (r"(?:公式|推导|证明|数学|复杂|抽象)", 0.5),
        (r"(?:记不住|忘了|又忘了|混淆)", 0.4),
        (r"(?:太多.*概念|概念.*太多|一堆.*术语)", 0.6),
    ]

    # ---- 投入度信号 ----
    ENGAGEMENT_HIGH_PATTERNS = [
        (r"(?:然后呢|接下来|继续|下一个|还有吗|再来)", 0.7),
        (r"(?:我自己试试|让我想想|我来写|我做一下)", 0.6),
    ]
    ENGAGEMENT_LOW_PATTERNS = [
        (r"^(?:嗯|哦|好|行|对|是的|知道了|懂了)\s*$", 0.5),
        (r"(?:随便|都行|无所谓|不知道)", 0.3),
    ]

    def analyze(
        self,
        user_message: str,
        history: List[Dict[str, str]] = None,
        previous_state: Optional[RealtimeLearningState] = None,
    ) -> RealtimeLearningState:
        """
        分析单条用户消息，返回实时学情状态

        Args:
            user_message: 当前用户消息
            history: 最近对话历史（用于上下文分析）
            previous_state: 上一轮状态（用于平滑过渡）
        """
        state = RealtimeLearningState()

        if not user_message.strip():
            return state

        msg = user_message.strip()
        evidence = []

        # ---- 1. 困惑度分析 ----
        confusion_scores = []
        for pattern, weight in self.CONFUSION_PATTERNS:
            if re.search(pattern, msg):
                confusion_scores.append(weight)
        if confusion_scores:
            state.confusion_level = min(1.0, max(confusion_scores))
            evidence.append(f"检测到困惑信号: 强度={state.confusion_level:.1f}")

        # ---- 2. 情绪检测 ----
        for pattern, weight in self.FRUSTRATION_PATTERNS:
            if re.search(pattern, msg):
                state.emotion = "frustrated"
                evidence.append("检测到挫败情绪")
                break

        for pattern, weight in self.EXCITEMENT_PATTERNS:
            if re.search(pattern, msg):
                if state.emotion == "frustrated":
                    pass  # 保留 frustration
                else:
                    state.emotion = "excited"
                evidence.append("检测到兴奋/好奇情绪")
                state.curiosity_level = weight
                break

        # ---- 3. 疲劳度 ----
        for pattern, weight in self.FATIGUE_PATTERNS:
            if re.search(pattern, msg):
                state.fatigue_level = max(state.fatigue_level, weight)
                evidence.append(f"检测到疲劳信号: {weight:.1f}")

        if any(kw in msg for kw in ["休息", "暂停", "停一下"]):
            state.fatigue_level = max(state.fatigue_level, 0.7)

        # ---- 4. 认知负荷 ----
        load_scores = []
        for pattern, weight in self.COGNITIVE_LOAD_PATTERNS:
            if re.search(pattern, msg):
                load_scores.append(weight)
        if load_scores:
            state.cognitive_load_level = min(1.0, max(load_scores))
            evidence.append(f"检测到认知负荷信号: {state.cognitive_load_level:.1f}")

        # ---- 5. 投入度 ----
        high_signals = sum(1 for p, w in self.ENGAGEMENT_HIGH_PATTERNS if re.search(p, msg))
        low_signals = sum(1 for p, w in self.ENGAGEMENT_LOW_PATTERNS if re.search(p, msg))
        if high_signals > 0:
            state.engagement = "high"
            evidence.append("高投入度")
        elif low_signals > 0:
            state.engagement = "low"
            evidence.append("低投入度")

        # ---- 6. 卡点主题检测 ----
        if state.confusion_level > 0.3:
            # 提取可能的卡点主题
            topic_patterns = [
                r"(?:这个|那个|什么叫|什么是)([^\s，。！？]{2,20})",
                r"([^\s，。！？]{2,20})(?:不太懂|不理解|没明白|好难)",
            ]
            for pattern in topic_patterns:
                matches = re.findall(pattern, msg)
                for m in matches:
                    if m not in state.stuck_topics and len(m) < 20:
                        state.stuck_topics.append(m)

        # ---- 7. 好奇主题 ----
        if state.curiosity_level > 0.3:
            curious_patterns = [
                r"(?:想(?:学|了解|知道|看|探索))([^\s，。！？]{2,20})",
                r"(?:对|关于)([^\s，。！？]{2,20})(?:感兴趣|好奇)",
            ]
            for pattern in curious_patterns:
                matches = re.findall(pattern, msg)
                for m in matches:
                    if m not in state.curiosity_topics and len(m) < 20:
                        state.curiosity_topics.append(m)

        # ---- 8. 与历史状态平滑融合 ----
        if previous_state:
            state = self._smooth_state(state, previous_state, msg)

        # ---- 9. 生成策略建议 ----
        state = self._generate_strategy(state)
        state.evidence = evidence

        return state

    def _smooth_state(
        self, new: RealtimeLearningState, old: RealtimeLearningState, msg: str
    ) -> RealtimeLearningState:
        """与历史状态平滑融合 —— 避免单条消息导致剧烈跳变"""
        # 困惑度：当前权重 0.7，历史权重 0.3
        if new.confusion_level > 0:
            new.confusion_level = new.confusion_level * 0.7 + old.confusion_level * 0.3
        else:
            # 无新困惑信号时，困惑缓慢衰减
            new.confusion_level = old.confusion_level * 0.7

        # 疲劳度：累加但缓慢衰减
        if new.fatigue_level > 0:
            new.fatigue_level = max(new.fatigue_level, old.fatigue_level * 0.5)
        else:
            new.fatigue_level = old.fatigue_level * 0.85  # 缓慢恢复

        # 认知负荷：类似处理
        if new.cognitive_load_level > 0:
            new.cognitive_load_level = new.cognitive_load_level * 0.6 + old.cognitive_load_level * 0.4
        else:
            new.cognitive_load_level = old.cognitive_load_level * 0.8

        # 学习信心
        if new.emotion == "excited":
            new.confidence_level = min(1.0, old.confidence_level + 0.1)
        elif new.emotion == "frustrated":
            new.confidence_level = max(0.0, old.confidence_level - 0.15)
        elif new.confusion_level > 0.5:
            new.confidence_level = max(0.0, old.confidence_level - 0.05)
        else:
            new.confidence_level = old.confidence_level

        # 累积卡点
        for topic in old.stuck_topics:
            if topic not in new.stuck_topics:
                new.stuck_topics.append(topic)

        return new

    def _generate_strategy(self, state: RealtimeLearningState) -> RealtimeLearningState:
        """根据实时状态生成教学策略建议"""
        suggestions = []

        if state.confusion_level > 0.6:
            state.preferred_reply_style = "极度简化：用生活化类比，避免术语，每个概念配合1个最简单例子"
            state.next_best_action = "先降低难度，确认学生理解基础概念后再推进"
            suggestions.append("严重困惑 → 启动降压模式")
        elif state.confusion_level > 0.3:
            state.preferred_reply_style = "放慢节奏：拆解步骤，多用图示，每个新概念先确认理解"
            state.next_best_action = "放慢教学节奏，增加互动确认"
            suggestions.append("中度困惑 → 放慢节奏")

        if state.cognitive_load_level > 0.6:
            suggestions.append("高认知负荷 → 建议拆分知识点，减少单次学习量")
            state.next_best_action = "建议休息或转换学习方式"

        if state.fatigue_level > 0.6:
            suggestions.append("明显疲劳 → 建议简短总结后暂停")
            state.next_best_action = "主动询问是否需要休息"

        if state.emotion == "excited":
            state.preferred_reply_style = "保持节奏：可以适当延伸，引入进阶内容"
            state.next_best_action = "抓住好奇心窗口，引入相关拓展"
            suggestions.append("高兴趣 → 引入拓展内容")

        if state.emotion == "frustrated":
            state.preferred_reply_style = "共情回复：先安抚情绪，肯定努力，再提供最简单的成功路径"
            state.next_best_action = "情绪支持优先，再解决学习问题"
            suggestions.append("挫败感 → 优先情绪支持")

        logger.info(f"实时学情: {state.summary()} | 策略: {'; '.join(suggestions) if suggestions else '正常教学'}")
        return state


# ================================================================
# 个性化教学策略层
# 借鉴 LearnPath 的 personalization_strategy_service.py
# ================================================================
def build_personalization_prompt(
    realtime: Optional[RealtimeLearningState] = None,
    profile: Optional[dict] = None,
) -> str:
    """
    构建个性化教学策略提示词
    用于注入到 Agent 的 System Prompt 中
    """
    parts = []

    if realtime:
        if realtime.confusion_level > 0.4:
            parts.append(f"【教学策略】学生当前困惑度较高({realtime.confusion_level:.0%})，请放慢节奏，多用类比和图示，每引入一个新概念前先确认理解。")
        if realtime.cognitive_load_level > 0.6:
            parts.append(f"【教学策略】学生认知负荷高({realtime.cognitive_load_level:.0%})，请精简内容，只聚焦核心要点。")
        if realtime.fatigue_level > 0.5:
            parts.append("【教学策略】学生可能疲劳，请缩短本次回复，主动建议休息。")
        if realtime.emotion == "excited":
            parts.append("【教学策略】学生当前兴趣浓厚，可以适度延伸相关进阶内容。")
        if realtime.emotion == "frustrated":
            parts.append("【教学策略】学生有挫败感，请先给予肯定和鼓励，再提供清晰的解决路径。")
        if realtime.stuck_topics:
            parts.append(f"【教学策略】学生卡在: {', '.join(realtime.stuck_topics[:3])}，请针对性讲解。")

    if profile:
        level = profile.get("knowledge_base", {}).get("level", "")
        style = profile.get("cognitive_style", {})
        if level:
            parts.append(f"【学生水平】{level}")
        if style:
            parts.append(f"【认知风格】{style}")

    return "\n".join(parts) if parts else ""


# 全局单例
_analyzer: Optional[RealtimeStateAnalyzer] = None


def get_analyzer() -> RealtimeStateAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = RealtimeStateAnalyzer()
    return _analyzer
