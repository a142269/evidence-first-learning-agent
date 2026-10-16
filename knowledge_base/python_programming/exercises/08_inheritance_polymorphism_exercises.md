---
chapter_ref: "08"
chapter_title: "继承与多态"
kp_refs: [PY_012]
bloom_focus: [Apply, Analyze, Create]
total_points: 50
deadline_hint: 本章配套学习时长 4 学时
---

# 继承与多态 · 章节练习

> **配套**:A3 章节 §08 继承与多态
> **配对代码**:`code_examples/08_inheritance_demo.py`

---

## 一、选择题(每题 2 分,共 10 分)

### Q1(Remember)
Python 用什么算法决定多继承的方法解析顺序?

- A. 深度优先
- B. 广度优先
- C. C3 线性化
- D. 随机

<details><summary>答案</summary>C。Python 用 C3 线性化算法,可保证每个类只出现一次。</details>

### Q2(Apply)
调用 `super()` 在子类方法中的作用是?

- A. 调用父类同名方法
- B. 创建父类实例
- C. 删除父类
- D. 跳过父类

<details><summary>答案</summary>A。`super()` 返回父类的代理对象,用于调用被重写的父类方法。</details>

### Q3(Apply)
`class D(B, C)` 中,`D.__mro__` 的第一个元素是?

- A. `D`
- B. `B`
- C. `C`
- D. `object`

<details><summary>答案</summary>A。MRO 总是从子类开始。</details>

### Q4(Analyze)
`@abstractmethod` 装饰的方法在子类中没实现会怎样?

- A. 正常实例化
- B. 运行时调用才报错
- C. 实例化时抛 TypeError
- D. 自动生成空实现

<details><summary>答案</summary>C。抽象方法未实现时,Python 在实例化时抛 TypeError,防止错误使用。</details>

### Q5(Evaluate)
"鸭子类型"的核心思想是?

- A. 严格的类型检查
- B. 必须显式继承接口
- C. 看对象有什么方法,而不看它是什么类
- D. 用 type() 判断

<details><summary>答案</summary>C。只要对象有需要的方法,就能用,不强制类型/继承关系。</details>

---

## 二、填空题(每空 2 分,共 4 分)

### Q6(Apply)
`isinstance(x, (int, float))` 用于检查 x 是否是 int 或 float 中的 ______ 一个。

<details><summary>答案</summary>任一</details>

### Q7(Apply)
`issubclass(Dog, Animal)` 在 Dog 继承 Animal 时返回 ______ 。

<details><summary>答案</summary>True</details>

---

## 三、简答题(每题 6 分,共 12 分)

### Q8(Understand)
请说明 MRO(Method Resolution Order)在多继承中的作用。如何查看一个类的 MRO?

<details><summary>参考答案</summary>MRO 决定多继承时方法查找的顺序,Python 用 C3 线性化算法,保证:
1. 子类在父类之前
2. 父类按继承顺序
3. 每个类只出现一次
查看方法:
- `ClassName.__mro__`(元组)
- `ClassName.mro()`(列表)
- `help(ClassName)`</details>

### Q9(Analyze)
什么是菱形继承问题?Python 是如何用 super() 协同调用解决的?

<details><summary>参考答案</summary>菱形继承:A 是 B/C 的父类,D 同时继承 B/C,形成菱形。
问题:如果每个类都调 `A.method()`,A.method 会被调用两次,引发"重复调用"bug。
Python 解决:用 `super()` 协同链式调用,沿 MRO 链传递控制,每个类只执行一次。
```python
class A:
    def m(self): return "A"
class B(A):
    def m(self): return f"B({super().m()})"
class C(A):
    def m(self): return f"C({super().m()})"
class D(B, C):
    def m(self): return f"D({super().m()})"
# D().m() == "D(B(C(A)))"  每个类一次
```</details>

---

## 四、编程题(每题 12 分,共 24 分)

### Q10(Apply)
实现 `Shape` 抽象基类,要求 `area` / `perimeter` 为抽象方法,子类 `Circle` / `Rectangle` 必须实现。

<details><summary>参考实现</summary>

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self): pass

    @abstractmethod
    def perimeter(self): pass

class Circle(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14159 * self.r ** 2

    def perimeter(self):
        return 2 * 3.14159 * self.r

class Rectangle(Shape):
    def __init__(self, w, h):
        self.w, self.h = w, h

    def area(self):
        return self.w * self.h

    def perimeter(self):
        return 2 * (self.w + self.h)
```

</details>

### Q11(Create)
用多继承实现"会飞的鱼" `FlyingFish(Fish, Bird)`,通过 `super()` 协同 `swim` / `fly` / `speak` 三个方法,演示 MRO 协同调用。

<details><summary>参考实现</summary>

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "..."

class Fish(Animal):
    def swim(self):
        return f"{self.name} 游泳"
    def speak(self):
        return f"{self.name}: bubble"

class Bird(Animal):
    def fly(self):
        return f"{self.name} 飞翔"
    def speak(self):
        return f"{self.name}: chirp"

class FlyingFish(Fish, Bird):
    def speak(self):
        return f"{super().speak()} + chirp!"

ff = FlyingFish("飞飞")
print(ff.swim())  # 飞飞 游泳
print(ff.fly())   # 飞飞 飞翔
print(ff.speak()) # 飞飞: bubble + chirp!
print(FlyingFish.__mro__)
# (FlyingFish, Fish, Bird, Animal, object)
```

</details>

---

*本章配套代码:`code_examples/08_inheritance_demo.py` 包含 6 个 demo 函数,涵盖单继承、super、MRO、菱形继承、ABC、鸭子类型。*
