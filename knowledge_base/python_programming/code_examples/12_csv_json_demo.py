"""Python 程序设计 · 配套实操示例 12 · CSV 与 JSON demo

对应章节: 12 CSV 与 JSON 结构化数据处理
对应 KP  : PY_018 (CSV 与 JSON 处理)
Bloom 关注: Apply / Analyze
运行方式 : python 12_csv_json_demo.py
依赖     : 纯标准库
说明     : 6 个 demo 函数覆盖 CSV reader/writer、DictReader/Writer、JSON dumps/loads、ensure_ascii、自定义对象、嵌套结构。
"""
from __future__ import annotations

import csv
import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. CSV reader / writer
# ---------------------------------------------------------------------------
def demo_csv_basic() -> None:
    rows = [
        ["name", "age", "city"],
        ["Alice", 25, "Beijing"],
        ["Bob", 30, "Shanghai"],
    ]
    p = Path(tempfile.gettempdir()) / "demo_basic.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    with p.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        loaded = list(reader)
    # csv 读出来的全是 str,数字也是字符串
    expected = [[r[0], r[1], r[2]] for r in rows]  # age, city 转 str 后比较
    assert loaded[0] == expected[0]  # 表头
    assert loaded[1] == ["Alice", "25", "Beijing"]
    assert loaded[2] == ["Bob", "30", "Shanghai"]
    p.unlink()
    print(f"[OK] csv basic (rows={len(loaded)})")


# ---------------------------------------------------------------------------
# 2. DictReader / DictWriter
# ---------------------------------------------------------------------------
def demo_csv_dict() -> None:
    p = Path(tempfile.gettempdir()) / "demo_dict.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["name", "age", "city"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({"name": "Alice", "age": 25, "city": "Beijing"})
        writer.writerow({"name": "Bob", "age": 30, "city": "Shanghai"})

    with p.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        loaded = list(reader)
    assert loaded[0]["name"] == "Alice"
    assert loaded[1]["city"] == "Shanghai"
    p.unlink()
    print(f"[OK] csv dict ({len(loaded)} rows, fields={list(loaded[0].keys())})")


# ---------------------------------------------------------------------------
# 3. JSON dumps / loads
# ---------------------------------------------------------------------------
def demo_json_basic() -> None:
    data = {
        "name": "Alice",
        "age": 25,
        "tags": ["vip", "new"],
        "profile": {"level": 1, "xp": 100},
    }

    # 字符串
    s = json.dumps(data)
    assert isinstance(s, str)
    obj = json.loads(s)
    assert obj == data

    # 文件
    p = Path(tempfile.gettempdir()) / "demo_basic.json"
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    with p.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data
    p.unlink()
    print(f"[OK] json dumps/loads/dump/load (keys={list(loaded.keys())})")


# ---------------------------------------------------------------------------
# 4. ensure_ascii 与中文
# ---------------------------------------------------------------------------
def demo_ensure_ascii() -> None:
    data = {"name": "张三", "city": "北京"}
    # 默认:中文被转义
    s1 = json.dumps(data)
    assert "\\u" in s1
    # ensure_ascii=False:中文保留
    s2 = json.dumps(data, ensure_ascii=False)
    assert "张三" in s2
    # 解析
    obj = json.loads(s2)
    assert obj == data
    print("[OK] ensure_ascii=False (preserve Chinese)")


# ---------------------------------------------------------------------------
# 5. 自定义对象序列化(dataclass + datetime)
# ---------------------------------------------------------------------------
def demo_custom_serialization() -> None:
    @dataclass
    class User:
        name: str
        age: int
        created_at: datetime

    def default(obj):
        if isinstance(obj, User):
            d = asdict(obj)
            d["created_at"] = obj.created_at.isoformat()
            return d
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"not serializable: {type(obj)}")

    u = User("Alice", 25, datetime(2026, 7, 12, 10, 30))
    s = json.dumps(u, default=default, ensure_ascii=False, indent=2)
    obj = json.loads(s)
    assert obj["name"] == "Alice"
    assert obj["created_at"] == "2026-07-12T10:30:00"
    print(f"[OK] custom serialization (obj={obj})")


# ---------------------------------------------------------------------------
# 6. 综合实战:学生成绩 CSV ↔ JSON
# ---------------------------------------------------------------------------
def demo_student_grades() -> None:
    # 1. 写入 CSV
    p_csv = Path(tempfile.gettempdir()) / "demo_grades.csv"
    with p_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["name", "math", "english", "chinese"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({"name": "张三", "math": 90, "english": 85, "chinese": 92})
        writer.writerow({"name": "李四", "math": 78, "english": 95, "chinese": 88})

    # 2. 读取 CSV → 计算 total / average → 写 JSON
    students = []
    with p_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            math, eng, chi = int(row["math"]), int(row["english"]), int(row["chinese"])
            students.append({
                **row,
                "math": math, "english": eng, "chinese": chi,
                "total": math + eng + chi,
                "average": round((math + eng + chi) / 3, 2),
            })

    p_json = Path(tempfile.gettempdir()) / "demo_grades.json"
    with p_json.open("w", encoding="utf-8") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)

    # 3. 读回
    with p_json.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["total"] == 90 + 85 + 92
    assert loaded[0]["average"] == round((90 + 85 + 92) / 3, 2)
    p_csv.unlink()
    p_json.unlink()
    print(f"[OK] student grades (loaded[0]={loaded[0]})")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_csv_basic()
    demo_csv_dict()
    demo_json_basic()
    demo_ensure_ascii()
    demo_custom_serialization()
    demo_student_grades()
    print("\n✅ 所有测试通过!")
