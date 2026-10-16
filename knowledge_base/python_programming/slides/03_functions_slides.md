# 03: 函数定义与参数 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：40 分钟

---

## Slide 1：封面
- 标题：函数定义与参数
- 副标题：Python 程序设计 · 第 4 讲
- 讲师：A3 智学领航

## Slide 2：本讲大纲
- 函数是第一类对象
- 函数定义语法
- 参数类型（位置/关键字/默认/*args/**kwargs）
- 作用域 LEGB
- 闭包
- lambda 与函数式工具
- 文档字符串

## Slide 3：函数是第一类对象
- 可赋值给变量
- 可作为参数传递
- 可作为返回值
- 可存入容器
```python
f = greet
f("Python")
map(greet, names)
```
- [配图：函数对象与其他类型的并列]

## Slide 4：函数定义
```python
def add(a: int, b: int) -> int:
    """返回两数之和"""
    return a + b
```
- `def` 关键字
- 参数：必填 + 类型注解
- 返回值：箭头 `->` 标注
- 文档字符串（PEP 257）

## Slide 5：参数类型
- 位置参数：`add(1, 2)`
- 关键字参数：`add(b=2, a=1)`
- 默认参数：`def greet(name, greeting="Hello")`
- `*args`：位置参数打包成 tuple
- `**kwargs`：关键字参数打包成 dict
- 强制关键字：`def f(a, *, b):` （* 后必须用关键字）

## Slide 6：可变默认参数陷阱
```python
# ❌ 错误
def add(item, lst=[]):
    lst.append(item)
    return lst

# ✅ 正确
def add(item, lst=None):
    if lst is None:
        lst = []
    lst.append(item)
    return lst
```
- 默认参数在函数定义时计算一次
- 多次调用共享同一对象

## Slide 7：作用域 LEGB
```
Local → Enclosing → Global → Built-in
```
- 函数内部修改全局：`global x`
- 嵌套函数修改外层：`nonlocal x`
- 最佳实践：避免 global，用参数传递
- [配图：LEGB 查找顺序图]

## Slide 8：闭包
```python
def make_counter():
    n = 0
    def counter():
        nonlocal n
        n += 1
        return n
    return counter

c = make_counter()
c()  # 1
c()  # 2
```
- 函数 + 引用的外部变量
- 应用：装饰器、回调、状态保持

## Slide 9：lambda 与高阶函数
```python
square = lambda x: x ** 2
students.sort(key=lambda s: s[1], reverse=True)
```
- 匿名函数，只有一个表达式
- 配合 `sorted` / `map` / `filter`
- 复杂逻辑用 `def` 而非 lambda
- `map` / `filter` / `reduce` / `partial`

## Slide 10：文档字符串
- PEP 257 规范
- 三种风格：Google / NumPy / Sphinx
- 工具自动生成 API 文档
```python
def fetch_user(user_id: int) -> dict:
    """获取用户信息。

    Args:
        user_id: 用户唯一标识

    Returns:
        包含用户字段的字典
    """
```
- [配图：Sphinx 自动生成的 API 文档截图]

## Slide 11：常见误区
- ❌ 可变默认参数
- ❌ 忘记 `global` 声明就修改全局
- ❌ 函数嵌套太深（> 3 层应拆）
- ❌ lambda 内部不能用 if-else 语句
- ❌ 不写 docstring

## Slide 12：本讲总结与作业
- 核心要点：
  1. 函数是一等对象
  2. 区分参数类型与作用域
  3. 闭包捕获定义时环境
- 作业：
  1. 实现 `make_counter()`
  2. 实现 `log(*messages, **fields)`
  3. 用 `reduce` 实现 `mymax`
