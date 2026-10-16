---
chapter_ref: "17"
chapter_title: "Python 项目实战"
kp_refs: [PY_024]
bloom_focus: [Create, Evaluate]
total_points: 50
deadline_hint: 本章配套学习时长 8 学时(含项目实现)
---

# Python 项目实战 · 章节练习

> **配套**:A3 章节 §17 Python 项目实战

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
现代 Python 项目的配置文件主要用什么?

- A. `setup.py`
- B. `setup.cfg`
- C. `pyproject.toml`
- D. `requirements.txt`

<details><summary>答案</summary>C。PEP 621 把项目元信息统一到 pyproject.toml,setup.py 仍可共存但不再是主入口。</details>

### Q2(Apply)
`if __name__ == "__main__":` 的作用是?

- A. 防止无限递归
- B. 让代码只在直接运行该文件时执行,被 import 时不执行
- C. 让代码只能被 import
- D. 优化性能

<details><summary>答案</summary>B。`__name__` 在直接运行时是 `"__main__"`,被 import 时是模块名。</details>

### Q3(Apply)
`pip install -e .` 做什么?

- A. 升级 pip
- B. 开发模式安装(链接到源码,改动即时生效)
- C. 安装到虚拟环境
- D. 完全卸载再装

<details><summary>答案</summary>B。`-e` (editable)把项目作为可编辑安装,代码改动无需重装。</details>

### Q4(Analyze)
以下哪个目录结构是经典的 Python 项目布局?

- A. 所有代码在一个 `main.py` 文件
- B. `src/myapp/` + `tests/` + `pyproject.toml`
- C. 全部代码散落在根目录
- D. `lib/` + `bin/`

<details><summary>答案</summary>B。`src/` 布局是现代推荐,避免与系统包冲突;`tests/` 与源码分离。</details>

### Q5(Evaluate)
项目需要"运行前自动跑测试 + 检查代码风格",推荐用什么?

- A. pre-commit hook
- B. 手动跑 pytest
- C. CI/CD
- D. Makefile

<details><summary>答案</summary>A。pre-commit 在 git commit 时自动跑 black/ruff/pytest,本地就拦截问题。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`pytest` 中用 `@pytest.fixture` 装饰的函数可以提供测试 ______ 。

<details><summary>答案</summary>数据 / 上下文</details>

### Q7(Apply)
`pyproject.toml` 中的 `[project.optional-dependencies]` 通常定义 ______ 依赖(如 pytest)。

<details><summary>答案</summary>开发 / dev</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
为什么 Python 项目要分层(模型 / 存储 / 服务 / CLI)?如果不分层会怎样?

<details><summary>参考答案</summary>分层的核心目的:**关注点分离 + 可测试性**。
- 模型层(`models.py`):数据类,只关心数据结构与业务规则
- 存储层(`storage.py`):数据持久化,只关心 I/O
- 服务层(`service.py`):业务逻辑,组合模型与存储
- CLI 层(`cli.py`):用户接口,只关心参数解析与展示
不分层的问题:
1. 业务逻辑与 I/O 混在一起,单元测试难写
2. 改存储(JSON → SQLite)要改遍所有文件
3. 改 CLI 容易破坏业务逻辑
4. 多人协作冲突多
5. 代码复用差(其他项目想用业务逻辑,被 CLI 拖累)</details>

### Q9(Analyze)
什么是"依赖注入"?在 gradebook 项目中,`Storage` 是怎么被注入的?

<details><summary>参考答案</summary>依赖注入(DI):把组件所依赖的对象从外部传入,而不是内部创建。
好处:
1. 测试时可注入 mock / 临时对象
2. 替换实现容易(JSON → SQLite)
3. 依赖关系清晰
4gradebook 中的实现:
```python
storage = Storage(path)         # 入口创建
service = GradeBookService(storage)  # 注入到 service
```
- `GradeBookService.__init__(self, storage)` 接受 storage 参数
- 不在内部 `Storage()` 创建
- 测试时可以传 `Storage(tmp_path)` 临时目录
- 生产可以传 `Storage("data/students.json")`</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
为 §17 项目的 `Student` 数据类添加 `delete_score(subject: str) -> bool` 方法:存在则删除返回 True,不存在返回 False。

<details><summary>参考实现</summary>

```python
from dataclasses import dataclass, field

@dataclass
class Student:
    name: str
    student_id: str
    scores: dict = field(default_factory=dict)

    def add_score(self, subject, score):
        if not 0 <= score <= 100:
            raise ValueError(f"分数必须在 0-100: {score}")
        self.scores[subject] = score

    def delete_score(self, subject):
        if subject in self.scores:
            del self.scores[subject]
            return True
        return False

    def total(self):
        return sum(self.scores.values())

    def average(self):
        if not self.scores:
            return 0.0
        return round(self.total() / len(self.scores), 2)
```

</details>

### Q11(Create)
为 `GradeBookService` 添加 `list_students(subject: str | None = None) -> list[Student]` 方法:返回所有学生(或按学科筛选有成绩的学生),并按学号排序。

<details><summary>参考实现</summary>

```python
class GradeBookService:
    # 假设 self.students 已是 dict[str, Student]

    def list_students(self, subject=None):
        if subject is None:
            students = list(self.students.values())
        else:
            students = [s for s in self.students.values() if subject in s.scores]
        return sorted(students, key=lambda s: s.student_id)
```

</details>

---

*本章配套练习覆盖项目结构、依赖管理、CLI、测试、依赖注入、实战代码。*
