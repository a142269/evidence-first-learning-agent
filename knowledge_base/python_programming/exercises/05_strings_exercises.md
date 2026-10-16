---
chapter_ref: "05"
chapter_title: "字符串操作与正则入门"
kp_refs: [PY_009]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 3 学时
---

# 字符串操作与正则入门 · 章节练习

> **配套**:A3 章节 §05 字符串操作与正则入门
> **配对代码**:`code_examples/05_strings_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 3 中 `str` 的本质是?

- A. ASCII 字节序列
- B. Unicode 字符序列
- C. UTF-8 字节序列
- D. 任意编码字节序列

<details><summary>答案</summary>B。Python 3 字符串是 Unicode,字节串用 `bytes`。</details>

### Q2(Apply)
`"  hello  ".strip()` 的输出是?

- A. `"  hello  "`
- B. `"hello"`
- C. `"hello  "`
- D. `"  hello"`

<details><summary>答案</summary>B。`strip` 去除两端空白。</details>

### Q3(Apply)
`f"{3.14159:.2f}"` 的输出是?

- A. `"3.14"`
- B. `"3.14159"`
- C. `"3.142"`
- D. `"3.1"`

<details><summary>答案</summary>A。`:.2f` 保留 2 位小数(四舍五入)。</details>

### Q4(Analyze)
以下正则匹配 `"a1 b22 c333"` 中所有数字的结果是?
```python
re.findall(r"\d+", "a1 b22 c333")
```

- A. `["1", "22", "333"]`
- B. `["12", "3"]`
- C. `["1", "2", "3"]`
- D. `"12233"`

<details><summary>答案</summary>A。`\d+` 匹配一个或多个数字。</details>

### Q5(Evaluate)
下列哪种字符串拼接方式性能最好(对 N 个字符串)?

- A. `s = ""; for x in lst: s += x`
- B. `"".join(lst)`
- C. `reduce(lambda a, b: a + b, lst)`
- D. `"".join([str(x) for x in lst])`

<details><summary>答案</summary>B。`join` 是 O(n);`+=` 是 O(n²);reduce 与 `+=` 类似。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
执行 `re.findall(r"\w+", "hello, world!")` 的结果是 `["hello", "world"]`,`\w` 等价于字符类 `[______]`。

<details><summary>答案</summary>a-zA-Z0-9_</details>

### Q7(Apply)
执行 `"".join(["a", "b", "c"])` 的结果是 `"______"`。

<details><summary>答案</summary>abc</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 `str` 与 `bytes` 的区别,什么场景必须用 `bytes`?

<details><summary>参考答案</summary>- `str`:Unicode 字符序列,文本处理
- `bytes`:0-255 整数序列,二进制数据
必须用 `bytes` 的场景:
1. 网络通信(socket.send/recv)
2. 二进制文件读写(图片/音频/视频)
3. 哈希计算(`hashlib.md5(data)` 要求 bytes)
4. 序列化协议(如 Protobuf 二进制格式)
转换:`str.encode(encoding) → bytes`、`bytes.decode(encoding) → str`</details>

### Q9(Analyze)
正则的贪婪匹配与非贪婪匹配有什么区别?写代码说明。

<details><summary>参考答案</summary>贪婪:尽可能多匹配;非贪婪:尽可能少匹配(在量词后加 `?`)。
```python
import re
text = "<a><b>"
re.findall(r"<.*>", text)   # 贪婪: ['<a><b>']
re.findall(r"<.*?>", text)  # 非贪婪: ['<a>', '<b>']
```
常用量词:`*?` `+?` `??` `{n,m}?`。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `slugify(text: str) -> str`,把 `"Hello, World! 2026"` 转换为 `"hello-world-2026"`(小写、标点/连续空白换 `-`、首尾去 `-`)。

<details><summary>参考实现</summary>

```python
import re

def slugify(text):
    s = text.lower()
    s = re.sub(r"[\s_]+", "-", s)        # 空白与下划线换连字符
    s = re.sub(r"[^a-z0-9\-]", "", s)    # 去掉非字母数字
    s = re.sub(r"-+", "-", s)            # 合并连字符
    return s.strip("-")

print(slugify("Hello, World! 2026"))  # hello-world-2026
```

</details>

### Q11(Create)
实现 `extract_emails(text: str) -> list[str]`,从一段文本中提取所有合法 email 地址(简化版:`xxx@yyy.zzz`)。

<details><summary>参考实现</summary>

```python
import re

def extract_emails(text):
    pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    return pattern.findall(text)

text = "请联系 alice@example.com 或 bob.test+filter@school.edu.cn 反馈。"
print(extract_emails(text))
# ['alice@example.com', 'bob.test+filter@school.edu.cn']
```

</details>

---

*本章配套代码:`code_examples/05_strings_demo.py` 包含 7 个 demo 函数,涵盖格式化、常用方法、f-string 进阶、re 模块等。*
