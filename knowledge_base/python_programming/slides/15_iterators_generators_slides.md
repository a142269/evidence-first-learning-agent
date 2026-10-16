# 15: 迭代器与生成器 · 幻灯片大纲

> 总页数：10 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：迭代器与生成器
- 副标题：Python 程序设计 · 第 16 讲

## Slide 2：本讲大纲
- 迭代器协议
- 自定义迭代器
- yield 与生成器函数
- 生成器表达式
- 惰性计算应用
- 生成器高级方法
- itertools

## Slide 3：迭代器协议
- 可迭代对象：有 __iter__（iter() 调用）
- 迭代器：有 __iter__ + __next__（next() 调用）
- next() 到末尾抛 StopIteration
- for 循环本质：iter() + next() + 捕获 StopIteration
- [配图：迭代过程图]

## Slide 4：自定义迭代器
```python
class Countdown:
    def __init__(self, start):
        self.current = start
    def __iter__(self):
        return self
    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1
```
- 实现两个魔术方法

## Slide 5：生成器 - 优雅的迭代器
```python
def countdown(start):
    n = start
    while n > 0:
        yield n
        n -= 1
```
- yield 自动实现协议
- 不需要手动维护状态
- 局部变量自动保存
- [配图：生成器暂停/恢复示意]

## Slide 6：生成器表达式
- 方括号 [] → 列表推导式（立即）
- 圆括号 () → 生成器表达式（惰性）
```python
sum(i**2 for i in range(1_000_000))  # 几 KB
sum([i**2 for i in range(1_000_000)])  # 8MB+
```
- 内存优势
- 大数据首选

## Slide 7：惰性计算应用
- 大文件：for line in f
- 无限序列：fibonacci
- 数据管道：read → filter → transform
- [配图：数据管道流程]

## Slide 8：生成器高级方法
- send(value)：在 yield 处接收
- throw(exc)：在 yield 处抛异常
- close()：关闭生成器
- yield from sub_gen()：委派
- [代码示例：协程通信]

## Slide 9：itertools 模块
| 函数 | 用途 |
|------|------|
| count | 无限计数器 |
| cycle | 无限循环 |
| chain | 拼接迭代器 |
| islice | 切片 |
| takewhile | 满足条件则取 |
| groupby | 分组 |
| product | 笛卡尔积 |
| permutations | 排列 |
| combinations | 组合 |

## Slide 10：本讲总结与作业
- 核心要点：
  1. 迭代器协议 = __iter__ + __next__
  2. yield 自动实现协议
  3. 惰性计算省内存
- 作业：
  1. 实现 my_range
  2. 实现 read_large_csv
  3. 用 islice 实现 take
