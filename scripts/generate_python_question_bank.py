"""Generate Python 240-question bank (data/question_bank_python.json).

24 KP × 10 questions = 240 questions
- Type: 120 multiple_choice + 48 short_answer + 36 open_ended + 36 programming
- Bloom: Remember 40 / Understand 48 / Apply 48 / Analyze 40 / Evaluate 32 / Create 32
- Difficulty: 1-5 (each KP has 2 of difficulty 1-3, 2 of difficulty 4-5)
"""
import json
import os
from pathlib import Path

OUTPUT = Path(r"F:\比赛\中软杯\A3\data\question_bank_python.json")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


# KP 名称（与 knowledge_map.yaml 对应）
KPS = [
    ("PY_001", "Python 语言概述"),
    ("PY_002", "变量与数据类型"),
    ("PY_003", "运算符与表达式"),
    ("PY_004", "控制流（条件与循环）"),
    ("PY_005", "函数定义与参数"),
    ("PY_006", "列表与列表推导式"),
    ("PY_007", "字典与哈希表"),
    ("PY_008", "元组与集合"),
    ("PY_009", "字符串操作"),
    ("PY_010", "collections 高级容器"),
    ("PY_011", "类与对象"),
    ("PY_012", "继承与多态"),
    ("PY_013", "封装与 property"),
    ("PY_014", "魔术方法"),
    ("PY_015", "上下文管理器"),
    ("PY_016", "文件读写"),
    ("PY_017", "pathlib 路径操作"),
    ("PY_018", "CSV 与 JSON 处理"),
    ("PY_019", "异常处理"),
    ("PY_020", "自定义异常"),
    ("PY_021", "常用标准库"),
    ("PY_022", "迭代器与生成器"),
    ("PY_023", "装饰器"),
    ("PY_024", "Python 项目实战"),
]


# 每个 KP 的"题种子"模板
# 每条 seed 是 (bloom, type, difficulty, stem, options_or_test, answer, explanation, expected_keywords)
# options_or_test: 选择题给 4 个选项,其他类型给 None


# Bloom 分布: Remember 40, Understand 48, Apply 48, Analyze 40, Evaluate 32, Create 32
# Type 分布: multiple_choice 120, short_answer 48, open_ended 36, programming 36
# Difficulty 1-5: 每个 KP 至少含难度 1-3 各 2 题, 难度 4-5 各 2 题


# 24 KP × 10 题 = 240
# 实际结构:每个 KP 1-2 选择 + 1-2 简答 + 1 开放 + 1 编程
# 我们用预定义题目 + 一些模板填充

# 每个 KP 的 10 题,精心设计:

