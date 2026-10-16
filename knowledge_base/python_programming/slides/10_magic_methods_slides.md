# 10: 魔术方法与上下文管理器 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：40 分钟

---

## Slide 1：封面
- 标题：魔术方法与上下文管理器
- 副标题：Python 程序设计 · 第 11 讲

## Slide 2：本讲大纲
- 魔术方法概览
- __repr__ / __str__ / __eq__
- 运算符重载
- total_ordering
- 可迭代对象
- __call__
- 上下文管理器
- contextmanager

## Slide 3：魔术方法速查
- 比较：__eq__ / __lt__ / __le__ ...
- 算术：__add__ / __sub__ / __mul__
- 容器：__len__ / __getitem__ / __contains__
- 迭代：__iter__ / __next__
- 调用：__call__
- 上下文：__enter__ / __exit__
- [配图：魔术方法分类脑图]

## Slide 4：__repr__ vs __str__
- __repr__：明确表示（尽量可执行）
- __str__：友好展示
- 容器中显示 __repr__
- print() / str() 用 __str__
- 默认：`<ClassName object at 0x...>`

## Slide 5：运算符重载
```python
class Vector:
    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    def __rmul__(self, scalar):
        return self.__mul__(scalar)
    def __neg__(self):
        return Vector(-self.x, -self.y)
```
- 运算符 → 魔术方法
- __rmul__ 处理右侧运算
- @total_ordering 补齐比较

## Slide 6：@total_ordering
```python
@total_ordering
class Money:
    def __eq__(self, other): ...
    def __lt__(self, other): ...
```
- 写 __eq__ + __lt__
- 自动补齐 __le__ / __gt__ / __ge__
- 减少样板代码

## Slide 7：可迭代对象
- 任何 __iter__ 的对象都可迭代
- __iter__ 返回迭代器
- __next__ 返回下一个值
```python
class Countdown:
    def __iter__(self):
        n = self.start
        while n > 0:
            yield n
            n -= 1
```
- 生成器自动实现

## Slide 8：__call__
- 让对象像函数一样调用
- 应用：函数工厂、参数化函数、装饰器
```python
class Multiplier:
    def __init__(self, factor):
        self.factor = factor
    def __call__(self, x):
        return x * self.factor
double = Multiplier(2)
double(10)  # 20
```

## Slide 9：上下文管理器
- with 语句保证资源清理
- __enter__：进入，返回值赋给 as
- __exit__(exc_type, exc_val, exc_tb)：退出
- 返回 True 抑制异常
- 应用：文件、锁、计时、事务

## Slide 10：@contextmanager
```python
from contextlib import contextmanager

@contextmanager
def timer(label="block"):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        print(f"{label}: {time.perf_counter() - t0:.3f}s")
```
- 把生成器函数变成上下文管理器
- yield 之前 = __enter__
- yield 之后 = __exit__
- 更简洁

## Slide 11：常用上下文管理器
- `open()` 文件
- `contextlib.suppress(*exceptions)` 抑制
- `contextlib.closing(obj)` 自动 close
- `redirect_stdout` 重定向输出
- `ExitStack` 动态管理多个上下文

## Slide 12：本讲总结与作业
- 核心要点：
  1. 魔术方法定义对象行为
  2. 运算符重载让类支持内置语法
  3. with 保证资源清理
- 作业：
  1. 实现 Vector 算术
  2. 实现 Money 比较
  3. 实现 temporary_value 上下文
