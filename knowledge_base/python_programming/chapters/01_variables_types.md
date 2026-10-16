---
chapter_id: '01'
slug: variables_types
title: 变量与数据类型
kp_ids:
- PY_002
- PY_003
bloom_focus:
- Remember
- Understand
- Apply
prerequisites:
- '00'
estimated_minutes: 300
---

# 01: 变量与数据类型 · Python 世界的原子与分子

> **Bloom 层级**: Remember → Understand → Apply
> **建议学时**: 300 分钟(5 学时)
> **前置知识**: §00 Python 语言概述

## 学习目标

1. 掌握 Python 七种基本数据类型(int / float / str / bool / None / list / dict)的定义与使用。
2. 理解动态类型、引用语义与可变/不可变对象的本质区别。
3. 熟练进行类型转换(int() / str() / float() / bool()),理解转换失败的异常处理。
4. 区分 `is` 与 `==` 的语义差异,理解 CPython 字符串驻留(intern)机制。
5. 掌握各类运算符(算术、比较、逻辑、赋值、位运算)的用法与优先级。
6. 能运用变量与数据类型解决一般编程问题(数据校验、解析用户输入等)。

## 1.1 变量与赋值:标签,而不是盒子

Python 中的变量与传统编译型语言不同——它不是"装数据的盒子",而是"贴在对象上的标签"。看下面这段代码:

```python
a = 10
b = a
a = 20
print(b)  # 10,不是 20
```

执行流程:
1. 创建整数对象 `10`,把标签 `a` 贴上去
2. 让 `b` 也指向 `10`(不是"复制 a 的值")
3. 创建新对象 `20`,把 `a` 重新贴到 `20` 上
4. `b` 仍指向 `10`

可以用 `id()` 函数查看对象的内存地址:

```python
x = 256
y = x
print(id(x), id(y))  # 两个 id 相同,说明指向同一个对象
```

**多重赋值** Python 支持一行给多个变量赋值:

```python
a, b, c = 1, 2, 3
x = y = z = 0
first, *middle, last = [1, 2, 3, 4, 5]  # 解包
print(first, middle, last)  # 1 [2, 3, 4] 5
```

## 1.2 基本数据类型

### 1.2.1 数值类型

| 类型 | 关键字 | 例子 | 特性 |
|------|--------|------|------|
| 整数 | `int` | `-100, 0, 42` | 任意精度(无溢出) |
| 浮点数 | `float` | `3.14, -0.5, 1e10` | 双精度 64 位 IEEE 754 |
| 复数 | `complex` | `3+4j` | 实部+虚部 |
| 布尔 | `bool` | `True, False` | 实际是 int 的子类(0/1) |
| None | `NoneType` | `None` | "空"对象,占位符 |

```python
# 整数支持任意大数
big = 10**100  # 比宇宙原子数还大
print(big.bit_length())  # 位长 333

# 浮点数有精度问题
print(0.1 + 0.2)  # 0.30000000000000004
# 推荐用 decimal 模块处理金融数据
from decimal import Decimal
print(Decimal('0.1') + Decimal('0.2'))  # 0.3

# 布尔值是 int 子类
print(isinstance(True, int))  # True
print(True + True)  # 2
```

### 1.2.2 字符串类型

字符串是不可变的 Unicode 字符序列:

```python
s1 = 'hello'
s2 = "world"
s3 = """多行
字符串"""
s4 = r"原始\n字符串,不会转义"

# f-string(Python 3.6+)
name = "A3"
score = 95.5
print(f"{name} 得分: {score:.1f}")  # A3 得分: 95.5
print(f"{score=:.2f}")  # score=95.50(自记录表达式,3.8+)
```

### 1.2.3 容器类型概览

