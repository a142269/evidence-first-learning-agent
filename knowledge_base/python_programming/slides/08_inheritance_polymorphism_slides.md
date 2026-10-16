# 08: 继承与多态 · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：继承与多态
- 副标题：Python 程序设计 · 第 9 讲

## Slide 2：本讲大纲
- 继承基础
- super() 调用父类
- 多继承与 MRO
- 菱形继承
- 抽象基类 ABC
- 鸭子类型
- 组合 vs 继承

## Slide 3：单继承与方法重写
```python
class Animal:
    def speak(self): raise NotImplementedError
class Dog(Animal):
    def speak(self): return "Woof!"
```
- 父类方法不满足 → 子类重写
- 多态：同一接口不同实现
- [配图：UML 继承图]

## Slide 4：super() 调用父类
```python
class Bird(Animal):
    def __init__(self, name, wingspan):
        super().__init__(name)  # 调父类
        self.wingspan = wingspan
```
- 协同调用父类
- 避免硬编码父类名
- 支持链式调用

## Slide 5：MRO - 方法解析顺序
- C3 线性化算法
- 保证：子类在父类前，父类按声明顺序
- `D.__mro__` 查看顺序
```python
class D(B, C): pass
D.__mro__  # (D, B, C, A, object)
```
- [配图：C3 线性化算法示意]

## Slide 6：菱形继承 + super() 协同
```python
class A: def m(self): return "A"
class B(A): def m(self): return f"B({super().m()})"
class C(A): def m(self): return f"C({super().m()})"
class D(B, C): def m(self): return f"D({super().m()})"

D().m()  # "D(B(C(A)))"
```
- 每个类只执行一次
- super() 沿 MRO 链传递

## Slide 7：抽象基类 ABC
```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self): pass
    @abstractmethod
    def perimeter(self): pass

class Circle(Shape):
    def __init__(self, r): self.r = r
    def area(self): return 3.14159 * self.r ** 2
```
- 强制子类实现接口
- 未实现时实例化抛 TypeError
- 明确接口契约

## Slide 8：鸭子类型
```python
def make_speak(animal):
    return animal.speak()

class Robot:
    def speak(self):
        return "Beep!"

make_speak(Robot())  # "Beep!"
```
- 不需要继承
- 只要有 speak 方法就能用
- 灵活但难静态检查
- 核心抽象用 ABC，工具场景用鸭子

## Slide 9：组合 vs 继承
- 继承 "is-a"：ElectricCar is-a Car
- 组合 "has-a"：Car has-a Engine
- 优先组合，少用继承
- LSP：子类对象能完全替换父类
- [配图：组合 vs 继承关系图]

## Slide 10：实战：员工薪资
```python
class Employee(ABC):
    @abstractmethod
    def calc_salary(self): pass

class FullTime(Employee): ...
class PartTime(Employee): ...
class Intern(Employee): ...

total = sum(e.calc_salary() for e in staff)
```
- 抽象基类 + 多态
- 用 ABC 表达意图
- [代码示例：完整薪资系统]

## Slide 11：本讲总结与作业
- 核心要点：
  1. C3 线性化解决菱形继承
  2. ABC 强制接口契约
  3. 优先组合，少用继承
- 作业：
  1. 实现 Shape / Circle / Rectangle
  2. 实现 FlyingFish 多继承
  3. 用 isinstance 实现 safe_add
