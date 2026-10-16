# 04: 列表、字典、元组与集合 · 幻灯片大纲

> 总页数：12 页 | 建议讲解时长：50 分钟

---

## Slide 1：封面
- 标题：列表、字典、元组与集合
- 副标题：Python 程序设计 · 第 5 讲
- 讲师：A3 智学领航

## Slide 2：本讲大纲
- 四大内置容器概览
- 列表（list）
- 字典（dict）
- 元组（tuple）
- 集合（set）
- 时间复杂度对比
- 浅拷贝 vs 深拷贝

## Slide 3：四大容器概览
| 容器 | 可变 | 有序 | 重复 | 索引 | 哈希化 |
|------|------|------|------|------|--------|
| list | ✅ | ✅ | ✅ | ✅ | ❌ |
| tuple | ❌ | ✅ | ✅ | ✅ | ❌ |
| dict | ✅ | ✅ | key 唯一 | ✅ | key |
| set | ✅ | ❌ | ❌ | ❌ | ✅ |

## Slide 4：列表（list）
- 增：`append` / `insert` / `extend` / `+=`
- 删：`pop` / `remove` / `del` / `clear`
- 查：`index` / `count` / `in`
- 切片：`lst[1:5:2]` / `lst[::-1]`
- 排序：`sort()`（原地） / `sorted()`（新列表）
- [代码示例：常用操作合集]

## Slide 5：列表推导式与陷阱
```python
# ✅ 正确
nested = [[] for _ in range(3)]

# ❌ 陷阱
nested = [[]] * 3  # 三个元素是同一对象
```
- 推导式比循环快 ~20%
- 嵌套 ≤ 2 层
- 性能：避免在循环中 `lst.insert(0, x)`（O(n)）

## Slide 6：字典（dict）
- 创建：`{}` / `dict()` / `dict.fromkeys()` / 推导式
- 访问：`d[key]` / `d.get(key, default)`
- 修改：`d[key] = value` / `d.update()`
- 删除：`del` / `pop` / `popitem`
- 视图：`keys()` / `values()` / `items()`（动态）
- 哈希表原理：O(1) 平均
- [配图：哈希表结构示意图]

## Slide 7：dict 进阶
- `setdefault`：`d.setdefault(k, []).append(v)`
- `collections.defaultdict` 更简洁
- 3.7+ 保证插入顺序
- 哈希要求：key 必须是不可变对象
- [代码示例：词频统计 + Top-K]

## Slide 8：元组（tuple）
- 不可变序列
- 单元素元组必须有逗号：`(1,)`
- 解包：`a, b, c = (1, 2, 3)`
- `*` 收集：`first, *rest, last = lst`
- `namedtuple` / `typing.NamedTuple` 给字段命名
- 应用：字典 key、函数多返回值
- [代码示例：NamedTuple 定义]

## Slide 9：集合（set）
- 创建：`{}` / `set()` / 推导式
- 运算：`|` `&` `-` `^`
- 方法：`add` / `remove`（抛异常）/ `discard`（不抛）
- 性能：O(1) 成员检测
- 应用：去重、集合运算、Top-K 优化
- [配图：集合文氏图]

## Slide 10：时间复杂度对比
| 操作 | list | tuple | dict | set |
|------|------|-------|------|-----|
| 索引访问 | O(1) | O(1) | O(1) | N/A |
| 末尾增删 | O(1) | N/A | N/A | N/A |
| 中间增删 | O(n) | N/A | O(1) | O(1) |
| 成员检测 | O(n) | O(n) | O(1) | O(1) |

## Slide 11：浅拷贝 vs 深拷贝
```python
import copy
b = a.copy()         # 浅
b = copy.deepcopy(a) # 深
```
- 浅：只复制一层
- 深：递归复制所有层级
- 应用：快照、undo/redo、并发传数据
- [配图：浅/深拷贝对象图]

## Slide 12：本讲总结与作业
- 核心要点：
  1. 四大容器各有适用场景
  2. dict / set 是 O(1) 平均操作
  3. 拷贝分浅深
- 作业：
  1. 实现 `group_by(items, key)`
  2. 实现 `find_top_n(scores, n)`
  3. 写函数 `find_duplicates(lst)`
