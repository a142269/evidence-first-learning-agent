# 14: 常用标准库 · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：常用标准库（os/sys/datetime/re/logging）
- 副标题：Python 程序设计 · 第 15 讲

## Slide 2：本讲大纲
- sys 解释器交互
- os 操作系统接口
- datetime 日期时间
- re 正则高级
- logging 分级日志
- 其他常用库
- CLI 工具骨架

## Slide 3：sys 模块
- sys.version：解释器版本
- sys.argv：命令行参数
- sys.exit()：退出
- sys.stdin / stdout / stderr
- sys.path：模块搜索路径

## Slide 4：os 模块
- os.environ：环境变量
- os.getcwd() / os.chdir()
- os.path.join / exists / isdir
- os.walk()：遍历目录
- 推荐：os 用于环境变量，pathlib 用于路径

## Slide 5：datetime
```python
from datetime import datetime, timedelta

dt = datetime(2026, 7, 12, 10, 30)
dt.strftime("%Y-%m-%d %H:%M:%S")
dt = datetime.strptime("2026-07-12", "%Y-%m-%d")
delta = timedelta(days=7)
next_week = dt + delta
```
- 构造 / 格式化 / 解析 / 运算
- 时区：3.9+ zoneinfo
- [配图：datetime 格式符表]

## Slide 6：re 模块
- 5 个核心函数：search / match / findall / sub / split
- 编译：re.compile() 性能更好
- 标志：IGNORECASE / MULTILINE / DOTALL
- 命名组：(?P<name>...)
- [代码示例：邮箱/URL/IP 模式]

## Slide 7：logging 五级
| 级别 | 数值 | 用途 |
|------|------|------|
| DEBUG | 10 | 调试细节 |
| INFO | 20 | 正常信息 |
| WARNING | 30 | 警告 |
| ERROR | 40 | 错误 |
| CRITICAL | 50 | 致命 |

- basicConfig 配置
- 模块化 logger：getLogger(__name__)

## Slide 8：logging 实战
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

logger.info("处理中...")
logger.exception("失败")  # 自动记录堆栈
```
- 输出到文件
- 不同 handler
- [代码示例：完整 logging 配置]

## Slide 9：其他常用标准库
- math：数学函数
- random：随机数
- statistics：统计
- itertools：迭代工具
- functools：函数工具
- hashlib：哈希
- uuid：唯一标识
- argparse：CLI 解析
- subprocess：子进程

## Slide 10：argparse 实战
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("input", type=Path)
parser.add_argument("--top", type=int, default=3)
args = parser.parse_args()
```
- CLI 工具标配
- 自动生成 --help
- 子命令：add_subparsers
- [代码示例：学生成绩 CLI]

## Slide 11：本讲总结与作业
- 核心要点：
  1. sys/os 是基础
  2. datetime + re + logging 是高频
  3. 优先标准库，再考虑第三方
- 作业：
  1. 实现 days_until(target)
  2. 实现 parse_log_line(line)
  3. 用 argparse 写 CLI
