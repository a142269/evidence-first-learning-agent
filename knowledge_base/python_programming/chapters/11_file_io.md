---
chapter_id: '11'
slug: file_io
title: 文件读写与 pathlib
kp_ids:
- PY_016
- PY_017
bloom_focus:
- Apply
- Analyze
prerequisites:
- '10'
estimated_minutes: 300
---

# 11: 文件读写与 pathlib · 与外部世界对话

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 300 分钟(5 学时)
> **前置知识**: §10 魔术方法(上下文管理器)

## 学习目标

1. 掌握 `open()` 函数的文件模式、编码与缓冲。
2. 熟练使用 `with` 语句安全操作文件。
3. 理解文本模式与二进制模式的区别。
4. 掌握 `pathlib.Path` 的常用操作,理解相对 `os.path` 的优势。
5. 能用 `glob` / `rglob` 进行文件遍历与模式匹配。

## 11.1 open() 函数基础

```python
# 最常见的写法
with open("data.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

**核心参数**:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `file` | 必填 | 文件路径 |
| `mode` | `"r"` | 模式(见下表) |
| `encoding` | 平台相关 | 编码(推荐显式) |
| `buffering` | -1 | 缓冲策略(0=无,1=行,>1=字节) |
| `newline` | None | 换行符处理 |

**模式字符**:

| 字符 | 含义 |
|------|------|
| `r` | 读(默认) |
| `w` | 写(覆盖) |
| `x` | 排他创建(已存在则失败) |
| `a` | 追加 |
| `b` | 二进制 |
| `t` | 文本(默认) |
| `+` | 同时读写 |

可组合,例:`"rb"` 读二进制,`"w+b"` 读写二进制。

## 11.2 文件读写方法

```python
# 读取
content = f.read()          # 整个文件
line = f.readline()         # 一行
lines = f.readlines()       # 所有行(列表)

# 遍历(内存友好)
for line in f:
    print(line.rstrip())    # 注意末尾有 \n

# 写入
f.write("hello\n")          # 字符串
f.writelines(["a\n", "b\n"])  # 多行

# 指针
f.tell()                    # 当前位置
f.seek(0)                   # 回到开头
```

**实战建议**:大文件用 `for line in f` 逐行处理,不要用 `f.read()` 全部加载。

## 11.3 with 语句:资源管理的标准方式

文件操作必须用 `with` —— 无论是否异常,文件都会被关闭:

```python
# ❌ 错误写法
f = open("data.txt")
data = f.read()
# 如果中间抛异常,文件不关
f.close()

# ✅ 正确
with open("data.txt") as f:
    data = f.read()
# 自动关闭
```

`with` 本质是上下文管理器(`__enter__` / `__exit__`),底层调用 `f.close()`。

## 11.4 文本模式 vs 二进制模式

```python
# 文本模式:自动处理编码与换行
with open("text.txt", "r", encoding="utf-8") as f:
    text = f.read()  # str

# 二进制模式:原始字节
with open("image.png", "rb") as f:
    data = f.read()  # bytes
```

**何时用二进制**:
1. 图片、音频、视频等非文本文件
2. 网络 socket 数据
3. 跨平台文件(避免 Windows \r\n 与 Unix \n 转换问题)

## 11.5 编码问题

**错误案例**:

```python
with open("data.txt", "rb") as f:
    raw = f.read()
text = raw.decode("utf-8")  # 解码失败抛 UnicodeDecodeError
```

**解决方案**:

```python
# 1. 指定 errors 处理
with open("data.txt", encoding="utf-8", errors="replace") as f:
    text = f.read()  # 错误字符用 U+FFFD 替换

# 2. chardet 自动检测(需安装)
# import chardet
# encoding = chardet.detect(raw)["encoding"]
```

**Windows 常见坑**:默认编码是 GBK,跨平台代码必须显式 `encoding="utf-8"`。

## 11.6 pathlib:现代路径操作

`pathlib` 提供了面向对象的路径 API,比 `os.path` 更直观。

### 11.6.1 创建 Path

```python
from pathlib import Path

p = Path("data") / "subdir" / "file.txt"  # 路径拼接(/)
print(p)               # data\subdir\file.txt (Windows)
print(p.as_posix())    # data/subdir/file.txt
home = Path.home()     # 用户主目录
cwd = Path.cwd()       # 当前工作目录
```

### 11.6.2 属性

```python
p = Path("/home/user/data.txt")

