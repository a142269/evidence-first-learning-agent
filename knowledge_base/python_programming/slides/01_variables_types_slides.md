# 01: 变量与数据类型 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：40 分钟

---

## Slide 1：封面
- 标题：变量与数据类型
- 副标题：Python 程序设计 · 第 2 讲
- 讲师：A3 智学领航

## Slide 2：本讲大纲
- 变量与赋值
- 基本数据类型
- 动态类型 vs 类型注解
- 可变与不可变
- is vs ==
- 类型转换

## Slide 3：变量是"标签"
```python
a = 10
b = a
a = 20
print(b)  # 10
```
- Python 变量是"贴在对象上的标签"
- 不是"装数据的盒子"
- 多个变量可指向同一对象
- [配图：变量与对象关系图]

## Slide 4：基本数据类型
| 类型 | 例子 | 特性 |
|------|------|------|
| int | 42, 0, -100 | 任意精度 |
| float | 3.14, 1e10 | 双精度 IEEE 754 |
| str | "hello" | 不可变 Unicode |
| bool | True / False | int 的子类 |
| None | None | 空对象 |

## Slide 5：动态类型
```python
x = 10          # int
x = "hello"     # str
x = [1, 2]      # list
```
- 灵活但有风险
- 类型注解（3.5+）：
  ```python
  def greet(name: str) -> str: ...
  ```
- 静态检查工具：mypy / pyright

## Slide 6：可变 vs 不可变
- 不可变：int / float / str / tuple / frozenset
- 可变：list / dict / set / bytearray
- 内存中的差别
- [配图：可变 vs 不可变对象的 id 变化]

## Slide 7：is vs ==
```python
a = [1, 2, 3]
b = [1, 2, 3]
a == b   # True（值相等）
a is b   # False（不同对象）
```
- `==`：调用 `__eq__`，比较值
- `is`：比较内存地址
- 判断 None 用 `is`

## Slide 8：类型转换
| 转换 | 例子 |
|------|------|
| int("42") | 42 |
| int(42.9) | 42（截断） |
| float("3.14") | 3.14 |
| str(42) | "42" |
| bool(0) | False |

[代码示例：safe_int 转换函数]

## Slide 9：运算符优先级
```
** → +x -x ~x → * / // % → + - → << >>
→ & → ^ → | → 比较 → not → and → or
```
- 链式比较：`1 < x < 10`
- 海象运算符 `:=`（3.8+）
- [配图：运算符优先级金字塔图]

## Slide 10：金融场景 - Decimal
```python
from decimal import Decimal
Decimal("0.1") + Decimal("0.2")  # 0.3
0.1 + 0.2                          # 0.30000000000000004
```
- 浮点数不适合精确计算
- Decimal 用于金融、税务
- [代码示例：货币计算]

## Slide 11：常见误区
- ❌ `a += b` 总是新建对象
- ❌ `[[]] * 3` 创建独立对象（实际共享）
- ❌ 空对象 `[]` / `0` / `""` 是 `False` 但不是 `None`
- ❌ 浮点数 `==` 比较（用 `abs(a-b) < eps`）

## Slide 12：本讲总结与作业
- 核心要点：
  1. 变量是"标签"非"盒子"
  2. 区分可变/不可变
  3. `is` vs `==` 不可混用
- 作业：
  1. 实现 `safe_divide(a, b)`
  2. 实现 `normalize_score(scores)`
  3. 阅读 §01 章节，写 200 字反思
