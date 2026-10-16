"""
视频生成服务 — 三级降级

Level 1: 讯飞数字人视频大模型 API（异步任务 → 轮询 → 下载 MP4）
Level 2: 动态幻灯片（Pillow 精美幻灯片 + ffmpeg + 按段落 TTS 音画同步）
Level 3: 静态头像 + TTS + ffmpeg（兜底）

用法:
    svc = get_video_service()
    result = svc.synthesize("欢迎学习机器学习", resource_id="res_001", agent_key="tutor")
    print(result.filepath)
"""
from __future__ import annotations

import hashlib
import hmac
import base64
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path("data/artifacts/video")
FFMPEG_TIMEOUT = 120
NARRATION_AUDIO_FILTER = (
    "highpass=f=70,lowpass=f=13500,"
    "equalizer=f=180:t=q:w=1:g=1.5,"
    "acompressor=threshold=0.125:ratio=2:attack=20:release=250:makeup=1.4,"
    "loudnorm=I=-16:LRA=9:TP=-1.5,alimiter=limit=0.95"
)


def _prepare_speech_text(text: str) -> str:
    """把 Markdown/公式式讲稿整理成更自然的中文旁白文本。"""
    speech = str(text or "")
    replacements = {
        "Self-Attention": "自注意力",
        "self-attention": "自注意力",
        "Multi-Head Attention": "多头注意力",
        "Q/K/V": "Q、K、V",
        "QKV": "Q、K、V",
        "sqrt(d_k)": "根号 d k",
        "softmax": "Softmax",
    }
    for source, target in replacements.items():
        speech = speech.replace(source, target)
    speech = re.sub(r"```[\s\S]*?```", " 代码示例请查看画面。 ", speech)
    speech = re.sub(r"`([^`]+)`", r"\1", speech)
    speech = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", speech)
    speech = re.sub(r"^[#>*+\-]+\s*", "", speech, flags=re.MULTILINE)
    speech = re.sub(r"\*\*|__|~~", "", speech)
    # 教学转折词后补短停顿，让神经网络音色更接近自然讲解，而不是连续念稿。
    for marker in ("首先", "其次", "然后", "接下来", "最后", "例如", "也就是说"):
        speech = re.sub(rf"{marker}(?![，。！？；：])", f"{marker}，", speech)
    speech = re.sub(r"(?<!自)注意(?![，。！？；：力])", "注意，", speech)
    speech = re.sub(r"([。！？；])(?=\S)", r"\1 ", speech)
    speech = re.sub(r"\s+", " ", speech).strip()
    return speech


def _leading_black_end(detection_log: str, max_trim_seconds: float = 3.0) -> float:
    """从 ffmpeg blackdetect 日志提取开头黑场结束时间。"""
    for match in re.finditer(
        r"black_start:(?P<start>\d+(?:\.\d+)?)\s+black_end:(?P<end>\d+(?:\.\d+)?)",
        str(detection_log or ""),
    ):
        start = float(match.group("start"))
        end = float(match.group("end"))
        if start <= 0.05 and 0.05 < end <= max_trim_seconds:
            return end
    return 0.0

# ================================================================
# Agent 形象配置
# ================================================================
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_AVATAR_DIR = _PROJECT_ROOT / "frontend" / "public" / "avatars"

AGENT_VIDEO_CATALOG: Dict[str, Dict[str, Any]] = {
    "planner": {
        "name": "智狐", "title": "学习规划师",
        "avatar_path": str(_AVATAR_DIR / "zhihu.png"),
        "voice": "xiaofeng", "accent_color": "#ea5a1a",
        "bg_color": (234, 90, 26), "description": "适合路径规划、学习建议",
    },
    "tutor": {
        "name": "智灵", "title": "知识讲师",
        "avatar_path": str(_AVATAR_DIR / "zhiling.png"),
        "voice": "xiaoyan", "accent_color": "#2f9f6b",
        "bg_color": (47, 159, 107), "description": "适合知识点讲解",
    },
    "content": {
        "name": "阿匠", "title": "内容工匠",
        "avatar_path": str(_AVATAR_DIR / "ajiang.png"),
        "voice": "xiaokun", "accent_color": "#d89229",
        "bg_color": (216, 146, 41), "description": "适合资料导读",
    },
    "quiz": {
        "name": "小龙", "title": "小龙挑战",
        "avatar_path": str(_AVATAR_DIR / "xiaolong.png"),
        "voice": "xiaoxin", "accent_color": "#8f5b32",
        "bg_color": (143, 91, 50), "description": "适合练习题讲解",
    },
    "evaluation": {
        "name": "团团", "title": "熊猫评分",
        "avatar_path": str(_AVATAR_DIR / "tuantuan.png"),
        "voice": "xiaomeng", "accent_color": "#4a8c78",
        "bg_color": (74, 140, 120), "description": "适合评估反馈",
    },
    "safety": {
        "name": "球球", "title": "刺猬守护",
        "avatar_path": str(_AVATAR_DIR / "qiuqiu.png"),
        "voice": "zhixiang", "accent_color": "#3b7f88",
        "bg_color": (59, 127, 136), "description": "适合安全提示",
    },
}
DEFAULT_AGENT = "tutor"


@dataclass
class VideoResult:
    filepath: str = ""
    method: str = ""
    duration_ms: float = 0.0
    agent_key: str = DEFAULT_AGENT
    agent_name: str = ""
    text_length: int = 0
    video_size: int = 0
    audio_path: str = ""
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.filepath) and not self.error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath, "method": self.method,
            "duration_ms": round(self.duration_ms, 1),
            "agent_key": self.agent_key, "agent_name": self.agent_name,
            "text_length": self.text_length, "video_size": self.video_size,
            "audio_path": self.audio_path, "error": self.error,
        }


# ================================================================
# Level 1: 讯飞数字人视频 API 客户端
# ================================================================
VID_HOST = "vms.cn-huadong-1.xf-yun.com"
VID_GENERATE_PATH = "/v1/private/video/generate"
VID_QUERY_PATH = "/v1/private/video/query"
VID_POLL_INTERVAL = 5  # 轮询间隔秒数