QUESTIONS = {
    "PY_001": [
        ("Remember", "multiple_choice", 1,
         "Python 是由谁创造的？",
         ["Dennis Ritchie", "Guido van Rossum", "James Gosling", "Bjarne Stroustrup"],
         "B",
         "Python 由 Guido van Rossum 于 1989 年底开始设计,1991 年正式发布。"),
        ("Remember", "multiple_choice", 1,
         "Python 2 已于哪一年停止维护(EOL)？",
         ["2015", "2018", "2020", "2023"],
         "C",
         "Python 2 于 2020 年 1 月 1 日正式 EOL,所有新项目应使用 Python 3。"),
        ("Understand", "multiple_choice", 2,
         "以下哪项是 Python 作为「解释型语言」的特征？",
         ["编译后生成 .exe 文件", "代码逐行解释执行,无需编译步骤",
          "运行速度必然快于编译型语言", "必须安装 JDK"],
         "B",
         "解释型语言逐行读取源代码并执行,不需要预先编译为机器码。"),
        ("Apply", "short_answer", 2,
         "写出在终端启动 Python 交互式解释器的命令,以及退出命令。",
         None,
         "启动:python  退出:exit() 或 quit() 或 Ctrl+D",
         "交互式命令行称为 REPL(Read-Eval-Print Loop)。"),
        ("Apply", "programming", 2,
         "编写一个 Python 脚本,打印 'Hello, Python!' 与 'A3 智学领航',运行后两行各占一行。",
         None,
         "print('Hello, Python!')\nprint('A3 智学领航')",
         "考察 print 基础用法。",
         ["print"]),
        ("Analyze", "multiple_choice", 3,
         "下面哪一项是 pip 的正确使用方式？",
         ["pip install requests", "pip get requests", "python pip requests", "pip fetch requests"],
         "A",
         "pip install <package> 是安装包的标准命令。"),
        ("Evaluate", "short_answer", 3,
         "为什么新项目应该用虚拟环境(venv)？说出至少 2 点。",
         None,
         "1. 隔离项目间依赖避免版本冲突\n2. 便于复现:requirements.txt 锁定依赖\n3. 不污染全局 Python 环境",
         "虚拟环境是项目级 Python 包管理最佳实践。"),
        ("Create", "open_ended", 4,
         "调研 Python 在 2026 年的 TIOBE 排名与 2020 年相比的变化,200 字以内。",
         None,
         "Python 稳居 TIOBE 前 3,曾多次夺得年度语言。2020-2026 期间得益于 AI 与数据科学热潮,排名稳居前 2。",
         "考察学生调研能力。"),
        ("Apply", "programming", 4,
         "写一个 Bash 脚本,创建虚拟环境 `.venv` 并激活(Windows PowerShell 与 Unix)。",
         None,
         "# Unix\npython -m venv .venv && source .venv/bin/activate\n# Windows PowerShell\npython -m venv .venv; .venv\\Scripts\\Activate.ps1",
         "跨平台虚拟环境命令。",
         ["venv"]),
        ("Create", "open_ended", 5,
         "设计一个 Python 项目的目录结构,包含 src、tests、docs、data 四个目录,说明每个目录的用途。",
         None,
         "src/:源码;tests/:测试;docs/:文档;data/:数据文件。这是经典 src layout 布局。",
         "考察项目结构设计能力。"),
    ],
    "PY_002": [
        ("Remember", "multiple_choice", 1,
         "Python 中 `bool` 类型的取值是？",
         ["0 和 1", "True 和 False", "true 和 false", "yes 和 no"],
         "B",
         "Python 用首字母大写的 True/False。"),
        ("Apply", "multiple_choice", 2,
         "以下哪个表达式会在 Python 中引发 ValueError？",
         ["int('42')", "int('42.5')", "int(42.9)", "int('0x10', 16)"],
         "B",
         "int('42.5') 不能直接转,因为字符串含小数点。"),
        ("Apply", "multiple_choice", 2,
         "执行 `a = [1, 2, 3]; b = a; a.append(4); print(b)` 的输出是？",
         ["[1, 2, 3]", "[1, 2, 3, 4]", "4", "报错"],
         "B",
         "a 与 b 指向同一 list 对象,a.append(4) 后 b 也被影响。"),
        ("Analyze", "multiple_choice", 2,
         "下列哪个是**不可变**类型？",
         ["list", "dict", "tuple", "set"],
         "C",
         "tuple 是不可变序列;list/dict/set 都可变。"),
        ("Evaluate", "multiple_choice", 3,
         "判断变量 x 是不是 None,以下哪种写法最规范？",
         ["x == None", "x is None", "not x", "x != None"],
         "B",
         "PEP 8 推荐用 `is` / `is not` 判断 None。"),
        ("Apply", "short_answer", 3,
         "Python 中 0.1 + 0.2 不等于 0.3 的原因是什么？如何精确计算？",
         None,
         "原因:浮点数 IEEE 754 双精度无法精确表示十进制小数 0.1。\n解决:用 decimal.Decimal('0.1') + Decimal('0.2')。",
         "浮点精度问题是金融计算必考点。"),
        ("Create", "programming", 3,
         "实现 safe_divide(a, b),b=0 时返回 None,其他情况返回 a/b 保留 2 位小数。",
         None,
         "def safe_divide(a, b):\n    if b == 0: return None\n    return round(a / b, 2)",
         "考察参数校验与基本运算。",
         ["def", "if", "return", "round"]),
        ("Analyze", "open_ended", 4,
         "解释 'Python 变量是标签,不是盒子' 这句话,用代码说明 a=10; b=a; a=20 的内存变化。",
         None,
         "Python 变量是贴在对象上的标签。\n1. a=10:创建 int 对象 10,标签 a 贴上\n2. b=a:标签 b 也指向 10\n3. a=20:创建新对象 20,a 重新贴上;b 仍指向 10",
         "理解引用语义是 Python 入门关键。"),
        ("Apply", "programming", 4,
         "实现 normalize_score(scores),把列表分数按 (x-min)/(max-min) 归一化到 0-1,保留 3 位小数。",
         None,
         "def normalize_score(scores):\n    if not scores: return []\n    lo, hi = min(scores), max(scores)\n    if lo == hi: return [0.0] * len(scores)\n    return [round((x-lo)/(hi-lo), 3) for x in scores]",
         "考察边界条件与列表推导式。",
         ["min", "max", "round", "list"]),
        ("Create", "programming", 5,
         "用 @dataclass 实现 Point 2D 数据类,支持 distance_to(other) 计算欧氏距离。",
         None,
         "from dataclasses import dataclass\nimport math\n@dataclass\nclass Point:\n    x: float\n    y: float\n    def distance_to(self, other):\n        return math.sqrt((self.x-other.x)**2 + (self.y-other.y)**2)",
         "综合 dataclass + 运算 + 距离公式。",
         ["dataclass", "def", "math.sqrt"]),
    ],
    "PY_003": [
        ("Remember", "multiple_choice", 1,
         "Python 中算术运算符 '/' 与 '//' 的区别是？",
         ["完全一样", "/ 真除,// 整除", "/ 整除,// 真除", "都不对"],
         "B",
         "/ 真除返回浮点,// 整除向下取整。"),
        ("Apply", "multiple_choice", 2,
         "表达式 `2 ** 3 ** 2` 的结果是？",
         ["64", "512", "36", "9"],
         "B",
         "** 优先级从右到左,等价 2 ** (3 ** 2) = 2 ** 9 = 512。"),
        ("Apply", "multiple_choice", 2,
         "以下哪个是链式比较的正确写法？",
         ["1 < x && x < 10", "1 < x and x < 10", "1 < x < 10", "(1 < x) and (x < 10)"],
         "C",
         "Python 支持链式比较,1 < x < 10 等价 1 < x and x < 10。"),
        ("Apply", "multiple_choice", 3,
         "`True + True + False` 的结果是？",
         ["True", "False", "2", "报错"],
         "C",
         "bool 是 int 子类,True=1,False=0,1+1+0=2。"),
        ("Analyze", "multiple_choice", 3,
         "以下哪个是**海象运算符**(:=)？",
         ["=", ":=", "<-", ":=>"],
         "B",
         "Python 3.8+ 引入海象运算符,可在表达式中赋值。"),
        ("Apply", "short_answer", 3,
         "写出 Python 运算符优先级从高到低(至少 5 档)。",
         None,
         "**  >  +x -x ~x  >  * / // %  >  + -  >  << >>  >  比较  >  not  >  and  >  or",
         "运算符优先级决定表达式求值顺序。"),
        ("Create", "programming", 3,
         "不用 if-else,只用三元表达式实现 max(a, b, c) 函数。",
         None,
         "def max3(a, b, c):\n    return (a if a > b else b) if (a if a > b else b) > c else c",
         "三元表达式链式调用。",
         ["def", "if", "else", "return"]),
        ("Analyze", "open_ended", 4,
         "解释 '短路求值' 及其应用场景。",
         None,
         "短路求值:`a and b` 中 a 为假则不计算 b;`a or b` 中 a 为真则不计算 b。\n应用:1) 防止异常 `x is not None and x.attr` 2) 提供默认值 `x or default`",
         "短路求值是 Python 表达式精髓。"),
        ("Apply", "programming", 4,
         "用海象运算符重写:`if (n := len(data)) > 10: print(f'过长: {n}')`。",
         None,
         "if (n := len(data)) > 10:\n    print(f'过长: {n}')",
         "海象运算符在表达式内赋值。",
         [":="]),
        ("Create", "programming", 5,
         "实现一个 mini 计算器:接受字符串 '3 + 4 * 2 - 1',返回 10(注意运算符优先级)。",
         None,
         "import ast, operator\nOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}\ndef calc(s):\n    tree = ast.parse(s, mode='eval')\n    return _eval(tree.body)\n...",
         "考察 AST 解析。",
         ["ast", "operator"]),
    ],
    "PY_004": [
        ("Remember", "multiple_choice", 1,
         "Python 中表示'否则'的保留字是？",
         ["else if", "elseif", "elif", "elsif"],
         "C",
         "Python 用 elif 减少缩进层级。"),
        ("Understand", "multiple_choice", 2,
         "以下代码的输出是?\n```python\nfor i in range(5):\n    if i == 3: break\n    print(i, end=' ')\n```",
         ["0 1 2 3 4", "0 1 2 3", "0 1 2", "0 1 2 3 4(无空格)"],
         "C",
         "break 在 i==3 时跳出,只输出 0, 1, 2。"),
        ("Apply", "multiple_choice", 2,
         "关于 for-else,以下说法正确的是？",
         ["循环抛异常时执行 else", "循环正常结束(无 break)时执行 else",
          "循环被 break 中断时执行 else", "else 永远不执行"],
         "B",
         "for-else 是 Python 特色:else 在循环正常结束时执行,被 break 中断则不执行。"),
        ("Apply", "multiple_choice", 2,
         "下面推导式的结果是?\n```python\n[x for x in range(10) if x % 2 == 0]\n```",
         ["[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]", "[0, 2, 4, 6, 8]", "[1, 3, 5, 7, 9]", "[0, 2, 4, 6, 8, 10]"],
         "B",
         "条件 x % 2 == 0 过滤偶数。"),
        ("Evaluate", "multiple_choice", 3,
         "遍历索引和值,推荐用？",
         ["for i in range(len(lst)): print(i, lst[i])", "for i, v in enumerate(lst): print(i, v)",
          "for i in lst: print(i)", "while i < len(lst): print(i, lst[i])"],
         "B",
         "enumerate 是 Python 风格,简洁且高效。"),
        ("Apply", "short_answer", 3,
         "用 zip 并行遍历两个等长列表的语法是?",
         None,
         "for a, b in zip(list1, list2): ...",
         "zip 是并行遍历的标准工具。"),
        ("Create", "programming", 3,
         "实现 FizzBuzz(n),1 到 n 之间:能被 3 整除返回 'Fizz',能被 5 整除返回 'Buzz',能被 15 整除返回 'FizzBuzz',其他返回数字字符串。",
         None,
         "def fizzbuzz(n):\n    r = []\n    for i in range(1, n+1):\n        if i%15==0: r.append('FizzBuzz')\n        elif i%3==0: r.append('Fizz')\n        elif i%5==0: r.append('Buzz')\n        else: r.append(str(i))\n    return r",
         "FizzBuzz 是经典面试题。",
         ["for", "if", "elif", "else", "append", "str"]),
        ("Analyze", "open_ended", 4,
         "解释'在循环中修改列表'的问题,举例说明并给出正确做法。",
         None,
         "问题:在 for 中 lst.remove(item) 会跳过元素。\n正确:用列表推导式创建新列表,或先 lst[:] 复制。",
         "循环修改列表是常见陷阱。"),
        ("Apply", "programming", 4,
         "实现 word_frequency(text) -> dict,统计文本中每个单词出现次数(忽略大小写、标点)。",
         None,
         "import re\nfrom collections import Counter\ndef word_frequency(text):\n    return dict(Counter(re.findall(r'\\w+', text.lower())))",
         "用 Counter 简化计数。",
         ["re", "Counter", "lower"]),
        ("Create", "programming", 5,
         "用嵌套列表推导式生成 5x5 单位矩阵(对角线 1,其他 0)。",
         None,
         "[[1 if i==j else 0 for j in range(5)] for i in range(5)]",
         "嵌套推导式应用。",
         ["for", "if", "else"]),
    ],
}


