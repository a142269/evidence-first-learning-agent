"""Python 程序设计 · 配套实操示例 11 · 文件读写与 pathlib demo

对应章节: 11 文件读写与 pathlib
对应 KP  : PY_016 (文件读写), PY_017 (pathlib 路径操作)
Bloom 关注: Apply / Analyze
运行方式 : python 11_file_io_demo.py
依赖     : 纯标准库
说明     : 8 个 demo 函数覆盖 open 模式、读写方法、with、二进制、pathlib、glob、临时文件、综合实战。
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. open() 模式 + 读写
# ---------------------------------------------------------------------------
def demo_open_modes() -> None:
    """演示读 / 写 / 追加 / 二进制"""
    p = Path(tempfile.gettempdir()) / "demo_open.txt"

    # 写
    with p.open("w", encoding="utf-8") as f:
        f.write("Hello\n")
        f.write("Python\n")

    # 读(默认 r)
    with p.open(encoding="utf-8") as f:
        content = f.read()
    assert "Hello" in content and "Python" in content

    # 追加
    with p.open("a", encoding="utf-8") as f:
        f.write("Appended\n")
    with p.open(encoding="utf-8") as f:
        assert "Appended" in f.read()

    # 排他创建(已存在则失败)
    try:
        with p.open("x", encoding="utf-8") as f:
            f.write("exclusive")
        assert False, "should have raised"
    except FileExistsError as e:
        print(f"  caught expected FileExistsError: {e}")

    p.unlink()
    print("[OK] open modes (r/w/a/x)")


# ---------------------------------------------------------------------------
# 2. read() / readline() / readlines() / 迭代
# ---------------------------------------------------------------------------
def demo_read_methods() -> None:
    p = Path(tempfile.gettempdir()) / "demo_read.txt"
    p.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    # 全部读
    all_text = p.read_text(encoding="utf-8")
    assert "line 1" in all_text

    # 一行一行
    with p.open(encoding="utf-8") as f:
        first = f.readline().rstrip()
        rest = f.read().splitlines()
    assert first == "line 1"
    assert rest == ["line 2", "line 3"]

    # 迭代(内存友好)
    lines = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            lines.append(line.rstrip())
    assert lines == ["line 1", "line 2", "line 3"]

    p.unlink()
    print(f"[OK] read methods (lines={lines})")


# ---------------------------------------------------------------------------
# 3. with 语句保证关闭
# ---------------------------------------------------------------------------
def demo_with_statement() -> None:
    p = Path(tempfile.gettempdir()) / "demo_with.txt"
    p.write_text("with demo", encoding="utf-8")

    # with 退出后 f 已关闭
    with p.open(encoding="utf-8") as f:
        data = f.read()
    try:
        f.read()  # ❌ ValueError: I/O operation on closed file
    except ValueError as e:
        print(f"  caught expected ValueError: {e}")
    assert f.closed is True
    p.unlink()
    print("[OK] with statement auto-close")


# ---------------------------------------------------------------------------
# 4. 文本 vs 二进制
# ---------------------------------------------------------------------------
def demo_text_vs_binary() -> None:
    p = Path(tempfile.gettempdir()) / "demo_text_binary.txt"
    p.write_text("你好", encoding="utf-8")

    # 文本模式
    with p.open("r", encoding="utf-8") as f:
        text = f.read()
    assert isinstance(text, str)

    # 二进制模式
    with p.open("rb") as f:
        raw = f.read()
    assert isinstance(raw, bytes)
    assert raw == "你好".encode("utf-8")
    p.unlink()
    print(f"[OK] text vs binary (len(text)={len(text)}, len(bytes)={len(raw)})")


# ---------------------------------------------------------------------------
# 5. pathlib 属性
# ---------------------------------------------------------------------------
def demo_pathlib_attributes() -> None:
    p = Path("data") / "subdir" / "file.txt"
    assert p.name == "file.txt"
    assert p.stem == "file"
    assert p.suffix == ".txt"
    assert p.parent.name == "subdir"
    assert "data" in p.parts
    print(f"[OK] pathlib attrs (name={p.name}, suffix={p.suffix})")


# ---------------------------------------------------------------------------
# 6. pathlib 读写 + 目录操作
# ---------------------------------------------------------------------------
def demo_pathlib_rw() -> None:
    p = Path(tempfile.gettempdir()) / "demo_pathlib_rw.txt"
    p.write_text("hello pathlib", encoding="utf-8")
    assert p.exists()
    assert p.is_file()
    assert p.read_text(encoding="utf-8") == "hello pathlib"

    # 创建 + 删除目录
    d = Path(tempfile.gettempdir()) / "demo_dir_a" / "demo_dir_b"
    d.mkdir(parents=True, exist_ok=True)
    assert d.exists()
    d.rmdir()  # 删最深的空目录
    d.parent.rmdir()  # 再删父目录
    p.unlink()
    print("[OK] pathlib read/write/mkdir")


# ---------------------------------------------------------------------------
# 7. glob / rglob 模式匹配
# ---------------------------------------------------------------------------
def demo_glob() -> None:
    # 用临时目录做实验
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text("# a")
        (root / "b.py").write_text("# b")
        (root / "sub").mkdir()
        (root / "sub" / "c.py").write_text("# c")
        (root / "sub" / "sub2").mkdir()
        (root / "sub" / "sub2" / "d.py").write_text("# d")
        (root / "readme.md").write_text("# readme")

        # 当前层 .py
        shallow = sorted(p.name for p in root.glob("*.py"))
        assert shallow == ["a.py", "b.py"]

        # 递归所有 .py
        deep = sorted(p.name for p in root.rglob("*.py"))
        assert deep == ["a.py", "b.py", "c.py", "d.py"]

    print(f"[OK] glob vs rglob (shallow={shallow}, deep={deep})")


# ---------------------------------------------------------------------------
# 8. 综合实战:统计代码行数
# ---------------------------------------------------------------------------
def demo_count_lines() -> None:
    """统计当前 .py 脚本目录的总行数"""
    src_dir = Path(__file__).parent
    py_files = list(src_dir.glob("*.py"))
    total_lines = 0
    file_count = 0
    for f in py_files:
        if f.name == "11_file_io_demo.py":  # 排除自己
            continue
        file_count += 1
        with f.open(encoding="utf-8") as fh:
            total_lines += sum(1 for _ in fh)
    print(f"[OK] count lines ({file_count} files, {total_lines} lines)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_open_modes()
    demo_read_methods()
    demo_with_statement()
    demo_text_vs_binary()
    demo_pathlib_attributes()
    demo_pathlib_rw()
    demo_glob()
    demo_count_lines()
    print("\n✅ 所有测试通过!")
