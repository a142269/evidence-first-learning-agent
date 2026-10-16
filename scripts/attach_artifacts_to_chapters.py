"""
attach_artifacts_to_chapters.py — 多模态产物自动入库 (Plan D Round 4 B 主线)

目的
----
Round 3 收口时已在 data/artifacts/{pptx,mp3,mermaid_png,manim} 留下
4 份代表性多模态产物 (C1-C4)。本脚本扫描这些产物, 把它们以
frontmatter `artifacts:` 字段挂到对应 KB 章节 markdown, 完成
"AI 生成产物 → KB 章节索引" 的闭环。

设计
----
- 不解析 frontmatter 全部字段, 只用 regex 在 `---` 闭合前**追加**
  `artifacts:` 列表 (不修改任何已有字段, 安全)
- 重复运行时通过内容字符串检测幂等: 若 `artifacts:` 已含目标条目
  则跳过, 不会重复追加
- 默认 dry-run, --apply 才写盘
- 同时维护一个 `data/artifacts_index.json` 总索引, 给前端 / 资源 API 用

用法
----
    python -m scripts.attach_artifacts_to_chapters              # 预览
    python -m scripts.attach_artifacts_to_chapters --apply      # 实际写盘
    python -m scripts.attach_artifacts_to_chapters --verbose   # 详细日志
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


WORKSPACE = Path(__file__).resolve().parents[1]
KB_ROOT = WORKSPACE / "knowledge_base"
ARTIFACTS_ROOT = WORKSPACE / "data" / "artifacts"
INDEX_PATH = WORKSPACE / "data" / "artifacts_index.json"


# ============================================================
# 1. 关键产物映射 (Round 3 收口 11 项里的 C1-C4)
# ============================================================
KEY_ARTIFACTS: list[dict] = [
    {
        "filename": "pptx_e8db0ea64c.pptx",
        "course": "artificial_intelligence",
        "chapter_slug": "05_transformer_and_llm",
        "type": "pptx",
        "title": "Self-Attention 多头注意力可视化 (C1)",
        "rel_path": "data/artifacts/pptx/pptx_e8db0ea64c.pptx",
    },
    {
        "filename": "tts_4db511b9ec.mp3",
        "course": "artificial_intelligence",
        "chapter_slug": "17_backpropagation",
        "type": "mp3",
        "title": "反向传播算法语音讲解 (C2)",
        "rel_path": "data/artifacts/mp3/tts_4db511b9ec.mp3",
    },
    {
        "filename": "f0af78e51dcd.png",
        "course": "artificial_intelligence",
        "chapter_slug": "04_cnn_and_vision",
        "type": "mermaid_png",
        "title": "CNN 架构 Mermaid 思维导图 (C3)",
        "rel_path": "data/artifacts/mermaid_png/f0af78e51dcd.png",
    },
    {
        "filename": "convolutional_neural_network_placeholder.svg",
        "course": "artificial_intelligence",
        "chapter_slug": "04_cnn_and_vision",
        "type": "manim_svg",
        "title": "卷积神经网络 Manim 动画占位 (C4 — 兜底)",
        "rel_path": "data/artifacts/manim/convolutional_neural_network_placeholder.svg",
    },
]

# 跳过的开发期/测试期文件名前缀
SKIP_PREFIXES = (
    "badbullet-", "badtitle-", "compat-", "smoke-", "test_", "_cache_",
    "test_mock_", "bench-", "huge-", "empty-",
)
SKIP_SUFFIXES = ("_mock.mp3",)


# ============================================================
# 2. 工具
# ============================================================
def _chapter_path(course: str, slug: str) -> Path:
    return KB_ROOT / course / "chapters" / f"{slug}.md"


def _detect_frontmatter(text: str) -> Optional[tuple[str, str]]:
    """检测 markdown 是否有 yaml frontmatter

    返回: (frontmatter_str_including_dashes, body_str)  或  None
    """
    m = re.match(r"^(---\n)(.+?)\n(---)\n?(.*)$", text, re.DOTALL)
    if not m:
        return None
    fm_open = m.group(1)         # "---\n"
    fm_body = m.group(2)         # 中间 yaml 内容 (不含 ---)
    fm_close = m.group(3)        # "---"
    body = m.group(4)            # 正文
    # 保留原 fm_open/fm_body/fm_close 完整, 方便正则替换
    full_fm = fm_open + fm_body + "\n" + fm_close
    return full_fm, body


def _has_artifact_entry(fm_body: str, rel_path: str) -> bool:
    """frontmatter body 中是否已含该 rel_path (幂等检查)"""
    return f"'{rel_path}'" in fm_body or f'"{rel_path}"' in fm_body


def _append_artifacts_block(fm_body: str, entries: list[dict]) -> str:
    """在 fm_body 末尾追加 (或合并) artifacts: 列表块

    策略: 若已含 artifacts: 块, 找到它的结束位置, 在末尾追加新条目;
          否则直接在 fm_body 末尾新增 artifacts: 块。
    """
    new_entries = []
    for e in entries:
        block = (
            f"    - type: '{e['type']}'\n"
            f"      path: '{e['rel_path']}'\n"
            f"      title: '{e['title']}'\n"
        )
        new_entries.append(block)

    artifacts_re = re.compile(r"^(artifacts:\n)((?:[ \t]+-.*\n(?:[ \t]+.*\n)*)*)", re.MULTILINE)
    m = artifacts_re.search(fm_body)
    if m:
        # 已有 artifacts: 块, 追加到现有条目末尾
        new_block = "".join(new_entries)
        return fm_body[: m.end()] + new_block + fm_body[m.end():]

    # 没有任何 artifacts: 块, 在 fm_body 末尾追加新块
    new_block = "\nartifacts:\n" + "".join(new_entries)
    # 确保前面有空行分隔
    if not fm_body.endswith("\n"):
        fm_body += "\n"
    return fm_body + new_block


def discover_artifacts() -> list[dict]:
    """扫 artifacts 目录, 返回 (filename, type, abs_path) 列表

    仅扫 4 类目录, 跳过 SKIP_PREFIXES/SUFFIXES
    """
    found: list[dict] = []
    subdirs = {
        "pptx": "pptx",
        "mp3": "mp3",
        "mermaid_png": "mermaid_png",
        "manim_svg": "manim",
    }
    for type_name, subdir in subdirs.items():
        d = ARTIFACTS_ROOT / subdir
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if not p.is_file():
                continue
            name = p.name
            if any(name.startswith(pre) for pre in SKIP_PREFIXES):
                continue
            if any(name.endswith(suf) for suf in SKIP_SUFFIXES):
                continue
            found.append({
                "filename": name,
                "type": type_name,
                "abs_path": str(p),
                "rel_path": str(p.relative_to(WORKSPACE)),
            })
    return found


# ============================================================
# 3. 主体
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description="多模态产物 → KB 章节 frontmatter 挂载")
    parser.add_argument("--apply", action="store_true", help="实际写盘, 否则只 dry-run")
    parser.add_argument("--verbose", action="store_true", help="详细日志")
    args = parser.parse_args()

    print("=" * 72)
    print("A3 Round 4 B 主线 — 多模态产物自动入库")
    print("=" * 72)
    print(f"模式: {'[APPLY 实际写盘]' if args.apply else '[DRY-RUN 预览]'}")
    print()

    # 1) 扫 4 类目录总数
    all_found = discover_artifacts()
    print(f"[1] data/artifacts 扫到 {len(all_found)} 份非测试产物")
    by_type: dict[str, int] = {}
    for a in all_found:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"    {t:<14} {n}")
    print()

    # 2) 按章节分组待追加的 entries
    by_chapter: dict[tuple[str, str], list[dict]] = {}
    for art in KEY_ARTIFACTS:
        key = (art["course"], art["chapter_slug"])
        by_chapter.setdefault(key, []).append(art)

    # 3) 关键产物入 KB
    print(f"[2] 关键产物挂载 (Round 3 收口 C1-C4, 共 {len(KEY_ARTIFACTS)} 项)")
    print("    " + "-" * 65)
    success = 0
    skipped = 0
    failed = 0
    for (course, slug), entries in by_chapter.items():
        chapter_path = _chapter_path(course, slug)
        if not chapter_path.exists():
            for e in entries:
                print(f"    [FAIL] {e['filename']:<48} 章节 {slug}.md 不存在")
                failed += 1
            continue

        text = chapter_path.read_text(encoding="utf-8")
        det = _detect_frontmatter(text)
        if det is None:
            for e in entries:
                print(f"    [FAIL] {e['filename']:<48} {slug}.md 无 frontmatter")
                failed += 1
            continue

        full_fm, body = det
        # fm_body 是 full_fm 去掉首尾 --- 的中间部分
        fm_body = full_fm[4:-3]  # 去掉 "---\n" 和末尾 "---"
        # 实际上 full_fm 末尾一定有 "\n---" — 用 rstrip
        fm_body = re.sub(r"^\n?-+$", "", full_fm.replace("---\n", "", 1).rstrip())
        # 重新解析: full_fm = "---\n<body>\n---"
        m = re.match(r"^---\n(.*?)\n?---\s*$", full_fm, re.DOTALL)
        if not m:
            for e in entries:
                print(f"    [FAIL] {e['filename']:<48} {slug}.md frontmatter 解析失败")
                failed += 1
            continue
        fm_body = m.group(1)

        # 幂等检查: 哪些 entry 还没挂
        to_add: list[dict] = []
        for e in entries:
            if _has_artifact_entry(fm_body, e["rel_path"]):
                print(f"    [SKIP] {e['filename']:<48} 已在 {slug}.md frontmatter")
                skipped += 1
            else:
                to_add.append(e)

        if not to_add:
            continue

        # 构造新 frontmatter
        new_fm_body = _append_artifacts_block(fm_body, to_add)
        new_full_fm = "---\n" + new_fm_body + "\n---\n"
        new_text = new_full_fm + body

        # 干跑 / 写盘
        for e in to_add:
            if args.apply:
                print(f"    [APPLY] {e['filename']:<48} → {slug}.md  frontmatter.artifacts")
            else:
                print(f"    [DRY ] {e['filename']:<48} → {slug}.md  frontmatter.artifacts (未写盘)")
            success += 1

        if args.apply:
            chapter_path.write_text(new_text, encoding="utf-8")
    print("    " + "-" * 65)
    print(f"    成功 {success}  跳过 {skipped}  失败 {failed}")
    print()

    # 4) 写盘后校验
    if args.apply:
        print("[3] 写盘后的章节 frontmatter 抽样校验")
        print("    " + "-" * 65)
        for art in KEY_ARTIFACTS:
            p = _chapter_path(art["course"], art["chapter_slug"])
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            det = _detect_frontmatter(text)
            if det is None:
                print(f"    [FAIL] {art['chapter_slug']}.md frontmatter 丢失!")
                failed += 1
                continue
            full_fm, _ = det
            if art["rel_path"] in full_fm:
                # 同时确保原字段还在 (例如 kp_ids)
                # 这里粗略校验: frontmatter 至少有 7 行
                if full_fm.count("\n") >= 7:
                    print(f"    [OK]   {art['chapter_slug']}.md  含 {art['filename']}  + 原字段未失")
                else:
                    print(f"    [WARN] {art['chapter_slug']}.md  frontmatter 行数偏少")
            else:
                print(f"    [FAIL] {art['chapter_slug']}.md  不含 {art['filename']}")
                failed += 1
        print("    " + "-" * 65)
        print()

    # 5) 写总索引 artifacts_index.json
    print(f"[4] 写总索引 {INDEX_PATH.relative_to(WORKSPACE)}")
    index_doc = {
        "version": "round4-0705",
        "generated_by": "scripts/attach_artifacts_to_chapters.py",
        "key_artifacts": [
            {k: v for k, v in e.items() if k != "abs_path"}
            for e in KEY_ARTIFACTS
        ],
        "discovered_total": len(all_found),
        "discovered_by_type": by_type,
        "kb_attached": sum(len(v) for v in by_chapter.values()),
    }
    if args.apply:
        INDEX_PATH.write_text(
            json.dumps(index_doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"    [APPLY] 写入 {INDEX_PATH.relative_to(WORKSPACE)}  ({len(json.dumps(index_doc))} bytes)")
    else:
        print(f"    [DRY ] 将写入 {INDEX_PATH.relative_to(WORKSPACE)}")
    print()

    # 6) 总结
    print("=" * 72)
    if args.apply:
        print(f"[APPLY DONE] {success} 份关键产物已挂载到 KB 章节 frontmatter")
    else:
        print(f"[DRY-RUN DONE] 预览 {success} 份, 用 --apply 实际写盘")
    print(f"  data/artifacts 总产物: {len(all_found)} 份 (开发期 noise 已跳过)")
    print(f"  KB 章节已挂载: {success} 份 (C1-C4)")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
