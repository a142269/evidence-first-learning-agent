---
chapter_ref: "11"
chapter_title: "文件读写与 pathlib"
kp_refs: [PY_016, PY_017]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 5 学时
---

# 文件读写与 pathlib · 章节练习

> **配套**:A3 章节 §11 文件读写与 pathlib
> **配对代码**:`code_examples/11_file_io_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中文件操作的推荐写法是?

- A. `f = open("x"); ...; f.close()`
- B. `with open("x") as f: ...`
- C. `try: f = open("x"); finally: f.close()`
- D. A 和 C 都可以

<details><summary>答案</summary>B。`with` 是最简洁且安全的方式(异常也保证关闭)。</details>

### Q2(Apply)
打开图片文件应该用什么模式?

- A. `"r"`
- B. `"rb"`
- C. `"w"`
- D. `"b"`

<details><summary>答案</summary>B。二进制模式,`b` 表示字节流,图片不是文本。</details>

### Q3(Apply)
`Path("data") / "sub" / "file.txt"` 的结果类型是?

- A. `str`
- B. `bytes`
- C. `PosixPath` 或 `WindowsPath`
- D. `Path`

<details><summary>答案</summary>C。跨平台:Windows 上是 `WindowsPath`,Linux/macOS 是 `PosixPath`,都是 `Path` 的子类。</details>

### Q4(Analyze)
以下代码有什么问题?
```python
with open("data.txt", "r") as f:
    content = f.read()
print(content)
```
假设在 Windows 中文系统上,文件是 UTF-8 编码。

- A. 文件不存在会报错
- B. 编码不匹配可能报错或乱码
- C. 没问题
- D. 应该用 `encoding="gbk"`

<details><summary>答案</summary>B。Windows 默认 GBK,与 UTF-8 不一致,可能 `UnicodeDecodeError`。</details>

### Q5(Evaluate)
遍历当前目录所有 .py 文件(含子目录),推荐用?

- A. `os.listdir()` 递归
- B. `Path(".").rglob("*.py")`
- C. `glob.glob("*.py")`
- D. `os.walk(".")`

<details><summary>答案</summary>B。`rglob` 是 pathlib 的递归 glob,简洁直观。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`pathlib.Path("file.txt").suffix` 的值是 `"______"`(填写扩展名)。

<details><summary>答案</summary>.txt</details>

### Q7(Apply)
`with open("data.csv", "w", newline="")` 中 `newline=""` 的作用是避免 Windows 写入时 ______ 换行。

<details><summary>答案</summary>双重</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
文本模式与二进制模式有什么区别?什么场景必须用二进制?

<details><summary>参考答案</summary>- **文本模式**(默认 `t`):读写 str,自动处理编码与换行符
- **二进制模式**(`b`):读写 bytes,原始字节流
必须用二进制的场景:
1. 非文本文件(图片、音频、视频)
2. 网络 socket 通信
3. 跨平台共享二进制数据(避免 Windows \r\n 与 Unix \n 转换)
4. 哈希计算、加密、压缩等需要 bytes 的库</details>

### Q9(Analyze)
为什么 `pathlib.Path` 比 `os.path` 更推荐?举例说明三种优势。

<details><summary>参考答案</summary>1. **面向对象**:链式调用 `Path("a") / "b" / "c.txt"`,比 `os.path.join` 直观
2. **统一 API**:`exists()` / `is_file()` / `read_text()` 等都是方法,不必混用 `os.path` 和 `os` 模块
3. **跨平台**:自动处理 Windows `\` 与 Unix `/` 路径分隔符
4. **方法丰富**:`glob` / `rglob` / `with_name` / `with_suffix` 等
5. **类型清晰**:`WindowsPath` / `PosixPath` 表达意图</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
写函数 `count_lines(pattern: str) -> tuple[int, int]`,用 `pathlib.rglob` 找所有匹配 pattern 的文件,返回 (文件数, 总行数)。

<details><summary>参考实现</summary>

```python
from pathlib import Path

def count_lines(pattern):
    total_files = 0
    total_lines = 0
    for p in Path(".").rglob(pattern):
        if p.is_file():
            total_files += 1
            with p.open(encoding="utf-8", errors="ignore") as f:
                total_lines += sum(1 for _ in f)
    return total_files, total_lines

print(count_lines("*.py"))  # (10, 1234)
```

</details>

### Q11(Create)
实现 `merge_logs(log_dir: str, output: str)`,把目录下所有 `.log` 文件按文件名排序合并到一个输出文件,每段前加 `=== filename ===` 标题。

<details><summary>参考实现</summary>

```python
from pathlib import Path

def merge_logs(log_dir, output):
    log_path = Path(log_dir)
    out = Path(output)
    with out.open("w", encoding="utf-8") as fout:
        for log_file in sorted(log_path.glob("*.log")):
            fout.write(f"=== {log_file.name} ===\n")
            fout.write(log_file.read_text(encoding="utf-8"))
            fout.write("\n")
```

</details>

---

*本章配套代码:`code_examples/11_file_io_demo.py` 包含 8 个 demo 函数,涵盖 open 模式、读写方法、with、二进制、pathlib、glob、临时文件。*
