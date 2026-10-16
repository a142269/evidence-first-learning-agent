---
chapter_id: '12'
slug: csv_json
title: CSV 与 JSON 结构化数据处理
kp_ids:
- PY_018
bloom_focus:
- Apply
- Analyze
prerequisites:
- '11'
estimated_minutes: 180
---

# 12: CSV 与 JSON 结构化数据处理 · 数据交换的事实标准

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 180 分钟(3 学时)
> **前置知识**: §11 文件读写

## 学习目标

1. 掌握 `csv` 模块读写 CSV 文件(尤其 `DictReader` / `DictWriter`)。
2. 掌握 `json` 模块的序列化与反序列化。
3. 理解 JSON 与 Python 类型的对应关系。
4. 掌握中文 JSON 的 `ensure_ascii=False` 处理。
5. 能处理嵌套结构、自定义对象的 JSON 转换。

## 12.1 CSV 基础

CSV(Comma-Separated Values)是结构化数据最常见的存储格式之一。Python 的 `csv` 模块处理 CSV 文件。

### 12.1.1 读 CSV

```python
import csv

with open("data.csv", "r", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        print(row)  # 每一行是 list[str]
```

### 12.1.2 DictReader:按列名访问

```python
with open("data.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # row 是 dict:{"name": "Alice", "age": "25"}
        print(row["name"], row["age"])
```

### 12.1.3 写 CSV

```python
rows = [
    ["name", "age", "city"],
    ["Alice", 25, "Beijing"],
    ["Bob", 30, "Shanghai"],
]

with open("out.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(rows)
```

`newline=""` 避免 Windows 写入双重换行。

### 12.1.4 DictWriter:按列写入

```python
with open("out.csv", "w", encoding="utf-8", newline="") as f:
    fieldnames = ["name", "age", "city"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow({"name": "Alice", "age": 25, "city": "Beijing"})
    writer.writerow({"name": "Bob", "age": 30, "city": "Shanghai"})
```

### 12.1.5 自定义分隔符

```python
# TSV 文件:用 \t 分隔
csv.reader(f, delimiter="\t")
```

## 12.2 JSON 基础

JSON(JavaScript Object Notation)是现代 API 通信与配置文件的事实标准。

### 12.2.1 Python 与 JSON 类型对应

| Python | JSON |
|--------|------|
| `dict` | `{}` |
| `list` | `[]` |
| `tuple` | `[]`(不可逆) |
| `str` | `"string"` |
| `int` / `float` | `number` |
| `True` / `False` | `true` / `false` |
| `None` | `null` |

### 12.2.2 dumps / loads:字符串与对象

```python
import json

# Python → JSON 字符串
data = {"name": "Alice", "age": 25, "tags": ["vip", "new"]}
s = json.dumps(data)
print(s)  # '{"name": "Alice", "age": 25, "tags": ["vip", "new"]}'

# JSON 字符串 → Python
obj = json.loads(s)
print(obj["name"])  # "Alice"
```

### 12.2.3 dump / load:文件读写

```python
# 写文件
data = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 读文件
with open("data.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)
```

### 12.2.4 中文处理

```python
# ❌ 中文被转义
json.dumps({"name": "张三"})  # '{"name": "\\u5f20\\u4e09"}'

# ✅ 用 ensure_ascii=False
json.dumps({"name": "张三"}, ensure_ascii=False)  # '{"name": "张三"}'
```

### 12.2.5 美化输出

```python
print(json.dumps(data, indent=2, sort_keys=True))
# {
#   "age": 25,
#   "name": "Alice"
# }
```

## 12.3 自定义对象序列化

JSON 默认只支持基本类型,自定义类需要 `default` 参数:

```python
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class User:
    name: str
    age: int
    created_at: datetime

u = User("Alice", 25, datetime.now())

# ❌ 默认抛 TypeError
# json.dumps(u)

# ✅ 用 default 把对象转 dict
def user_default(obj):
    if isinstance(obj, User):
        return {**asdict(obj), "created_at": obj.created_at.isoformat()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not serializable: {type(obj)}")

print(json.dumps(u, default=user_default, ensure_ascii=False))
```

## 12.4 实战:学生成绩管理

```python
import json
import csv
from pathlib import Path

# 1. 从 CSV 读取
students = []
with open("scores.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        students.append({
            "name": row["name"],
            "math": int(row["math"]),
            "english": int(row["english"]),
            "chinese": int(row["chinese"]),
        })

# 2. 计算总分与平均
for s in students:
    s["total"] = s["math"] + s["english"] + s["chinese"]
    s["average"] = round(s["total"] / 3, 2)

# 3. 保存为 JSON
with open("scores.json", "w", encoding="utf-8") as f:
    json.dump(students, f, ensure_ascii=False, indent=2)

# 4. 加载回 Python
with open("scores.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)
print(loaded[0])  # 第一个学生
```

## 12.5 JSON 路径:`jsonpath` 与 `jq`

复杂 JSON 提取子字段,Python 标准库没有原生支持,常用:

```python
# 1. 手动 dict 访问
data["users"][0]["profile"]["name"]

# 2. jmespath(类似 JSONPath)
import jmespath
jmespath.search("users[0].profile.name", data)

# 3. shell 工具:jq(命令行)
# $ cat data.json | jq '.users[0].profile.name'
```

## 12.6 常见误区

- **误区 1**:`json.dump(data, f)` 不写 `ensure_ascii=False` —— 中文变 `\uXXXX`。
- **误区 2**:`json.loads()` 收到非 JSON 字符串会抛 `JSONDecodeError`,需要 try/except。
- **误区 3**:把 `tuple` 序列化 —— JSON 没 tuple,反序列化会变 list。
- **误区 4**:CSV 含嵌套数据 —— 应该用 JSON 或 YAML。
- **误区 5**:`indent=2` 写入大文件 —— 文件会膨胀 2-3 倍,仅调试用。

## 12.7 本章小结

1. `csv.reader` / `csv.writer` 按行处理;`DictReader` / `DictWriter` 按列名。
2. CSV 写入必须 `newline=""`(Windows)。
3. `json.dumps` / `loads` 处理字符串,`dump` / `load` 处理文件。
4. `ensure_ascii=False` 保留中文,`indent=2` 美化。
5. 自定义对象用 `default` 参数转换,常用 `dataclasses.asdict` 辅助。
6. JSON 是 API 与配置文件标准,CSV 是表格数据标准。

## 12.8 练习思考

1. **动手实践**:写函数 `csv_to_json(csv_path, json_path)`,把 CSV 转 JSON(首行是表头)。
2. **动手实践**:用 `DictWriter` 写入学生成绩表,字段含 name / math / english / chinese / total。
3. **代码分析**:下面代码输出什么?为什么?
   ```python
   data = {"name": "张三"}
   print(json.dumps(data))
   print(json.dumps(data, ensure_ascii=False))
   ```
4. **动手实践**:实现 `load_config(path) -> dict`,支持 JSON 与 YAML(YAML 用 `yaml.safe_load`)。
5. **拓展探索**:阅读 `pyyaml` 库文档,理解 YAML 的优势(注释、引用、多文档)。

## 12.9 拓展阅读

- csv 模块:https://docs.python.org/3/library/csv.html
- json 模块:https://docs.python.org/3/library/json.html
- jq(命令行 JSON 工具):https://jqlang.github.io/jq/

---

*配套代码示例:`code_examples/12_csv_json_demo.py`*
*配套练习:`exercises/12_csv_json_exercises.md`*
