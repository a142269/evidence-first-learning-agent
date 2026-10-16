# 16: 装饰器与闭包 · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：40 分钟

---

## Slide 1：封面
- 标题：装饰器与闭包
- 副标题：Python 程序设计 · 第 17 讲

## Slide 2：本讲大纲
- 装饰器是什么
- @functools.wraps
- 实战：常用装饰器
- 带参数的装饰器
- 类装饰器
- 装饰器堆叠
- 应用：Flask 风格

## Slide 3：装饰器是什么
- 接收函数并返回函数的可调用对象
- `@my_decorator` 等价 `func = my_decorator(func)`
- 不修改原函数，加功能
- 基于闭包
- [配图：装饰器作用示意]

## Slide 4：基础装饰器
```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        print("调用前")
        result = func(*args, **kwargs)
        print("调用后")
        return result
    return wrapper

@my_decorator
def greet(name):
    print(f"Hello, {name}!")
```

## Slide 5：@functools.wraps
- 装饰器会"替换"原函数
- 不加 @wraps：__name__ / __doc__ 丢失
- 加 @wraps：保留元信息
```python
from functools import wraps
def my_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```

## Slide 6：实战 - 常用装饰器
- 计时器：timer
- 日志：logged
- 缓存：@lru_cache
- 重试：retry
- [代码示例：四个装饰器]

## Slide 7：带参数装饰器（三层）
```python
def repeat(n):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(n):
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator

@repeat(3)
def hello(): print("hi")
```
- 工厂函数 + 装饰器 + 包装函数

## Slide 8：类装饰器
- 基于 __call__ 的类
- 可维护状态
```python
class CountCalls:
    def __init__(self, func):
        wraps(func)(self)
        self.func = func
        self.count = 0
    def __call__(self, *args, **kwargs):
        self.count += 1
        return self.func(*args, **kwargs)
```

## Slide 9：装饰器堆叠
```python
@timer
@logged
def f(): pass
# 等价:f = timer(logged(f))
# 调用:timer → logged → f → logged → timer
```
- 从下到上装饰
- 从上到下调用
- [配图：堆叠执行顺序图]

## Slide 10：实战 - Flask 风格路由
```python
routes = {}
def route(path):
    def decorator(func):
        routes[path] = func
        return func
    return decorator

@route("/")
def index(): return "home"
```
- 权限校验
- 重试机制
- 缓存策略
- [代码示例：完整应用]

## Slide 11：本讲总结与作业
- 核心要点：
  1. 装饰器 = 可调用对象
  2. @wraps 保留元信息
  3. 带参数需三层嵌套
- 作业：
  1. 实现 cache 装饰器
  2. 实现 rate_limit
  3. 实现 retry
