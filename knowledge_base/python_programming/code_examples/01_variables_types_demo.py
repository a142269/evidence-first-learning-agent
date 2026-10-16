"""Python 程序设计 · 配套实操示例 01 · 变量与数据类型 demo

对应章节: 01 变量与数据类型
对应 KP  : PY_002 (变量与数据类型), PY_003 (运算符与表达式)
Bloom 关注: Understand / Apply
运行方式 : python 01_variables_types_demo.py
依赖     : 纯标准库
说明     : 8 个 demo 函数覆盖变量赋值、动态类型、可变性、is vs ==、类型转换、运算符优先级、f-string 格式化。
"""
from __future__ import annotations

import sys


# ---------------------------------------------------------------------------
# 1. 环境自检 + 变量赋值演示
# ---------------------------------------------------------------------------
def demo_environment() -> None:
    """打印 Python 环境信息 + 基础变量"""
    print(f"Python  : {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    print(f"Encoding: {sys.getdefaultencoding()}")

    # 基础赋值
    name = "Python"
    version = 3.12
    is_stable = True
    print(f"{name} {version} (stable={is_stable})")
    print("[OK] environment + basic assignment")


# ---------------------------------------------------------------------------
# 2. 动态类型 + 类型注解
# ---------------------------------------------------------------------------
def demo_dynamic_typing() -> None:
    """变量可以重新指向不同类型"""
    x: int = 42
    print(f"x={x} (int), type={type(x).__name__}")
    x = "hello"
    print(f"x={x} (str), type={type(x).__name__}")
    x = [1, 2, 3]
    print(f"x={x} (list), type={type(x).__name__}")
    assert isinstance(x, list)
    print("[OK] dynamic typing")


# ---------------------------------------------------------------------------
# 3. 可变 vs 不可变
# ---------------------------------------------------------------------------
def demo_mutable_vs_immutable() -> None:
    """字符串不可变(list 可变)"""
    s = "hello"
    s_id_1 = id(s)
    s = s + " world"
    s_id_2 = id(s)
    assert s_id_1 != s_id_2, "字符串应创建新对象"
    print(f"str old_id={s_id_1}, new_id={s_id_2}")

    lst = [1, 2, 3]
    lst_id_1 = id(lst)
    lst.append(4)
    lst_id_2 = id(lst)
    assert lst_id_1 == lst_id_2, "list 原地修改"
    print(f"list id unchanged: {lst_id_1 == lst_id_2}, now={lst}")
    print("[OK] mutable vs immutable")


# ---------------------------------------------------------------------------
# 4. is vs ==
# ---------------------------------------------------------------------------
def demo_is_vs_eq() -> None:
    """is 比较身份(id),== 比较值"""
    a = [1, 2, 3]
    b = [1, 2, 3]
    assert (a == b) is True
    assert (a is b) is False
    print(f"a == b: {a == b}, a is b: {a is b}")

    # None 用 is
    x = None
    assert (x is None) is True
    assert (x == None) is True  # 也成立,但风格不佳
    print("[OK] is vs ==")


# ---------------------------------------------------------------------------
# 5. 类型转换
# ---------------------------------------------------------------------------
def demo_type_conversion() -> None:
    """int / float / str / bool 之间的转换"""
    assert int("42") == 42
    assert int(42.9) == 42  # 截断
    assert float("3.14") == 3.14
    assert str(42) == "42"
    assert bool(0) is False
    assert bool(1) is True
    assert bool("") is False
    assert bool("hi") is True
    # 失败抛 ValueError
    try:
        int("abc")
    except ValueError as e:
        print(f"  caught expected ValueError: {e}")
    print("[OK] type conversion")


# ---------------------------------------------------------------------------
# 6. 运算符优先级
# ---------------------------------------------------------------------------
def demo_operator_precedence() -> None:
    """验证常见优先级"""
    # * 高于 +
    assert 2 + 3 * 4 == 14
    # ** 高于 *
    assert 2 * 3 ** 2 == 18
    # 比较可链式
    x = 5
    assert 1 < x < 10
    # 海象运算符(3.8+)
    if (n := len("hello")) == 5:
        print(f"  walrus n={n}")
    # 短路求值
    assert ("" or "default") == "default"
    assert ("a" and "b") == "b"
    print("[OK] operator precedence")


# ---------------------------------------------------------------------------
# 7. 格式化(f-string)
# ---------------------------------------------------------------------------
def demo_formatting() -> None:
    """f-string 各种格式说明符"""
    name = "A3"
    score = 95.5
    print(f"{name} 得分: {score:.1f}")
    print(f"{score=:.2f}")  # 自记录表达式

    # 对齐与宽度
    for label in ["left", "center", "right"]:
        text = label
        print(f"|{text:<10}|{text:^10}|{text:>10}|")

    # 千分位 + 百分比
    big = 1234567
    ratio = 0.876
    print(f"big={big:,}, ratio={ratio:.2%}")
    print("[OK] f-string formatting")


# ---------------------------------------------------------------------------
# 8. 金融场景:Decimal 精确计算
# ---------------------------------------------------------------------------
def demo_decimal_precision() -> None:
    """float 不适合金融计算,用 Decimal"""
    from decimal import Decimal
    a = Decimal("0.1")
    b = Decimal("0.2")
    assert a + b == Decimal("0.3")
    assert (0.1 + 0.2) != 0.3  # float 有误差
    print(f"Decimal 0.1+0.2 = {a + b}")
    print(f"float   0.1+0.2 = {0.1 + 0.2}")
    print("[OK] decimal precision")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    demo_environment()
    demo_dynamic_typing()
    demo_mutable_vs_immutable()
    demo_is_vs_eq()
    demo_type_conversion()
    demo_operator_precedence()
    demo_formatting()
    demo_decimal_precision()
    print("\n✅ 所有测试通过!")
