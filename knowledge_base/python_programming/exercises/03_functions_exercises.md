---
chapter_ref: "03"
chapter_title: "函数定义与参数"
kp_refs: [PY_005]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 函数定义与参数 · 章节练习

> **配套**:A3 章节 §03 函数定义与参数
> **配对代码**:`code_examples/03_functions_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中定义函数的关键字是?

- A. `function`
- B. `def`
- C. `func`
- D. `lambda`

<details><summary>答案</summary>B。`def` 是函数定义关键字,`lambda` 是匿名函数。</details>

### Q2(Apply)
以下函数定义有哪个错误?
```python
def f(a, b=1, c):
    return a + b + c
```

- A. 参数顺序错误
- B. 默认参数必须在非默认参数之后
- C. 缺少类型注解
- D. 没有 return

<details><summary>答案</summary>B。Python 语法规定:有默认值的参数必须排在无默认值参数之后。</details>

### Q3(Understand)
以下代码的输出是?
```python
def f(lst=[]):
    lst.append(1)
    return lst
print(f())
print(f())
```

- A. `[1]` 和 `[1]`
- B. `[1]` 和 `[1, 1]`
- C. `None` 和 `None`
- D. 报错

<details><summary>答案</summary>B。可变默认参数被多次调用共享,第二次 `lst` 已含 1。</details>

### Q4(Analyze)
在 `*args` 和 `**kwargs` 中,`*` 和 `**` 的作用是?

- A. 装饰器
- B. 解包(打包/收集)
- C. 类型注解
- D. 命名空间

<details><summary>答案</summary>B。`*` 把位置参数打包成 tuple,`**` 把关键字参数打包成 dict。</details>

### Q5(Evaluate)
判断一个变量是否为 `None`,PEP 8 推荐?

- A. `if x == None:`
- B. `if x is None:`
- C. `if not x:`
- D. `if x != None:`

<details><summary>答案</summary>B。`is` 用于身份比较,适合单例(None/True/False)。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Remember)
Python 中匿名函数的关键字是 ______ ,只允许一个表达式。

<details><summary>答案</summary>lambda</details>

### Q7(Apply)
函数内部修改外层(非全局)变量,需用 `______` 关键字声明。

<details><summary>答案</summary>nonlocal</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 LEGB 规则,并解释为什么函数内能直接访问 `print` / `len` 等内置函数。

<details><summary>参考答案</summary>LEGB 是 Python 名字查找顺序:
- **L**ocal(函数内部局部)
- **E**nclosing(嵌套外层函数)
- **G**lobal(模块全局)
- **B**uilt-in(内置)

`print` / `len` 等内置函数位于 `builtins` 模块,当 L/E/G 都找不到时,Python 会在 Built-in 命名空间查找,因此函数内可以直接使用。</details>

### Q9(Analyze)
什么是闭包?写一个 `make_counter()` 函数,返回的 counter 每次调用值加 1(用闭包,不用 `global`)。

<details><summary>参考答案</summary>闭包 = 函数 + 其引用的外部变量。闭包能"捕获"定义时的环境。

```python
def make_counter():
    n = 0
    def counter():
        nonlocal n
        n += 1
        return n
    return counter

c = make_counter()
print(c(), c(), c())  # 1 2 3
```

闭包的应用:装饰器、回调、函数工厂、状态保持。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现一个 `log(*messages, level="INFO", **fields)` 函数,输出格式 `level | msg1 msg2 ... | key=value key=value ...`。

<details><summary>参考实现</summary>

```python
def log(*messages, level="INFO", **fields):
    msg_part = " ".join(str(m) for m in messages)
    field_part = " ".join(f"{k}={v}" for k, v in fields.items())
    return f"{level} | {msg_part} | {field_part}"

print(log("User", "login", level="INFO", user="alice", ip="127.0.0.1"))
# INFO | User login | user=alice ip=127.0.0.1
```

</details>

### Q11(Create)
用 `functools.reduce` 实现 `mymax(iterable, key=None)`,返回可迭代对象中最大的元素(支持 `key` 参数)。

<details><summary>参考实现</summary>

```python
from functools import reduce

def mymax(iterable, key=None):
    if key is None:
        return reduce(lambda a, b: a if a > b else b, iterable)
    return reduce(lambda a, b: a if key(a) > key(b) else b, iterable)

print(mymax([3, 1, 4, 1, 5, 9, 2, 6]))                # 9
print(mymax(["apple", "banana"], key=len))            # banana
```

</details>

---

*本章配套代码:`code_examples/03_functions_demo.py` 包含 7 个 demo 函数,涵盖 *args/**kwargs、闭包、lambda、map/filter/reduce 等。*
