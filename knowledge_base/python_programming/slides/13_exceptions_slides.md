# 13: 异常处理与自定义异常 · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：异常处理与自定义异常
- 副标题：Python 程序设计 · 第 14 讲

## Slide 2：本讲大纲
- 异常的本质
- 异常层级
- try/except/else/finally
- raise / raise from
- 自定义异常
- 反模式
- 实战

## Slide 3：异常的本质
- 程序遇到错误时**中断当前执行流**并向外传播
- 异常对象携带：类型、消息、堆栈
- Python 内置几十种异常
- [配图：异常传播路径]

## Slide 4：异常层级
```
BaseException
├── KeyboardInterrupt (Ctrl+C)
├── SystemExit (sys.exit)
└── Exception
    ├── ArithmeticError → ZeroDivisionError
    ├── LookupError → IndexError / KeyError
    ├── TypeError
    ├── ValueError
    ├── OSError → FileNotFoundError
    └── ...
```
- 业务只接 Exception 子类
- 千万别接 BaseException

## Slide 5：四段式
```python
try:
    risky_operation()
except (ValueError, TypeError) as e:
    handle_error()
except Exception as e:
    fallback()
else:
    success_path()
finally:
    cleanup()
```
- try：放可能出错的代码
- except：捕获异常
- else：无异常时
- finally：必执行

## Slide 6：raise 与 raise from
```python
def divide(a, b):
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b

try:
    parse_config(path)
except FileNotFoundError as e:
    raise ConfigError(...) from e  # 链接原因
```
- `raise` 主动抛
- `raise from` 显式链接
- `raise from None` 抑制链

## Slide 7：自定义异常
```python
class AppError(Exception): pass
class NotFoundError(AppError): pass
class ValidationError(AppError): pass
class PermissionDeniedError(AppError): pass
```
- 继承 Exception
- 名字以 Error 结尾
- 模块级常量
- 业务异常族便于集中处理

## Slide 8：异常处理反模式
- ❌ 裸 except：吞掉所有异常
- ❌ 用异常做控制流（慢）
- ❌ 静默失败
- ❌ 业务代码 try 太多
- ✅ 边界层处理，中间层传播
- [配图：异常处理架构图]

## Slide 9：稳健的文件读取
```python
def read_json(path):
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as e:
        raise ConfigError("文件不存在") from e
    except json.JSONDecodeError as e:
        raise ConfigError("JSON 错误") from e
```
- 每种异常具体处理
- 用 from 保留原始堆栈
- 边界层处理 + 包装

## Slide 10：实战 - UserService
```python
class UserService:
    def create(self, name, age):
        if not name: raise ValidationError(...)
        if name in self.users: raise ValidationError(...)
    def get(self, name):
        if name not in self.users: raise NotFoundError(...)
    def delete(self, name, current):
        if current != "admin": raise PermissionDeniedError(...)
```
- CRUD 操作 + 异常
- 业务异常体系
- [代码示例：完整服务]

## Slide 11：本讲总结与作业
- 核心要点：
  1. 只接 Exception 子类
  2. raise from 保留堆栈
  3. 自定义异常继承 AppError
- 作业：
  1. 实现 safe_divide
  2. 设计 UserService 异常体系
  3. 写一个稳健的文件读取函数
