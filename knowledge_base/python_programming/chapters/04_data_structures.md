---
chapter_id: '04'
slug: data_structures
title: 列表、字典、元组与集合
kp_ids:
- PY_006
- PY_007
- PY_008
bloom_focus:
- Apply
- Analyze
prerequisites:
- '03'
estimated_minutes: 600
---

# 04: 列表、字典、元组与集合 · Python 内置容器的艺术

> **Bloom 层级**: Apply → Analyze
> **建议学时**: 600 分钟(10 学时)
> **前置知识**: §03 函数定义与参数

## 学习目标

1. 深入掌握 list 的增删改查、切片、列表推导式与排序。
2. 深入掌握 dict 的哈希表原理、键值约束、字典推导式。
3. 理解 tuple 的不可变性与命名元组(namedtuple)的应用。
4. 理解 set 的去重、集合运算与时间复杂度。
5. 能根据场景选择合适的数据结构,理解 Big-O 时间复杂度。
6. 掌握浅拷贝与深拷贝的差异。

## 4.1 数据结构总览

| 容器 | 可变 | 有序 | 重复 | 索引 | 哈希化 | 适用场景 |
|------|------|------|------|------|--------|----------|
| list | ✅ | ✅ | ✅ | ✅ | ❌ | 通用序列 |
| tuple | ❌ | ✅ | ✅ | ✅ | ❌ | 不可变记录、字典 key |
| dict | ✅ | ✅(插入序) | key 唯一 | ✅ | key | 映射、缓存 |
| set | ✅ | ❌ | ❌ | ❌ | ✅ | 去重、集合运算 |

## 4.2 列表(list)

### 4.2.1 创建与访问

```python
lst = [1, 2, 3, 4, 5]
empty = []
mixed = [1, "hello", 3.14, [1, 2]]  # 任意类型可混

# 索引(支持负数)
print(lst[0], lst[-1])  # 1 5
```

### 4.2.2 切片(slice)

切片语法 `lst[start:stop:step]`,返回新 list:

```python
lst = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
lst[2:5]      # [2, 3, 4]
lst[:3]       # [0, 1, 2]
lst[7:]       # [7, 8, 9]
lst[::2]      # [0, 2, 4, 6, 8]
lst[::-1]     # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]  ← 反转
lst[1:8:3]    # [1, 4, 7]

# 切片赋值
lst[2:5] = [20, 30]  # 替换
del lst[2:4]         # 删除
```

### 4.2.3 增删改查

```python
lst = [1, 2, 3]

# 增
lst.append(4)        # 末尾追加 [1, 2, 3, 4]
lst.insert(0, 0)     # 位置插入 [0, 1, 2, 3, 4]
lst.extend([5, 6])   # 拼接 [0, 1, 2, 3, 4, 5, 6]
lst += [7, 8]        # 等价于 extend

# 删
lst.pop()            # 末尾弹出 8
lst.pop(0)           # 位置弹出 0
lst.remove(3)        # 按值删(只删第一个) [1, 2, 4, 5, 6, 7]
del lst[0]           # 按索引删
lst.clear()          # 清空

# 查
lst.index(3)         # 第一次出现的索引,不存在 ValueError
3 in lst             # True
lst.count(3)         # 出现次数
```

### 4.2.4 排序与反转

```python
lst = [3, 1, 4, 1, 5, 9, 2, 6]

# 原地排序(返回 None)
lst.sort()                    # 升序
lst.sort(reverse=True)        # 降序
lst.sort(key=lambda x: -x)    # 自定义 key

# 返回新列表(原列表不变)
new_lst = sorted(lst)
new_lst = sorted(lst, reverse=True)
new_lst = sorted(lst, key=str)  # 按字符串排序

# 反转
lst.reverse()           # 原地
list(reversed(lst))     # 返回迭代器
```

### 4.2.5 列表的坑

```python
# 1. 乘法复制陷阱
nested = [[]] * 3
nested[0].append(1)
print(nested)  # [[1], [1], [1]]  ← 三个元素是同一对象!

# ✅ 正确
nested = [[] for _ in range(3)]
nested[0].append(1)
print(nested)  # [[1], [], []]

# 2. 迭代中修改
for item in lst:
    if condition:
        lst.remove(item)  # 跳过元素!

# ✅ 正确
lst = [x for x in lst if not condition]
```

