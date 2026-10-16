---
chapter_id: '05'
slug: strings
title: 字符串操作与正则入门
kp_ids:
- PY_009
bloom_focus:
- Apply
- Analyze
prerequisites:
- '04'
estimated_minutes: 180
---

# 05: 字符串操作与正则入门 · 文本处理的瑞士军刀

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 180 分钟(3 学时)
> **前置知识**: §04 数据结构

## 学习目标

1. 掌握字符串的不可变性、Unicode 编码与字节串的区别。
2. 熟练使用 f-string、format、% 三种字符串格式化方式。
3. 掌握常用字符串方法:`split` / `join` / `strip` / `replace` / `find` 等。
4. 了解正则表达式的基本语法,能用 `re` 模块做模式匹配。
5. 能用字符串与正则解决文本清洗、日志解析、数据提取等实际问题。

## 5.1 字符串的本质

Python 3 字符串是 **Unicode 字符序列**;字节串(`bytes`)是 0-255 整数序列:

```python
s = "你好"           # str(Unicode)
b = s.encode()        # b'\xe4\xbd\xa0\xe5\xa5\xbd' 字节串
s2 = b.decode()       # '你好'

# 字符与码点
print(ord("A"))       # 65
print(chr(65))        # 'A'
print(hex(ord("你"))) # 0x4f60
```

**不可变性**:所有"修改"字符串的方法,实际都是返回新字符串:

```python
s = "hello"
print(s.upper())  # 'HELLO'
print(s)          # 'hello'  ← 原字符串不变
```

## 5.2 字符串字面量

```python
# 单引号 / 双引号等价
s1 = 'hello'
s2 = "hello"

# 三引号:多行字符串
doc = """
多行
字符串
"""

# 原始字符串(r 前缀):不转义
path = r"C:\Users\Alice\new\file.txt"
# 如果不用 r,需要写成 "C:\\Users\\Alice\\new\\file.txt"
```

## 5.3 字符串格式化

### 5.3.1 f-string(Python 3.6+,推荐)

```python
name = "Alice"
age = 25
print(f"{name} 今年 {age} 岁")  # Alice 今年 25 岁

# 表达式
print(f"{2 + 3}")            # 5
print(f"{name.upper()}")     # ALICE

# 格式说明符
pi = 3.14159
print(f"{pi:.2f}")           # 3.14
print(f"{pi:10.2f}")         # '      3.14'(宽度 10)
print(f"{'hi':>10}")         # '        hi'(右对齐)
print(f"{'hi':<10}|")        # 'hi        |'(左对齐)
print(f"{'hi':^10}|")        # '    hi    |'(居中)
print(f"{1234567:,}")        # '1,234,567'(千分位)

# 自记录表达式(3.8+)
print(f"{name=}, {age=}")    # name='Alice', age=25
```

### 5.3.2 str.format

```python
"{name} is {age}".format(name="Bob", age=30)        # 'Bob is 30'
"{} + {} = {}".format(1, 2, 3)                      # '1 + 2 = 3'
"{0} {1} {0}".format("A", "B")                      # 'A B A'
"{:.2f}".format(3.14159)                            # '3.14'
```

### 5.3.3 % 格式化(遗留)

```python
"%s is %d" % ("Carol", 28)        # 'Carol is 28'
"%.2f" % 3.14159                  # '3.14'
```

**新代码一律用 f-string**,可读性最好。

## 5.4 常用字符串方法

### 5.4.1 大小写转换

```python
"Hello, World!".upper()      # 'HELLO, WORLD!'
"Hello, World!".lower()      # 'hello, world!'
"hello, world!".title()      # 'Hello, World!'
"hello WORLD".capitalize()   # 'Hello world'
"Hello".swapcase()           # 'hELLO'
```

### 5.4.2 去除与填充

```python
"  hello  ".strip()          # 'hello'
"  hello  ".lstrip()         # 'hello  '
"  hello  ".rstrip()         # '  hello'

"42".zfill(5)                # '00042'
"hi".center(10, "-")         # '----hi----'
"hi".ljust(10)               # 'hi        '
"hi".rjust(10)               # '        hi'
```

### 5.4.3 切分与拼接

```python
# split:字符串 → 列表
"a,b,c".split(",")           # ['a', 'b', 'c']
"a  b  c".split()            # ['a', 'b', 'c']  ← 默认按空白
"a\nb\nc".splitlines()       # ['a', 'b', 'c']

# join:列表 → 字符串
",".join(["a", "b", "c"])    # 'a,b,c'
"".join(["h", "e", "l", "l", "o"])  # 'hello'
```

**性能**:`"".join()` 比 `+=` 拼接 N 个字符串快 N 倍(后者是 O(n²))。

### 5.4.4 查找与替换

```python
s = "hello world hello"

s.find("world")        # 6
s.find("xyz")          # -1(不抛异常)
s.index("xyz")         # ❌ ValueError

s.replace("hello", "hi")     # 'hi world hi'
s.replace("hello", "hi", 1)  # 只替换 1 次

s.startswith("hello")        # True
s.endswith("hello")          # True
s.count("hello")             # 2
```

### 5.4.5 判断类方法

```python
"123".isdigit()       # True
"abc".isalpha()       # True
"abc123".isalnum()    # True
"   ".isspace()       # True
"Hello".istitle()     # True
"hello".islower()     # True
"42".isdecimal()      # True
"\u00b2".isdigit()    # True(² 是 Unicode 数字)
```

## 5.5 正则表达式入门

正则(Regex)用模式字符串描述字符串集合。Python 用 `re` 模块。

### 5.5.1 基础元字符

