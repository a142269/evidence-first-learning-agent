---
chapter_id: '13'
slug: exceptions
title: 异常处理与自定义异常
kp_ids:
- PY_019
- PY_020
bloom_focus:
- Apply
- Analyze
prerequisites:
- '11'
estimated_minutes: 300
---

# 13: 异常处理与自定义异常 · 写出稳健的代码

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 300 分钟(5 学时)
> **前置知识**: §11 文件读写

## 学习目标

1. 理解 Python 异常层级与 BaseException / Exception 的区别。
2. 掌握 try / except / else / finally 的完整结构。
3. 掌握 raise 主动抛异常与 raise from 异常链。
4. 掌握自定义异常类的设计模式。
5. 能用异常处理实现健壮的 I/O、网络、数据校验代码。

## 13.1 异常的本质

Python 用"异常"表示错误,程序遇到异常会**中断当前执行流**并向外传播:

```python
>>> 1 / 0
ZeroDivisionError: division by zero

>>> int("abc")
ValueError: invalid literal for int() with base 10: 'abc'

>>> open("nonexistent.txt")
FileNotFoundError: [Errno 2] No such file or directory: 'nonexistent.txt'
```

## 13.2 异常层级

```
BaseException
├── KeyboardInterrupt       (Ctrl+C)
├── SystemExit              (sys.exit())
├── GeneratorExit
└── Exception
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   └── OverflowError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── TypeError
    ├── ValueError
    ├── OSError
    │   ├── FileNotFoundError
    │   └── PermissionError
    └── ...(数十种)
```

**重要原则**:
- 业务代码**只捕获 Exception 及其子类**
- **不要捕获 BaseException** —— 会吞掉 KeyboardInterrupt 和 SystemExit,导致无法正常退出

## 13.3 try / except / else / finally

完整四段式结构:

```python
try:
    result = risky_operation()
except (ValueError, TypeError) as e:
    # 捕获特定异常
    log.error(f"Invalid input: {e}")
    result = default
except Exception as e:
    # 兜底:其他所有异常
    log.exception("Unexpected error")
    raise  # 重新抛
else:
    # 没异常时执行
    process(result)
finally:
    # 无论是否有异常都执行
    cleanup()
```

| 块 | 触发时机 | 用途 |
|----|----------|------|
| `try` | 总是执行 | 放可能出错的代码 |
| `except` | 发生匹配异常时 | 错误处理 |
| `else` | try 块没抛异常时 | 成功路径(让 try 块更小) |
| `finally` | 不管是否异常 | 资源清理 |

**最佳实践**:
1. 异常类型尽量具体(`except ValueError` 而非 `except Exception`)
2. 不要 `try` 太多代码,只包"可能出错"的部分
3. `finally` 做清理,而不是 `except` 中

## 13.4 主动抛异常:raise

```python
def divide(a, b):
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b

# 重新抛当前异常
try:
    risky()
except Exception:
    log.error("...")
    raise  # 重新抛,不丢栈信息
```

## 13.5 异常链:raise from

```python
try:
    raw = open("data.json").read()
except FileNotFoundError as e:
    raise ConfigError("配置文件缺失") from e  # 显式链接原因
```

`from None` 抑制异常链:

```python
try:
    parse(data)
except ValueError:
    raise InvalidDataError("数据格式错误") from None
```

## 13.6 自定义异常

**设计原则**:
1. 继承 `Exception`(不是 `BaseException`)
2. 名字以 `Error` 结尾
3. 模块级常量,不要局部定义
4. 异常类应该少(过多例外等于没结构)

```python
# 业务异常基类
class AppError(Exception):
    """应用异常的基类"""
    pass

class ValidationError(AppError):
    """参数校验失败"""
    pass

class NotFoundError(AppError):
    """资源未找到"""
    pass

class PermissionDeniedError(AppError):
    """权限不足"""
    pass

# 使用
def get_user(user_id):
    if user_id <= 0:
        raise ValidationError(f"非法 user_id: {user_id}")
    user = db.find(user_id)
    if not user:
        raise NotFoundError(f"用户不存在: {user_id}")
    return user
```

**进阶:异常属性**

```python
class APIError(Exception):
    def __init__(self, message, status_code=500, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}

err = APIError("服务异常", status_code=503)
print(err.status_code)  # 503
```

## 13.7 异常处理的反模式

### 13.7.1 裸 except

```python
# ❌ 错误:吞掉所有异常
try:
    risky()
except:
    pass

# ✅ 正确:具体异常 + 日志
try:
    risky()
except ValueError as e:
    log.warning(f"Value error: {e}")
```

