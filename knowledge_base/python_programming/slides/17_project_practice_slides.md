# 17: Python 项目实战 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：50 分钟

---

## Slide 1：封面
- 标题：Python 项目实战 - 学生成绩管理系统
- 副标题：Python 程序设计 · 第 18 讲（结业课）

## Slide 2：本讲大纲
- 项目目标
- 项目结构
- 数据模型
- 存储层
- 服务层
- CLI 层
- 单元测试
- 部署与扩展

## Slide 3：项目目标
- CLI 工具 `gradebook`
- 功能：增删改查学生、成绩、Top-N、报告
- 持久化到 JSON
- 日志记录
- 完整测试覆盖
- [配图：项目截图示例]

## Slide 4：项目结构
```
gradebook/
├── pyproject.toml
├── README.md
├── src/gradebook/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── models.py
│   ├── storage.py
│   ├── service.py
│   └── logger.py
├── tests/
└── data/
```

## Slide 5：依赖管理 pyproject.toml
```toml
[project]
name = "gradebook"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
gradebook = "gradebook.cli:main"
```
- PEP 621 标准
- pip install -e . 开发模式

## Slide 6：数据模型
```python
@dataclass
class Student:
    name: str
    student_id: str
    scores: dict = field(default_factory=dict)

    def add_score(self, subject, score):
        if not 0 <= score <= 100:
            raise ValueError(...)
        self.scores[subject] = score

    def total(self): ...
    def average(self): ...
```

## Slide 7：存储层
```python
class JSONStorage:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Student]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text("utf-8"))
        return {sid: Student(**d) for sid, d in data.items()}

    def save(self, students): ...
```

## Slide 8：服务层
```python
class GradeBookService:
    def __init__(self, storage: JSONStorage):
        self.storage = storage
        self.students = storage.load()

    def add_student(self, name, student_id): ...
    def add_score(self, student_id, subject, score): ...
    def top_n(self, n) -> list[Student]: ...
    def list_students(self, subject=None): ...
```
- 业务逻辑与 I/O 分离
- 异常处理 + 日志

## Slide 9：CLI 层
```python
import argparse
parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="command", required=True)
p_add = sub.add_parser("add")
p_add.add_argument("name")
p_add.add_argument("--id", required=True)
```
- 6 个子命令
- 完整错误处理
- [代码示例：CLI 入口]

## Slide 10：单元测试
```python
import pytest

@pytest.fixture
def svc(tmp_path):
    storage = JSONStorage(tmp_path / "test.json")
    return GradeBookService(storage)

def test_add_student(svc):
    s = svc.add_student("Alice", "S001")
    assert s.name == "Alice"

def test_invalid_score(svc):
    svc.add_student("A", "1")
    with pytest.raises(ValueError):
        svc.add_score("1", "math", 150)
```
- pytest 框架
- fixture 复用
- 覆盖率 ≥ 80%

## Slide 11：部署与扩展
- 工具链：black / ruff / mypy / pytest
- 打包：pyinstaller 单文件
- 容器化：Docker
- 扩展：SQLite / FastAPI / 图表
- CI/CD：GitHub Actions

## Slide 12：本讲总结与作业
- 核心要点：
  1. 工程化：分层 + 依赖管理 + 测试
  2. 实战：完整 CLI 项目
  3. 扩展：数据库、Web、可视化
- 作业：
  1. 补全 delete_student / list_students
  2. SQLite 替代 JSON
  3. 完整测试套件 + 覆盖率报告
- 完课！
