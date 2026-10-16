---
chapter_ref: "07"
chapter_title: "类与对象"
kp_refs: [PY_011]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 5 学时
---

# 类与对象 · 章节练习

> **配套**:A3 章节 §07 类与对象
> **配对代码**:`code_examples/07_oop_basics_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 中实例方法的第一个参数约定是?

- A. `cls`
- B. `self`
- C. `this`
- D. `obj`

<details><summary>答案</summary>B。`self` 是约定(不是关键字),代表当前实例。</details>

### Q2(Apply)
以下代码输出什么?
```python
class C:
    x = 1
a = C()
a.x = 99
print(C.x)
```

- A. `99`
- B. `1`
- C. `AttributeError`
- D. `0`

<details><summary>答案</summary>B。`a.x = 99` 只创建实例属性遮蔽类属性,`C.x` 仍为 1。</details>

### Q3(Apply)
`@classmethod` 的第一个参数是?

- A. `self`
- B. `cls`
- C. `instance`
- D. 没有

<details><summary>答案</summary>B。`cls` 是类本身,常用于替代构造。</details>

### Q4(Analyze)
`@staticmethod` 与 `@classmethod` 的本质区别?

- A. 性能不同
- B. staticmethod 不能访问 cls/this,classmethod 可以
- C. 都能访问 self
- D. staticmethod 更快

<details><summary>答案</summary>B。staticmethod 是普通函数,classmethod 第一参数是 cls。</details>

### Q5(Evaluate)
需要"对用户隐藏但子类可见"的属性,推荐命名?

- A. `self.x`
- B. `self._x`
- C. `self.__x`
- D. `self.x_`

<details><summary>答案</summary>B。单下划线表达"内部用"约定,子类可访问;`__x` 会名称改写。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`@property` 装饰的函数,可以用 `@xxx.setter` 定义对应的 ______ 。

<details><summary>答案</summary>setter(赋值器)</details>

### Q7(Remember)
`__str__` 与 `__repr__` 都未定义时,类的字符串表示默认显示类似 `______` 的内容。

<details><summary>答案</summary><__main__.ClassName object at 0x...></details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
实例属性、类属性、实例方法、类方法、静态方法的本质区别是什么?用表格说明访问范围。

<details><summary>参考答案</summary>| 类型 | 装饰器 | 第一参数 | 访问实例 | 访问类 | 用途 |
|------|--------|----------|----------|--------|------|
| 实例方法 | 无 | self | ✅ | ✅ | 操作实例数据 |
| 类方法 | @classmethod | cls | ❌ | ✅ | 替代构造、工厂 |
| 静态方法 | @staticmethod | 无 | ❌ | ❌ | 工具函数 |

类属性被所有实例共享,实例属性每个实例独立;类属性被实例"赋值"时,会创建实例属性遮蔽类属性,不影响其他实例。</details>

### Q9(Analyze)
`@property` 装饰器把方法"伪装"成属性有什么好处?举例说明三种典型用法。

<details><summary>参考答案</summary>好处:保留"属性"语法的简洁,在背后执行额外逻辑。
1. **计算属性**:`@property def area(self): return self.r ** 2 * pi`
2. **数据校验**:`@age.setter` 中判断 0 ≤ value ≤ 150
3. **延迟加载**:`@property def data(self):` 第一次访问才加载文件
4. **兼容性**:把方法改成 property 不破坏调用方代码</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `Rectangle` 类,含 `width` / `height` 属性,提供 `area` / `perimeter` 只读 property,`is_square` 静态方法,`from_string("10x20")` 类方法。

<details><summary>参考实现</summary>

```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    @property
    def area(self):
        return self.width * self.height

    @property
    def perimeter(self):
        return 2 * (self.width + self.height)

    @staticmethod
    def is_square(w, h):
        return w == h

    @classmethod
    def from_string(cls, s):
        w, h = map(float, s.split("x"))
        return cls(w, h)
```

</details>

### Q11(Create)
用 `@dataclass` 写一个 `Product` 数据类:字段 `name`(str)、`price`(float,默认 0)、`tags`(list,默认空 list 用 field)、`__repr__` 隐藏 `tags`。

<details><summary>参考实现</summary>

```python
from dataclasses import dataclass, field

@dataclass
class Product:
    name: str
    price: float = 0.0
    tags: list = field(default_factory=list, repr=False)

p = Product("Widget", 9.9, ["new", "hot"])
print(p)  # Product(name='Widget', price=9.9)
print(p.tags)  # ['new', 'hot']
```

</details>

---

*本章配套代码:`code_examples/07_oop_basics_demo.py` 包含 8 个 demo 函数,涵盖基础类、属性、方法类型、封装、property、魔术方法、运算符重载、实战。*
