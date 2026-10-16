---
chapter_ref: "12"
chapter_title: "CSV 与 JSON 结构化数据处理"
kp_refs: [PY_018]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 3 学时
---

# CSV 与 JSON 结构化数据处理 · 章节练习

> **配套**:A3 章节 §12 CSV 与 JSON
> **配对代码**:`code_examples/12_csv_json_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
JSON 的 4 种基本数据结构是?

- A. list / tuple / dict / set
- B. object / array / string / number
- C. object / array / string / null
- D. dict / list / int / float

<details><summary>答案</summary>C。JSON 只有:object({})、array([])、string、number、true/false、null。</details>

### Q2(Apply)
Python 中 `json.dumps({"name": "张三"})` 的输出是?

- A. `{"name": "张三"}`
- B. `{"name": "\\u5f20\\u4e09"}`
- C. 报错
- D. `{"name": null}`

<details><summary>答案</summary>B。默认 `ensure_ascii=True`,中文被转义为 \uXXXX。</details>

### Q3(Apply)
要保留 JSON 中的中文,应加什么参数?

- A. `ensure_ascii=False`
- B. `ascii=False`
- C. `encoding="utf-8"`
- D. `unicode=True`

<details><summary>答案</summary>A。`ensure_ascii=False` 让 dumps 输出原字符而非 \u 转义。</details>

### Q4(Analyze)
`csv.DictReader(f)` 返回的每行是什么类型?

- A. `list`
- B. `dict`
- C. `tuple`
- D. `str`

<details><summary>答案</summary>B。DictReader 把每行转成 dict,key 是表头。</details>

### Q5(Evaluate)
存储一个包含嵌套 dict + list 的复杂对象,推荐用?

- A. CSV
- B. JSON
- C. TXT
- D. 纯 Python pickle

<details><summary>答案</summary>B。JSON 天然支持嵌套,且跨语言、人类可读。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`json.loads('{"a": 1}')` 的返回类型是 Python 的 ______ 。

<details><summary>答案</summary>dict</details>

### Q7(Apply)
`json.dumps(data, ______=2)` 让输出带 2 空格缩进,易于阅读。

<details><summary>答案</summary>indent</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
Python 与 JSON 的类型对应关系是什么?哪些类型会丢失信息?

<details><summary>参考答案</summary>对应关系:
- dict ↔ object
- list / tuple ↔ array(tuple 不可逆变 list)
- str ↔ string
- int / float ↔ number
- True / False ↔ true / false
- None ↔ null
丢失信息:
- tuple → list(类型不可逆)
- int(超过 JS 安全整数范围 2^53)可能有精度损失
- bytes / datetime / 自定义类 需自定义 default 函数</details>

### Q9(Analyze)
`ensure_ascii=False` 有什么作用?在哪些场景必须设置?

<details><summary>参考答案</summary>作用:让 `json.dumps` 不把非 ASCII 字符(如中文)转成 `\uXXXX`,直接输出 UTF-8 原字符。
必须设置的场景:
1. 配置文件需要人类可读(中文 key 或 value)
2. API 返回 JSON 给前端,前端需显示中文
3. 数据导出(JSON 文件需直接 cat 看得懂)
不设置的代价:文件大小膨胀(中文变 6 字节 \u),可读性差。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
写函数 `csv_to_json(csv_path, json_path)`,把 CSV 转 JSON(首行表头,其余数据行),中文正常显示,2 空格缩进。

<details><summary>参考实现</summary>

```python
import csv
import json

def csv_to_json(csv_path, json_path):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
```

</details>

### Q11(Create)
实现 `save_user_profile(user: dict, json_path)`,user 含 `name` / `age` / `created_at`(datetime),用 default 参数把 datetime 序列化为 ISO 字符串。

<details><summary>参考实现</summary>

```python
import json
from datetime import datetime

def save_user_profile(user, json_path):
    def default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"not serializable: {type(obj)}")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(user, f, default=default, ensure_ascii=False, indent=2)
```

</details>

---

*本章配套代码:`code_examples/12_csv_json_demo.py` 包含 6 个 demo 函数,涵盖 CSV 读写、JSON dumps/loads、ensure_ascii、自定义对象、嵌套处理。*