class XunfeiDigitalHumanClient:
    """讯飞数字人视频大模型 API 客户端"""

    def __init__(self, app_id: str, api_key: str, api_secret: str, timeout: int = 180):
        self._app_id = app_id
        self._api_key = api_key
        self._api_secret = api_secret
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self._app_id and self._api_key and self._api_secret)

    def _build_auth_url(self, path: str, method: str = "POST") -> str:
        now = datetime.now(timezone.utc)
        date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        signing = f"host: {VID_HOST}\ndate: {date}\n{method} {path} HTTP/1.1"
        sig = base64.b64encode(
            hmac.new(self._api_secret.encode(), signing.encode(), hashlib.sha256).digest()
        ).decode()
        auth_origin = (
            f'api_key="{self._api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{sig}"'
        )
        auth = base64.b64encode(auth_origin.encode()).decode()
        params = urlencode({"authorization": auth, "date": date, "host": VID_HOST})
        return f"https://{VID_HOST}{path}?{params}"

    def generate_video(self, prompt: str, word_count: int = 120) -> Optional[Dict]:
        """提交数字人视频生成任务并轮询结果

        Returns:
            payload dict (含 video/audio/image URL)，失败返回 None
        """
        import requests as req

        # Step 1: 创建任务
        url = self._build_auth_url(VID_GENERATE_PATH, "POST")
        body = {
            "header": {"app_id": self._app_id},
            "parameter": {"avatar": {"prompt": prompt, "word_count": word_count}},
        }
        try:
            resp = req.post(url, json=body, timeout=30,
                            headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                logger.warning(f"[VID] generate failed: {resp.status_code} {resp.text[:200]}")
                return None
            data = resp.json()
            task_id = data.get("header", {}).get("task_id", "")
            code = data.get("header", {}).get("code", -1)
            if code != 0 or not task_id:
                logger.warning(f"[VID] generate error: code={code}, msg={data.get('header', {}).get('message')}")
                return None
            logger.info(f"[VID] task created: {task_id}")
        except Exception as exc:
            logger.error(f"[VID] generate exception: {exc}")
            return None

        # Step 2: 轮询
        query_url = self._build_auth_url(VID_QUERY_PATH, "POST")
        query_body = {"header": {"app_id": self._app_id, "task_id": task_id}}
        deadline = time.time() + self._timeout

        while time.time() < deadline:
            time.sleep(VID_POLL_INTERVAL)
            try:
                resp = req.post(query_url, json=query_body, timeout=15,
                                headers={"Content-Type": "application/json"})
                if resp.status_code != 200:
                    logger.warning(f"[VID] query failed: {resp.status_code}")
                    continue
                qdata = resp.json()
                status = qdata.get("header", {}).get("task_status", "")
                logger.info(f"[VID] polling: status={status}")

                if status in ("3", "4"):
                    payload = qdata.get("payload", {})
                    if payload and payload.get("video"):
                        logger.info(f"[VID] video ready: {payload['video'][:80]}")
                        return payload
                    if status == "4":
                        logger.warning("[VID] task completed but no video URL")
                        return None
            except Exception as exc:
                logger.warning(f"[VID] query exception: {exc}")

        logger.warning(f"[VID] polling timeout ({self._timeout}s)")
        return None

    @staticmethod
    def download_file(url: str, dest_path: str) -> bool:
        import requests as req
        try:
            resp = req.get(url, timeout=60, stream=True)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                return True
        except Exception as exc:
            logger.warning(f"[VID] download failed: {exc}")
        return False


# ================================================================
# Level 2: 动态幻灯片生成器
# ================================================================
@dataclass
class TextSegment:
    """一段讲解文本及其对应的幻灯片信息"""
    heading: str
    content_lines: List[str]
    raw_text: str          # 该段的完整原文（用于 TTS 朗读）
    audio_path: str = ""   # 该段 TTS 音频路径
    duration: float = 0.0  # 该段音频时长（秒）
    is_title: bool = False # 是否是标题页
    visual_cue: str = ""   # 本段画面焦点提示（由讲稿模型生成，只展示不朗读）


class SlideGenerator:
    """用 Pillow 生成精美教学幻灯片 PNG

    设计要素：
    - 径向渐变背景（深色 + Agent 主题色微染）
    - 左侧渐变彩条
    - 标题胶囊（半透明圆角矩形背景）
    - 彩色菱形项目符号
    - 底部进度圆点
    - Agent 头像圆形 + 名称
    - 装饰几何图形（角落半透明圆）
    """

    WIDTH = 1280
    HEIGHT = 720

    def __init__(self):
        self._font_title_xl = self._load_font(44, bold=True)
        self._font_title = self._load_font(34, bold=True)
        self._font_body = self._load_font(27)
        self._font_body_sm = self._load_font(22)
        self._font_small = self._load_font(18)
        self._font_agent = self._load_font(20, bold=True)
        self._font_page = self._load_font(16)

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> Any:
        from PIL import ImageFont
        candidates = [
            ("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
        ]
        for fp in candidates:
            if Path(fp).exists():
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    # ---- 渐变背景 ----
    @staticmethod
    def _make_gradient_bg(
        width: int, height: int,
        bg_dark: Tuple[int, int, int] = (18, 20, 30),
        tint: Tuple[int, int, int] = (47, 159, 107),
        tint_strength: float = 0.15,
    ) -> Any:
        """生成径向渐变背景：中心略亮，边缘暗，叠加主题色微染"""
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (width, height), bg_dark)
        draw = ImageDraw.Draw(img)
        cx, cy = width // 2, height // 2
        max_dist = int((cx ** 2 + cy ** 2) ** 0.5)
        # 用椭圆条带模拟径向渐变（每隔 4px 一条）
        for r in range(max_dist, 0, -4):
            ratio = 1 - r / max_dist
            r_val = int(bg_dark[0] + (tint[0] - bg_dark[0]) * tint_strength * ratio * 0.8)
            g_val = int(bg_dark[1] + (tint[1] - bg_dark[1]) * tint_strength * ratio * 0.8)
            b_val = int(bg_dark[2] + (tint[2] - bg_dark[2]) * tint_strength * ratio * 0.8)
            r_val = max(0, min(255, r_val))
            g_val = max(0, min(255, g_val))
            b_val = max(0, min(255, b_val))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(r_val, g_val, b_val))
        return img

    @staticmethod
    def _make_alpha_rect(
        width: int, height: int,
        color: Tuple[int, int, int], alpha: int,
        radius: int = 0,
    ) -> Any:
        """生成半透明圆角矩形（RGBA）"""
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        if radius > 0:
            draw.rounded_rectangle([0, 0, width - 1, height - 1],
                                   radius=radius, fill=(*color, alpha))
        else:
            draw.rectangle([0, 0, width - 1, height - 1], fill=(*color, alpha))
        return img

    @staticmethod
    def _draw_diamond(draw: Any, cx: int, cy: int, size: int, fill: Any):
        """画菱形项目符号"""
        pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
        draw.polygon(pts, fill=fill)

    @staticmethod
    def _draw_circle(draw: Any, cx: int, cy: int, r: int, fill: Any):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
        hex_str = hex_str.lstrip("#")
        if len(hex_str) == 6:
            return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
        return (47, 159, 107)

    @staticmethod
    def _clean_display_text(text: str) -> str:
        """移除不会被幻灯片正确呈现的标记，但保留全部可读内容。"""
        cleaned = str(text or "")
        cleaned = re.sub(r"```[\s\S]*?```", "代码示例请查看配套资源。", cleaned)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", cleaned)
        cleaned = re.sub(r"^[#>*+\-]+\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"\*\*|__|~~", "", cleaned)
        cleaned = re.sub(r"[\t\r ]+", " ", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        return cleaned.strip()

    @staticmethod
    def _split_visual_units(text: str, max_chars: int = 34) -> List[str]:
        """把讲稿完整拆成适合一行或两行展示的语义单元，不静默截字。"""
        cleaned = SlideGenerator._clean_display_text(text)
        sentences = [
            part.strip()
            for part in re.split(r"(?<=[。！？!?；;])\s*|\n+", cleaned)
            if part.strip()
        ]
        if not sentences:
            sentences = [cleaned] if cleaned else []

        units: List[str] = []
        for sentence in sentences:
            remaining = sentence
            while len(remaining) > max_chars:
                window = remaining[: max_chars + 1]
                cut = max(
                    window.rfind("，"), window.rfind("、"), window.rfind("："),
                    window.rfind(","), window.rfind(":"), window.rfind(" "),
                )
                if cut < max(12, max_chars // 2):
                    cut = max_chars
                else:
                    cut += 1
                units.append(remaining[:cut].strip())
                remaining = remaining[cut:].strip()
            if remaining:
                units.append(remaining)
        return units

    @staticmethod
    def _wrap_by_pixels(draw: Any, text: str, font: Any, max_width: int) -> List[str]:
        """按真实像素宽度换行，兼容中英文与公式符号。"""
        lines: List[str] = []
        current = ""
        for char in str(text or ""):
            candidate = current + char
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if current and bbox[2] - bbox[0] > max_width:
                lines.append(current.rstrip())
                current = char.lstrip()
            else:
                current = candidate
        if current or not lines:
            lines.append(current.rstrip())
        return lines

    def generate_slides(
        self, segments: List[TextSegment], agent: Dict[str, Any],
    ) -> List[str]:
        """为每个 segment 生成一张幻灯片 PNG

        Returns:
            PNG 文件路径列表（与 segments 一一对应）
        """
        from PIL import Image, ImageDraw, ImageFilter

        slides: List[str] = []
        total = len(segments)
        agent_name = agent.get("name", "")
        agent_title = agent.get("title", "")
        accent_hex = agent.get("accent_color", "#2f9f6b")
        bg_color = agent.get("bg_color", (47, 159, 107))
        avatar_path = agent.get("avatar_path", "")

        accent = self._hex_to_rgb(accent_hex)

        # 预生成背景（所有幻灯片共用同一渐变背景）
        base_bg = self._make_gradient_bg(self.WIDTH, self.HEIGHT, tint=bg_color)

        # 加载头像（如有）
        avatar_img = None
        if avatar_path and Path(avatar_path).exists():
            try:
                avatar_img = Image.open(avatar_path).convert("RGBA")
                size = 48
                avatar_img = avatar_img.resize((size, size), Image.LANCZOS)
                mask = Image.new("L", (size, size), 0)
                md = ImageDraw.Draw(mask)
                md.ellipse([0, 0, size - 1, size - 1], fill=255)
                avatar_img.putalpha(mask)
            except Exception:
                avatar_img = None

        for idx, seg in enumerate(segments):
            # 复制背景
            img = base_bg.copy().convert("RGBA")
            draw = ImageDraw.Draw(img, "RGBA")

            # ---- 左侧渐变彩条 ----
            bar_w = 6
            for y in range(self.HEIGHT):
                ratio = y / self.HEIGHT
                r_val = int(accent[0] * (1 - ratio * 0.4))
                g_val = int(accent[1] * (1 - ratio * 0.4))
                b_val = int(accent[2] * (1 - ratio * 0.4))
                draw.line([(0, y), (bar_w, y)], fill=(r_val, g_val, b_val))

            # ---- 装饰半透明圆（右上角 + 右下角） ----
            deco = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            deco_draw = ImageDraw.Draw(deco)
            deco_draw.ellipse([self.WIDTH - 200, -80, self.WIDTH + 80, 200],
                              fill=(*accent, 15))
            deco_draw.ellipse([self.WIDTH - 120, self.HEIGHT - 180, self.WIDTH + 60, self.HEIGHT + 60],
                              fill=(*accent, 10))
            deco = deco.filter(ImageFilter.GaussianBlur(radius=30))
            img = Image.alpha_composite(img, deco)
            draw = ImageDraw.Draw(img, "RGBA")

            if seg.is_title:
                self._render_title_slide(draw, img, seg, agent, accent, avatar_img, idx, total)
            else:
                self._render_content_slide(draw, img, seg, agent, accent, avatar_img, idx, total)

            # ---- 底部进度圆点 ----
            dot_y = self.HEIGHT - 28
            dot_start_x = self.WIDTH // 2 - (total - 1) * 12
            for d in range(total):
                cx = dot_start_x + d * 24
                if d == idx:
                    self._draw_circle(draw, cx, dot_y, 5, accent)
                else:
                    self._draw_circle(draw, cx, dot_y, 3, (80, 80, 100, 180))

            # 保存
            slide_path = str(ARTIFACTS_DIR / f"_slide_{idx:02d}.png")
            img.convert("RGB").save(slide_path, "PNG")
            slides.append(slide_path)
            logger.debug(f"[Slide] generated slide {idx + 1}/{total}: {seg.heading}")

        return slides

    def _render_title_slide(
        self, draw: Any, img: Any, seg: TextSegment, agent: Dict[str, Any],
        accent: Tuple[int, int, int], avatar_img: Any, idx: int, total: int,
    ):
        """渲染标题页"""
        # ---- 标题胶囊 ----
        title = seg.heading
        font = self._font_title_xl
        # 标题必须完整显示；实际主题过长时按宽度逐级缩小，而不是让右侧字符消失。
        for size in (44, 40, 36, 32, 28):
            candidate = self._load_font(size, bold=True)
            candidate_box = draw.textbbox((0, 0), title, font=candidate)
            font = candidate
            if candidate_box[2] - candidate_box[0] <= self.WIDTH - 180:
                break
        bbox = draw.textbbox((0, 0), title, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pill_x = (self.WIDTH - tw) // 2 - 30
        pill_y = 200
        pill_w = tw + 60
        pill_h = th + 40
        # 半透明圆角矩形
        pill_overlay = self._make_alpha_rect(pill_w, pill_h, accent, 30, radius=pill_h // 2)
        img.paste(pill_overlay, (pill_x, pill_y), pill_overlay)
        # 标题文字
        draw.text((pill_x + 30, pill_y + 20), title, fill=(255, 255, 255), font=font)

        # ---- 副标题/简介 ----
        sub_y = pill_y + pill_h + 40
        for line in seg.content_lines[:3]:
            wrapped = self._wrap_by_pixels(
                draw, line, self._font_body, self.WIDTH - 260,
            )
            for wl in wrapped:
                bbox2 = draw.textbbox((0, 0), wl, font=self._font_body)
                w2 = bbox2[2] - bbox2[0]
                draw.text(((self.WIDTH - w2) // 2, sub_y), wl,
                          fill=(200, 200, 215), font=self._font_body)
                sub_y += 36
            sub_y += 8

        # ---- Agent 信息（底部居中） ----
        agent_y = self.HEIGHT - 100
        agent_text = f"{agent.get('name', '')}  ·  {agent.get('title', '')}"
        bbox3 = draw.textbbox((0, 0), agent_text, font=self._font_agent)
        aw = bbox3[2] - bbox3[0]
        ax = (self.WIDTH - aw) // 2
        if avatar_img:
            img.paste(avatar_img, (ax - 60, agent_y - 8), avatar_img)
            draw.ellipse([ax - 62, agent_y - 10, ax - 14, agent_y + 38],
                         outline=accent, width=2)
            draw.text((ax, agent_y), agent_text, fill=accent, font=self._font_agent)
        else:
            self._draw_circle(draw, ax - 20, agent_y + 12, 8, accent)
            draw.text((ax, agent_y), agent_text, fill=accent, font=self._font_agent)

    def _render_content_slide(
        self, draw: Any, img: Any, seg: TextSegment, agent: Dict[str, Any],
        accent: Tuple[int, int, int], avatar_img: Any, idx: int, total: int,
    ):
        """渲染内容页 — 带段落编号、卡片式要点布局"""
        margin_x = 70
        margin_top = 50

        # ---- 段落编号徽章 ----
        badge_size = 44
        badge_x = margin_x
        badge_y = margin_top
        # 圆形编号背景
        badge_overlay = self._make_alpha_rect(
            badge_size, badge_size, accent, 40, radius=badge_size // 2,
        )
        img.paste(badge_overlay, (badge_x, badge_y), badge_overlay)
        badge_text = f"{idx:02d}"
        bbox_badge = draw.textbbox((0, 0), badge_text, font=self._font_title)
        bw = bbox_badge[2] - bbox_badge[0]
        bh = bbox_badge[3] - bbox_badge[1]
        draw.text(
            (badge_x + (badge_size - bw) // 2, badge_y + (badge_size - bh) // 2 - 2),
            badge_text, fill=(255, 255, 255), font=self._font_title,
        )

        # ---- 标题区域 ----
        title = seg.heading
        font = self._font_title
        title_x = badge_x + badge_size + 16
        bbox = draw.textbbox((0, 0), title, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        title_y = badge_y + (badge_size - th) // 2 - 2
        # 标题文字
        draw.text((title_x, title_y), title, fill=(255, 255, 255), font=font)
        # 分隔线
        line_y = badge_y + badge_size + 18
        draw.rectangle([margin_x, line_y, self.WIDTH - margin_x, line_y + 2],
                        fill=(*accent, 80))

        # ---- 内容区域：卡片式要点 ----
        content_y = line_y + 28

        # ---- 画面焦点提示（讲稿模型生成的 visual_cue，主题色强调） ----
        if seg.visual_cue:
            cue_text = f"◆ 本段看点：{seg.visual_cue}"
            cue_font = self._font_body_sm
            cue_lines = self._wrap_by_pixels(
                draw, cue_text, cue_font, self.WIDTH - margin_x * 2 - 20,
            )[:1]
            for cue_line in cue_lines:
                draw.text((margin_x + 4, content_y), cue_line,
                          fill=accent, font=cue_font)
                content_y += 30
            content_y += 6
        max_y = self.HEIGHT - 110
        indent = margin_x + 32
        line_spacing = 40
        card_padding_v = 8
        card_padding_h = 16

        for line_idx, line in enumerate(seg.content_lines):
            if content_y > max_y:
                break
            wrapped = self._wrap_by_pixels(
                draw, line, self._font_body, self.WIDTH - indent - margin_x - 20,
            )
            # 计算卡片高度
            card_height = len(wrapped) * line_spacing + card_padding_v * 2
            if content_y + card_height > max_y:
                # 空间不够，不加卡片背景，直接渲染
                for wi, wl in enumerate(wrapped):
                    if content_y > max_y:
                        break
                    if wi == 0:
                        self._draw_diamond(draw, margin_x + 10, content_y + 14,
                                           6, accent)
                    draw.text((indent, content_y), wl,
                              fill=(228, 230, 240), font=self._font_body)
                    content_y += line_spacing
                content_y += 6
                continue

            # 半透明卡片背景
            card_w = self.WIDTH - margin_x * 2 - 10
            card_overlay = self._make_alpha_rect(
                card_w, card_height, (255, 255, 255), 12, radius=10,
            )
            img.paste(card_overlay, (margin_x + 5, content_y - card_padding_v),
                      card_overlay)

            text_y = content_y
            for wi, wl in enumerate(wrapped):
                if wi == 0:
                    self._draw_diamond(draw, margin_x + 18, text_y + 14,
                                       6, accent)
                draw.text((indent + 8, text_y), wl,
                          fill=(235, 238, 248), font=self._font_body)
                text_y += line_spacing
            content_y += card_height + 4

        # ---- 页码（左下角） ----
        page_text = f"{idx + 1} / {total}"
        draw.text((margin_x, self.HEIGHT - 45), page_text,
                  fill=(120, 125, 140), font=self._font_page)

        # ---- Agent 信息（右下角） ----
        agent_y = self.HEIGHT - 70
        agent_text = f"{agent.get('name', '')}"
        if avatar_img:
            img.paste(avatar_img, (self.WIDTH - margin_x - 48, agent_y - 4), avatar_img)
            draw.ellipse([self.WIDTH - margin_x - 50, agent_y - 6,
                          self.WIDTH - margin_x - 2, agent_y + 42],
                         outline=accent, width=2)
            draw.text((self.WIDTH - margin_x - 58, agent_y + 50), agent_text,
                      fill=(150, 150, 165), font=self._font_page)
        else:
            self._draw_circle(draw, self.WIDTH - margin_x - 20, agent_y + 12,
                              6, accent)
            draw.text((self.WIDTH - margin_x - 10, agent_y), agent_text,
                      fill=(150, 150, 165), font=self._font_page)

    # ---- 文本拆分 ----
    @staticmethod
    def split_text(text: str, topic: str = "") -> List[TextSegment]:
        """将讲解文本拆分为 TextSegment 列表

        支持三种讲稿格式：
        1. Kimi 结构化 JSON：{"sections": [{"title", "slide_lines", "narration"}]}
           → slide_lines 直接作为幻灯片要点，narration 作为 TTS 朗读文本
        2. 【段落标题】格式：按段落标记拆分分镜
        3. 传统纯文本：按句拆分后每 4 句一组
        """
        clean_topic = SlideGenerator._clean_display_text(topic)

        # ---- 优先检测 JSON 格式（Kimi 结构化输出） ----
        import json as _json
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                data = _json.loads(stripped)
                sections = data.get("sections") if isinstance(data, dict) else None
                if isinstance(sections, list) and len(sections) >= 2:
                    segments: List[TextSegment] = []
                    for sec in sections:
                        if not isinstance(sec, dict):
                            continue
                        title = str(sec.get("title") or "").strip()[:40]
                        slide_lines = [
                            str(s).strip()[:80]
                            for s in sec.get("slide_lines", [])
                            if str(s).strip()
                        ]
                        narration = str(sec.get("narration") or "").strip()
                        if not (title and slide_lines and narration):
                            continue
                        # 每个 section 生成一张幻灯片：
                        # - heading = 段落标题
                        # - content_lines = slide_lines（给学生看的要点）
                        # - raw_text = narration（给 TTS 读的完整讲解）
                        segments.append(TextSegment(
                            heading=title,
                            content_lines=slide_lines[:6],
                            raw_text=narration[:1200],
                            is_title=(len(segments) == 0),
                            visual_cue=str(sec.get("visual_cue") or "").strip()[:40],
                        ))
                    if segments:
                        return segments
            except (_json.JSONDecodeError, TypeError):
                pass  # 不是有效 JSON，继续尝试其他格式

        # ---- 检测【段落标题】格式 ----
        section_pattern = re.compile(r"【(.+?)】")
        has_sections = bool(section_pattern.search(text))

        if has_sections:
            raw_sections: List[Tuple[str, str]] = []
            for m in section_pattern.finditer(text):
                sec_title = m.group(1).strip()
                body_start = m.end()
                next_match = section_pattern.search(text, body_start)
                body_end = next_match.start() if next_match else len(text)
                body = text[body_start:body_end].strip()
                if body:
                    raw_sections.append((sec_title, body))
            intro = text[:section_pattern.search(text).start()].strip() if section_pattern.search(text) else ""
            segments = []
            if intro:
                intro_units = SlideGenerator._split_visual_units(intro)
                if intro_units:
                    title = clean_topic[:30] if clean_topic else intro_units[0][:24]
                    segments.append(TextSegment(
                        heading=title,
                        content_lines=intro_units[:4],
                        raw_text=f"{title}。{''.join(intro_units[:4])}",
                        is_title=True,
                    ))
            for sec_title, body in raw_sections:
                units = SlideGenerator._split_visual_units(body)
                if not units:
                    continue
                page_groups = [units[i:i + 4] for i in range(0, len(units), 4)]
                for _idx, lines in enumerate(page_groups):
                    heading = sec_title if _idx == 0 else f"{sec_title}（续）"
                    segments.append(TextSegment(
                        heading=heading,
                        content_lines=lines,
                        raw_text=f"{heading}。{''.join(lines)}",
                        is_title=False,
                    ))
            if segments:
                return segments

        # ---- 传统纯文本：按句拆分后每 4 句一组 ----
        units = SlideGenerator._split_visual_units(text)
        if not units:
            return []

        title = clean_topic[:30] if clean_topic else units[0][:24]
        first_lines = units[:2]
        segments = [TextSegment(
            heading=title,
            content_lines=first_lines,
            raw_text=(
                "" if title and title.lower() in "".join(first_lines).lower()
                else f"{title}。"
            ) + "".join(first_lines),
            is_title=True,
        )]

        remaining = units[2:]
        page_groups = [remaining[i:i + 4] for i in range(0, len(remaining), 4)]
        for page_index, lines in enumerate(page_groups, 1):
            joined = "".join(lines)
            has_caution = bool(re.search(r"(?<!自)注意(?!力)", joined))
            if has_caution or any(keyword in joined for keyword in ("误区", "避免", "容易")):
                heading = "容易出错的地方"
            elif any(keyword in joined for keyword in ("例如", "例子", "场景")):
                heading = "示例拆解"
            elif page_index == len(page_groups):
                heading = "自测与总结"
            else:
                heading = f"关键步骤 {page_index}"
            segments.append(TextSegment(
                heading=heading,
                content_lines=lines,
                raw_text=f"{heading}。{joined}",
                is_title=False,
            ))

        return segments


# ================================================================
# 主服务
# ================================================================
class AgentVideoService:
    """视频生成服务 — 三级降级"""

    def __init__(self):
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        self._slide_gen = SlideGenerator()
        self._dh_client = self._init_dh_client()

    def _init_dh_client(self) -> Optional[XunfeiDigitalHumanClient]:
        try:
            from backend.app.core.config import get_config
            xf = get_config().xunfei
            if xf.vid_available:
                return XunfeiDigitalHumanClient(
                    xf.vid_app_id, xf.vid_api_key, xf.vid_api_secret, xf.vid_timeout,
                )
        except Exception as exc:
            logger.debug(f"[Video] DH client init failed: {exc}")
        return None

    @property
    def digital_human_available(self) -> bool:
        return self._dh_client is not None and self._dh_client.available

    # ---- 公共入口 ----
    def synthesize(
        self, text: str, resource_id: str, agent_key: str = DEFAULT_AGENT,
        voice: Optional[str] = None, topic: str = "",
    ) -> VideoResult:
        start = time.perf_counter()

        if not text or not text.strip():
            return VideoResult(method="error", error="文本为空",
                               duration_ms=(time.perf_counter() - start) * 1000)

        agent = AGENT_VIDEO_CATALOG.get(agent_key, AGENT_VIDEO_CATALOG[DEFAULT_AGENT])

        # ---- Level 1: 讯飞数字人 API ----
        # 该接口单次 prompt 上限为 300 字。过去这里静默截断长讲稿，导致
        # 完整课程只剩一个简单开场。长内容改走动态分镜 + 讯飞 TTS，保留
        # 全部讲稿，并继续使用逐页音画同步链路。
        prepared_text = _prepare_speech_text(text)
        if self.digital_human_available and len(prepared_text) <= 300:
            result = self._gen_with_digital_human(text, resource_id, agent)
            if result and result.success:
                return result
        elif self.digital_human_available:
            logger.info(
                "[Video] 讲稿 %s 字超过数字人单任务上限，改用完整动态分镜",
                len(prepared_text),
            )

        # ---- Level 2: 动态幻灯片 ----
        result = self._gen_with_slides(text, resource_id, agent, voice, topic)
        if result and result.success:
            return result

        # ---- Level 3: 静态头像 ----
        result = self._gen_with_static_avatar(text, resource_id, agent, voice)
        if result:
            return result

        return VideoResult(
            method="error", error="所有视频生成方案均失败",
            agent_key=agent_key, agent_name=agent.get("name", ""),
            duration_ms=(time.perf_counter() - start) * 1000,
        )

    # ---- Level 1: 数字人 ----
    def _gen_with_digital_human(
        self, text: str, resource_id: str, agent: Dict[str, Any],
    ) -> Optional[VideoResult]:
        start = time.perf_counter()
        logger.info("[Video] Level 1: 讯飞数字人 API")
        try:
            # 讯飞数字人 API 限制 prompt ≤ 300 字符，过去传 500 会被 400 拒绝。
            prompt = text[:300]
            word_count = min(300, max(50, len(text) // 3))
            payload = self._dh_client.generate_video(prompt, word_count)
            if not payload:
                logger.warning("[Video] 数字人 API 未返回结果，降级")
                return None

            # 下载视频
            video_url = payload.get("video", "")
            output_path = str(ARTIFACTS_DIR / f"{resource_id}.mp4")
            if not XunfeiDigitalHumanClient.download_file(video_url, output_path):
                logger.warning("[Video] 数字人视频下载失败")
                return None
            output_path = self._trim_leading_black(output_path)

            # 同时下载音频（如果有）
            audio_url = payload.get("audio", "")
            audio_path = ""
            if audio_url:
                audio_path = str(ARTIFACTS_DIR / f"{resource_id}_audio.wav")
                XunfeiDigitalHumanClient.download_file(audio_url, audio_path)

            size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"[Video] 数字人视频生成成功: {output_path} ({size} bytes, {elapsed:.0f}ms)")
            return VideoResult(
                filepath=output_path, method="digital_human",
                agent_key=agent.get("key", DEFAULT_AGENT),
                agent_name=agent.get("name", ""),
                text_length=len(text), video_size=size,
                audio_path=audio_path, duration_ms=elapsed,
            )
        except Exception as exc:
            logger.warning(f"[Video] 数字人 API 异常: {exc}")
            return None

    # ---- Level 2: 动态幻灯片（音画同步） ----
    def _gen_with_slides(
        self, text: str, resource_id: str, agent: Dict[str, Any],
        voice: Optional[str], topic: str = "",
    ) -> Optional[VideoResult]:
        """动态幻灯片方案 — 按段落拆分 TTS 实现音画同步

        流程：
        1. 将讲解文本拆分为多个段落
        2. 为每段单独生成 TTS 音频并获取时长
        3. 为每段生成精美幻灯片 PNG
        4. 拼接所有音频
        5. ffmpeg 按每段音频时长控制对应幻灯片显示时间
        """
        start = time.perf_counter()
        logger.info("[Video] Level 2: 动态幻灯片方案（音画同步）")
        try:
            agent_voice = voice or agent.get("voice", "xiaoyan")

            # Step 1: 拆分文本
            display_topic = topic or text[:24].replace("\n", " ")
            segments = SlideGenerator.split_text(text, display_topic)
            n = len(segments)
            logger.info(f"[Video] 文本拆分为 {n} 段")

            # Step 2: 为每段生成 TTS 音频（音画同步核心）
            for i, seg in enumerate(segments):
                seg_id = f"{resource_id}_seg{i:02d}"
                audio = self._generate_tts(seg.raw_text, seg_id, agent_voice)
                if audio:
                    seg.audio_path = audio
                    seg.duration = self._get_audio_duration(audio)
                    logger.info(f"[Video] 段 {i+1}/{n} TTS: {seg.duration:.1f}s - {seg.heading}")
                else:
                    seg.duration = max(3.0, len(seg.raw_text) * 0.15)
                    logger.warning(f"[Video] 段 {i+1} TTS 失败，估算 {seg.duration:.1f}s")

            # Step 3: 生成幻灯片 PNG
            if any(not seg.audio_path for seg in segments):
                logger.warning("[Video] 存在无真实配音的片段，放弃静音幻灯片并进入下一降级层")
                return None

            slide_paths = self._slide_gen.generate_slides(segments, agent)
            if not slide_paths:
                logger.warning("[Video] 幻灯片生成失败")
                return None
            logger.info(f"[Video] 生成了 {len(slide_paths)} 张幻灯片")

            # Step 4: 合并音频
            audio_segments = [s.audio_path for s in segments if s.audio_path]
            if audio_segments:
                merged_audio = self._concat_audio(
                    audio_segments, str(ARTIFACTS_DIR / f"{resource_id}_merged.mp3"),
                )
            else:
                merged_audio = ""

            # Step 5: 获取每张幻灯片的时长
            durations = [max(2.0, s.duration) for s in segments]
            total_duration = sum(durations)
            logger.info(f"[Video] 总时长: {total_duration:.1f}s, 各段: {[f'{d:.1f}' for d in durations]}")

            # Step 6: ffmpeg 合成
            output_path = str(ARTIFACTS_DIR / f"{resource_id}.mp4")
            video_path = self._compose_slides_with_durations(
                slide_paths, merged_audio, output_path, durations,
                audio_segments=audio_segments,
            )
            if not video_path:
                return None

            # 清理临时幻灯片
            for sp in slide_paths:
                try:
                    os.unlink(sp)
                except OSError:
                    pass

            size = os.path.getsize(video_path)
            elapsed = (time.perf_counter() - start) * 1000
            logger.info(f"[Video] 幻灯片视频生成成功: {video_path} ({size} bytes, {elapsed:.0f}ms)")
            return VideoResult(
                filepath=video_path, method="animated_slides",
                agent_key=agent.get("key", DEFAULT_AGENT),
                agent_name=agent.get("name", ""),
                text_length=len(text), video_size=size,
                audio_path=merged_audio, duration_ms=elapsed,
            )
        except Exception as exc:
            logger.error(f"[Video] 幻灯片方案异常: {exc}")
            return None

    def _concat_audio(
        self, audio_paths: List[str], output_path: str,
    ) -> str:
        """拼接多段音频为一个文件"""
        if len(audio_paths) == 1:
            return audio_paths[0]
        ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
        concat_path = str(ARTIFACTS_DIR / "_audio_concat.txt")
        with open(concat_path, "w", encoding="utf-8") as f:
            for ap in audio_paths:
                abs_p = str(Path(ap).resolve()).replace("\\", "/")
                f.write(f"file '{abs_p}'\n")
        cmd = [
            ffmpeg_bin, "-y", "-f", "concat", "-safe", "0",
            "-i", concat_path,
            "-af", NARRATION_AUDIO_FILTER,
            "-ar", "48000", "-ac", "1",
            "-c:a", "libmp3lame", "-b:a", "160k",
            output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception as exc:
            logger.warning(f"[Video] audio concat failed: {exc}")
        finally:
            try:
                os.unlink(concat_path)
            except OSError:
                pass
        return audio_paths[0] if audio_paths else ""

    def _compose_slides_with_durations(
        self, slide_paths: List[str], audio_path: str,
        output_path: str, durations: List[float],
        audio_segments: Optional[List[str]] = None,
    ) -> Optional[str]:
        """用 ffmpeg 将多张幻灯片按各自时长合成视频（音画同步）"""
        ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
        n = len(slide_paths)
        if n == 0:
            return None

        # 优先逐页锁定“单张画面 + 单段语音”，消除 MP3 编码延迟逐页累积。
        if audio_segments and len(audio_segments) == n:
            synchronized = self._compose_synchronized_segments(
                slide_paths, audio_segments, output_path,
            )
            if synchronized:
                return synchronized
            logger.warning("[Video] 逐页音画锁定失败，回退到统一时间轴合成")

        total_duration = sum(durations)

        # 构建 concat 文件（每张幻灯片按对应时长显示）
        concat_path = str(ARTIFACTS_DIR / "_slides_concat.txt")
        abs_slides = [str(Path(sp).resolve()).replace("\\", "/") for sp in slide_paths]
        with open(concat_path, "w", encoding="utf-8") as f:
            for i, sp in enumerate(abs_slides):
                f.write(f"file '{sp}'\n")
                f.write(f"duration {durations[i]:.2f}\n")
            # concat 要求最后重复一次
            f.write(f"file '{abs_slides[-1]}'\n")

        audio_args = []
        if audio_path and os.path.exists(audio_path):
            audio_args = ["-i", audio_path]

        vf_parts = [
            "scale=1280:720",
            "format=yuv420p",
            f"fade=t=out:st={max(0, total_duration - 0.8):.2f}:d=0.8",
        ]

        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_path,
        ] + audio_args + [
            "-vf", ",".join(vf_parts),
            "-r", "25",
            "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        ]
        if audio_args:
            cmd += [
                "-af", f"{NARRATION_AUDIO_FILTER},aresample=async=1:first_pts=0",
                "-c:a", "aac", "-b:a", "160k", "-shortest",
            ]
        cmd += ["-movflags", "+faststart", output_path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"[Video] slides ffmpeg OK: {output_path}")
                return output_path
            logger.warning(f"[Video] slides ffmpeg failed: {result.stderr[-400:]}")
            return self._compose_slides_simple_v2(
                slide_paths, audio_path, output_path, durations,
            )
        except Exception as exc:
            logger.warning(f"[Video] slides ffmpeg exception: {exc}")
            return None
        finally:
            try:
                os.unlink(concat_path)
            except OSError:
                pass

    def _compose_synchronized_segments(
        self,
        slide_paths: List[str],
        audio_segments: List[str],
        output_path: str,
    ) -> Optional[str]:
        """逐页生成带独立音轨的片段，再合并为同一条音画时间轴。"""
        ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
        output_stem = re.sub(r"[^0-9A-Za-z_-]+", "_", Path(output_path).stem) or "video"
        clip_paths: List[str] = []
        concat_path = str(ARTIFACTS_DIR / f"_{output_stem}_av_concat.txt")

        try:
            for idx, (slide_path, segment_audio) in enumerate(zip(slide_paths, audio_segments)):
                if not os.path.exists(slide_path) or not os.path.exists(segment_audio):
                    return None
                clip_path = str(ARTIFACTS_DIR / f"_{output_stem}_av_{idx:02d}.mp4")
                clip_paths.append(clip_path)
                cmd = [
                    ffmpeg_bin, "-y",
                    "-loop", "1", "-framerate", "25", "-i", slide_path,
                    "-i", segment_audio,
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", "scale=1280:720,format=yuv420p",
                    "-r", "25", "-c:v", "libx264", "-preset", "medium",
                    "-tune", "stillimage", "-pix_fmt", "yuv420p",
                    "-af", NARRATION_AUDIO_FILTER,
                    "-ar", "48000", "-ac", "1", "-c:a", "aac", "-b:a", "160k",
                    # 图片输入会无限循环；以本页音轨结尾作为唯一切页依据。
                    "-shortest", "-movflags", "+faststart", clip_path,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT,
                )
                if result.returncode != 0 or not os.path.exists(clip_path):
                    logger.warning(
                        "[Video] page %s A/V lock failed: %s", idx + 1, result.stderr[-300:],
                    )
                    return None

            with open(concat_path, "w", encoding="utf-8") as concat_file:
                for clip_path in clip_paths:
                    abs_path = str(Path(clip_path).resolve()).replace("\\", "/")
                    concat_file.write(f"file '{abs_path}'\n")

            # 最终增加一小段末帧冻结缓冲，再由 -shortest 以音轨结束点收口：
            # 即使 AAC 有几十毫秒编码延迟，也不会出现画面先结束、语音仍继续。
            concat_cmd = [
                ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
                "-filter_complex", "[0:v]tpad=stop_mode=clone:stop_duration=1[v]",
                "-map", "[v]", "-map", "0:a:0",
                "-r", "25", "-c:v", "libx264", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-shortest", "-movflags", "+faststart", output_path,
            ]
            result = subprocess.run(
                concat_cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT,
            )
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info("[Video] per-slide A/V synchronization OK: %s", output_path)
                return output_path
            logger.warning("[Video] synchronized concat failed: %s", result.stderr[-300:])
            return None
        except Exception as exc:
            logger.warning("[Video] synchronized composition exception: %s", exc)
            return None
        finally:
            for temporary in [concat_path, *clip_paths]:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def _compose_slides_simple_v2(
        self, slide_paths: List[str], audio_path: str,
        output_path: str, durations: List[float],
    ) -> Optional[str]:
        """简化版幻灯片合成（无 fade，纯 concat + 按时长）"""
        ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
        concat_path = str(ARTIFACTS_DIR / "_slides_concat2.txt")
        abs_slides = [str(Path(sp).resolve()).replace("\\", "/") for sp in slide_paths]
        with open(concat_path, "w", encoding="utf-8") as f:
            for i, sp in enumerate(abs_slides):
                f.write(f"file '{sp}'\n")
                f.write(f"duration {durations[i]:.2f}\n")
            f.write(f"file '{abs_slides[-1]}'\n")

        audio_args = []
        if audio_path and os.path.exists(audio_path):
            audio_args = ["-i", audio_path]

        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat", "-safe", "0", "-i", concat_path,
        ] + audio_args + [
            "-vf", "scale=1280:720,format=yuv420p",
            "-r", "25",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        ]
        if audio_args:
            cmd += [
                "-af", f"{NARRATION_AUDIO_FILTER},aresample=async=1:first_pts=0",
                "-c:a", "aac", "-b:a", "160k", "-shortest",
            ]
        cmd += ["-movflags", "+faststart", output_path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass
        finally:
            try:
                os.unlink(concat_path)
            except OSError:
                pass
        return None

    # ---- Level 3: 静态头像 ----
    def _gen_with_static_avatar(
        self, text: str, resource_id: str, agent: Dict[str, Any],
        voice: Optional[str],
    ) -> Optional[VideoResult]:
        start = time.perf_counter()
        logger.info("[Video] Level 3: 静态头像方案")
        try:
            agent_voice = voice or agent.get("voice", "xiaoyan")
            audio_path = self._generate_tts(text, resource_id, agent_voice)
            if not audio_path:
                return VideoResult(
                    method="error", error="TTS 失败",
                    agent_name=agent.get("name", ""),
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            avatar_path = agent.get("avatar_path", "")
            if avatar_path and Path(avatar_path).exists():
                output_path = str(ARTIFACTS_DIR / f"{resource_id}.mp4")
                duration = self._get_audio_duration(audio_path)
                video_path = self._compose_static_ffmpeg(
                    avatar_path, audio_path, output_path, duration, agent,
                )
                if video_path:
                    return VideoResult(
                        filepath=video_path, method="static_avatar",
                        agent_name=agent.get("name", ""),
                        text_length=len(text),
                        video_size=os.path.getsize(video_path),
                        audio_path=audio_path,
                        duration_ms=(time.perf_counter() - start) * 1000,
                    )
            return None
        except Exception as exc:
            logger.error(f"[Video] 静态头像异常: {exc}")
            return None

    # ---- 工具方法 ----
    def _trim_leading_black(self, video_path: str) -> str:
        """检测并裁掉数字人供应商视频开头最多 3 秒的黑场。"""
        ffmpeg_bin = self._get_ffmpeg_path()
        if not ffmpeg_bin or not os.path.exists(video_path):
            return video_path
        try:
            detect = subprocess.run(
                [
                    ffmpeg_bin, "-hide_banner", "-i", video_path,
                    "-vf", "blackdetect=d=0.12:pix_th=0.10",
                    "-an", "-f", "null", "NUL",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            black_end = _leading_black_end(detect.stderr)
            if black_end <= 0:
                return video_path

            source = Path(video_path)
            trimmed = source.with_name(f"{source.stem}_trimmed{source.suffix}")
            trim_start = black_end + 0.03
            result = subprocess.run(
                [
                    ffmpeg_bin, "-y", "-ss", f"{trim_start:.3f}", "-i", video_path,
                    "-map", "0:v:0", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(trimmed),
                ],
                capture_output=True,
                text=True,
                timeout=FFMPEG_TIMEOUT,
            )
            if result.returncode == 0 and trimmed.exists() and trimmed.stat().st_size > 0:
                os.replace(trimmed, source)
                logger.info("[Video] 已裁掉数字人视频开头 %.2f 秒黑场", trim_start)
            return video_path
        except Exception as exc:
            logger.warning("[Video] 黑场检测/裁剪跳过: %s", exc)
            return video_path

    @staticmethod
    def _get_ffmpeg_path() -> Optional[str]:
        for name in ["ffmpeg", "ffmpeg.exe"]:
            try:
                subprocess.run([name, "-version"], capture_output=True, timeout=3)
                return name
            except Exception:
                continue
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).exists():
                return exe
        except ImportError:
            pass
        except Exception:
            pass
        for path in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]:
            if Path(path).exists():
                return path
        return None

    @staticmethod
    def _get_audio_duration(audio_path: str) -> float:
        ffmpeg = AgentVideoService._get_ffmpeg_path()
        try:
            import shutil

            ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
            if not ffprobe and ffmpeg:
                ffmpeg_path = Path(ffmpeg)
                sibling_name = "ffprobe.exe" if ffmpeg_path.suffix.lower() == ".exe" else "ffprobe"
                sibling = ffmpeg_path.with_name(sibling_name)
                if sibling.exists():
                    ffprobe = str(sibling)
            if ffprobe:
                result = subprocess.run(
                    [ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    duration = float(result.stdout.strip())
                    if duration > 0:
                        return duration
        except Exception:
            pass

        # imageio-ffmpeg 通常没有同目录 ffprobe；只读取 ffmpeg 媒体头即可获取
        # Duration，无需完整解码音频，也不会把所有片段错误地估算成 10 秒。
        if ffmpeg:
            try:
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-i", audio_path],
                    capture_output=True, text=True, timeout=10,
                )
                match = re.search(
                    r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
                    result.stderr or "",
                )
                if match:
                    hours, minutes, seconds = match.groups()
                    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                    if duration > 0:
                        return duration
            except Exception:
                pass
        try:
            import wave
            with wave.open(audio_path, "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            return 10.0

    def _generate_tts(self, text: str, resource_id: str, voice: str) -> Optional[str]:
        try:
            from backend.app.services.multimodal.tts_xunfei import get_tts_service
            tts = get_tts_service()
            speech_text = _prepare_speech_text(text)
            result = tts.synthesize(
                speech_text,
                resource_id,
                voice=voice,
                speed=50,
                volume=58,
                pitch=50,
                prefer_natural=True,
            )
            if result.success and result.method != "mock":
                return result.filepath
            if result.method == "mock":
                logger.warning("[Video] TTS 仅返回静音 Mock，不作为可交付配音")
        except Exception as exc:
            logger.error(f"[Video] TTS 异常: {exc}")
        return None

    def _compose_static_ffmpeg(
        self, avatar_path: str, audio_path: str,
        output_path: str, duration: float, agent: Dict[str, Any],
    ) -> Optional[str]:
        """静态头像 + TTS 合成（兜底）"""
        ffmpeg_bin = self._get_ffmpeg_path() or "ffmpeg"
        duration = max(3.0, min(300.0, duration))

        vf = (
            f"scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
            f"zoompan=z='min(zoom+0.0008,1.08)':d={int(duration*25)}:s=1280x720:fps=25"
        )
        cmd = [
            ffmpeg_bin, "-y", "-loop", "1", "-framerate", "25", "-t", str(duration),
            "-i", avatar_path, "-i", audio_path,
            "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-af", f"{NARRATION_AUDIO_FILTER},aresample=async=1:first_pts=0",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", output_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path
        except Exception:
            pass
        return None

    @staticmethod
    def list_agents() -> List[Dict[str, Any]]:
        return [
            {"key": k, "name": v["name"], "title": v["title"], "voice": v["voice"],
             "description": v["description"],
             "avatar_exists": Path(v["avatar_path"]).exists()}
            for k, v in AGENT_VIDEO_CATALOG.items()
        ]

    @staticmethod
    def select_agent_for_content(content_type: str) -> str:
        mapping = {
            "path": "planner", "plan": "planner",
            "explain": "tutor", "concept": "tutor", "lecture": "tutor",
            "resource": "content", "document": "content", "ppt": "content",
            "quiz": "quiz", "exercise": "quiz", "practice": "quiz",
            "evaluation": "evaluation", "review": "evaluation", "summary": "evaluation",
            "safety": "safety", "notice": "safety",
        }
        return mapping.get(content_type.lower(), DEFAULT_AGENT)


# ================================================================
# 全局单例
# ================================================================
_video_service: Optional[AgentVideoService] = None


def get_video_service() -> AgentVideoService:
    global _video_service
    if _video_service is None:
        _video_service = AgentVideoService()
    return _video_service


def reset_video_service() -> None:
    global _video_service
    _video_service = None