| 容器 | 可变 | 有序 | 重复元素 | 索引访问 | 适用场景 |
|------|------|------|----------|----------|----------|
| `list` | ✅ | ✅ | ✅ | ✅ | 通用序列 |
| `tuple` | ❌ | ✅ | ✅ | ✅ | 不可变记录 |
| `dict` | ✅ | ✅(插入序,3.7+) | key 唯一 | ✅ | 映射 |
| `set` | ✅ | ❌ | ❌ | ❌ | 去重、集合运算 |

容器类型在 §04 详细展开。

## 1.3 动态类型与类型注解

Python 是动态类型语言——变量无需声明类型,同一个变量可以先后指向不同类型的对象:

```python
x = 10       # int
x = "hello"  # 现在是 str
x = [1, 2]   # 现在是 list
```

**类型注解**(Python 3.5+)是"可选的"类型提示,不影响运行:

```python
def greet(name: str, times: int = 1) -> str:
    return f"Hello, {name}! " * times

# 注解不强制
print(greet(123, "abc"))  # 也能跑,但 IDE 会警告
```

类型注解的好处:
- IDE 智能补全更准
- mypy / pyright 静态检查
- 代码自文档化

**运行时类型检查**:

```python
x = "42"
print(type(x))           # <class 'str'>
print(isinstance(x, str))  # True
```

## 1.4 可变与不可变对象

这是 Python 面试的高频考点:

| 不可变(immutable) | 可变(mutable) |
|-------------------|----------------|
| int, float, bool, str | list |
| tuple | dict |
| frozenset | set |
| bytes | bytearray |

```python
# 不可变:看似修改,实则创建新对象
a = "hello"
print(id(a))  # 140...
a = a + " world"
print(id(a))  # 不同的 id

# 可变:原地修改
lst = [1, 2, 3]
print(id(lst))  # 140...
lst.append(4)
print(id(lst))  # 同一个 id
```

**为什么重要?** 函数传参时,不可变对象是"值传递"语义,可变对象是"引用传递"语义:

```python
def modify(x, lst):
    x = 999            # 不影响外部
    lst.append(999)    # 影响外部!

a = 1
b = [1, 2, 3]
modify(a, b)
print(a, b)  # 1 [1, 2, 3, 999]
```

## 1.5 is 与 == 的区别

- `==` 比较**值**是否相等(调用 `__eq__` 方法)
- `is` 比较**身份**是否相同(内存地址是否一致,即 `id()` 是否相同)

```python
a = [1, 2, 3]
b = [1, 2, 3]
print(a == b)  # True,值相同
print(a is b)  # False,不同对象

c = a
print(a is c)  # True,指向同一对象
```

**常见陷阱**:CPython 对小整数(-5~256)和简单字符串做了"驻留"优化,导致某些场景 `is` 行为不可预期:

```python
# 驻留优化内
a = 256
b = 256
print(a is b)  # True

# 驻留优化外
a = 257
b = 257
print(a is b)  # False(大多数情况)
```

**最佳实践**:判断 `None` 用 `is`(`x is None`),其他场景一律用 `==`。

## 1.6 类型转换

```python
# 显式转换
int("42")          # 42
int("42.5")        # ❌ ValueError
int(42.9)          # 42(截断,不四舍五入)
float("3.14")      # 3.14
str(42)            # "42"
bool(0)            # False
bool(1)            # True
bool("")           # False
list("abc")        # ['a', 'b', 'c']
tuple([1, 2])      # (1, 2)
set([1, 1, 2])     # {1, 2}
dict([(1, 'a'), (2, 'b')])  # {1: 'a', 2: 'b'}
```

**转换失败会抛异常**:

```python
int("abc")  # ValueError: invalid literal for int()
```

**安全转换**(Python 3.13+)或自定义:

```python
def safe_int(s, default=0):
    try:
        return int(s)
    except (ValueError, TypeError):
        return default
```

## 1.7 运算符与优先级

### 1.7.1 算术运算符

