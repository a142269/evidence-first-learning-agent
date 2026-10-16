---
chapter_id: '14'
slug: standard_library
title: 常用标准库(os/sys/datetime/re/logging)
kp_ids:
- PY_021
bloom_focus:
- Apply
- Analyze
prerequisites:
- '11'
estimated_minutes: 240
---

# 14: 常用标准库 · 站在巨人的肩膀上

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 240 分钟(4 学时)
> **前置知识**: §11 文件 I/O

## 学习目标

1. 掌握 `os` / `sys` 模块的常用功能。
2. 掌握 `datetime` 的日期时间处理与格式化。
3. 掌握 `re` 模块的高级正则特性。
4. 掌握 `logging` 模块的分级日志体系。
5. 能根据场景选择合适的标准库替代手写实现。

## 14.1 sys:Python 解释器交互

```python
import sys

# 解释器信息
sys.version          # "3.12.4 (main, ...)"
sys.platform         # "win32" / "linux" / "darwin"
sys.executable       # Python 解释器路径
sys.path             # 模块搜索路径

# 命令行参数
sys.argv             # ['script.py', 'arg1', 'arg2']

# 退出程序
sys.exit(0)          # 正常退出
sys.exit("出错了")   # 非 0 退出,打印消息

# 标准输入输出
sys.stdin            # 标准输入
sys.stdout.write("hello")  # 不自动换行
sys.stderr.write("error\n")
```

## 14.2 os:操作系统接口

```python
import os

# 环境变量
os.environ["PATH"]
os.getenv("HOME", default="/tmp")

# 当前目录
os.getcwd()
os.chdir("/tmp")

# 路径操作(老式)
os.path.join("a", "b", "c.txt")  # 跨平台拼接
os.path.exists("file.txt")
os.path.isdir("dir")
os.path.basename("/a/b/c.txt")  # "c.txt"
os.path.dirname("/a/b/c.txt")   # "/a/b"
os.path.splitext("file.txt")    # ("file", ".txt")

# 推荐用 pathlib(Path),但 os 在批量操作仍然强
os.makedirs("a/b/c", exist_ok=True)
os.rename("old", "new")
os.remove("file.txt")
os.rmdir("empty_dir")

# 遍历目录
for root, dirs, files in os.walk("."):
    for f in files:
        print(os.path.join(root, f))
```

## 14.3 datetime:日期与时间

```python
from datetime import date, datetime, timedelta, timezone

# 当前时间
now = datetime.now()
today = date.today()

# 构造
dt = datetime(2026, 7, 12, 10, 30, 0)

# 字段
dt.year, dt.month, dt.day
dt.hour, dt.minute, dt.second
dt.weekday()  # 0=周一

# 格式化
dt.strftime("%Y-%m-%d %H:%M:%S")        # "2026-07-12 10:30:00"
dt.strftime("%Y年%m月%d日")              # "2026年07月12日"

# 解析
dt = datetime.strptime("2026-07-12", "%Y-%m-%d")

# 时间差
delta = timedelta(days=7)
next_week = now + delta
diff = next_week - now
print(diff.days)  # 7

# 时区(3.9+ zoneinfo)
from zoneinfo import ZoneInfo
dt_shanghai = datetime.now(ZoneInfo("Asia/Shanghai"))
dt_ny = dt_shanghai.astimezone(ZoneInfo("America/New_York"))
```

**格式符**:

| 符号 | 含义 | 示例 |
|------|------|------|
| `%Y` | 4 位年 | 2026 |
| `%m` | 月(01-12) | 07 |
| `%d` | 日(01-31) | 12 |
| `%H` | 时(00-23) | 10 |
| `%M` | 分(00-59) | 30 |
| `%S` | 秒(00-59) | 00 |
| `%A` | 星期全名 | Monday |
| `%a` | 星期缩写 | Mon |

## 14.4 re:正则表达式

```python
import re

# 常用函数
re.search(pattern, string)    # 找第一个匹配
re.match(pattern, string)     # 从开头匹配
re.findall(pattern, string)   # 所有匹配(列表)
re.finditer(pattern, string)  # 所有匹配(迭代器)
re.sub(pattern, repl, string) # 替换
re.split(pattern, string)     # 切分

# 预编译(重复使用)
pattern = re.compile(r"\d+")

# 常用模式
email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
url = r"https?://[\w.-]+"
ipv4 = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"

# 标志
re.IGNORECASE      # 大小写不敏感
re.MULTILINE       # ^ $ 匹配每行
re.DOTALL          # . 匹配换行
re.compile(..., flags=re.IGNORECASE | re.MULTILINE)
```

