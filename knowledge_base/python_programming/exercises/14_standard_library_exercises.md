---
chapter_ref: "14"
chapter_title: "常用标准库(os/sys/datetime/re/logging)"
kp_refs: [PY_021]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 常用标准库 · 章节练习

> **配套**:A3 章节 §14 常用标准库

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 日志的五级从低到高是?

- A. INFO < DEBUG < WARNING < ERROR < CRITICAL
- B. DEBUG < INFO < WARNING < ERROR < CRITICAL
- C. DEBUG < INFO < ERROR < WARNING < CRITICAL
- D. INFO < DEBUG < WARNING < CRITICAL < ERROR

<details><summary>答案</summary>B。从低到高:DEBUG(10) → INFO(20) → WARNING(30) → ERROR(40) → CRITICAL(50)。</details>

### Q2(Apply)
`datetime.now()` 与 `datetime.now(timezone.utc)` 的区别?

- A. 完全一样
- B. 后者带时区信息(naive vs aware)
- C. 前者更快
- D. 前者更精确

<details><summary>答案</summary>B。前者 naive datetime(无时区),后者 aware datetime(带 UTC 时区)。跨时区推荐后者。</details>

### Q3(Apply)
`re.findall(r"\d+", "a1b22c333")` 的结果是?

- A. `[1, 22, 333]`
- B. `["1", "22", "333"]`
- C. `"122333"`
- D. `["a1b22c333"]`

<details><summary>答案</summary>B。findall 返回 list[str]。</details>

### Q4(Analyze)
`os.path.join("a", "/b", "c")` 的结果是?

- A. `"a/b/c"`
- B. `"/b/c"`
- C. `"a\\b\\c"`
- D. 报错

<details><summary>答案</summary>B。绝对路径 `/b` 会重置前面的拼接,只保留 `/b/c`(因为 POSIX 路径以 / 开头)。</details>

### Q5(Evaluate)
需要记录带时间戳的可分级的应用日志,推荐用?

- A. `print()`
- B. `logging`
- C. 写文件
- D. stdout

<details><summary>答案</summary>B。logging 提供 5 级、可重定向、可结构化、可模块化。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`datetime(2026, 7, 12).strftime("%Y-%m-%d")` 的输出是 `"______"`。

<details><summary>答案</summary>2026-07-12</details>

### Q7(Apply)
`logging.getLogger(__name__)` 在模块中调用,`__name__` 是当前模块的 ______ 名。

<details><summary>答案</summary>完整(含包路径,如 gradebook.service)</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 `os.path` 与 `pathlib` 的定位,新项目应该选哪个?

<details><summary>参考答案</summary>- `os.path`:老式字符串路径操作,基于字符串拼接
- `pathlib`:面向对象的路径 API,Python 3.4+ 标准库
新项目应选 `pathlib`,原因:
1. 链式调用更直观:`Path("a") / "b" / "c.txt"`
2. API 统一:`exists()` / `is_file()` / `read_text()` 等
3. 跨平台自动处理分隔符
4. 配合 `glob` / `rglob` / `with_name` 等高级功能
但 `os.walk` / `os.listdir` / `os.environ` 等仍然有用,新代码混用是 OK 的。</details>

### Q9(Analyze)
`logging` 模块的"模块化 logger"如何实现?为什么推荐用 `getLogger(__name__)`?

<details><summary>参考答案</summary>模块化 logger:每个模块用 `logger = logging.getLogger(__name__)` 创建一个 logger,通过 `__name__` 自动获得模块路径(如 `gradebook.service`),形成层级结构。
推荐原因:
1. **层级控制**:`logging.getLogger("a.b.c")` 可继承 `a.b` / `a` 的配置
2. **粒度调节**:`logging.getLogger("gradebook").setLevel(DEBUG)` 只影响该项目
3. **可读性**:日志中 `name=gradebook.service` 一眼看出哪个模块
4. **避免全局污染**:比 `logging.info(...)` 更灵活</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
用 `datetime` 写一个 `days_until(target: str) -> int` 函数,接受 `"YYYY-MM-DD"` 字符串,返回到该日期的天数(正数表示未来,负数表示过去)。

<details><summary>参考实现</summary>

```python
from datetime import datetime, date

def days_until(target):
    target_date = datetime.strptime(target, "%Y-%m-%d").date()
    today = date.today()
    return (target_date - today).days

print(days_until("2026-12-31"))  # 距今正/负天数
```

</details>

### Q11(Create)
实现一个 `parse_log_line(line: str) -> dict`,解析 `[2026-07-12 10:30:45] INFO user.login: User alice logged in`,返回 `{"time": ..., "level": ..., "module": ..., "msg": ...}`(用正则)。

<details><summary>参考实现</summary>

```python
import re
from datetime import datetime

def parse_log_line(line):
    pattern = re.compile(
        r"\[(?P<time>[\d\-: ]+)\]\s+"
        r"(?P<level>\w+)\s+"
        r"(?P<module>[\w.]+):\s+"
        r"(?P<msg>.+)"
    )
    m = pattern.match(line)
    if not m:
        return None
    d = m.groupdict()
    d["time"] = datetime.strptime(d["time"], "%Y-%m-%d %H:%M:%S")
    return d
```

</details>

---

*本章配套练习覆盖 sys / os / datetime / re / logging 五大常用标准库。*
