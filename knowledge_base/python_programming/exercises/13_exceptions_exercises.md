---
chapter_ref: "13"
chapter_title: "异常处理与自定义异常"
kp_refs: [PY_019, PY_020]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 5 学时
---

# 异常处理与自定义异常 · 章节练习

> **配套**:A3 章节 §13 异常处理与自定义异常
> **配对代码**:`code_examples/13_exceptions_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
以下哪个**不是** Python 内置异常?

- A. `ValueError`
- B. `IndexError`
- C. `NullPointerError`
- D. `KeyError`

<details><summary>答案</summary>C。Python 没有 `NullPointerError`(那是 Java),对应的是 `AttributeError` 或 `TypeError`。</details>

### Q2(Apply)
以下 try-except 结构中,else 块什么时候执行?

- A. 总是执行
- B. 发生异常时执行
- C. 不发生异常时执行
- D. finally 之后执行

<details><summary>答案</summary>C。`else` 只在 try 块没抛异常时执行,用于"成功路径"。</details>

### Q3(Apply)
下面代码的输出是?
```python
try:
    raise ValueError("error")
except Exception as e:
    print(type(e).__name__)
```

- A. `Exception`
- B. `ValueError`
- C. `error`
- D. 报错

<details><summary>答案</summary>B。`type(e).__name__` 是具体异常类的名字。</details>

### Q4(Analyze)
下面代码有什么问题?
```python
try:
    risky()
except:
    pass
```

- A. 没问题
- B. 裸 except 会吞掉 KeyboardInterrupt,无法 Ctrl+C 退出
- C. 应该加 `log`
- D. B 和 C 都对

<details><summary>答案</summary>D。裸 `except:` 等价于 `except BaseException:`,会吞掉所有异常包括 Ctrl+C,严重反模式。</details>

### Q5(Evaluate)
业务异常基类应该继承?

- A. `BaseException`
- B. `Exception`
- C. `RuntimeError`
- D. `object`

<details><summary>答案</summary>B。继承 Exception 才能被 except Exception 捕获,且不影响 Ctrl+C 退出。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`raise AppError("...") from e` 中的 `from` 用于显式设置异常 ______ 。

<details><summary>答案</summary>链(chain) / 上下文</details>

### Q7(Apply)
`finally` 块在 try 块抛异常后 ______ 执行(填"会"或"不会")。

<details><summary>答案</summary>会</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
`Exception` 和 `BaseException` 的区别是什么?为什么业务异常只继承 `Exception`?

<details><summary>参考答案</summary>- `BaseException` 是所有异常的最终基类
- `Exception` 继承自 BaseException,是一般异常的基类
- `BaseException` 还包括 `KeyboardInterrupt` (Ctrl+C)、`SystemExit` (sys.exit)、`GeneratorExit`
业务异常只继承 `Exception` 的原因:
1. 业务代码 `except Exception` 能捕获业务异常
2. 但 `except Exception` 不会捕获 KeyboardInterrupt / SystemExit
3. 用户 Ctrl+C 时,程序能正常退出,不会被业务异常处理逻辑吞掉</details>

### Q9(Analyze)
"异常应在边界层处理,中间层传播"的设计原则是什么?举例说明。

<details><summary>参考答案</summary>设计原则:异常处理应该发生在"边界层"(API、I/O、用户输入校验),中间业务逻辑只让异常自然传播。
原因:
1. 中间层 try/except 会丢失异常上下文
2. 边界层知道"怎么向用户报告"(HTTP 状态码、错误消息、日志)
3. 中间层只关心"业务逻辑",不关心"怎么呈现错误"
示例:Web API 控制器(边界)捕获 ValidationError 转 400 响应,业务 service 层直接 raise 让异常传播。</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `safe_divide(a, b)`,b=0 时返回 None,其他异常用 `raise AppError(...) from e` 包装。

<details><summary>参考实现</summary>

```python
class AppError(Exception):
    pass

def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None
    except TypeError as e:
        raise AppError(f"类型错误: {e}") from e
```

</details>

### Q11(Create)
设计一组业务异常(`AppError` / `NotFoundError` / `ValidationError` / `PermissionError`),实现一个 `UserService` 类,提供 `create` / `get` / `delete` 三个方法,合理使用异常。

<details><summary>参考实现</summary>

```python
class AppError(Exception):
    pass

class NotFoundError(AppError):
    pass

class ValidationError(AppError):
    pass

class PermissionError(AppError):
    pass

class UserService:
    def __init__(self):
        self.users = {}

    def create(self, name, age):
        if not name or not isinstance(name, str):
            raise ValidationError("name 必须是非空字符串")
        if not isinstance(age, int) or age < 0:
            raise ValidationError("age 必须是非负整数")
        if name in self.users:
            raise ValidationError(f"用户已存在: {name}")
        self.users[name] = {"name": name, "age": age}
        return self.users[name]

    def get(self, name):
        if name not in self.users:
            raise NotFoundError(f"用户不存在: {name}")
        return self.users[name]

    def delete(self, name, current_user):
        if current_user != "admin":
            raise PermissionError("只有管理员可删除用户")
        if name not in self.users:
            raise NotFoundError(f"用户不存在: {name}")
        del self.users[name]
```

</details>

---

*本章配套代码:`code_examples/13_exceptions_demo.py` 包含 7 个 demo 函数,涵盖异常层级、四段式、raise from、自定义异常、实战。*