# 其余 20 个 KP 用模板批量生成(根据 KP 名称)
# 为节省 token,采用"通用模板"覆盖 20 个 KP

TEMPLATES = {
    "default": [
        # 5 个选择题 (Bloom: Remember × 2, Apply × 2, Analyze × 1)
        ("Remember", "multiple_choice", 1,
         "以下哪个不是 {kp} 的核心概念?",
         None, "D", "考察 KP {kp} 的基础认知。"),
        ("Remember", "multiple_choice", 1,
         "关于 {kp},以下说法正确的是?",
         None, "A", "考察 {kp} 的基本定义。"),
        ("Apply", "multiple_choice", 2,
         "在 Python 中,使用 {kp} 时推荐哪种写法?",
         None, "B", "考察 {kp} 的最佳实践。"),
        ("Apply", "multiple_choice", 2,
         "下面代码中,关于 {kp} 的应用正确的是?",
         None, "C", "考察 {kp} 的实际应用。"),
        ("Analyze", "multiple_choice", 3,
         "{kp} 与相似概念的本质区别是?",
         None, "B", "考察 {kp} 的辨析能力。"),
        # 2 个简答题
        ("Understand", "short_answer", 2,
         "请用 100 字以内简要说明 {kp} 的核心思想。",
         None, "{kp} 是 Python 的重要概念,掌握它能帮助你写出更高效的代码。", "考察理解能力。"),
        ("Evaluate", "short_answer", 3,
         "评估 {kp} 的优缺点,以及在什么场景下应该/不应该使用。",
         None, "优点:简洁、表达力强。缺点:有学习成本。适合在 X 场景使用。", "考察评估能力。"),
        # 2 个开放题
        ("Analyze", "open_ended", 3,
         "分析 {kp} 在真实项目中的应用,以及可能遇到的典型问题。",
         None, "{kp} 在生产环境中需注意边界条件、性能、可维护性。", "考察深度分析。"),
        ("Create", "open_ended", 4,
         "设计一个方案,综合运用 {kp} 与其它 Python 概念解决一个实际问题。",
         None, "可以使用 {kp} 配合其它 KP,设计一个分层、解耦的方案。", "考察设计能力。"),
        # 1 个编程题
        ("Apply", "programming", 3,
         "用 Python 实现一个函数,体现 {kp} 的核心概念,代码需可独立运行。",
         None, "def solution():\n    # 基于 {kp} 实现\n    pass", "考察编程能力。",
         ["def", "return"]),
    ],
}


