"""
多模态生成师 Agent —— 生成思维导图、代码案例、PPT 等

对应赛题需求2（资源生成）：思维导图、代码类实操案例、教学演示PPT

P1-4 升级:
- 思维导图走 MermaidStudio (5 种 diagram + 校验 + 3 级降级渲染)
- 自动 detect_intent 选 diagram 类型
- 输出 resources[].data_uri 让前端直接 <img> 渲染, 不再依赖前端 mermaid.js
"""
from __future__ import annotations

import json
import logging
import re
from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.multimodal.mermaid import (
    detect_intent,
    get_mermaid_studio,
)

logger = logging.getLogger(__name__)


class MultimodalAgent(BaseAgent):
    """多模态生成师 —— 思维导图 + 代码案例 + PPT"""

    prompt_version = "v2"  # P1-4

    @property
    def name(self) -> str:
        return "multimodal_agent"

    @property
    def description(self) -> str:
        return "生成思维导图、代码案例、PPT 等多模态学习资源"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名多模态教学资源设计专家，擅长把复杂知识拆解为清晰而丰富的可视化教材。\n\n"
            "你可以生成以下类型的资源：\n\n"
            "1. **思维导图** —— 用 Mermaid mindmap 语法，必须做到有深度：\n"
            "   - 至少 5-7 个一级分支，覆盖该主题的核心侧面；\n"
            "   - 每个一级分支下 3-5 个二级节点（具体概念、方法或子模块）；\n"
            "   - 高价值节点可再挂 1-2 个三级节点（关键算法、代表模型、典型案例）；\n"
            "   - 分支名和节点名要具体（例如「Self-Attention」「BPE 分词」「AdamW」），不写「基础概念/核心组件」这种笼统词；\n"
            "2. **代码实操案例** —— 完整可运行的代码 + 详细中文注释，含关键行说明思路；\n"
            "3. **PPT 大纲** —— 结构化的演示文稿内容。\n\n"
            "输出规范：\n"
            "- 思维导图：使用 ```mermaid 代码块。示例格式：\n"
            "  ```mermaid\n"
            "  mindmap\n"
            "    root((主题))\n"
            "      一级分支A\n"
            "        二级节点A1\n"
            "          三级节点\n"
            "        二级节点A2\n"
            "      一级分支B\n"
            "  ```\n"
            "- 代码案例：使用对应语言的代码块，附详细中文注释与运行示例；\n"
            "- PPT：结构化 Markdown，每页用 ## 分隔。\n"
            "- 末尾附上资源元数据：\n"
            '```resource_meta\n'
            '{"type": "mindmap|code|ppt", "title": "...", "language": "python"}\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """生成多模态资源"""
        resource_type = self._detect_resource_type(context.user_input)
        user_prompt = self._build_prompt(context, resource_type)

        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=self._strategy_extra_system(context),
            temperature=0.6,
        )

        meta = self._extract_resource_meta(result)
        actual_type = meta.get("type", resource_type)

        # 2026-07-12：resource 里的 metadata 子字段是前端 attachments 的数据源。
        # 让 code/mermaid_code/data_uri 同时出现在 top-level 和 metadata，
        # 兼容不同前端消费方式。
        resource_meta: dict = {
            "title": meta.get("title", context.user_input[:30]),
        }
        resources = [{
            "type": actual_type,
            "title": resource_meta["title"],
            "format": "markdown",
            "metadata": resource_meta,
        }]

        display_content = result

        # ---- 思维导图 / 图类内容 → 先结构化，再由模板生成安全 Mermaid ----
        if actual_type in ("mindmap", "diagram"):
            try:
                raw_mermaid = self._extract_mermaid_block(result)
                if raw_mermaid:
                    topic, branches, leaves = self._outline_from_mermaid(raw_mermaid)
                else:
                    topic, branches, leaves = self._mindmap_topic(context.user_input), [], {}
                if len(branches) < 2:
                    from backend.app.api.v1.artifacts.multi import _default_mindmap_outline
                    topic = self._mindmap_topic(context.user_input)
                    branches, leaves = _default_mindmap_outline(topic)
                if branches:
                    diagram_kind = detect_intent(context.user_input)
                    studio = get_mermaid_studio()
                    # 不再直接渲染 LLM 裸代码。MindmapNode → template 会清理
                    # 括号、冒号、列表符等 Mermaid 控制字符，避免语法错误图。
                    render = studio.from_concept(topic, branches, leaves)
                    mermaid_code = render.mermaid_code
                    resources[0].update({
                        "format": "image/png",
                        "diagram_kind": diagram_kind,
                        "png_path": render.png_path,
                        "data_uri": render.data_uri,
                        "render_method": render.method,
                        "render_warnings": render.warnings,
                    })
                    resource_meta.update({
                        "mermaid_code": mermaid_code,
                        "data_uri": render.data_uri,
                        "branches": branches,
                        "leaves": leaves,
                        "diagram_kind": diagram_kind,
                        "render_method": render.method,
                    })
                    meta["render_method"] = render.method
                    meta["diagram_kind"] = diagram_kind
                    display_content = (
                        f"## {topic} · 思维导图\n\n"
                        f"已整理为 **{len(branches)} 个一级分支**、"
                        f"**{sum(len(v) for v in leaves.values())} 个知识节点**。"
                        "你可以直接查看下方导图；源码仅放在可折叠区域中。"
                    )
            except Exception as exc:
                logger.warning(f"[MultimodalAgent] mermaid render skip: {exc}")

        # ---- 代码类内容 → 把源码同样塞进 metadata，供前端气泡预览 ----
        if actual_type in ("code", "codeblock"):
            code_block = self._extract_code_block(result)
            if code_block:
                resource_meta["code"] = code_block
                resource_meta["language"] = meta.get("language", "python")

        return self._success(
            content=display_content,
            content_type=actual_type,
            resources=resources,
            metadata=meta,
        )

    @staticmethod
    def _extract_code_block(text: str) -> str:
        """从 markdown 里抽出第一段 ```lang ... ``` 代码块。"""
        m = re.search(r"```(?:\w+)?\s*\n(.*?)\n```", text or "", re.DOTALL)
        return m.group(1).strip() if m else ""

    def _detect_resource_type(self, user_input: str) -> str:
        """根据用户输入推断资源类型 — P1-4 复用 mermaid.detect_intent

        判定顺序:
            1. code 关键词 → "code"  (先于 mermaid, 否则 detect_intent 的 mindmap
               兜底会把 "写段代码" / "做个 PPT" 这类请求吞掉)
            2. ppt 关键词 → "ppt"
            3. 其余 → 走 mermaid.detect_intent (mindmap/flowchart/.../兜底 mindmap)
        """
        if any(kw in user_input for kw in ["代码", "编程", "实现", "code", "demo"]):
            return "code"
        if any(kw in user_input for kw in ["PPT", "演示", "课件", "幻灯片"]):
            return "ppt"
        kind = detect_intent(user_input)
        diagram_kinds = {
            "mindmap", "flowchart", "sequence", "class", "graph",
        }
        if kind in diagram_kinds:
            return "mindmap"  # 统一回 mindmap 类型, 具体 diagram_kind 后续传
        return "mindmap"

    @staticmethod
    def _extract_mermaid_block(text: str) -> str:
        """提取 ```mermaid 代码块"""
        m = re.search(r"```mermaid\s*\n(.*?)\n```", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _mindmap_topic(user_input: str) -> str:
        quoted = re.search(r"[「『\"“]([^」』\"”]{2,60})[」』\"”]", user_input or "")
        if quoted:
            return quoted.group(1).strip()
        if "transformer" in (user_input or "").lower():
            return "Transformer 架构"
        cleaned = re.sub(r"@\S+", "", user_input or "")
        return re.split(r"[，。；;！!?？\n]", cleaned.strip())[0][:40] or "知识主题"

    @staticmethod
    def _outline_from_mermaid(code: str) -> tuple[str, list[str], dict[str, list[str]]]:
        """从 LLM mindmap 代码提取纯文本层级，不携带任何 Mermaid 语法。"""
        rows: list[tuple[int, str]] = []
        topic = "知识主题"
        for raw in (code or "").splitlines():
            if not raw.strip() or raw.strip().lower() == "mindmap":
                continue
            if raw.lstrip().startswith(("%%", "classDef", "style ")):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            label = raw.strip()
            root = re.match(r"root\s*\(\((.*?)\)\)\s*$", label, re.IGNORECASE)
            if root:
                topic = root.group(1).strip() or topic
                rows.append((indent, "__ROOT__"))
                continue
            label = re.sub(r"^[-*+]\s+", "", label)
            # 只剥离 Mermaid 的节点 ID（如 n1[标签]），不能误删
            # "Encoder [B,N,D]" 这类本身含 shape 的知识点名称。
            label = re.sub(r"^[A-Za-z][\w-]*\s*(?=[\[({])", "", label)
            label = label.strip("()[]{}\"' ")
            if label:
                rows.append((indent, label[:80]))

        root_index = next((i for i, (_, text) in enumerate(rows) if text == "__ROOT__"), -1)
        content_rows = rows[root_index + 1:] if root_index >= 0 else rows
        if not content_rows:
            return topic, [], {}
        branch_indent = min(indent for indent, _ in content_rows)
        branches: list[str] = []
        leaves: dict[str, list[str]] = {}
        current = ""
        for indent, label in content_rows:
            if indent == branch_indent:
                current = label
                if current not in leaves and len(branches) < 8:
                    branches.append(current)
                    leaves[current] = []
            elif current and len(leaves[current]) < 6:
                leaves[current].append(label)
        return topic, branches, leaves

    def _build_prompt(self, context: AgentContext, resource_type: str) -> str:
        type_labels = {
            "mindmap": "思维导图（Mermaid mindmap 格式）",
            "code": "代码实操案例（完整可运行代码 + 注释）",
            "ppt": "PPT 大纲（结构化分页内容）",
        }
        parts = [
            f"请生成一份{type_labels.get(resource_type, '学习资源')}：\n",
            f"主题：{context.user_input}\n",
        ]

        if context.profile:
            level = context.profile.get("knowledge_base", {}).get("level", "中等")
            parts.append(f"学生水平：{level}")

        if context.rag_results:
            parts.append("\n## 相关知识参考")
            for doc in context.rag_results[:3]:
                parts.append(doc.get("content", "")[:300])

        return "\n".join(parts)

    def _extract_resource_meta(self, llm_output: str) -> dict:
        import re
        pattern = r"```resource_meta\s*\n(.*?)\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return {}