### 13.7.2 用异常做控制流

```python
# ❌ 用异常跳出循环(慢)
def find_user(users, target_id):
    for u in users:
        try:
            if u.id == target_id:
                raise Found
        except Found:
            return u
    return None

# ✅ 正常 break
def find_user(users, target_id):
    for u in users:
        if u.id == target_id:
            return u
    return None
```

### 13.7.3 异常处理空逻辑

```python
# ❌ 捕获了但什么都不做
try:
    data = load()
except Exception:
    pass  # 静默失败

# ✅ 至少记录
try:
    data = load()
except Exception as e:
    log.exception("Failed to load data")
    data = default_data
```

## 13.8 实战:稳健的文件读取

```python
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def read_json(path):
    """读取 JSON,带完整异常处理"""
    p = Path(path)
    try:
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"文件不存在: {p}")
        raise  # 让上层决定
    except PermissionError:
        logger.error(f"权限不足: {p}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON 格式错误: {e}")
        raise DataFormatError(f"配置文件损坏: {p}") from e
    except OSError as e:
        logger.error(f"I/O 错误: {e}")
        raise
```

## 13.9 实战:输入校验

```python
def create_user(name, age, email):
    """创建用户,参数校验完整"""
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name 必须是非空字符串")
    if not isinstance(age, int) or age < 0 or age > 150:
        raise ValidationError(f"age 必须在 0-150 之间: {age}")
    if "@" not in email:
        raise ValidationError(f"非法 email: {email}")
    # ... 业务逻辑
    return User(name, age, email)

# 链式校验
try:
    user = create_user("Alice", 25, "alice@example.com")
except ValidationError as e:
    return {"error": str(e)}, 400
```

## 13.10 上下文管理器 + 异常

`__exit__` 可以访问异常信息:

```python
class suppress:
    """等价于 contextlib.suppress"""
    def __init__(self, *exceptions):
        self.exceptions = exceptions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return exc_type is not None and issubclass(exc_type, self.exceptions)

# 用法
with suppress(FileNotFoundError):
    os.remove("temp.txt")  # 不存在不报错
```

## 13.11 常见误区

- **误区 1**:`except:` 裸 except —— 吞掉所有异常,包括 KeyboardInterrupt。
- **误区 2**:`return` 在 finally 中 —— 会覆盖 try/except 的 return,可能吞掉异常。
- **误区 3**:异常处理里抛新异常不写 `from e` —— 丢失原始堆栈。
- **误区 4**:每个函数都 try/except —— 错误处理应该是"边界层"的事,中间层只让异常传播。
- **误区 5**:`raise` 写在 except 外(没在处理异常) —— `raise RuntimeError("xxx")` 是新异常,不是重新抛。

## 13.12 本章小结

1. 异常层级:BaseException → Exception → 具体异常,业务只接 Exception。
2. 四段式:`try` / `except` / `else` / `finally` 各司其职。
3. `raise` 主动抛,`raise from` 链接原因,`raise from None` 抑制链。
4. 自定义异常:继承 Exception,模块级定义,以 Error 结尾。
5. 异常应在"边界层"(API、I/O、用户输入)处理,中间层传播即可。
6. 避免裸 except、用异常做控制流、静默失败。

## 13.13 练习思考

1. **代码分析**:下面代码有什么问题?如何修复?
   ```python
   try:
       data = open("data.txt").read()
   except:
       pass
   ```
2. **动手实践**:实现 `safe_divide(a, b)`,捕获 ZeroDivisionError,返回 None,其他异常用 raise from 包装成 AppError。
3. **动手实践**:设计一组业务异常:`NotFoundError` / `ValidationError` / `PermissionError`,继承一个 `AppError` 基类,实现 create_user / get_user / delete_user 三个函数。
4. **动手实践**:用 `contextlib.suppress` 静默删除多个可能不存在的临时文件。
5. **拓展探索**:阅读 `httpx` 库源码,看它如何用异常层级表达不同错误(连接、超时、状态码等)。

## 13.14 拓展阅读

- 异常层级官方文档:https://docs.python.org/3/library/exceptions.html
- 错误处理 PEP 8 指南:https://peps.python.org/pep-0008/#programming-recommendations
- 《流畅的 Python》第 7 章 函数装饰器和闭包(异常处理部分)

---

*配套代码示例:`code_examples/13_exceptions_demo.py`*
*配套练习:`exercises/13_exceptions_exercises.md`*
