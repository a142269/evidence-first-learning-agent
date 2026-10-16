"""
调用讯飞 TTS + 视频 API 为两门课生成教学视频并入库

用法:
    python scripts/generate_videos.py

生成流程:
    1. 读取课程知识点的语音脚本（docs/voice_scripts/ 或自动生成）
    2. 调用 AgentVideoService.synthesize() 生成视频
       - Level 1: 讯飞数字人 API（如可用）
       - Level 2: 动态幻灯片 + TTS 音画同步
       - Level 3: 静态头像 + TTS
    3. 将生成的视频文件路径写入 resources 表
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# 确保项目根目录在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.app.core.config import get_config
from backend.app.core.database import SessionLocal, init_db
from backend.app.core import models
from backend.app.services.multimodal.video_xunfei import get_video_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ================================================================
# 两门课的视频生成清单
# ================================================================
VIDEO_SCRIPTS = [
    # ---- 人工智能导论（已有 14 条种子记录，但无实际文件 → 重新生成） ----
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_self_attention",
        "title": "Self-Attention 计算流程动画演示",
        "agent_key": "tutor",
        "kp_ids": ["attention_mechanism", "transformer"],
        "text": (
            "今天我们来理解 Transformer 中最核心的机制——Self-Attention，也就是自注意力机制。"
            "想象你正在参加一场鸡尾酒会。当你在听一个人说话时，你会自动过滤掉其他人的声音，"
            "把注意力集中在当前交谈的人身上。在模型中，每个词都在与其他所有词进行交流，"
            "并计算它们之间的关联度。\n"
            "具体来说，每个词会被映射为三个向量：Query、Key 和 Value。"
            "Query 表示我要找什么，Key 表示我是谁，Value 表示我有什么信息。"
            "注意力权重的计算公式是：Attention 等于 softmax 乘以 Q 乘以 K 的转置，再除以根号 dk，最后乘以 V。"
            "除以根号 dk 是为了防止点积结果过大导致梯度消失。\n"
            "多头注意力机制则是将词向量投影到多个不同的子空间中，分别计算注意力，最后再将结果拼接。"
            "这使得模型能够从不同的表示子空间中捕捉到更加丰富的特征。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_transformer_arch",
        "title": "Transformer 整体架构动画演示",
        "agent_key": "tutor",
        "kp_ids": ["transformer", "attention_mechanism"],
        "text": (
            "Transformer 是一种完全基于注意力机制的序列到序列模型。"
            "它由编码器和解码器两部分组成。编码器负责阅读和理解输入序列，"
            "解码器负责生成输出序列。\n"
            "编码器由多个相同的层堆叠而成，每层包含一个多头注意力层和一个前馈神经网络。"
            "解码器除了包含编码器中的结构外，还多了一个掩码多头注意力层，"
            "用于防止模型在生成当前词时偷看后面的词。\n"
            "此外，Transformer 还使用了位置编码来让模型知道词与词之间的顺序关系，"
            "使用残差连接来防止梯度消失，使用层归一化来稳定训练。"
            "这些设计共同造就了 Transformer 在自然语言处理领域的统治地位。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_rag_flow",
        "title": "RAG 检索增强生成全流程动画",
        "agent_key": "content",
        "kp_ids": ["rag", "transformer"],
        "text": (
            "RAG 是检索增强生成的缩写，它是解决大语言模型幻觉问题的重要方案。"
            "RAG 的核心思想是：在生成回答之前，先从外部知识库中检索相关信息，"
            "然后将检索到的内容作为上下文提供给大模型，让模型基于事实生成回答。\n"
            "RAG 的流程分为三步。第一步是索引：将文档切分成小块，为每个块生成向量嵌入，存入向量数据库。"
            "第二步是检索：将用户问题转化为向量，在向量数据库中搜索最相似的文档块。"
            "第三步是生成：将检索到的文档块和用户问题一起交给大模型，生成最终回答。\n"
            "在 A3 智学领航系统中，RAG 被用于课程知识库的智能问答，确保 AI 助教的回答有据可依。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_cnn",
        "title": "卷积神经网络工作原理精讲",
        "agent_key": "tutor",
        "kp_ids": ["cnn", "neural_networks"],
        "text": (
            "卷积神经网络是处理图像数据的利器。它的核心组件是卷积层。"
            "卷积层使用一个小型的滤波器，也叫卷积核，在图像上滑动，"
            "每次滑动都计算滤波器与图像局部区域的点积，生成一个特征图。\n"
            "卷积操作有两个重要优势。第一是局部连接：每个神经元只关注图像的一个局部区域，"
            "这模拟了人类视觉系统的感受野机制。第二是权值共享：同一个滤波器在整个图像上共享参数，"
            "大大减少了模型参数量。\n"
            "除了卷积层，CNN 还包含池化层来降低特征图尺寸，以及全连接层进行最终分类。"
            "经典的 CNN 架构包括 AlexNet、VGG、ResNet 等，它们在 ImageNet 竞赛中取得了突破性成果。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_backprop",
        "title": "神经网络与反向传播可视化讲解",
        "agent_key": "tutor",
        "kp_ids": ["neural_networks", "backpropagation"],
        "text": (
            "反向传播是训练神经网络的核心算法。它的本质是利用链式法则，"
            "从输出层向输入层逐层计算损失函数对每个参数的梯度，然后用梯度下降法更新参数。\n"
            "具体流程是这样的。首先是前向传播：输入数据从输入层经过隐藏层到达输出层，"
            "每一层的输出是上一层输出乘以权重再经过激活函数。"
            "然后计算损失：比较输出层的预测值和真实标签之间的差异。\n"
            "接下来是反向传播：从输出层开始，计算损失对每个权重的偏导数，逐层向前传播。"
            "最后是参数更新：用计算出的梯度乘以学习率，更新每个权重。\n"
            "梯度消失是反向传播的主要挑战之一，当网络层数较深时，梯度在向后传播过程中会逐渐变小，"
            "导致靠近输入层的参数几乎不更新。ReLU 激活函数和残差连接是解决这个问题的有效方法。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_rl_qlearning",
        "title": "强化学习 Q-Learning 算法精讲",
        "agent_key": "tutor",
        "kp_ids": ["reinforcement_learning"],
        "text": (
            "强化学习是机器学习的三大范式之一。在强化学习中，智能体通过与环境交互来学习最优策略。"
            "每次交互，智能体观察环境状态，采取一个动作，环境返回一个奖励和新状态。\n"
            "Q-Learning 是最经典的强化学习算法之一。它维护一个 Q 表，"
            "Q 表记录了在每个状态下采取每个动作的预期累积奖励。"
            "Q 值的更新公式是：新 Q 值等于旧 Q 值加上学习率乘以"
            "（即时奖励加上折扣因子乘以下一状态的最大 Q 值，再减去旧 Q 值）。\n"
            "当状态空间和动作空间很大时，Q 表会变得不可行。"
            "深度 Q 网络用神经网络来近似 Q 函数，解决了这个问题，这就是著名的 DQN 算法。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_agent_tool",
        "title": "AI Agent 规划与工具调用视频",
        "agent_key": "planner",
        "kp_ids": ["ai_agent", "multi_agent_systems"],
        "text": (
            "AI Agent 是能够自主感知环境、做出决策并执行行动的智能体。"
            "一个完整的 Agent 系统包含三个核心组件：感知、决策和行动。\n"
            "感知模块负责理解用户意图和当前环境状态。"
            "决策模块通常基于大语言模型，负责规划和推理，决定下一步该做什么。"
            "行动模块通过调用外部工具来执行具体任务，比如搜索网页、查数据库、执行代码等。\n"
            "在 A3 系统中，我们实现了六个 Agent 协同工作：智狐负责学习路径规划，"
            "智灵负责知识讲解，阿匠负责资源生成，小龙负责出题练习，"
            "团团负责评估反馈，球球负责安全守护。这就是多智能体协作的力量。"
        ),
    },
    {
        "course": "artificial_intelligence",
        "rid": "vid_ai_ml_basics",
        "title": "机器学习基础概念精讲视频",
        "agent_key": "tutor",
        "kp_ids": ["ml_basics", "supervised_learning"],
        "text": (
            "机器学习是让计算机从数据中自动学习规律的技术。"
            "它分为三大范式：监督学习、无监督学习和强化学习。\n"
            "监督学习是最常见的类型。在监督学习中，训练数据同时包含特征和标签，"
            "模型学习从特征到标签的映射关系。典型的监督学习任务包括分类和回归。"
            "线性回归用于预测连续数值，逻辑回归用于二分类问题。\n"
            "过拟合是机器学习的头号敌人。当模型在训练集上表现极好但在测试集上表现很差时，"
            "就发生了过拟合。解决过拟合的方法包括：增加数据量、正则化、Dropout 和早停等。"
        ),
    },
    # ---- Python 程序设计 ----
    {
        "course": "python_programming",
        "rid": "vid_py_overview",
        "title": "Python 语言概述与开发环境搭建",
        "agent_key": "tutor",
        "kp_ids": ["PY_001"],
        "text": (
            "欢迎来到 Python 程序设计课程。Python 是一种解释型、面向对象的高级编程语言，"
            "由 Guido van Rossum 于 1989 年开始设计，1991 年正式发布。"
            "Python 的设计哲学强调代码的可读性和简洁性，它的语法几乎就像在读英语。\n"
            "Python 是跨平台的，可以在 Windows、macOS 和 Linux 上运行。"
            "搭建 Python 开发环境只需要两步：第一步，从 python.org 下载并安装 Python 解释器。"
            "第二步，选择一个代码编辑器，推荐使用 VS Code 或 PyCharm。\n"
            "安装完成后，打开终端输入 python，就能进入 REPL 交互式环境，"
            "输入 print 括号引号 Hello Python 引号括号，按下回车，你的第一行代码就运行了。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_control_flow",
        "title": "Python 控制流：条件判断与循环",
        "agent_key": "tutor",
        "kp_ids": ["PY_004"],
        "text": (
            "控制流是程序的骨架，它决定了代码的执行顺序。"
            "Python 的条件判断使用 if-elif-else 结构。"
            "比如根据分数判断等级：如果分数大于等于 90 分就是 A，"
            "否则如果大于等于 80 分就是 B，否则如果大于等于 60 分就是 C，"
            "都不满足就是 F。\n"
            "Python 有两种循环：for 循环和 while 循环。"
            "for 循环配合 range 函数可以遍历数字序列，"
            "while 循环在条件为真时反复执行代码块。\n"
            "列表推导式是 Python 的特色语法，它可以用一行代码生成列表。"
            "比如 squares 等于 x 的平方 for x in range 10，就生成了 0 到 81 的平方数列表。"
            "既简洁又高效，是 Pythonic 编程的典型代表。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_functions",
        "title": "Python 函数定义与参数传递",
        "agent_key": "tutor",
        "kp_ids": ["PY_005"],
        "text": (
            "函数是代码复用的基本单元。在 Python 中，使用 def 关键字定义函数。"
            "Python 的函数参数非常灵活，支持默认参数、关键字参数和可变参数。\n"
            "默认参数让你可以省略某些参数的值。比如 def greet 括号 name, greeting 等于 Hello 括号，"
            "调用时只传 name 就行，greeting 默认为 Hello。\n"
            "星号 args 收集多余的位置参数为一个元组，双星号 kwargs 收集多余的关键字参数为一个字典。"
            "这种设计让 Python 函数的接口非常灵活。\n"
            "Python 3.6 以上还支持类型注解，你可以在参数和返回值上标注类型，"
            "比如 def add 括号 a 冒号 int, b 冒号 int 箭头 int。"
            "类型注解不影响运行，但能大大提高代码的可读性。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_data_structures",
        "title": "Python 数据结构：列表、字典、元组与集合",
        "agent_key": "tutor",
        "kp_ids": ["PY_006", "PY_007", "PY_008"],
        "text": (
            "Python 内置了四种常用的数据结构：列表、字典、元组和集合。\n"
            "列表是有序可变的序列，支持增删改查。append 在末尾添加元素，"
            "insert 在指定位置插入，pop 弹出末尾元素，remove 按值删除。"
            "列表的索引访问是 O(1)，但 insert 和 remove 是 O(n)。\n"
            "字典是键值对的哈希映射，Python 3.7 以后保持插入顺序。"
            "字典的查找、插入和删除都是 O(1)。使用 get 方法可以安全访问不存在的键。\n"
            "元组是不可变序列，一旦创建就不能修改。集合是无序不重复元素的集合，"
            "支持并集、交集、差集等数学运算，非常适合去重操作。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_oop",
        "title": "Python 面向对象编程：类与对象",
        "agent_key": "tutor",
        "kp_ids": ["PY_011", "PY_012"],
        "text": (
            "面向对象编程是 Python 的核心编程范式。类是对象的蓝图，对象是类的实例。\n"
            "在 Python 中使用 class 关键字定义类。init 双下划线方法是构造函数，"
            "在创建对象时自动调用。self 参数代表当前实例本身，"
            "通过 self 可以访问实例属性和实例方法。\n"
            "继承让子类获得父类的所有属性和方法。Python 支持多继承，"
            "通过 super 函数可以调用父类的方法。"
            "当子类和父类有同名方法时，子类的方法会覆盖父类，这就是多态。\n"
            "property 装饰器可以把方法变成属性访问，实现对属性的受控读写。"
            "dataclass 装饰器可以自动生成 init 和 repr 等方法，大大减少样板代码。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_file_io",
        "title": "Python 文件读写与异常处理",
        "agent_key": "tutor",
        "kp_ids": ["PY_016", "PY_019"],
        "text": (
            "文件读写是 Python 最常用的操作之一。使用 open 函数打开文件，"
            "推荐使用 with 语句，它会自动在操作完成后关闭文件，即使发生异常也不会忘记关闭。\n"
            "文本文件用模式 r 读取，w 写入，a 追加。"
            "处理中文文件时，务必指定 encoding 等于 utf-8，避免乱码。\n"
            "异常处理用 try-except 结构。把可能出错的代码放在 try 块中，"
            "在 except 块中捕获并处理异常。"
            "建议捕获具体的异常类型，而不是用裸 except 捕获所有异常，"
            "这样既安全又不会掩盖真正的 bug。\n"
            "你还可以通过继承 Exception 类来创建自定义异常，"
            "为业务逻辑设计清晰的错误处理体系。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_generators",
        "title": "Python 迭代器与生成器精讲",
        "agent_key": "tutor",
        "kp_ids": ["PY_022"],
        "text": (
            "迭代器和生成器是 Python 中实现惰性计算的核心机制。\n"
            "迭代器协议要求对象实现 iter 和 next 两个方法。"
            "iter 返回迭代器自身，next 返回下一个值，没有更多值时抛出 StopIteration 异常。\n"
            "生成器是一种特殊的迭代器，使用 yield 关键字定义。"
            "当函数中包含 yield 时，它就不再是普通函数，而是一个生成器函数。"
            "每次调用 next 时，函数执行到 yield 处暂停，并返回 yield 后面的值。"
            "下次调用 next 时，从上次暂停的位置继续执行。\n"
            "生成器的最大优势是惰性计算：它不会一次性生成所有数据，而是按需生成。"
            "这在处理大数据流或无限序列时非常有用，既节省内存又提高效率。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_decorators",
        "title": "Python 装饰器与闭包",
        "agent_key": "tutor",
        "kp_ids": ["PY_023"],
        "text": (
            "装饰器是 Python 的高级特性，它可以在不修改原函数代码的前提下，给函数增加新功能。\n"
            "理解装饰器需要先理解闭包。闭包是引用了自由变量的函数。"
            "当一个内层函数引用了外层函数的变量时，即使外层函数已经返回，"
            "内层函数仍然可以访问这些变量，这就是闭包。\n"
            "装饰器本质上是一个接收函数作为参数并返回新函数的高阶函数。"
            "使用 @ 裱号语法糖可以优雅地将装饰器应用到目标函数上。\n"
            "Python 标准库中有很多实用的装饰器，比如 functools.wraps 用于保留原函数的元信息，"
            "functools.lru_cache 用于自动缓存函数结果，大幅提升递归函数的性能。"
            "带参数的装饰器和类装饰器进一步扩展了装饰器的应用场景。"
        ),
    },
    {
        "course": "python_programming",
        "rid": "vid_py_project",
        "title": "Python 综合项目：学生成绩管理系统",
        "agent_key": "planner",
        "kp_ids": ["PY_024"],
        "text": (
            "恭喜你来到了课程的最后一章——Python 综合项目实战。"
            "我们将用学到的所有知识，构建一个完整的学生成绩管理系统。\n"
            "这个项目包含以下模块：用类和继承设计学生和数据模型，"
            "用文件读写实现数据持久化，用异常处理保证程序健壮性，"
            "用装饰器实现日志记录和权限校验，用生成器实现大数据的惰性加载。\n"
            "项目结构遵循 Python 工程化最佳实践：使用虚拟环境隔离依赖，"
            "用 requirements.txt 管理依赖，用 pytest 编写测试，"
            "用 logging 模块记录日志，用 argparse 构建命令行界面。\n"
            "完成这个项目后，你就具备了独立开发 Python 应用的能力。"
            "记住，编程不是学出来的，是练出来的。多写代码，多犯错，多总结。"
        ),
    },
]


def generate_and_store(script: dict) -> bool:
    """生成单个视频并写入数据库"""
    rid = script["rid"]
    title = script["title"]
    text = script["text"]
    agent_key = script.get("agent_key", "tutor")

    logger.info(f"=== 生成视频: {title} (rid={rid}) ===")

    # 检查是否已有文件
    video_path = _PROJECT_ROOT / "data" / "artifacts" / "video" / f"{rid}.mp4"
    if video_path.exists():
        logger.info(f"视频文件已存在，跳过生成: {video_path}")
        _upsert_resource(script, str(video_path), "tts_slides")
        return True

    # 调用视频生成服务
    svc = get_video_service()
    result = svc.synthesize(text, resource_id=rid, agent_key=agent_key)

    if result.success:
        logger.info(f"✅ 视频生成成功: {result.filepath} ({result.video_size} bytes, method={result.method})")
        _upsert_resource(script, result.filepath, result.method)
        return True
    else:
        logger.error(f"❌ 视频生成失败: {result.error}")
        return False


def _upsert_resource(script: dict, filepath: str, method: str):
    """将视频记录写入 resources 表"""
    rid = script["rid"]
    with SessionLocal() as db:
        existing = db.get(models.ResourceRecord, rid)
        if existing:
            # 更新 filepath
            existing.metadata_data = {
                **(existing.metadata_data or {}),
                "filepath": filepath,
                "method": method,
            }
            logger.info(f"更新资源记录: {rid}")
        else:
            db.add(models.ResourceRecord(
                id=rid,
                user_id="",
                type="video",
                title=script["title"],
                content=script["text"][:500],
                content_type="markdown",
                agent_name="video_service",
                metadata_data={
                    "course": script["course"],
                    "scope": "course_published",
                    "status": "published",
                    "created_by": "teacher",
                    "created_by_name": "王老师",
                    "kp_ids": script["kp_ids"],
                    "method": method,
                    "filepath": filepath,
                },
                tags=["视频", "教学", script["course"]],
                created_at=time.time(),
            ))
            logger.info(f"新增资源记录: {rid}")
        db.commit()


def main():
    logger.info("=" * 60)
    logger.info("视频批量生成脚本 · 调用讯飞 API")
    logger.info("=" * 60)

    # 检查讯飞凭证
    config = get_config()
    logger.info(f"讯飞 TTS 可用: {config.xunfei.tts_available}")
    logger.info(f"讯飞数字人视频可用: {config.xunfei.vid_available}")

    # 确保数据库已初始化
    init_db()

    # 确保视频目录存在
    video_dir = _PROJECT_ROOT / "data" / "artifacts" / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    for i, script in enumerate(VIDEO_SCRIPTS, 1):
        logger.info(f"\n[{i}/{len(VIDEO_SCRIPTS)}] 处理中...")
        try:
            if generate_and_store(script):
                success_count += 1
            else:
                fail_count += 1
        except Exception as exc:
            logger.error(f"异常: {exc!r}")
            fail_count += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"完成！成功: {success_count}, 失败: {fail_count}, 总计: {len(VIDEO_SCRIPTS)}")
    logger.info(f"视频文件目录: {video_dir}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