| 字符 | 含义 |
|------|------|
| `.` | 任意单字符(除换行) |
| `^` | 行首 |
| `$` | 行尾 |
| `*` | 前一项 0 或多次 |
| `+` | 前一项 1 或多次 |
| `?` | 前一项 0 或 1 次 |
| `{n}` | 前一项恰好 n 次 |
| `{n,m}` | 前一项 n 到 m 次 |
| `[]` | 字符类([abc], [a-z], [^0-9]) |
| `|` | 或 |
| `()` | 分组 |
| `\` | 转义 |

### 5.5.2 常用模式

```python
import re

# 匹配
re.match(r"hello", "hello world")      # 从开头匹配
re.search(r"world", "hello world")    # 任意位置查找
re.findall(r"\d+", "a1 b22 c333")     # ['1', '22', '333']
re.finditer(r"\d+", "a1 b22 c333")    # 迭代器

# 替换
re.sub(r"\d+", "N", "a1 b22 c333")    # 'aN bN cN'

# 分割
re.split(r"[,;\s]+", "a,b; c  d")      # ['a', 'b', 'c', 'd']
```

### 5.5.3 字符类速记

| 速记 | 等价 | 含义 |
|------|------|------|
| `\d` | `[0-9]` | 数字 |
| `\D` | `[^0-9]` | 非数字 |
| `\w` | `[a-zA-Z0-9_]` | 单词字符 |
| `\W` | `[^a-zA-Z0-9_]` | 非单词字符 |
| `\s` | `[ \t\n\r\f\v]` | 空白 |
| `\S` | `[^ \t\n\r\f\v]` | 非空白 |

### 5.5.4 分组与命名

```python
# 捕获组
m = re.match(r"(\d{4})-(\d{2})-(\d{2})", "2026-07-12")
print(m.groups())  # ('2026', '07', '12')

# 命名组(更易读)
m = re.match(r"(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})", "2026-07-12")
print(m.group("year"))  # '2026'
print(m.groupdict())    # {'year': '2026', 'month': '07', 'day': '12'}

# 引用
re.sub(r"(\w+) \1", r"\1", "hello hello")  # 'hello'
```

### 5.5.5 贪婪 vs 非贪婪

```python
# 默认贪婪:尽可能多匹配
re.findall(r"<.*>", "<a><b>")  # ['<a><b>']

# 非贪婪:尽可能少匹配
re.findall(r"<.*?>", "<a><b>")  # ['<a>', '<b>']
```

### 5.5.6 编译提高性能

需要重复使用时,先 `compile`:

```python
pattern = re.compile(r"\d+")
pattern.findall("a1 b22")  # ['1', '22']
```

**预编译建议**:同一条正则使用 ≥3 次时,值得预编译。

## 5.6 实战:日志解析

```python
import re

log = """
2026-07-12 10:23:45 INFO  [user.py:42] User login: alice
2026-07-12 10:23:50 ERROR [db.py:88] Connection refused
2026-07-12 10:24:01 INFO  [user.py:55] User login: bob
"""

pattern = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2}) "
    r"(?P<time>\d{2}:\d{2}:\d{2}) "
    r"(?P<level>INFO|ERROR|WARN) "
    r"\[(?P<module>[\w.]+):(?P<line>\d+)\] "
    r"(?P<msg>.+)"
)

for m in pattern.finditer(log):
    print(m.groupdict())
# {'date': '2026-07-12', 'time': '10:23:45', 'level': 'INFO', 'module': 'user.py', 'line': '42', 'msg': 'User login: alice'}
# ...
```

## 5.7 常见误区

- **误区 1**:用 `+` 拼接大量字符串——性能 O(n²),改用 `join`。
- **误区 2**:混淆 `str` 与 `bytes`——网络/文件 I/O 要显式 `.encode()` / `.decode()`。
- **误区 3**:正则贪婪匹配导致"匹配过头"——加 `?` 转非贪婪。
- **误区 4**:用正则做"所有事"——简单字符串操作更清晰时,优先用 `str` 方法。
- **误区 5**:忽略 Unicode——中文/emoji 处理时,`.isdigit()` 不够,要看 `unicodedata`。

## 5.8 本章小结

1. Python 3 字符串是 Unicode 序列,不可变;字节串用 `bytes`。
2. f-string 是首选格式化方式,支持表达式、对齐、精度。
3. `join` / `split` / `strip` / `replace` / `find` 是最高频的方法。
4. 正则用 `re` 模块,核心函数:`match` / `search` / `findall` / `sub` / `split`。
5. 命名组 `(?P<name>...)` 让正则更具可读性。
6. 贪婪匹配默认,加 `?` 变非贪婪。
7. 实战:日志解析、数据提取、文本清洗。

## 5.9 练习思考

1. **概念辨析**:说明 `str` 和 `bytes` 的区别,什么场景必须用 `bytes`?
2. **动手实践**:写函数 `slugify(text) -> str`,把 `"Hello, World! 2026"` 转成 `"hello-world-2026"`(小写、空格/标点换 `-`、合并连字符)。
3. **动手实践**:用 f-string 输出一个 3 行 4 列的乘法表,数字右对齐宽度 4。
4. **动手实践**:用正则提取 URL 中的协议、域名、路径:`"https://docs.python.org/3/library/re.html"`。
5. **代码优化**:把以下循环改为 `join`:
   ```python
   result = ""
   for item in items:
       result += f"{item}\n"
   ```

## 5.10 拓展阅读

- Python 字符串方法文档:https://docs.python.org/3/library/stdtypes.html#string-methods
- re 模块文档:https://docs.python.org/3/library/re.html
- 《流畅的 Python》第 4 章 文本与字节序列

---

*配套代码示例:`code_examples/05_strings_demo.py`*
*配套练习:`exercises/05_strings_exercises.md`*
