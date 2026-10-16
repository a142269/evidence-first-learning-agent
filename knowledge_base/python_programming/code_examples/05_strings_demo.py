"""Python 程序设计 · 配套实操示例 05 · 字符串 demo

对应章节: 05 字符串操作与正则入门
对应 KP  : PY_009 (字符串操作)
Bloom 关注: Apply / Analyze
运行方式 : python 05_strings_demo.py
依赖     : 纯标准库
说明     : 7 个 demo 函数覆盖 f-string、常用方法、str/bytes、join/split、re 模块、日志解析、slugify。
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# 1. f-string 格式化
# ---------------------------------------------------------------------------
def demo_fstring() -> None:
    name = "A3"
    score = 95.5
    pi = 3.1415926

    # 基本
    assert f"{name} 得分 {score}" == "A3 得分 95.5"
    # 精度
    assert f"{pi:.2f}" == "3.14"
    # 宽度对齐
    assert f"{'hi':>10}|" == "        hi|"
    assert f"{'hi':^10}|" == "    hi    |"
    # 千分位
    assert f"{1234567:,}" == "1,234,567"
    # 百分比
    assert f"{0.876:.2%}" == "87.60%"
    # 自记录
    assert f"{score=}" == "score=95.5"
    assert f"{score=:.1f}" == "score=95.5"
    print("[OK] f-string formatting")


# ---------------------------------------------------------------------------
# 2. 字符串方法
# ---------------------------------------------------------------------------
def demo_string_methods() -> None:
    s = "  Hello, World!  "

    # 大小写
    assert s.upper().strip() == "HELLO, WORLD!"
    assert "HELLO".lower() == "hello"
    assert "hello world".title() == "Hello World"
    assert "hello WORLD".swapcase() == "HELLO world"

    # 去除与填充
    assert s.strip() == "Hello, World!"
    assert "42".zfill(5) == "00042"
    assert "hi".center(10, "-") == "----hi----"

    # 切分与拼接
    parts = "a,b,c".split(",")
    assert parts == ["a", "b", "c"]
    joined = ",".join(parts)
    assert joined == "a,b,c"

    # 查找
    assert "hello".find("ll") == 2
    assert "hello".count("l") == 2
    assert "hello world".startswith("hello")
    assert "hello world".endswith("world")
    print("[OK] string methods")


# ---------------------------------------------------------------------------
# 3. str vs bytes
# ---------------------------------------------------------------------------
def demo_str_bytes() -> None:
    s = "你好,世界"
    b = s.encode("utf-8")
    s2 = b.decode("utf-8")
    assert isinstance(s, str)
    assert isinstance(b, bytes)
    assert s == s2
    # 字符与码点
    assert ord("A") == 65
    assert chr(65) == "A"
    assert hex(ord("你")) == "0x4f60"
    print(f"[OK] str vs bytes (len(s)={len(s)}, len(b)={len(b)})")


# ---------------------------------------------------------------------------
# 4. join 性能:vs += 拼接
# ---------------------------------------------------------------------------
def demo_join_performance() -> None:
    import time

    parts = [f"item_{i}" for i in range(50_000)]

    t0 = time.perf_counter()
    s_join = "".join(parts)
    t_join = time.perf_counter() - t0

    t0 = time.perf_counter()
    s_plus = ""
    for p in parts:
        s_plus += p
    t_plus = time.perf_counter() - t0

    assert s_join == s_plus
    assert t_join < t_plus
    print(f"[OK] join perf (join={t_join*1000:.1f}ms, +=={t_plus*1000:.1f}ms)")


# ---------------------------------------------------------------------------
# 5. 正则基础
# ---------------------------------------------------------------------------
def demo_regex_basic() -> None:
    text = "a1 b22 c333"

    # findall
    nums = re.findall(r"\d+", text)
    assert nums == ["1", "22", "333"]

    # 字符类
    words = re.findall(r"\w+", "hello, world!")
    assert words == ["hello", "world"]

    # search
    m = re.search(r"(\d+)", "abc 42 xyz")
    assert m.group(1) == "42"

    # sub
    masked = re.sub(r"\d+", "N", "a1 b22 c333")
    assert masked == "aN bN cN"

    # split
    parts = re.split(r"[,;\s]+", "a,b; c  d")
    assert parts == ["a", "b", "c", "d"]
    print("[OK] regex basics")


# ---------------------------------------------------------------------------
# 6. 命名组 + 贪婪/非贪婪
# ---------------------------------------------------------------------------
def demo_regex_advanced() -> None:
    # 命名组
    m = re.match(
        r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})",
        "2026-07-12"
    )
    assert m.group("year") == "2026"
    assert m.groupdict() == {"year": "2026", "month": "07", "day": "12"}

    # 贪婪 vs 非贪婪
    text = "<a><b>"
    greedy = re.findall(r"<.*>", text)
    non_greedy = re.findall(r"<.*?>", text)
    assert greedy == ["<a><b>"]
    assert non_greedy == ["<a>", "<b>"]
    print(f"[OK] regex named groups + greedy/non-greedy")


# ---------------------------------------------------------------------------
# 7. 实战:日志解析 + slugify
# ---------------------------------------------------------------------------
def demo_practical() -> None:
    # 日志解析
    log = """
2026-07-12 10:23:45 INFO  [user.py:42] User login: alice
2026-07-12 10:23:50 ERROR [db.py:88] Connection refused
"""
    pattern = re.compile(
        r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<level>INFO|ERROR|WARN)\s+"
        r"\[(?P<module>[\w.]+):(?P<line>\d+)\]\s+"
        r"(?P<msg>.+)"
    )
    parsed = [m.groupdict() for m in pattern.finditer(log)]
    assert len(parsed) == 2
    assert parsed[0]["level"] == "INFO"
    assert parsed[1]["level"] == "ERROR"

    # slugify
    def slugify(text: str) -> str:
        s = text.lower()
        s = re.sub(r"[\s_]+", "-", s)
        s = re.sub(r"[^a-z0-9\-]", "", s)
        s = re.sub(r"-+", "-", s)
        return s.strip("-")

    assert slugify("Hello, World! 2026") == "hello-world-2026"
    assert slugify("A3  智学领航") == "a3"
    print(f"[OK] log parsing + slugify (parsed {len(parsed)} log lines)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_fstring()
    demo_string_methods()
    demo_str_bytes()
    demo_join_performance()
    demo_regex_basic()
    demo_regex_advanced()
    demo_practical()
    print("\n✅ 所有测试通过!")
