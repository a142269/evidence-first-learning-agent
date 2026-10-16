"""临时预览：调用 attach_artifacts 的内部函数, 把 apply 后 frontmatter 写到 .tmp/"""
import re
import sys
from pathlib import Path

sys.path.insert(0, r"F:\比赛\中软杯\A3")
from scripts.attach_artifacts_to_chapters import (  # noqa: E402
    _detect_frontmatter,
    _append_artifacts_block,
    KEY_ARTIFACTS,
    _chapter_path,
)

WS = Path(r"F:\比赛\中软杯\A3")
out_dir = WS / ".tmp" / "attach_preview"
out_dir.mkdir(parents=True, exist_ok=True)

print("=== 模拟 apply 后 frontmatter 预览 ===\n")
for art in KEY_ARTIFACTS:
    p = _chapter_path(art["course"], art["chapter_slug"])
    text = p.read_text(encoding="utf-8")
    det = _detect_frontmatter(text)
    if det is None:
        print(f"[FAIL] {p.name} 无 frontmatter")
        continue
    full_fm, body = det
    m = re.match(r"^---\n(.*?)\n?---\s*$", full_fm, re.DOTALL)
    fm_body = m.group(1)
    new_fm_body = _append_artifacts_block(fm_body, [art])
    new_full_fm = "---\n" + new_fm_body + "\n---\n"
    new_text = new_full_fm + body

    # 写到 tmp 预览
    preview_path = out_dir / p.name
    preview_path.write_text(new_text, encoding="utf-8")

    # 校验：原字段是否还在
    orig_keys = ["chapter_id", "slug", "title", "kp_ids", "bloom_focus",
                 "prerequisites", "estimated_minutes"]
    lost = [k for k in orig_keys if f"{k}:" not in new_full_fm]
    has_art = art["rel_path"] in new_full_fm

    status = "OK" if not lost and has_art else "FAIL"
    print(f"[{status}] {p.name}  artifacts={has_art}  原字段丢失={lost}")

# 写 .tmp 下 diff: 原始 vs 预览
print("\n=== 3 个文件的原 frontmatter vs 预览 frontmatter ===\n")
for art in KEY_ARTIFACTS:
    orig = _chapter_path(art["course"], art["chapter_slug"]).read_text(encoding="utf-8")
    preview = (out_dir / _chapter_path(art["course"], art["chapter_slug"]).name).read_text(encoding="utf-8")

    orig_fm = re.match(r"^---\n(.*?)\n?---\s*", orig, re.DOTALL).group(1)
    prev_fm = re.match(r"^---\n(.*?)\n?---\s*", preview, re.DOTALL).group(1)

    # 找新增行
    orig_lines = set(orig_fm.splitlines())
    prev_lines = set(prev_fm.splitlines())
    added = prev_lines - orig_lines
    print(f"--- {_chapter_path(art['course'], art['chapter_slug']).name} ---")
    print(f"原 frontmatter 行数: {len(orig_lines)}")
    print(f"预览 frontmatter 行数: {len(prev_lines)}")
    print(f"新增行 ({len(added)}):")
    for line in sorted(added):
        print(f"  + {line}")
    print()
