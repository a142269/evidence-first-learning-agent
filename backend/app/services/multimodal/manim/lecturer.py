"""
AI Lecturer Agent — Manim 教学动画生成智能体 (Phase 3 Innovation 2)

Pipeline:
    1. LLM 分析主题 → 选模板 + 选人格
    2. LLM 填充内容 → ManimDSLSpec
    3. DSLCompiler 编译 → 安全 Manim Python
    4. ManimRenderer 渲染 → MP4/PNG/SVG

用法:
    agent = AILecturerAgent(llm_client)
    result = await agent.execute(context)
    # result.metadata["render_result"] → RenderResult
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.multimodal.manim.dsl import ManimDSLSpec
from backend.app.services.multimodal.manim.compiler import DSLCompiler, ManimSafetyValidator
from backend.app.services.multimodal.manim.templates import (
    PERSONAS,
    PersonaStyle,
    SceneTemplateFactory,
    TeacherPersona,
)
from backend.app.services.multimodal.manim.renderer import (
    ManimRenderer,
    RenderResult,
    get_manim_renderer,
)

logger = logging.getLogger(__name__)

# ================================================================
# LLM Prompt 模板
# ================================================================
DSL_GENERATION_PROMPT = """你是 Manim 教学动画设计师。根据以下信息生成一个完整的教学动画场景规格。

## 教学信息
- 主题: {topic}
- 模板: {template}
- 讲师人格: {persona_name} — {persona_tagline}
- 目标观众: {audience_level}

## 模板说明
{template_description}

## 内容要求
{content_requirements}

## 输出格式
严格按以下 JSON 格式输出 (不要输出 Python 代码!):

```json
{{
  "title": "动画标题",
  "description": "简短描述",
  "content": {{
    // 根据模板提供所需字段
  }}
}}
```