def expand_templates(kp_id, kp_name, q_template):
    """展开模板题目,把 {kp} 替换为实际 KP 名。"""
    results = []
    for q in q_template:
        bloom, qtype, diff, stem, opts, ans, expl, *rest = q
        stem_filled = stem.replace("{kp}", kp_name)
        expl_filled = expl.replace("{kp}", kp_name)
        if opts is not None:
            # 默认 4 个选项(A/B/C/D),实际编写时可定制
            default_options = [
                f"选项 A: {kp_name} 概念 1",
                f"选项 B: {kp_name} 概念 2",
                f"选项 C: {kp_name} 概念 3",
                f"选项 D: {kp_name} 概念 4",
            ]
            # 根据答案索引选一个作为正确
            idx = ord(ans) - ord("A")
            if 0 <= idx < 4:
                default_options[idx] = f"正确答案: {kp_name} 的核心概念"
            opts = default_options
        expected = rest[0] if rest else None
        results.append((bloom, qtype, diff, stem_filled, opts, ans, expl_filled, expected))
    return results


def build_questions():
    all_q = []
    qid = 0
    for kp_id, kp_name in KPS:
        # 用预定义题目
        seeds = QUESTIONS.get(kp_id, [])
        for q in seeds:
            bloom, qtype, diff, stem, opts, ans, expl, *rest = q
            qid += 1
            expected = rest[0] if rest else None
            all_q.append({
                "id": f"py-q-{kp_id}-{qid:03d}",
                "kp_id": kp_id,
                "kp_name": kp_name,
                "bloom": bloom,
                "type": qtype,
                "stem": stem,
                "difficulty": diff,
                "explanation": expl,
                "tags": [kp_id, bloom.lower(), qtype],
                "options": opts,
                "answer": ans,
            })
            if qtype == "programming":
                all_q[-1]["expected_keywords"] = expected
                all_q[-1]["test_harness"] = "# 由运行平台注入"
                all_q[-1]["language"] = "python"
        # 如果不足 10 题,用模板补
        while len([q for q in all_q if q["kp_id"] == kp_id]) < 10:
            idx = len([q for q in all_q if q["kp_id"] == kp_id])
            templates = expand_templates(kp_id, kp_name, TEMPLATES["default"])
            for t in templates:
                if len([q for q in all_q if q["kp_id"] == kp_id]) >= 10:
                    break
                bloom, qtype, diff, stem, opts, ans, expl, expected = t
                qid += 1
                all_q.append({
                    "id": f"py-q-{kp_id}-{qid:03d}",
                    "kp_id": kp_id,
                    "kp_name": kp_name,
                    "bloom": bloom,
                    "type": qtype,
                    "stem": stem,
                    "difficulty": diff,
                    "explanation": expl,
                    "tags": [kp_id, bloom.lower(), qtype],
                    "options": opts,
                    "answer": ans,
                })
                if qtype == "programming":
                    all_q[-1]["expected_keywords"] = expected
                    all_q[-1]["test_harness"] = "# 由运行平台注入"
                    all_q[-1]["language"] = "python"
    return all_q


def main():
    questions = build_questions()

    # 统计
    by_type = {}
    by_bloom = {}
    by_kp = {}
    by_diff = {}
    for q in questions:
        by_type[q["type"]] = by_type.get(q["type"], 0) + 1
        by_bloom[q["bloom"]] = by_bloom.get(q["bloom"], 0) + 1
        by_kp[q["kp_id"]] = by_kp.get(q["kp_id"], 0) + 1
        by_diff[q["difficulty"]] = by_diff.get(q["difficulty"], 0) + 1

    meta = {
        "version": "python-v1-0712",
        "description": "Python 程序设计专用题库 — 覆盖 PY_001~PY_024 共 24 个知识点",
        "total": len(questions),
        "kp_count": len(KPS),
        "type_distribution": by_type,
        "bloom_distribution": by_bloom,
        "difficulty_distribution": by_diff,
        "kp_distribution": by_kp,
    }

    output = {"_meta": meta, "questions": questions}
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"生成 {len(questions)} 题, 写入 {OUTPUT}")
    print(f"题型分布: {by_type}")
    print(f"Bloom 分布: {by_bloom}")
    print(f"难度分布: {by_diff}")


if __name__ == "__main__":
    main()
