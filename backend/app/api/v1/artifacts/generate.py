"""
Artifacts 生成端点 - 5 类资源 POST 路由

赛题需求 2 的 "至少 5 种类型的个性化资源" 全部覆盖:

| 路由                            | 资源类型     | 后端模块                  |
|--------------------------------|--------------|-------------------------|
| POST /generate/pptx            | 讲解 PPT      | services.multimodal.pptx |
| POST /generate/mermaid         | 思维导图等 5 种 | services.multimodal.mermaid |
| POST /generate/code            | 代码案例 + 运行 | services.multimodal.code_sandbox |
| POST /generate/tts             | 朗读音频      | services.multimodal.tts_xunfei |
| POST /generate/manim           | 教学视频     | services.multimodal.manim |

每个端点:
- Pydantic 入参校验 (replace 旧 dict 风格)
- 统一返回 ResourceResult: {resource_id, type, filepath, data_uri?, metadata, duration_ms}
- 失败返回 4xx + 结构化 error
- 自动写入 ArtifactRegistry
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.v1.artifacts.registry import get_artifact_registry


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


# ================================================================
# 通用响应模型
# ================================================================
class ResourceResult(BaseModel):
    """统一资源生成响应"""
    model_config = ConfigDict(extra="allow")

    resource_id: str
    type: str
    filepath: str = ""
    data_uri: str = ""
    method: str = ""        # 实际生成方式 (e.g. mmdc/playwright/placeholder)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str = ""
    success: bool = True


def _make_rid(prefix: str, payload: Any) -> str:
    """构造 deterministic resource_id, 同 payload 复用文件"""
    h = hashlib.sha1(str(payload).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


# ================================================================
# 1. PPTX
# ================================================================
class SlideIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    bullets: List[str] = Field(default_factory=list)
    layout_hint: str = ""
    code_block: str = ""
    visual_intent: str = ""
    narrative_job: str = ""
    speaker_notes: str = ""


class PPTXRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str = ""
    slides: List[SlideIn] = Field(default_factory=list)
    summary: List[str] = Field(default_factory=list)
    review: List[str] = Field(default_factory=list)
    theme_name: str = Field("academic", pattern="^(academic|modern|high_contrast)$")
    resource_id: Optional[str] = None
    session_id: str = ""
    # 由多资源编排层传入，便于资源库明确展示实际内容来源与版式版本。
    content_source: str = ""
    design_version: str = ""
    model_name: str = ""
    outline_source: str = ""
    provider_trace: Dict[str, Any] = Field(default_factory=dict)
    template_path: str = ""


@router.post("/generate/pptx", response_model=ResourceResult)
def generate_pptx(req: PPTXRequest = Body(...)) -> ResourceResult:
    """生成讲解 PPT (走旧 PPTXBuilder facade, 内部转发到新 SlideDeckBuilder)"""
    from backend.app.services.multimodal.pptx_builder import (
        PPTXBuilder, PPTXOutline, SlideContent,
    )
    start = time.perf_counter()

    # 同一主题面向不同学生时，内容、顺序和视觉主题都会变化。只按标题哈希
    # 会让后生成的课件覆盖前一位学生的 registry 记录，看起来“个性化无效”。
    rid_payload = {
        "title": req.title,
        "subtitle": req.subtitle,
        "theme": req.theme_name,
        "slides": [slide.model_dump() for slide in req.slides],
        "summary": req.summary,
        "review": req.review,
        "content_source": req.content_source,
        "design_version": req.design_version,
        "model_name": req.model_name,
        "outline_source": req.outline_source,
        "template_path": req.template_path,
    }
    rid = req.resource_id or _make_rid("pptx", rid_payload)
    slides = [
        SlideContent(
            title=s.title,
            bullets=list(s.bullets),
            layout_hint=s.layout_hint,
            code_block=s.code_block,
            notes="\n".join(filter(None, [
                s.speaker_notes.strip(),
                f"叙事任务：{s.narrative_job}" if s.narrative_job else "",
                f"主视觉：{s.visual_intent}" if s.visual_intent else "",
            ])),
        )
        for s in req.slides
    ]
    outline = PPTXOutline(
        title=req.title, subtitle=req.subtitle,
        slides=slides, summary_points=req.summary,
        review_questions=req.review, theme_name=req.theme_name,
        template_path=req.template_path,
    )
    r = PPTXBuilder().build(outline, rid)
    filepath = r.get("filepath", "")
    if filepath:
        get_artifact_registry().register(
            rid, "pptx", filepath,
            metadata={
                "title": req.title,
                "slides_count": r.get("slides_count", 0),
                "lint_warnings": r.get("lint_warnings", []),
                "theme_name": req.theme_name,
                "content_source": req.content_source,
                "design_version": req.design_version,
                "model_name": req.model_name,
                "outline_source": req.outline_source,
                "provider_trace": req.provider_trace,
                "template_name": Path(req.template_path).stem if req.template_path else "built-in-editorial",
            },
            session_id=req.session_id,
        )
    return ResourceResult(
        resource_id=rid, type="pptx", filepath=filepath,
        method="python-pptx" if filepath else "fallback",
        metadata={
            "slides_count": r.get("slides_count", 0),
            "lint_warnings": r.get("lint_warnings", [])[:5],
            "json_fallback": r.get("json_fallback"),
            "theme_name": req.theme_name,
            "content_source": req.content_source,
            "design_version": req.design_version,
            "model_name": req.model_name,
            "outline_source": req.outline_source,
            "provider_trace": req.provider_trace,
            "template_name": Path(req.template_path).stem if req.template_path else "built-in-editorial",
        },
        success=bool(filepath),
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


# ================================================================
# 2. Mermaid (思维导图 / 流程图 / 时序图 / 类图 / 知识图谱)
# ================================================================
class MermaidConceptRequest(BaseModel):
    """从概念词构建 mindmap (一键 demo 路径)"""
    title: str = Field(..., min_length=1, max_length=80)
    branches: List[str] = Field(..., min_length=1, max_length=8)
    leaves: Dict[str, List[str]] = Field(default_factory=dict)
    session_id: str = ""
    resource_id: Optional[str] = None


class MermaidCodeRequest(BaseModel):
    """从已有 Mermaid 代码渲染"""
    code: str = Field(..., min_length=1, max_length=8000)
    kind: str = Field("mindmap", description="mindmap/flowchart/sequence/class/graph")
    name_hint: str = ""
    session_id: str = ""
    resource_id: Optional[str] = None


def _persist_mermaid_source(resource_id: str, code: str) -> str:
    """Persist Mermaid source when the optional PNG renderer is unavailable."""
    if not str(code or "").strip():
        return ""
    output_dir = Path("data/artifacts/mermaid_source")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{resource_id}.mmd"
    path.write_text(str(code).strip() + "\n", encoding="utf-8")
    return str(path)


@router.post("/generate/mermaid", response_model=ResourceResult)
def generate_mermaid_from_concept(
    req: MermaidConceptRequest = Body(...),
) -> ResourceResult:
    """从主题词 + 分支构建思维导图 (赛题 5 类资源核心)"""
    from backend.app.services.multimodal.mermaid import get_mermaid_studio
    start = time.perf_counter()

    rid = req.resource_id or _make_rid("mermaid", req.title)
    studio = get_mermaid_studio()
    r = studio.from_concept(
        title=req.title, branches=req.branches, leaves=req.leaves,
    )
    filepath = r.png_path or _persist_mermaid_source(rid, r.mermaid_code)
    artifact_type = "mermaid_png" if r.png_path else "mermaid_source"
    if filepath:
        get_artifact_registry().register(
            rid, artifact_type, filepath,
            metadata={
                "kind": r.kind,
                "method": r.method,
                "mermaid_code": r.mermaid_code,
            },
            session_id=req.session_id,
        )
    return ResourceResult(
        resource_id=rid, type=artifact_type,
        filepath=filepath,
        data_uri=r.data_uri or "",
        method=r.method,
        metadata={
            "kind": r.kind,
            "mermaid_code": r.mermaid_code,
            "warnings": r.warnings,
            "validation_passed": r.validation_passed,
        },
        success=bool(filepath),
        error=r.error,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


@router.post("/generate/mermaid-code", response_model=ResourceResult)
def generate_mermaid_from_code(
    req: MermaidCodeRequest = Body(...),
) -> ResourceResult:
    """从 Mermaid 代码渲染 (LLM 已生成完整代码时)"""
    from backend.app.services.multimodal.mermaid import get_mermaid_studio
    start = time.perf_counter()

    rid = req.resource_id or _make_rid("mermaid", req.code[:60])
    studio = get_mermaid_studio()
    r = studio.render_code(req.code, kind=req.kind, name_hint=req.name_hint)
    filepath = r.png_path or _persist_mermaid_source(rid, req.code)
    artifact_type = "mermaid_png" if r.png_path else "mermaid_source"
    if filepath:
        get_artifact_registry().register(
            rid, artifact_type, filepath,
            metadata={"kind": r.kind, "method": r.method},
            session_id=req.session_id,
        )
    return ResourceResult(
        resource_id=rid, type=artifact_type,
        filepath=filepath,
        data_uri=r.data_uri or "",
        method=r.method,
        metadata={
            "kind": r.kind,
            "warnings": r.warnings,
            "validation_passed": r.validation_passed,
        },
        success=bool(filepath),
        error=r.error,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


# ================================================================
# 3. Code Sandbox (代码案例 + 真实运行)
# ================================================================
class CodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=10000)
    language: str = Field("python", description="目前仅支持 python")
    timeout: int = Field(5, ge=1, le=30)
    with_review: bool = True
    session_id: str = ""
    resource_id: Optional[str] = None


@router.post("/generate/code", response_model=ResourceResult)
def execute_code(req: CodeRequest = Body(...)) -> ResourceResult:
    """3 级安全沙箱执行代码并返回结果

    Level 1 AST 静态分析 → Level 2 RestrictedPython → Level 3 subprocess
    """
    from backend.app.services.multimodal.code_sandbox import get_code_sandbox
    start = time.perf_counter()

    rid = req.resource_id or _make_rid("code", req.code[:60])
    sandbox = get_code_sandbox()
    result = sandbox.execute(
        req.code, language=req.language,
        timeout=req.timeout, with_review=req.with_review,
    )

    # 2026-07-12 修复：过去 register 传 filepath="", 触发 /download/{rid}
    # 返回 "file not found for artifact code_xxx"。改为把源码写入
    # data/artifacts/code/{rid}.py，供群聊内的下载/预览按钮使用。
    code_dir = Path("data/artifacts/code")
    code_dir.mkdir(parents=True, exist_ok=True)
    ext = ".py" if req.language == "python" else ".txt"
    code_path = code_dir / f"{rid}{ext}"
    try:
        code_path.write_text(req.code, encoding="utf-8")
        code_filepath = str(code_path)
    except OSError as exc:  # noqa: BLE001
        logger.warning(f"[code] persist source failed: {exc}")
        code_filepath = ""

    get_artifact_registry().register(
        rid, "code_result", code_filepath,
        metadata={
            "code": req.code,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
            "passed": result.passed,
            "execution_level": result.execution_level,
            "review_hints": result.review_hints,
            "security_warnings": result.security_warnings,
            "language": req.language,
        },
        session_id=req.session_id,
    )
    return ResourceResult(
        resource_id=rid, type="code_result", filepath=code_filepath,
        method=f"sandbox-level-{result.execution_level}",
        metadata={
            "code": req.code,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
            "passed": result.passed,
            "execution_level": result.execution_level,
            "review_hints": result.review_hints,
            "security_warnings": result.security_warnings,
            "language": req.language,
        },
        # 2026-07-12：代码沙盒即使 stdout 非零仍算生成成功，
        # 只有当代码语法错/超时/被安全检查拒绝时才算失败。
        # 避免"生成成功但被 registry 标记 success=False"导致前端拿不到。
        success=(not result.error),
        error=result.error or "",
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


# ================================================================
# 4. TTS (朗读音频)
# ================================================================
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=800)
    voice: str = "xiaoyan"
    speed: int = Field(50, ge=0, le=100)
    volume: int = Field(50, ge=0, le=100)
    pitch: int = Field(50, ge=0, le=100)
    session_id: str = ""
    resource_id: Optional[str] = None


@router.post("/generate/tts", response_model=ResourceResult)
def generate_tts(req: TTSRequest = Body(...)) -> ResourceResult:
    """讯飞 TTS 朗读 (失败降级到 Mock MP3)"""
    from backend.app.services.multimodal.tts_xunfei import get_tts_service
    start = time.perf_counter()

    rid = req.resource_id or _make_rid("tts", f"{req.voice}:{req.text[:60]}")
    r = get_tts_service().synthesize(
        text=req.text, resource_id=rid,
        voice=req.voice, speed=req.speed,
        volume=req.volume, pitch=req.pitch,
    )
    if r.filepath:
        get_artifact_registry().register(
            rid, "mp3", r.filepath,
            metadata={
                "voice": req.voice, "text_length": r.text_length,
                "method": r.method, "cached": r.cached,
            },
            session_id=req.session_id,
        )
    return ResourceResult(
        resource_id=rid, type="mp3", filepath=r.filepath or "",
        method=r.method,
        metadata={
            "voice": req.voice,
            "text_length": r.text_length,
            "audio_size": r.audio_size,
            "cached": r.cached,
        },
        success=r.success, error=r.error,
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )


@router.get("/tts/voices")
def list_tts_voices() -> Dict[str, Any]:
    """列出可用音色"""
    from backend.app.services.multimodal.tts_xunfei import XunfeiTTSService
    return {"voices": XunfeiTTSService.list_voices()}


# ================================================================
# 5. Manim 教学视频
# ================================================================
class ManimRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=120)
    template: Optional[str] = Field(
        None, description="concept/comparison/timeline/code/None",
    )
    persona: str = Field(
        "serious", description="serious/humorous/passionate/calm/curious",
    )
    render: bool = Field(True, description="实际跑 Manim 渲染 (慢, 演示前预渲染)")
    session_id: str = ""
    resource_id: Optional[str] = None


@router.post("/generate/manim", response_model=ResourceResult)
def generate_manim(req: ManimRequest = Body(...)) -> ResourceResult:
    """Manim DSL → Python 代码 → 视频 (Phase 3 Innovation 2)"""
    from backend.app.agents.base import AgentContext
    from backend.app.services.multimodal.manim.lecturer import AILecturerAgent
    start = time.perf_counter()

    rid = req.resource_id or _make_rid(
        "manim", f"{req.template}:{req.persona}:{req.topic}",
    )
    # 视频二级 Manim 降级也必须使用讯飞专用客户端；讯飞暂不可用时只让
    # AILecturer 使用其本地模板，不能重新继承全局 DeepSeek 配置。
    from backend.app.core.llm_client import create_xunfei_spark_client
    agent = AILecturerAgent(
        llm_client=create_xunfei_spark_client(allow_local_fallback=True),
    )
    ctx = AgentContext(
        user_input=req.topic,
        extra={
            "template": req.template,
            "persona": req.persona,
            "render": req.render,
        },
    )
    resp = asyncio.run(agent.execute(ctx))
    render = resp.metadata.get("render_result", {}) or {}
    video_path = render.get("video_path", "")

    artifact_type = "manim_video" if video_path else "manim_code"
    get_artifact_registry().register(
        rid, artifact_type, video_path,
        metadata={
            "topic": req.topic,
            "template": req.template,
            "persona": req.persona,
            "method": render.get("method"),
            "generated_code": (resp.metadata or {}).get(
                "generated_code", "",
            )[:5000],
        },
        session_id=req.session_id,
    )
    return ResourceResult(
        resource_id=rid, type=artifact_type, filepath=video_path,
        method=render.get("method") or "code_only",
        metadata={
            "topic": req.topic,
            "template": req.template,
            "persona": req.persona,
            "generated_code": (resp.metadata or {}).get(
                "generated_code", "",
            )[:5000],
            "render_details": render,
        },
        success=resp.success and (bool(video_path) or not req.render),
        error=resp.error or "",
        duration_ms=round((time.perf_counter() - start) * 1000, 2),
    )
