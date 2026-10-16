---
chapter_id: '17'
slug: project_practice
title: Python 项目实战:学生成绩管理系统
kp_ids:
- PY_024
bloom_focus:
- Create
- Evaluate
prerequisites:
- '13'
estimated_minutes: 480
---

# 17: Python 项目实战 · 学生成绩管理系统

> **Bloom 层级**: Create → Evaluate
> **建议学时**: 480 分钟(8 学时)
> **前置知识**: §13 异常处理

## 学习目标

1. 掌握 Python 项目的工程化组织(目录结构、模块划分)。
2. 掌握虚拟环境与依赖管理(pyproject.toml / requirements.txt)。
3. 掌握命令行参数解析(argparse)。
4. 掌握日志配置(logging)。
5. 掌握单元测试基础(pytest)。
6. 独立完成一个完整的命令行工具项目。

## 17.1 项目目标

实现一个 CLI 工具 `gradebook`,支持:
- 添加/查询/删除学生
- 录入成绩并计算总分/平均分
- 按成绩排序并显示前 N 名
- 持久化到 JSON 文件
- 日志记录关键操作

## 17.2 项目结构

```
gradebook/
├── pyproject.toml          # 项目配置与依赖
├── README.md
├── src/
│   └── gradebook/
│       ├── __init__.py
│       ├── __main__.py     # 入口(python -m gradebook)
│       ├── cli.py          # 命令行参数解析
│       ├── models.py       # 数据类(Student / Grade)
│       ├── storage.py      # JSON 持久化
│       ├── service.py      # 业务逻辑
│       └── logger.py       # 日志配置
├── tests/
│   ├── test_models.py
│   ├── test_service.py
│   └── test_storage.py
└── data/
    └── students.json       # 数据文件
```

## 17.3 依赖管理:pyproject.toml

```toml
[project]
name = "gradebook"
version = "0.1.0"
description = "学生成绩管理 CLI"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=7.0", "ruff"]

[project.scripts]
gradebook = "gradebook.cli:main"
```

安装:`pip install -e .`(开发模式)

## 17.4 核心代码

### 17.4.1 models.py:数据类

```python
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime

@dataclass
class Student:
    name: str
    student_id: str
    scores: dict = field(default_factory=dict)  # {"math": 90, ...}

    def add_score(self, subject: str, score: float):
        if not 0 <= score <= 100:
            raise ValueError(f"分数必须在 0-100 之间: {score}")
        self.scores[subject] = score

    def total(self) -> float:
        return sum(self.scores.values())

    def average(self) -> float:
        if not self.scores:
            return 0.0
        return round(self.total() / len(self.scores), 2)
```

### 17.4.2 storage.py:持久化

```python
import json
from pathlib import Path
from .models import Student

class Storage:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Student]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {sid: Student(**d) for sid, d in data.items()}

    def save(self, students: dict[str, Student]) -> None:
        data = {sid: asdict(s) for sid, s in students.items()}
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
```

### 17.4.3 service.py:业务逻辑

```python
import logging
from .models import Student
from .storage import Storage

logger = logging.getLogger(__name__)

class GradeBookService:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.students = storage.load()

    def add_student(self, name: str, student_id: str) -> Student:
        if student_id in self.students:
            raise ValueError(f"学号已存在: {student_id}")
        student = Student(name=name, student_id=student_id)
        self.students[student_id] = student
        self.storage.save(self.students)
        logger.info(f"添加学生: {name}({student_id})")
        return student

    def add_score(self, student_id: str, subject: str, score: float) -> None:
        student = self.students.get(student_id)
        if not student:
            raise KeyError(f"学生不存在: {student_id}")
        student.add_score(subject, score)
        self.storage.save(self.students)
        logger.info(f"录入成绩: {student_id} {subject}={score}")

    def top_n(self, n: int) -> list[Student]:
        return sorted(self.students.values(), key=lambda s: s.average(), reverse=True)[:n]
```

### 17.4.4 cli.py:命令行入口