## 14.5 logging:分级日志

### 14.5.1 五级日志

| 级别 | 数值 | 用途 |
|------|------|------|
| DEBUG | 10 | 调试细节 |
| INFO | 20 | 正常运行信息 |
| WARNING | 30 | 警告(可恢复) |
| ERROR | 40 | 错误(影响功能) |
| CRITICAL | 50 | 致命错误 |

### 14.5.2 基础用法

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logging.debug("调试信息")     # 不显示(level=INFO)
logging.info("用户登录")      # 显示
logging.warning("磁盘剩余 5%")
logging.error("请求失败")
logging.critical("数据库宕机")
```

### 14.5.3 模块化日志器

```python
# mymodule.py
logger = logging.getLogger(__name__)

def process():
    logger.info("开始处理")
    # ...
    logger.debug("中间状态: ...")
    logger.error("处理失败")
```

### 14.5.4 输出到文件

```python
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
```

## 14.6 其他常用标准库速览

| 模块 | 用途 |
|------|------|
| `math` | 数学函数(三角、对数、阶乘) |
| `random` | 随机数(`randint` / `choice` / `shuffle` / `sample`) |
| `statistics` | 统计函数(mean / median / stdev) |
| `json` | JSON 序列化(见 §12) |
| `csv` | CSV 读写(见 §12) |
| `itertools` | 迭代工具(chain / cycle / groupby / product) |
| `functools` | 函数工具(partial / reduce / lru_cache / total_ordering) |
| `collections` | 高级容器(见 §06) |
| `pathlib` | 路径操作(见 §11) |
| `argparse` | 命令行参数解析 |
| `subprocess` | 子进程管理 |
| `urllib` | URL 处理 |
| `hashlib` | 哈希(md5 / sha256) |
| `uuid` | UUID 生成 |
| `time` | 时间戳 |

## 14.7 实战:CLI 工具骨架

```python
import argparse
import logging
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="学生成绩统计")
    parser.add_argument("input", type=Path, help="CSV 文件")
    parser.add_argument("--top", type=int, default=3, help="显示前 N 名")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("grade")

    if not args.input.exists():
        logger.error(f"文件不存在: {args.input}")
        sys.exit(1)

    # ... 处理逻辑
    logger.info(f"读取 {args.input}")

if __name__ == "__main__":
    main()
```

## 14.8 常见误区

- **误区 1**:用 `print` 做日志——无法分级、无法重定向、无法结构化。
- **误区 2**:`datetime.now()` 不带时区——跨时区部署会出 bug,用 `datetime.now(timezone.utc)` 或 `ZoneInfo`。
- **误区 3**:正则写得太复杂——可读性差,先尝试 str 方法。
- **误区 4**:`os.path` 与 `pathlib` 混用——选一种保持一致。
- **误区 5**:`sys.exit()` 在库代码中——库不应该 exit,应该 raise。

## 14.9 本章小结

1. `sys`:解释器交互、命令行参数、退出。
2. `os`:环境变量、路径、目录操作(老式,新代码用 `pathlib`)。
3. `datetime`:日期时间构造、格式化、时间差、时区。
4. `re`:正则的 5 个核心函数 + 编译 + 标志。
5. `logging`:5 级日志 + 模块化 logger + basicConfig。
6. Python 标准库"电池包含"——遇到问题先查标准库。

## 14.10 练习思考

1. **动手实践**:用 `datetime` 计算从今天到下一个元旦还有多少天。
2. **动手实践**:用 `logging` 写一个函数,接受 level 参数,根据 level 输出不同消息。
3. **动手实践**:用 `argparse` 写一个 CLI,接受 `--input` / `--output` / `--verbose` 三个参数。
4. **代码分析**:解释 `datetime.now()` 和 `datetime.now(timezone.utc)` 的区别。
5. **拓展探索**:阅读 `pathlib.Path.glob` 源码,看它底层是怎么实现的。

## 14.11 拓展阅读

- 标准库索引:https://docs.python.org/3/library/index.html
- logging HOWTO:https://docs.python.org/3/howto/logging.html
- 《Python 标准库》Doug Hellmann 著

---

*配套练习:`exercises/14_standard_library_exercises.md`*
