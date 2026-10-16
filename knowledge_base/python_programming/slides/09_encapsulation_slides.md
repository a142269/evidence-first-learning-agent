# 09: 封装、property 与 dataclass · 幻灯片大纲

> 总页数：10 页 | 建议讲解时长：30 分钟

---

## Slide 1：封面
- 标题：封装、property 与 dataclass
- 副标题：Python 程序设计 · 第 10 讲

## Slide 2：本讲大纲
- Python 封装哲学
- 属性访问拦截
- @property 进阶
- @dataclass 详解
- __slots__ 优化
- 描述符简介

## Slide 3：Python 封装哲学
- "我们都是自愿遵守约定的成年人"
- 私有属性靠"约定 + 名称改写"
- 99% 场景用 `_attr` 单下划线
- [配图：name mangling 前后对比]

## Slide 4：属性访问拦截
- `__getattribute__`：所有属性访问
- `__getattr__`：仅当属性 NOT FOUND
- `__setattr__`：所有属性赋值（注意递归）
- 应用：ORM 字段懒加载、代理模式

## Slide 5：@property 进阶
- 计算属性（Circle.area）
- 数据校验（User.age）
- 延迟加载（Image.data）
- 兼容性：方法改属性不破坏调用
- [代码示例：Temperature 类]

## Slide 6：@dataclass
```python
from dataclasses import dataclass, field

@dataclass
class Point:
    x: float
    y: float

p = Point(3, 4)
p == Point(3, 4)  # True
```
- 自动生成 __init__ / __repr__ / __eq__
- 减少样板代码
- field() 处理可变默认值
- [代码示例：Product 数据类]

## Slide 7：@dataclass(frozen=True)
- 不可变数据类
- 自动 __hash__
- 应用：常量、缓存 key、配置
- [代码示例：GeoPoint 距离计算]

## Slide 8：__slots__ 优化
- 默认每个实例有 __dict__
- __slots__ 锁定属性，省内存
- 限制：不能再加新属性
- 适合：大量实例
- [配图：dict vs slots 内存对比]

## Slide 9：描述符简介
- property 的底层机制
- 三个魔术方法：__get__ / __set__ / __delete__
- __set_name__ 自动获取属性名
- 应用：Django ORM、SQLAlchemy column
- [代码示例：Positive 描述符]

## Slide 10：本讲总结与作业
- 核心要点：
  1. Python 封装靠"约定"
  2. @property 用于校验/计算
  3. @dataclass 简化数据类
- 作业：
  1. 实现 Temperature
  2. 实现 Address @dataclass
  3. 实现 Positive 描述符
