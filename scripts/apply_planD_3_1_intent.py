"""Plan D 3.1 orchestrator.py 安全替换脚本"""
import sys
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\backend\app\agents\orchestrator.py")
text = p.read_text(encoding="utf-8")

OLD_START = '        """意图分类：规则匹配 + LLM兜底"""'
OLD_END_MARKER = '            return []\n\n    def _plan_tasks('

start_idx = text.find(OLD_START)
if start_idx < 0:
    print("[FAIL] cannot find OLD_START")
    sys.exit(1)

# 找到紧接着 _plan_tasks 的位置
end_idx = text.find(OLD_END_MARKER, start_idx)
if end_idx < 0:
    print("[FAIL] cannot find OLD_END_MARKER")
    sys.exit(1)

NEW = '''        """意图分类：规则匹配 + LLM 兜底

        Plan D · 3.1 — 关键词扩充 + 兜底 fallback 到 tutoring
        """
        # 规则快速匹配（每意图扩 5-12 个同义词）
        intent_keywords = {
            "generate_doc": [
                "讲解", "文档", "课程笔记", "知识点说明",
                "整理", "总结", "归纳", "笔记", "复习材料",
                "梳理", "汇总", "概览", "大纲", "讲义", "课件",
            ],
            "generate_mindmap": [
                "思维导图", "知识图谱", "脑图",
                "画个图", "整理图", "结构图", "关系图",
            ],
            "generate_exercise": [
                "题目", "练习", "测试", "习题", "出题",
                "考考我", "检验", "做几道", "巩固",
                "刷题", "演练", "来一题", "出几道", "测评卷", "考卷",
            ],
            "generate_reading": [
                "扩展", "拓展阅读", "参考资料",
                "推荐阅读", "延伸材料", "更多材料", "论文", "导读",
            ],
            "generate_video": [
                "视频", "动画", "演示",
                "录个视频", "可视化讲解", "可不可以展示", "做个动图",
            ],
            "plan_path": [
                "学习计划", "路径", "下一步", "怎么学",
                "我下一步", "学什么", "该怎么走", "制定计划",
                "帮我规划", "生成路线", "推荐路线", "学习路线", "学习路径",
            ],
            "tutoring": [
                "为什么", "怎么办", "解释下", "不太懂",
                "什么是", "区别是", "原理是", "怎么理解",
                "教我", "帮我理解", "展开说", "细说", "举个例子",
            ],
            "evaluation": [
                "诊断", "评估下", "测评", "水平",
                "学得怎么样", "掌握了吗", "薄弱", "强弱项",
            ],
        }

        matched: List[str] = []
        for intent, keywords in intent_keywords.items():
            if any(kw in user_input for kw in keywords):
                matched.append(intent)

        # 始终包含画像更新（每次对话更新画像）
        if "profile_update" not in matched:
            matched.insert(0, "profile_update")

        # 如果没有规则匹配到，由 LLM 判断意图
        if len(matched) <= 1:  # 只有 profile_update
            llm_intent = await self._llm_classify_intent(user_input)
            matched.extend(llm_intent)

        # Plan D · 3.1 — 兜底：LLM 也分类不出时仍返回 tutoring
        if matched == ["profile_update"]:
            matched.append("tutoring")

        return matched

    async def _llm_classify_intent(self, user_input: str) -> List[str]:
        """LLM 意图兜底 —— 当规则覆盖不到时调用 IntentClassifier

        Phase 1: 通过 services/intent_classifier.py 调用 LLM（2s 超时）
        Phase 2: 用标注数据训练 BERT-tiny 分类器替代

        Plan D · 3.1 — 异常时 fallback 到 ["tutoring"] 而非 []
        避免 orchestrator 不调度任何 Agent、返回空白。
        """
        try:
            from backend.app.services.intent_classifier import get_intent_classifier
            classifier = get_intent_classifier(self.llm)
            return await classifier.classify(user_input)
        except Exception as exc:
            logger.warning(
                f"[Orchestrator] IntentClassifier 失败: {exc}，fallback 到 tutoring"
            )
            return ["tutoring"]

'''

new_text = text[:start_idx] + NEW + text[end_idx:]
p.write_text(new_text, encoding="utf-8")
print(f"[OK] replaced bytes: {len(text) - len(new_text)} ({len(new_text)} new bytes)")