```python
import argparse
import logging
import sys
from pathlib import Path
from .service import GradeBookService
from .storage import Storage

def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="学生成绩管理")
    parser.add_argument("--data", type=Path, default=Path("students.json"))
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="添加学生")
    p_add.add_argument("name")
    p_add.add_argument("--id", required=True, dest="student_id")

    # score
    p_score = sub.add_parser("score", help="录入成绩")
    p_score.add_argument("--id", required=True, dest="student_id")
    p_score.add_argument("subject")
    p_score.add_argument("score", type=float)

    # top
    p_top = sub.add_parser("top", help="前 N 名")
    p_top.add_argument("n", type=int, nargs="?", default=3)

    args = parser.parse_args(argv)
    setup_logging(args.verbose)
    storage = Storage(args.data)
    svc = GradeBookService(storage)

    try:
        if args.command == "add":
            svc.add_student(args.name, args.student_id)
            print(f"已添加: {args.name}({args.student_id})")
        elif args.command == "score":
            svc.add_score(args.student_id, args.subject, args.score)
            print(f"已录入: {args.subject}={args.score}")
        elif args.command == "top":
            for i, s in enumerate(svc.top_n(args.n), 1):
                print(f"{i}. {s.name}({s.student_id}) avg={s.average()}")
    except (ValueError, KeyError) as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## 17.5 单元测试

```python
# tests/test_service.py
import pytest
from pathlib import Path
from gradebook.service import GradeBookService
from gradebook.storage import Storage

@pytest.fixture
def svc(tmp_path):
    storage = Storage(tmp_path / "test.json")
    return GradeBookService(storage)

def test_add_student(svc):
    s = svc.add_student("Alice", "S001")
    assert s.name == "Alice"
    assert svc.students["S001"] == s

def test_add_score(svc):
    svc.add_student("Bob", "S002")
    svc.add_score("S002", "math", 90)
    assert svc.students["S002"].average() == 90.0

def test_top_n(svc):
    svc.add_student("A", "1")
    svc.add_student("B", "2")
    svc.add_score("1", "math", 80)
    svc.add_score("2", "math", 90)
    top = svc.top_n(2)
    assert top[0].name == "B"

def test_invalid_score(svc):
    svc.add_student("A", "1")
    with pytest.raises(ValueError):
        svc.add_score("1", "math", 150)

def test_duplicate_student(svc):
    svc.add_student("A", "1")
    with pytest.raises(ValueError):
        svc.add_student("A2", "1")
```

运行:`pytest -v`

## 17.6 工具链

- **代码格式化**:`black src/ tests/`
- **静态检查**:`ruff check src/`
- **类型检查**:`mypy src/`
- **依赖管理**:用 `pip-tools` 或 `uv` 锁定版本
- **CI/CD**:GitHub Actions 跑 `pytest` + `ruff`

## 17.7 部署

### 17.7.1 打包为可执行文件

```bash
pip install pyinstaller
pyinstaller --onefile src/gradebook/__main__.py
# 生成 dist/gradebook.exe
```

### 17.7.2 Docker 化

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
ENTRYPOINT ["gradebook"]
```

## 17.8 进一步扩展

- **数据库**:用 SQLite 替代 JSON,支持更多学生
- **Web 化**:用 FastAPI 包装成 REST API
- **可视化**:用 matplotlib 生成成绩分布图
- **导出**:导出为 Excel / PDF 报告
- **AI 助手**:接入 LLM,自然语言查询成绩

## 17.9 常见误区

- **误区 1**:把所有代码塞进一个文件——难维护,无法测试。
- **误区 2**:用 `python` 全局环境——依赖冲突;用 `venv` / `uv`。
- **误区 3**:代码直接 `print` 不打日志——无法重定向、无法分级。
- **误区 4**:不写测试——重构时心惊胆战。
- **误区 5**:业务逻辑与 I/O 混合——难测试,改用依赖注入。

## 17.10 本章小结

1. 工程化项目:目录结构、模块划分、入口、依赖。
2. `pyproject.toml` 是现代 Python 项目的事实标准。
3. 数据类(`@dataclass`) + 存储层 + 服务层 + CLI 是经典分层。
4. 单元测试用 `pytest`,`@pytest.fixture` 提供测试数据。
5. 工具链:格式化(black) + 检查(ruff) + 类型(mypy) + 测试(pytest)。
6. 部署:PyInstaller 单文件 / Docker 镜像。
7. 进一步扩展:数据库、Web 化、可视化、AI 集成。

## 17.11 练习思考

1. **动手实践**:补全 GradeBook 项目的 `delete_student` / `list_students` 方法。
2. **动手实践**:把 JSON 存储替换为 SQLite,使用 `sqlite3` 标准库。
3. **代码分析**:解释 `if __name__ == "__main__"` 的作用,为什么 CLI 入口需要它?
4. **动手实践**:用 `pytest` 写完整的测试套件,覆盖率 ≥ 80%。
5. **拓展探索**:阅读 `click` / `typer` 库,对比 `argparse` 的开发体验。

## 17.12 拓展阅读

- pyproject.toml 规范:https://peps.python.org/pep-0621/
- pytest 官方文档:https://docs.pytest.org/
- 《Python 工匠》—— 工程项目实践
- Hypermodern Python:https://medium.com/@cjolowicz/cookiecutter-hypermodern-python-edc5a4f37b6f

---

*配套练习:`exercises/17_project_practice_exercises.md`*