## 4.3 字典(dict)

### 4.3.1 创建

```python
d1 = {"name": "Alice", "age": 25}
d2 = dict(name="Bob", age=30)         # 关键字参数
d3 = dict([("name", "Carol"), ("age", 28)])  # 二元组列表
d4 = {x: x**2 for x in range(5)}     # 字典推导式
d5 = dict.fromkeys(["a", "b"], 0)    # {'a': 0, 'b': 0}
```

### 4.3.2 哈希表原理

dict 底层是哈希表,平均查找/插入/删除都是 **O(1)**。要求 key 必须是**可哈希的**(不可变类型:int / str / tuple)。

```python
hash(42)             # 42
hash("hello")        # 随机正整数
hash((1, 2, 3))      # 可哈希
hash([1, 2])         # ❌ TypeError: list is unhashable
```

### 4.3.3 访问与修改

```python
d = {"name": "Alice", "age": 25}

# 访问
d["name"]                 # 'Alice'
d.get("name")             # 'Alice'
d.get("unknown", "N/A")   # 'N/A'  ← 不抛 KeyError

# 修改
d["age"] = 26
d.update({"city": "Beijing", "age": 27})

# 删除
del d["city"]
d.pop("age", None)        # 不存在返回 None,不抛异常
d.popitem()               # 弹出最后插入的 (key, value)
```

### 4.3.4 视图对象

```python
d = {"a": 1, "b": 2, "c": 3}
d.keys()      # dict_keys(['a', 'b', 'c'])
d.values()    # dict_values([1, 2, 3])
d.items()     # dict_items([('a', 1), ('b', 2), ('c', 3)])

# 视图动态反映 dict 变化
view = d.keys()
d["d"] = 4
print("d" in view)  # True
```

### 4.3.5 setdefault 与 defaultdict

```python
# setdefault:key 不存在时设默认值
d = {}
d.setdefault("fruits", []).append("apple")
d.setdefault("fruits", []).append("banana")
# {'fruits': ['apple', 'banana']}

# collections.defaultdict 更简洁
from collections import defaultdict
dd = defaultdict(list)
dd["fruits"].append("apple")
```

### 4.3.6 字典的有序性

Python 3.7+ 字典保证**插入顺序**,但不要依赖它做"有序查找":

```python
# 仍然可用 OrderedDict 显式表达意图
from collections import OrderedDict
od = OrderedDict()
od["a"] = 1
od["b"] = 2
```

## 4.4 元组(tuple)

### 4.4.1 不可变序列

```python
t = (1, 2, 3)
t = 1, 2, 3         # 圆括号可省
t = (1,)            # 单元素元组必须有逗号
empty = ()

# 不可变:不能增删改
t[0] = 99  # ❌ TypeError
```

### 4.4.2 解包

```python
a, b, c = (1, 2, 3)
first, *rest, last = [1, 2, 3, 4, 5]
# first=1, rest=[2,3,4], last=5

# 变量交换
a, b = b, a
```

### 4.4.3 命名元组(namedtuple)

```python
from collections import namedtuple
Point = namedtuple("Point", ["x", "y"])
p = Point(3, 4)
print(p.x, p.y)      # 3 4
print(p[0], p[1])    # 也支持索引
print(p._asdict())   # {'x': 3, 'y': 4}

# Python 3.7+ typing.NamedTuple 更强大(支持类型注解)
from typing import NamedTuple
class User(NamedTuple):
    name: str
    age: int
    email: str = ""
```

**优势**:比普通类更轻量,自带 `__repr__` / `__eq__` / 解包支持。

## 4.5 集合(set)

### 4.5.1 创建与去重

```python
s = {1, 2, 3, 2, 1}  # {1, 2, 3}
empty = set()         # ❌ {} 是空 dict
lst = [1, 2, 2, 3, 3, 3]
unique = set(lst)     # {1, 2, 3}
```

### 4.5.2 集合运算

