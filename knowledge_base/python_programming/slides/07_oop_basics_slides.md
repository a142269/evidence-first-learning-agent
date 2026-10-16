# 07: 类与对象 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：40 分钟

---

## Slide 1：封面
- 标题：类与对象
- 副标题：Python 程序设计 · 第 8 讲

## Slide 2：本讲大纲
- 面向对象三大特性
- 类定义与 self
- 实例/类属性
- 实例/类/静态方法
- 封装与命名约定
- @property
- 魔术方法
- 综合实战：银行卡

## Slide 3：面向对象三大特性
- 封装：将数据与行为打包
- 继承：子类复用父类
- 多态：同一接口不同实现
- Python 一切皆对象

## Slide 4：类定义基础
```python
class Dog:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def bark(self):
        return f"{self.name} says: Woof!"
```
- `class` 关键字
- `__init__` 构造方法
- `self` 是当前实例引用
- [配图：类与对象关系图]

## Slide 5：实例属性 vs 类属性
```python
class Circle:
    pi = 3.14159  # 类属性
    def __init__(self, r):
        self.r = r  # 实例属性
```
- 类属性被所有实例共享
- 实例属性每个实例独立
- 遮蔽：`c.pi = 3.14` 创建实例属性

## Slide 6：三种方法
| 方法 | 装饰器 | 第一参数 | 用途 |
|------|--------|----------|------|
| 实例方法 | 无 | self | 操作实例 |
| 类方法 | @classmethod | cls | 替代构造 |
| 静态方法 | @staticmethod | 无 | 工具函数 |

[代码示例：Date.from_string 替代构造]

## Slide 7：封装与命名
- `self.x` 公有
- `self._x` 内部（约定）
- `self.__x` 名称改写（`x = self._ClassName__x`）
- `self.__x__` 魔术方法

## Slide 8：@property
```python
class User:
    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if not 0 <= value <= 150:
            raise ValueError("...")
        self._age = value
```
- 像属性一样访问，背后加逻辑
- 应用：校验、计算属性、延迟加载
- [代码示例：Temperature 类]

## Slide 9：魔术方法
- `__repr__` / `__str__`：字符串表示
- `__eq__` / `__hash__`：相等与哈希
- `__add__` / `__sub__` / `__mul__`：运算符
- `__len__` / `__getitem__`：序列协议
- `__enter__` / `__exit__`：上下文

## Slide 10：运算符重载
```python
class Vector:
    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    def __abs__(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5
```
- 运算符 → 魔术方法
- `__rmul__` 右侧运算
- `@total_ordering` 补齐比较

## Slide 11：综合实战 - BankAccount
```python
class BankAccount:
    bank_name = "A3 银行"
    def __init__(self, owner, balance=0):
        self._balance = balance
    @property
    def balance(self): ...
    def deposit(self, amount): ...
    def withdraw(self, amount): ...
```
- 封装 + property + 异常
- [代码示例：完整实现]

## Slide 12：本讲总结与作业
- 核心要点：
  1. self 不是关键字
  2. 区分三种方法
  3. @property 用于校验
- 作业：
  1. 实现 Rectangle 类
  2. 实现 Temperature 类
  3. 阅读 Python 数据模型