p.name            # 'data.txt'
p.stem            # 'data'
p.suffix          # '.txt'
p.suffixes        # ['.tar', '.gz']
p.parent          # PosixPath('/home/user')
p.parents[0]      # 父目录
p.parents[1]      # 祖父目录
p.root            # '/'
p.parts           # ('/', 'home', 'user', 'data.txt')
```

### 11.6.3 文件操作

```python
p = Path("data.txt")

p.exists()              # 文件/目录是否存在
p.is_file()             # 是文件
p.is_dir()              # 是目录
p.stat()                # 详细信息(st_size, st_mtime, ...)

# 读
text = p.read_text(encoding="utf-8")
data = p.read_bytes()

# 写
p.write_text("hello", encoding="utf-8")
p.write_bytes(b"\x00\x01")

# 创建/删除
p.mkdir(parents=True, exist_ok=True)  # 创建目录
p.unlink(missing_ok=True)            # 删除文件(missing_ok 静默)
```

### 11.6.4 glob 模式匹配

```python
Path(".").glob("*.py")        # 当前目录所有 .py
Path(".").rglob("*.py")       # 递归所有 .py
Path("src").glob("**/*.md")   # src 下所有 .md(含子目录)
```

**实战:统计代码行数**

```python
total = 0
for p in Path(".").rglob("*.py"):
    total += sum(1 for _ in p.open(encoding="utf-8"))
print(total)
```

## 11.7 实战:日志聚合

```python
from pathlib import Path
from datetime import datetime

log_dir = Path("logs")
output = Path("combined.log")

with output.open("w", encoding="utf-8") as out:
    for log_file in sorted(log_dir.glob("*.log")):
        out.write(f"--- {log_file.name} ---\n")
        out.write(log_file.read_text(encoding="utf-8"))
        out.write("\n")
```

## 11.8 临时文件

```python
from tempfile import NamedTemporaryFile, TemporaryDirectory

# 临时文件
with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write("hello")
    print(f.name)

# 临时目录
with TemporaryDirectory() as d:
    p = Path(d) / "data.txt"
    p.write_text("test")
    print(p)  # 退出 with 自动删除
```

## 11.9 常见误区

- **误区 1**:Windows 上不写 `encoding` —— 默认 GBK,中文乱码。
- **误区 2**:`f.read()` 读取超大文件 —— 内存爆。
- **误区 3**:`open()` 后不用 `with` —— 异常时文件不关,资源泄漏。
- **误区 4**:把 Windows 路径硬编码到代码里 —— 用 `pathlib` 跨平台。
- **误区 5**:`"r+"` 模式不存在的文件就失败 —— 想新建文件用 `"w+"`。

## 11.10 本章小结

1. `open()` 是文件操作入口,`with` 是标准写法。
2. 模式:`r` / `w` / `a` / `x` / `b` / `t` / `+` 可组合。
3. 文本 vs 二进制:文本处理字符串,二进制处理 bytes。
4. `pathlib.Path` 提供面向对象路径 API,`/` 拼接路径。
5. `glob` / `rglob` 做模式匹配,支持 `**` 递归。
6. 大文件用逐行迭代,不要一次性 `read()`。
7. 显式 `encoding="utf-8"` 避免跨平台乱码。

## 11.11 练习思考

1. **动手实践**:用 `with` 读取一个文本文件,统计行数、单词数、字符数。
2. **动手实践**:用 `pathlib` 遍历当前目录所有 `.py` 文件,统计总行数与文件数。
3. **代码分析**:下面代码有什么问题?如何修复?
   ```python
   f = open("data.txt", "r")
   lines = f.readlines()
   result = process(lines)
   f.close()
   ```
4. **动手实践**:把多个 CSV 文件合并为一个,每个文件加表头注释(`# file: xxx.csv`)。
5. **拓展探索**:阅读 `shutil` 模块文档,了解 `copy2` / `move` / `rmtree` 的用法。

## 11.12 拓展阅读

- pathlib 官方文档:https://docs.python.org/3/library/pathlib.html
- io 模块:https://docs.python.org/3/library/io.html
- 《流畅的 Python》第 17 章 文件与 I/O

---

*配套代码示例:`code_examples/11_file_io_demo.py`*
*配套练习:`exercises/11_file_io_exercises.md`*
