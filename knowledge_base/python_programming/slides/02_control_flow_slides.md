# 02: 控制流：条件与循环 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：控制流：条件与循环
- 副标题：Python 程序设计 · 第 3 讲
- 讲师：A3 智学领航

## Slide 2：本讲大纲
- 结构化程序设计
- if-elif-else
- for / range / enumerate / zip
- while
- break / continue / else
- 列表推导式
- match-case（3.10+）

## Slide 3：三大基本结构
- 顺序：代码按书写顺序执行
- 选择：if-elif-else
- 循环：for / while
- Böhm-Jacopini 定理：任何可计算程序都可用这三种结构组合
- [配图：流程图符号图例]

## Slide 4：if-elif-else
```python
def grade(score):
    if score >= 90: return "A"
    elif score >= 80: return "B"
    elif score >= 60: return "C"
    else: return "F"
```
- 缩进代表代码块（4 空格）
- 真值测试：`0` `""` `[]` `{}` `None` 都是 False
- 推荐 `if not items:` 而非 `if len(items) == 0:`

## Slide 5：三元表达式
```python
status = "成年" if age >= 18 else "未成年"
max_val = a if a > b else b
```
- C 风格：`x if cond else y`
- 适合简单条件
- 复杂判断仍用 if-else

## Slide 6：for + range
```python
for i in range(5):        # 0 1 2 3 4
    print(i)
for i in range(1, 10, 2): # 1 3 5 7 9
    print(i)
```
- `range(stop)` / `range(start, stop, step)`
- 惰性序列，O(1) 内存
- 反序：`range(10, 0, -1)`

## Slide 7：enumerate 与 zip
```python
for i, v in enumerate(fruits, start=1):
    print(f"{i}: {v}")

for name, score in zip(names, scores):
    print(f"{name}: {score}")
```
- `enumerate`：同时拿索引和值
- `zip`：并行遍历多个序列
- 长度不同时以最短为准
- `itertools.zip_longest` 可补齐

## Slide 8：while 循环
```python
while True:
    user_input = input("输入 q 退出: ")
    if user_input == "q":
        break
```
- 适用：不知道循环次数
- 死循环风险：必须保证有 break 或条件更新

## Slide 9：break / continue / else
```python
for n in range(2, 10):
    for x in range(2, n):
        if n % x == 0:
            break
    else:
        print(f"{n} 是素数")
```
- `break`：跳出当前循环
- `continue`：跳过本轮
- `else`：循环正常结束时执行（被 break 不执行）

## Slide 10：列表推导式
```python
squares = [i**2 for i in range(10)]
evens = [i for i in range(10) if i % 2 == 0]
pairs = [(x, y) for x in range(3) for y in range(3)]
```
- 4 种推导式：list / dict / set / generator
- 性能 vs 显式循环：略快
- 嵌套 ≤ 2 层；超 2 层用显式循环
- [代码示例：FizzBuzz 推导式版]

## Slide 11：match-case（3.10+）
```python
def http_status(status):
    match status:
        case 200: return "OK"
        case 301 | 302: return "Redirect"
        case 404: return "Not Found"
        case _: return "Unknown"
```
- 类似 switch-case
- 支持模式匹配（结构化）
- 3.10 之前用 if-elif 实现

## Slide 12：本讲总结与作业
- 核心要点：
  1. 三大结构 + 真值测试
  2. enumerate / zip 是 Python 风格
  3. 列表推导式简洁高效
- 作业：
  1. 实现 FizzBuzz
  2. 实现 `word_frequency(text)`
  3. 反汇编循环看字节码
