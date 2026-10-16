# 00: Python 语言概述 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：30 分钟

---

## Slide 1：封面
- 标题：Python 语言概述与环境搭建
- 副标题：Python 程序设计 · 第 1 讲
- 讲师：A3 智学领航
- 日期：2026-07

## Slide 2：本讲大纲
- Python 发展历史
- 解释型语言特点
- 环境搭建
- hello world
- pip 与虚拟环境

## Slide 3：Python 的诞生
- 1989 年，Guido van Rossum
- 1991 年正式发布（0.9.0）
- 设计哲学：简洁、可读性
- "Python 之禅"（PEP 20）
- [配图：Python logo + Guido 照片]

## Slide 4：Python 的核心特点
| 特点 | 说明 |
|------|------|
| 解释型 | 无需编译，逐行执行 |
| 动态类型 | 变量无需声明类型 |
| 跨平台 | Windows/macOS/Linux |
| 丰富的库 | 标准库 + PyPI 50 万+ 包 |
| 强类型 | 类型不自动转换 |

## Slide 5：解释型 vs 编译型
- 编译型：源码 → 编译器 → 机器码 → 执行（C/C++）
- 解释型：源码 → 解释器 → 逐行执行（Python）
- Python 实际上是"字节码 + 解释器"混合
- [配图：编译型 vs 解释型执行流程对比图]

## Slide 6：搭建 Python 环境
- 下载：python.org/downloads
- 安装：勾选 "Add Python to PATH"
- 验证：`python --version`
- IDE 选择：VS Code（推荐） / PyCharm / Jupyter
- [配图：VS Code 截图 + Python 扩展]

## Slide 7：第一个程序
```python
print("Hello, Python!")
print("A3 智学领航 · Python 课程")
```
- 运行方式：`python hello.py`
- 输出展示
- [代码示例：完整 hello.py 文件]

## Slide 8：REPL 交互式探索
- 启动：终端输入 `python`
- 提示符：`>>>` / `...`
- 常用操作：
  - 算术计算
  - 变量赋值
  - `import this`（Python 之禅）
- 退出：`exit()` / Ctrl+D
- [配图：REPL 截图]

## Slide 9：pip 与虚拟环境
- pip 基础：`install` / `list` / `freeze` / `uninstall`
- requirements.txt 锁定依赖
- 虚拟环境：解决多项目依赖冲突
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  ```
- [配图：venv 目录结构]

## Slide 10：Python 的应用领域
| 领域 | 框架/库 | 代表应用 |
|------|---------|----------|
| 数据科学 | pandas / NumPy | 数据分析 |
| 机器学习 | PyTorch / TF | ChatGPT |
| Web | Django / FastAPI | Instagram |
| 自动化 | Ansible | 服务器管理 |
| A3 系统 | - | 本课程配套 |

## Slide 11：常见误区
- ❌ "Python 慢" → NumPy / PyPy 加速
- ❌ "Python 2 还能用" → 2020 EOL，用 Python 3
- ❌ "装完 Python 就能写代码" → 还需 venv / IDE
- ❌ "pip 装的越多越好" → 用 requirements.txt 锁定

## Slide 12：本讲总结与作业
- 3 个核心要点：
  1. Python 是解释型+动态类型+强类型
  2. 开发环境 = 解释器 + IDE + venv
  3. REPL 是探索式学习利器
- 作业：
  1. 搭建环境，运行 hello world
  2. 创建 venv，激活后用 pip 安装 requests
  3. 阅读 PEP 20，选 3 句最有共鸣的话
