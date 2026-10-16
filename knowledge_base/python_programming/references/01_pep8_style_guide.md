---
title: "PEP 8 — Python 代码风格指南"
authors: [Guido van Rossum, Barry Warsaw, Nick Coghlan]
year: 2001
url: https://peps.python.org/pep-0008/
kp_refs: [PY_001, PY_005, PY_011]
summary_zh: Python 官方代码风格规范,涵盖命名约定、缩进、导入排序等。
---

# PEP 8 — Python 代码风格指南

> **面向读者**:已学完 §00-§03 章节,想写出规范 Python 代码的同学

## 摘要

PEP 8 是 Python 社区的代码风格指南,由 Guido van Rossum 等核心开发者起草,自 2001 年起成为事实标准。PEP 8 不是"必须遵守的规则",而是"经验证的最佳实践",目的是让 Python 代码在大量开发者协作时保持一致的可读性。

## 关键规则

1. **缩进**:4 个空格,不混用 Tab
2. **行宽**:不超过 79 字符(文档/注释 72)
3. **空行**:顶层函数/类之间 2 空行,类方法之间 1 空行
4. **命名**:
   - 模块/函数/变量:`snake_case`
   - 类:`PascalCase`
   - 常量:`UPPER_SNAKE_CASE`
   - 内部:`_leading_underscore`
5. **导入**:
   - 每行一个 import
   - 顺序:标准库 → 第三方 → 本地
   - 分组用空行隔开
6. **空格**:
   - 运算符两侧: `a + b`
   - 函数参数默认值: `def f(x, y=0):`
   - 不在括号内侧加空格: `f(a, b)`
7. **注释**:
   - 块注释:用 `# `,与代码同缩进
   - 行内注释:少用,代码自身应该清晰
   - 文档字符串(PEP 257):所有公共模块/函数/类

## 完整代码风格示例

```python
"""模块文档字符串:说明模块作用。"""

import json
from pathlib import Path

MAX_RETRIES = 3  # 常量


def fetch_user(user_id: int, *, include_profile: bool = False) -> dict:
    """根据 user_id 获取用户信息。

    Args:
        user_id: 用户唯一标识
        include_profile: 是否包含详细 profile

    Returns:
        包含用户字段的字典
    """
    path = Path(f"data/{user_id}.json")
    if not path.exists():
        raise UserNotFoundError(user_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not include_profile:
        data.pop("profile", None)
    return data
```

## 对 Python 课程学习的启示

- 从第一章起就养成规范命名习惯,不要等"写熟了再改"
- IDE 安装 flake8 / black / ruff 自动检查与格式化
- 阅读开源项目(Requests、Flask、FastAPI)代码,体会 PEP 8 的实际应用
- "违反 PEP 8"前先想清楚为什么——风格的一致性 > 个人的偏好

## 工具链

| 工具 | 用途 | 推荐配置 |
|------|------|----------|
| `black` | 自动格式化(无配置) | `black src/` |
| `ruff` | 快速 lint + 格式化 | `ruff check src/ && ruff format src/` |
| `flake8` | PEP 8 风格检查 | `flake8 src/` |
| `isort` | 导入排序 | `isort src/` |
| `mypy` | 静态类型检查 | `mypy src/` |

## 推荐阅读顺序

1. §1 命名约定
2. §2 代码布局
3. §3 导入规范
4. §4 注释与文档字符串
5. §5 编程建议(本书第 10 节)

## 争议与变通

- **行宽 79 字符**:许多项目放宽到 88(black 默认)或 100
- **单引号 vs 双引号**:PEP 8 不强制,black 默认用双引号
- **类型注解**:PEP 8 没规定,但 PEP 484 是补充

## 链接

- 官方文档:https://peps.python.org/pep-0008/
- 中文翻译:https://www.python.org/dev/peps/pep-0008/