只输出 JSON, 不要其他文字。"""


# ================================================================
# AILecturerAgent
# ================================================================
class AILecturerAgent(BaseAgent):
    """AI 主讲老师 — 生成 Manim 教学动画

    支持的模板: concept / code / formula / comparison / timeline
    支持的人格: serious / friendly / humorous / minimalist / academic

    context.extra 可配置:
        template: 强制模板 (默认 auto-detect)
        persona: 强制人格 (默认 serious)
        render: 是否渲染 (默认 True)
    """

    prompt_version = "v1"

    # 模板 → 描述 (给 LLM 的指引)
    TEMPLATE_DESCRIPTIONS = {
        "concept": (
            "概念讲解模板: 分 3 个场景 (引入/核心/例子)。"
            "content 需提供: title, subtitle, definition, core_points (每行一个要点), "
            "example, summary"
        ),
        "code": (
            "代码走读模板: 分 3 个场景 (标题/代码+讲解/运行结果)。"
            "content 需提供: title, code (完整代码块), line_by_line (逐行解释), output"
        ),
        "formula": (
            "公式推导模板: 分 2 个场景 (前提/推导步骤+最终公式)。"
            "content 需提供: title, prerequisites, "
            "derivation_steps (每行一个推导步骤), final_formula (LaTeX)"
        ),
        "comparison": (
            "对比分析模板: 分 2 个场景 (左右对比/结论)。"
            "content 需提供: title, left_items (每行一项), right_items (每行一项), conclusion"
        ),
        "timeline": (
            "历史时间线模板: 1 个长场景。"
            "content 需提供: title, milestones (每行一个「年份: 事件」), summary"
        ),
    }

    def __init__(self, llm_client=None):
        super().__init__(llm_client=llm_client)
        self._compiler = DSLCompiler()
        self._safety = ManimSafetyValidator()
        self._renderer = get_manim_renderer()

    @property
    def name(self) -> str:
        return "ai_lecturer"

    @property
    def description(self) -> str:
        return "Manim 教学动画生成: 概念讲解/代码走读/公式推导/对比分析/时间线"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名精通 Manim 动画的教学设计师。\n\n"
            "你的任务:\n"
            "1. 分析教学主题，选择合适的讲解模板\n"
            "2. 根据讲师人格调整语言风格\n"
            "3. 输出结构化的动画场景规格 (JSON)\n\n"
            "原则:\n"
            "- 每个概念讲解控制在 3 个场景以内\n"
            "- 代码走读控制在 3 个场景以内\n"
            "- 公式推导控制步骤在 5 步以内\n"
            "- 对比分析突出差异点\n"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        topic = context.user_input
        if not topic or not topic.strip():
            return self._error("教学主题为空")

        # 配置
        template = context.extra.get("template") or self._detect_template(topic)
        persona_key = context.extra.get("persona", "serious")
        should_render = context.extra.get("render", True)

        persona_style = PersonaStyle(persona_key) if persona_key in PersonaStyle.__members__ else PersonaStyle.SERIOUS
        persona = PERSONAS[persona_style]

        start = time.perf_counter()

        # Step 1: LLM 生成内容
        content = await self._generate_content(topic, template, persona)

        # Step 2: 创建 DSL Spec
        try:
            spec = SceneTemplateFactory.create(
                template=template,
                topic=topic,
                content=content,
                persona=persona_style,
            )
        except Exception as exc:
            logger.exception("[AILecturer] DSL spec creation failed")
            return self._error(f"场景规格创建失败: {exc}")

        # Step 3: 编译
        try:
            code = self._compiler.compile(spec)
        except Exception as exc:
            logger.exception("[AILecturer] compilation failed")
            return self._error(f"代码编译失败: {exc}")

        # Step 4: 安全检查
        safe, error = self._safety.validate(code)
        if not safe:
            logger.error(f"[AILecturer] safety check failed: {error}")
            return self._error(f"安全检查未通过: {error}")

        # Step 5: 渲染
        result: Optional[RenderResult] = None
        if should_render:
            output_name = f"lecture_{hashlib.md5(topic.encode()).hexdigest()[:12]}"
            content_lines = [
                e.content for scene in spec.scenes for e in scene.elements
                if e.type in ("text", "bullet_list")
            ]
            result = self._renderer.render(
                code=code,
                output_name=output_name,
                title=spec.title,
                content_lines=content_lines[:15],
                concept=topic,
            )

        elapsed = (time.perf_counter() - start) * 1000

        # Build response
        render_info = result.to_dict() if result else {"method": "not_rendered"}

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=(
                f"## {spec.title}\n\n"
                f"**讲师**: {persona.name} ({persona.tagline})\n"
                f"**模板**: {template}\n"
                f"**场景**: {len(spec.scenes)} 个\n"
                f"**元素**: {spec.element_count()} 个\n"
                f"**动画**: {spec.animation_count()} 步\n"
                f"**渲染方式**: {render_info.get('method', 'skipped')}\n"
                f"**耗时**: {elapsed:.0f}ms\n\n"
                f"{'视频已生成: ' + (result.video_path if result and result.success else '渲染失败')}"
            ),
            content_type="manim_video",
            metadata={
                "topic": topic,
                "template": template,
                "persona": persona_key,
                "spec": spec.dict(),
                "render_result": render_info,
                "generated_code": code,
                "elapsed_ms": elapsed,
            },
            resources=[{
                "type": "manim_video",
                "title": spec.title,
                "format": "mp4" if (result and result.method == "manim") else "svg",
                "filepath": result.video_path if result else "",
                "template": template,
                "persona": persona_key,
            }],
        )

    # ----------------------------------------------------------------
    # LLM 辅助
    # ----------------------------------------------------------------
    async def _generate_content(
        self, topic: str, template: str, persona: TeacherPersona,
    ) -> Dict[str, str]:
        """调用 LLM 生成模板内容"""
        prompt = DSL_GENERATION_PROMPT.format(
            topic=topic,
            template=template,
            persona_name=persona.name,
            persona_tagline=persona.tagline,
            audience_level=persona.explanation_depth,
            template_description=self.TEMPLATE_DESCRIPTIONS.get(template, ""),
            content_requirements=(
                f"请提供 {persona.example_count} 个具体例子。"
                f"{'包含必要的数学公式。' if persona.use_formulas else '用通俗语言解释。'}"
                f"{'使用生动类比帮助理解。' if persona.use_analogies else '直接给出要点。'}"
            ),
        )

        messages = [
            {"role": "system", "content": "你是一个精确的 JSON 输出器。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]

        raw = ""
        try:
            if hasattr(self.llm, "achat"):
                raw = await self.llm.achat(messages, temperature=0.5, max_tokens=800)
            elif hasattr(self.llm, "chat"):
                raw = self.llm.chat(messages, temperature=0.5, max_tokens=800)
        except Exception as exc:
            logger.warning(f"[AILecturer] LLM failed: {exc}")

        # 解析 JSON
        parsed = self._parse_content_json(raw)
        if parsed:
            return parsed

        # LLM 失败 → 使用默认内容
        logger.info(f"[AILecturer] LLM failed, using fallback content for '{topic}'")
        return self._fallback_content(topic, template)

    def _parse_content_json(self, raw: str) -> Optional[Dict[str, str]]:
        """解析 LLM 输出的 JSON"""
        if not raw:
            return None
        raw = raw.strip()
        # 去 markdown 包裹
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if m:
            raw = m.group(1).strip()
        try:
            data = json.loads(raw)
            content = data.get("content", {})
            if isinstance(content, dict) and content:
                return content
        except json.JSONDecodeError:
            # Try extracting JSON object
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                    return data.get("content", {})
                except json.JSONDecodeError:
                    pass
        return None

    def _fallback_content(self, topic: str, template: str) -> Dict[str, str]:
        """LLM 不可用时的降级内容生成"""
        if template == "concept":
            return {
                "title": f"{topic} 详解",
                "subtitle": "核心概念讲解",
                "definition": f"{topic} 是指在相关领域中广泛应用的核心概念。",
                "core_points": f"• {topic} 的基本定义\n• 关键特征与属性\n• 常见应用场景\n• 与其他概念的关联",
                "example": f"例如，在实际应用中，{topic} 可以帮助解决具体问题。",
                "summary": f"掌握 {topic} 的核心要点，可为深入学习打下基础。",
            }
        elif template == "code":
            return {
                "title": f"{topic} 代码实战",
                "code": f"# {topic} 示例代码\n# 请参考官方文档获取完整实现",
                "line_by_line": "• 导入必要库\n• 定义核心函数\n• 执行主逻辑\n• 输出结果",
                "output": "✓ 运行成功",
            }
        elif template == "formula":
            return {
                "title": f"{topic} 公式推导",
                "prerequisites": "• 基础数学知识\n• 相关前置概念",
                "derivation_steps": "• 步骤 1: 建立模型\n• 步骤 2: 推导关键等式\n• 步骤 3: 化简得到最终形式",
                "final_formula": r"f(x) = \text{formula}",
            }
        elif template == "comparison":
            return {
                "title": f"{topic} 对比分析",
                "left_items": "• 特点 A1\n• 特点 A2\n• 特点 A3",
                "right_items": "• 特点 B1\n• 特点 B2\n• 特点 B3",
                "conclusion": "根据具体场景选择合适方案",
            }
        else:  # timeline
            return {
                "title": f"{topic} 发展历程",
                "milestones": "• 1990: 早期探索\n• 2000: 重要突破\n• 2010: 广泛应用\n• 2020: 最新进展",
                "summary": "回顾历史，展望未来",
            }

    # ----------------------------------------------------------------
    # 模板自动检测
    # ----------------------------------------------------------------
    def _detect_template(self, topic: str) -> str:
        """根据主题自动判断最佳模板"""
        lower = topic.lower()
        if any(kw in lower for kw in ["代码", "实现", "code", "编写", "编程", "函数"]):
            return "code"
        if any(kw in lower for kw in ["公式", "推导", "证明", "数学", "定理", "formula"]):
            return "formula"
        if any(kw in lower for kw in ["对比", "区别", "vs", "比较", "哪个", "对比"]):
            return "comparison"
        if any(kw in lower for kw in ["历史", "发展", "时间线", "演变", "历程", "timeline"]):
            return "timeline"
        return "concept"


import hashlib  # noqa: E402 — used in execute() for output_name hash
