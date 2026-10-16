---
chapter_ref: "00"
chapter_title: "Python 语言概述与环境搭建"
kp_refs: [PY_001]
bloom_focus: [Remember, Understand, Apply]
total_points: 20
deadline_hint: 本章配套学习时长 2 学时
---

# Python 语言概述 · 章节练习

> **配套**:A3 章节 §00 Python 语言概述
> **配对代码**:`code_examples/01_variables_types_demo.py`(内含环境自检函数)

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 是由谁创造的?

- A. Dennis Ritchie
- B. Guido van Rossum
- C. James Gosling
- D. Bjarne Stroustrup

<details><summary>答案</summary>B。Python 由 Guido van Rossum 于 1989 年底开始设计,1991 年正式发布。</details>

### Q2(Understand)
以下哪项是 Python 作为"解释型语言"的特征?

- A. 编译后生成 .exe 文件
- B. 代码逐行解释执行,无需编译步骤
- C. 运行速度必然快于编译型语言
- D. 必须安装 JDK

<details><summary>答案</summary>B。解释型语言逐行读取源代码并执行,不需要预先编译为机器码。</details>

### Q3(Remember)
Python 2 已于哪一年停止维护(EOL)?

- A. 2015
- B. 2018
- C. 2020
- D. 2023

<details><summary>答案</summary>C。Python 2 于 2020 年 1 月 1 日正式 EOL,所有新项目应使用 Python 3。</details>

### Q4(Apply)
在终端运行 Python 交互式环境的命令是?

- A. `python`
- B. `pip`
- C. `pyenv`
- D. `python-shell`

<details><summary>答案</summary>A。在终端输入 `python` 进入 REPL;`pip` 是包管理命令。</details>

### Q5(Analyze)
以下哪个命令可以查看当前 Python 解释器的版本?

- A. `python --version`
- B. `pip --version`
- C. `python -c "version"`
- D. `python list`

<details><summary>答案</summary>A。`python --version` 或 `python -V` 显示解释器版本。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Remember)
Python 的交互式命令行称为 ______ (英文缩写),输入 `python` 命令即可启动。

<details><summary>答案</summary>REPL(Read-Eval-Print Loop)</details>

### Q7(Apply)
创建项目级虚拟环境的命令是 `python -m ______ .venv`。

<details><summary>答案</summary>venv</details>

---

## 三、简答题(每题 6 分,共 6 分)

### Q8(Analyze)
请简述 Python 虚拟环境的作用,以及为什么在项目中应该使用虚拟环境(至少 2 点)。

<details><summary>参考答案</summary>虚拟环境为每个项目创建独立的 Python 包安装目录,使不同项目的依赖互不冲突。原因:
1. 隔离项目 A 与项目 B 的依赖,避免版本冲突(如 A 需要 Django 3.x,B 需要 Django 4.x)
2. 便于复现:`requirements.txt` 锁定依赖后,新机器 `pip install -r` 即可还原环境
3. 不污染全局 Python 环境,系统 Python 保持干净
4. 配合 `pyproject.toml` 与 Docker,可实现"一次构建,到处运行"</details>

---

## 四、编程题(每题 6 分,共 12 分)

### Q9(Apply)
编写 `env_check.py`,打印 Python 版本(`sys.version`)、当前平台(`sys.platform`)、当前默认编码(`sys.getdefaultencoding()`)。

<details><summary>参考实现</summary>

```python
import sys
print(f"Python : {sys.version.split()[0]}")
print(f"Platform: {sys.platform}")
print(f"Encoding: {sys.getdefaultencoding()}")
```

</details>

### Q10(Create)
编写 `setup_project.sh`(类 Unix)或 `setup_project.bat`(Windows),自动完成:
1. 创建项目目录 `a3-hello`
2. 在其中创建虚拟环境 `.venv`
3. 激活虚拟环境(用注释说明,不实际执行)
4. 在虚拟环境中安装 `requests` 包
5. 导出 `requirements.txt`

<details><summary>参考实现</summary>

```bash
#!/bin/bash
# Linux / macOS
mkdir a3-hello && cd a3-hello
python -m venv .venv
# 激活: source .venv/bin/activate
.venv/bin/pip install requests
.venv/bin/pip freeze > requirements.txt
```

```bat
@echo off
REM Windows
mkdir a3-hello
cd a3-hello
python -m venv .venv
REM 激活: .venv\Scripts\activate.bat
.venv\Scripts\pip install requests
.venv\Scripts\pip freeze > requirements.txt
```

</details>

---

*本章配套代码:`code_examples/01_variables_types_demo.py` 中的 `env_self_check()` 函数,会打印 Python 版本、平台、虚拟环境位置等关键信息。*