| 运算符 | 含义 | 例子 |
|--------|------|------|
| `+` `-` `*` `/` | 加减乘除 | `7 / 2 = 3.5`(真除) |
| `//` | 整除(向下取整) | `7 // 2 = 3` |
| `%` | 取模 | `7 % 2 = 1` |
| `**` | 幂 | `2 ** 10 = 1024` |
| `@` | 矩阵乘(NumPy) | `np.array(...) @ np.array(...)` |

### 1.7.2 比较与逻辑

```python
# 链式比较(Python 特色)
1 < x < 10          # 等价于 1 < x and x < 10
'a' < 'b' < 'c'     # True(字符串按字典序)

# 短路求值
'a' or 'b'          # 'a' (非空字符串为 True)
'' or 'b'           # 'b'
'a' and 'b'         # 'b'
'' and 'b'          # ''
```

### 1.7.3 海象运算符(Python 3.8+)

`:=` 可以在表达式中赋值:

```python
# 传统写法
n = len(data)
if n > 10:
    print(f"数据过长: {n}")

# 海象写法
if (n := len(data)) > 10:
    print(f"数据过长: {n}")
```

### 1.7.4 优先级(从高到低)

```
**  →  +x -x ~x  →  * / // %  →  + -  →  << >>  →
&  →  ^  →  |  →  比较运算  →  not  →  and  →  or
```

**记忆口诀**:一元 > 乘除 > 加减 > 位运算 > 比较 > 逻辑 > 赋值

## 1.8 常见误区

- **误区 1**:`a += b` 等价于 `a = a + b`——对不可变对象成立;对可变对象(如 list),`+=` 实际是 `extend`,而 `a = a + b` 会创建新对象。
- **误区 2**:`"a" * 3 == "aaa"`,`[1] * 3 == [1, 1, 1]`,但 `[[]] * 3 == [[], [], []]`——三个元素指向同一个内层 list,改一个全改!
- **误区 3**:布尔上下文中,`0` `""` `[]` `{}` `None` 都是 False,其他都算 True(包括负数、空对象)——**不要把空容器当 None 用**。
- **误区 4**:`float` 不能精确表示十进制小数,金融计算要用 `decimal.Decimal`;`==` 比较浮点数有风险,应该用 `abs(a - b) < 1e-9`。

## 1.9 本章小结

1. Python 变量是"贴在对象上的标签",不是装数据的盒子。
2. 基本类型:int / float / str / bool / None,容器类型:list / dict / tuple / set。
3. 动态类型 + 类型注解双轨制——灵活的同时提供可选的类型提示。
4. 可变 vs 不可变对象决定了函数参数的"引用"或"值"语义。
5. `is` 比较身份(id),`==` 比较值;判断 None 用 `is`。
6. 运算符优先级:** 最高,or 最低;链式比较是 Python 特色。
7. 海象运算符 `:=` 在表达式中赋值,3.8+ 可用。

## 1.10 练习思考

1. **概念辨析**:解释"Python 变量是标签,不是盒子",画图说明 `a = 10; b = a; a = 20` 的内存变化。
2. **动手实践**:写代码验证 `a = 257; b = 257; a is b` 在你的 Python 版本上输出什么,为什么?
3. **动手实践**:实现 `safe_int(s, default)`,处理 `int("abc")` 抛异常的情况,返回 default。
4. **代码分析**:下面代码输出什么?为什么?
   ```python
   a = [1, 2, 3]
   b = a
   a += [4]
   print(b)
   c = [1, 2, 3]
   d = c
   c = c + [4]
   print(d)
   ```
5. **拓展探索**:用 `dis` 模块反汇编 `a + b` 和 `a += b`,对比字节码差异。

## 1.11 拓展阅读

- Python 数据模型:https://docs.python.org/3/reference/datamodel.html
- PEP 8 命名约定:https://peps.python.org/pep-0008/#naming-conventions
- 《流畅的 Python》第 1 章 Python 数据模型
- mypy 官方文档:https://mypy.readthedocs.io/

---

*配套代码示例:`code_examples/01_variables_types_demo.py`*
*配套练习:`exercises/01_variables_types_exercises.md`*