```python
a = {1, 2, 3, 4}
b = {3, 4, 5, 6}

a | b        # 并集 {1, 2, 3, 4, 5, 6}
a & b        # 交集 {3, 4}
a - b        # 差集 {1, 2}
a ^ b        # 对称差 {1, 2, 5, 6}
a <= b       # a 是 b 的子集
a < b        # 真子集
a >= b       # 超集
```

### 4.5.3 集合方法

```python
s = {1, 2, 3}
s.add(4)              # {1, 2, 3, 4}
s.remove(2)           # 不存在抛 KeyError
s.discard(99)         # 不存在不报错
s.pop()               # 任意弹出一个
s.update({5, 6})      # 批量添加
```

**应用场景**:去重、成员检测(O(1))、求两列差异。

## 4.6 时间复杂度对比

| 操作 | list | tuple | dict | set |
|------|------|-------|------|-----|
| 索引访问 | O(1) | O(1) | O(1) | N/A |
| 末尾增删 | O(1)* | N/A | N/A | N/A |
| 中间增删 | O(n) | N/A | 平均 O(1) | 平均 O(1) |
| 成员检测 | O(n) | O(n) | O(1) | O(1) |
| 遍历 | O(n) | O(n) | O(n) | O(n) |

*list 末尾 append 是 O(1) amortized(均摊)。

## 4.7 浅拷贝与深拷贝

```python
import copy

a = [[1, 2], [3, 4]]

# 赋值(共享引用)
b = a
b[0][0] = 99
print(a)  # [[99, 2], [3, 4]] ← 被影响

# 浅拷贝(只复制一层)
b = a.copy()
b = a[:]
b = list(a)
b[0][0] = 99
print(a)  # [[99, 2], [3, 4]] ← 内层仍共享

# 深拷贝(完全独立)
b = copy.deepcopy(a)
b[0][0] = 99
print(a)  # [[1, 2], [3, 4]] ← 完全不受影响
```

**应用**:配置对象的快照、撤销/重做(undo/redo)栈。

## 4.8 常见误区

- **误区 1**:`[[]] * 3` 创建的三个元素是同一对象。
- **误区 2**:用 list 做 dict 的 key——list 不可哈希,会 TypeError。
- **误区 3**:在迭代 list 时删除元素——跳过/越界。
- **误区 4**:把 `dict.keys()` 当 list——3.7+ 之前它没有顺序(虽然现在有了)。
- **误区 5**:混淆浅拷贝与深拷贝——浅拷贝嵌套对象仍共享。

## 4.9 本章小结

1. list:动态数组,O(1) 末尾追加,O(n) 中间插入,支持切片与推导式。
2. dict:哈希表实现,O(1) 平均操作;key 必须是可哈希对象。
3. tuple:不可变序列,可做 dict key;namedtuple 提供字段命名。
4. set:无序不重复,O(1) 成员检测,支持集合代数运算。
5. 选数据结构看场景:频繁查找用 dict/set,有序序列用 list,不可变记录用 tuple。
6. 浅拷贝只复制一层,深拷贝用 `copy.deepcopy()` 递归复制。

## 4.10 练习思考

1. **代码分析**:解释下面输出:
   ```python
   a = [1, 2, 3]
   b = a
   a.append(4)
   print(b)  # ?
   a = [5, 6, 7]
   print(b)  # ?
   ```
2. **动手实践**:用 dict 统计一段文本中每个单词出现的次数(忽略大小写与标点)。
3. **动手实践**:写函数 `find_duplicates(lst) -> list`,找出列表中所有出现超过 1 次的元素(用 set)。
4. **代码优化**:把以下循环改为列表推导式:
   ```python
   result = []
   for item in items:
       if item.get("active"):
           result.append(item["name"].upper())
   ```
5. **动手实践**:用 namedtuple 表示"学生(姓名、学号、成绩)",实现一个班级(列表)按成绩排序的函数。

## 4.11 拓展阅读

- Python 容器官方文档:https://docs.python.org/3/tutorial/datastructures.html
- 《流畅的 Python》第 3 章 字典与集合
- TimeComplexity 官方 wiki:https://wiki.python.org/moin/TimeComplexity

---

*配套代码示例:`code_examples/04_data_structures_demo.py`*
*配套练习:`exercises/04_data_structures_exercises.md`*
