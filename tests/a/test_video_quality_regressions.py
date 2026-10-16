"""视频首帧、配音文本和音频交付质量回归测试。"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import shutil

from backend.app.services.multimodal import video_xunfei
from backend.app.services.multimodal.video_xunfei import (
    AgentVideoService,
    SlideGenerator,
    _leading_black_end,
    _prepare_speech_text,
)


def test_speech_text_removes_markdown_and_normalizes_attention_terms():
    text = _prepare_speech_text(
        "## Self-Attention\n**Q/K/V** 经过 `softmax`。\n```python\nprint('x')\n```"
    )

    assert "##" not in text
    assert "**" not in text
    assert "```" not in text
    assert "自注意力" in text
    assert "Q、K、V" in text
    assert "代码示例请查看画面" in text


def test_speech_text_adds_natural_teaching_pauses():
    text = _prepare_speech_text("首先理解输入。然后检查输出。例如使用一个张量。")

    assert "首先，" in text
    assert "然后，" in text
    assert "例如，" in text


def test_slide_segments_show_every_spoken_content_without_duplication():
    lecture = (
        "大家好，今天学习 Transformer。首先理解输入张量的形状和含义。"
        "然后观察 Q、K、V 如何参与注意力计算。"
        "例如，一个长度为四的序列会生成四行注意力权重。"
        "注意不要把头数和每个头的维度混淆。最后请用自己的话完成自测。"
    )
    segments = SlideGenerator.split_text(lecture, "Transformer 架构")

    visible_text = "".join(
        line for segment in segments for line in segment.content_lines
    )
    expected_text = "".join(SlideGenerator._split_visual_units(lecture))
    assert visible_text == expected_text
    assert all(len(segment.content_lines) <= 4 for segment in segments)
    assert all(
        "".join(segment.content_lines) in segment.raw_text
        for segment in segments
    )
    assert sum(segment.heading == "自测与总结" for segment in segments) <= 1


def test_leading_black_detector_only_accepts_short_intro_black():
    assert _leading_black_end("black_start:0 black_end:0.48 black_duration:0.48") == 0.48
    assert _leading_black_end("black_start:12.0 black_end:13.0 black_duration:1.0") == 0.0
    assert _leading_black_end("black_start:0 black_end:4.20 black_duration:4.20") == 0.0


def test_audio_duration_uses_ffmpeg_header_when_ffprobe_is_missing(monkeypatch):
    def fake_run(command, **kwargs):
        assert command[:3] == ["ffmpeg", "-hide_banner", "-i"]
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Duration: 00:00:02.34, start: 0.000000, bitrate: 128 kb/s",
        )

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(AgentVideoService, "_get_ffmpeg_path", staticmethod(lambda: "ffmpeg"))
    monkeypatch.setattr(video_xunfei.subprocess, "run", fake_run)

    assert AgentVideoService._get_audio_duration("voice.mp3") == 2.34


def test_slide_composition_has_visible_first_frame_and_normalized_audio(tmp_path, monkeypatch):
    slide = tmp_path / "slide.png"
    audio = tmp_path / "voice.mp3"
    output = tmp_path / "video.mp4"
    slide.write_bytes(b"png")
    audio.write_bytes(b"mp3")
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video_xunfei, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(video_xunfei.subprocess, "run", fake_run)
    monkeypatch.setattr(AgentVideoService, "_get_ffmpeg_path", staticmethod(lambda: "ffmpeg"))

    service = AgentVideoService()
    result = service._compose_slides_with_durations(
        [str(slide)], str(audio), str(output), [3.0],
    )

    assert result == str(output)
    command_text = " ".join(commands[0])
    assert "fade=t=in" not in command_text
    assert "loudnorm=I=-16" in command_text
    assert "+faststart" in command_text


def test_per_slide_audio_is_locked_before_final_concat(tmp_path, monkeypatch):
    slides = [tmp_path / "slide-1.png", tmp_path / "slide-2.png"]
    audios = [tmp_path / "voice-1.mp3", tmp_path / "voice-2.mp3"]
    output = tmp_path / "synced.mp4"
    for path in [*slides, *audios]:
        path.write_bytes(b"input")

    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"media")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video_xunfei, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(video_xunfei.subprocess, "run", fake_run)
    monkeypatch.setattr(AgentVideoService, "_get_ffmpeg_path", staticmethod(lambda: "ffmpeg"))

    service = AgentVideoService()
    result = service._compose_slides_with_durations(
        [str(path) for path in slides],
        str(audios[0]),
        str(output),
        [2.0, 2.0],
        audio_segments=[str(path) for path in audios],
    )

    assert result == str(output)
    assert len(commands) == 3
    for page_command in commands[:2]:
        command_text = " ".join(page_command)
        assert "-map 0:v:0 -map 1:a:0" in command_text
        assert "-shortest" in page_command
        assert "acompressor=" in command_text
    final_command_text = " ".join(commands[-1])
    assert "tpad=stop_mode=clone:stop_duration=1" in final_command_text
    assert "-shortest" in commands[-1]
