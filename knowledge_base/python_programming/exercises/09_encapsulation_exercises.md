---
chapter_ref: "09"
chapter_title: "封装、property 与 dataclass"
kp_refs: [PY_013]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 3 学时
---

# 封装、property 与 dataclass · 章节练习

> **配套**:A3 章节 §09 封装、property 与 dataclass
> **配对代码**:`code_examples/09_encapsulation_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Understand)
Python 中"私有属性"实际靠什么机制实现?

- A. 编译器强制
- B. 名称改写(name mangling)
- C. 虚拟机层拦截
- D. 没有私有属性

<details><summary>答案</summary>B。`__attr` 会被改写为 `_ClassName__attr`,但仍可强行访问。</details>

### Q2(Apply)
`@property` 装饰的方法可以?

- A. 像属性一样访问
- B. 像方法一样调用
- C. 用 del 删除
- D. 用 raise 抛异常

<details><summary>答案</summary>A。property 让方法以 `obj.attr` 形式访问,而不是 `obj.attr()`。</details>

### Q3(Apply)
`@dataclass` 自动生成以下哪些方法?

- A. `__init__`
- B. `__repr__`
- C. `__eq__`
- D. 以上全部

<details><summary>答案</summary>D。@dataclass 自动生成 `__init__` / `__repr__` / `__eq__`,可减少样板代码。</details>

### Q4(Analyze)
`__slots__ = ("x", "y")` 的作用是?

- A. 限制属性
- B. 节省内存
- C. 提高属性访问速度
- D. 以上都是

<details><summary>答案</summary>D。__slots__ 锁定允许的属性,避免 __dict__ 内存开销,略快。</details>

### Q5(Evaluate)
需要一个"不可变且可哈希"的数据类,应该用?

- A. `class Point: pass`
- B. `@dataclass`
- C. `@dataclass(frozen=True)`
- D. `tuple`

<details><summary>答案</summary>C。frozen=True 禁止赋值,可自动 __hash__。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`@dataclass` 装饰的类,若字段默认值是可变对象(如 list),应该用 `field(default_factory=______)`。

<details><summary>答案</summary>list</details>

### Q7(Remember)
Python 描述符的三个魔术方法是 `__get__` / `__set__` / `______`。

<details><summary>答案</summary>__delete__</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 `__getattr__` 与 `__getattribute__` 的区别,各举一个使用场景。

<details><summary>参考答案</summary>- `__getattribute__`:**所有**属性访问都会先经过它(包括点运算符、`getattr()`),默认实现是去 `__dict__` 查
- `__getattr__`:**仅当常规查不到**属性时才会被调用(兜底)
场景:
- `__getattr__`:动态代理(如 `__getattr__` 把未知属性转发给内部对象)、ORM 字段懒加载
- `__getattribute__`:完全接管属性访问(慎用,容易写错导致无限递归)</details>

### Q9(Analyze)
`@dataclass` 比手写 `__init__` / `__repr__` / `__eq__` 有什么优势?有什么限制?

<details><summary>参考答案</summary>优势:
1. **减少样板代码**:5 行定义代替 30+ 行手写
2. **不易出错**:字段类型注解即真相
3. **可组合**:`frozen=True` / `order=True` / `slots=True` 一行启用
4. **IDE 友好**:字段一眼可见
限制:
1. 复杂初始化逻辑(校验、计算字段)需用 `__post_init__`
2. 继承时父类字段顺序有要求
3. 不适合行为密集的"非数据类"</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
用 `@property` 实现一个 `Temperature` 类,内部存摄氏度,提供 `celsius` / `fahrenheit` 两个 property,转换公式 `F = C * 9/5 + 32`。

<details><summary>参考实现</summary>

```python
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("低于绝对零度")
        self._celsius = value

    @property
    def fahrenheit(self):
        return self._celsius * 9 / 5 + 32

t = Temperature(100)
print(t.celsius, t.fahrenheit)  # 100 212.0
```

</details>

### Q11(Create)
用 `@dataclass(frozen=True)` 写一个 `GeoPoint` 数据类(latitude / longitude),并实现一个 `distance_to(other)` 方法(用球面距离公式的简化版 —— 平面距离),验证其 hashable。

<details><summary>参考实现</summary>

```python
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lon: float

    def distance_to(self, other):
        # 简化:平面欧氏距离(经纬度当作坐标)
        return math.sqrt((self.lat - other.lat) ** 2 + (self.lon - other.lon) ** 2)

p1 = GeoPoint(39.9, 116.4)  # 北京
p2 = GeoPoint(31.2, 121.5)  # 上海

# hashable
cache = {p1: "北京"}
assert cache[p1] == "北京"
assert hash(p1) == hash(GeoPoint(39.9, 116.4))

print(f"距离: {p1.distance_to(p2):.2f}")
```

</details>

---

*本章配套代码:`code_examples/09_encapsulation_demo.py` 包含 7 个 demo 函数,涵盖 property、dataclass、slots、描述符等。*
