"""
为 A3 项目生成 5 个 Manim 动画脚本
每个实现一个核心概念的简短可视化
"""
import os

OUT = r"F:\比赛\中软杯\A3\data\artifacts\manim"
os.makedirs(OUT, exist_ok=True)

ANIMS = {}

# ============= 1. Self-Attention 计算流程 =============
ANIMS["01_self_attention_flow.py"] = '''
"""
主题: Self-Attention 计算流程
时长: 30-45 秒
展示: 输入词向量 -> Q/K/V 拆分 -> 注意力权重矩阵 -> 加权求和 -> 输出
运行: manim -pqh 01_self_attention_flow.py SelfAttentionFlow
"""
from manim import *

class SelfAttentionFlow(Scene):
    def construct(self):
        # 标题
        title = Text("Self-Attention 计算流程", font="Microsoft YaHei", color=BLUE_C).scale(0.7)
        title.to_edge(UP)
        self.play(Write(title))

        # 1. 输入词向量
        input_words = VGroup(
            Text("我", font="Microsoft YaHei"),
            Text("爱", font="Microsoft YaHei"),
            Text("学习", font="Microsoft YaHei"),
            Text("AI", font="Microsoft YaHei"),
        ).arrange(RIGHT, buff=0.6)
        input_label = Text("输入", font="Microsoft YaHei", color=GREY).scale(0.5)
        input_label.next_to(input_words, UP, buff=0.2)
        input_group = VGroup(input_words, input_label).move_to(UP * 1.5)
        self.play(FadeIn(input_group))
        self.wait(0.3)

        # 2. Q/K/V 三个分支
        qkv_box = VGroup(
            Rectangle(width=1.4, height=2, color=RED_C, fill_opacity=0.2),
            Rectangle(width=1.4, height=2, color=GREEN_C, fill_opacity=0.2),
            Rectangle(width=1.4, height=2, color=BLUE_C, fill_opacity=0.2),
        ).arrange(RIGHT, buff=0.2).move_to(ORIGIN)
        q_label = Text("Q\\n查询", font="Microsoft YaHei", color=RED_C).scale(0.5).move_to(qkv_box[0])
        k_label = Text("K\\n键", font="Microsoft YaHei", color=GREEN_C).scale(0.5).move_to(qkv_box[1])
        v_label = Text("V\\n值", font="Microsoft YaHei", color=BLUE_C).scale(0.5).move_to(qkv_box[2])
        qkv = VGroup(qkv_box, q_label, k_label, v_label)
        # 连线
        arrows_in = VGroup(*[
            Arrow(input_words[i].get_bottom(), qkv_box[i//4 % 3].get_top(), color=GREY, buff=0.1, stroke_width=2)
            for i in range(4)
        ])
        self.play(Create(qkv), Create(arrows_in))
        self.wait(0.3)

        # 3. 注意力权重矩阵
        matrix = Matrix(
            [[r"0.4", r"0.3", r"0.2", r"0.1"],
             [r"0.2", r"0.5", r"0.2", r"0.1"],
             [r"0.1", r"0.2", r"0.6", r"0.1"],
             [r"0.1", r"0.1", r"0.2", r"0.6"]],
            element_alignment_corner=ORIGIN
        ).scale(0.6)
        matrix.move_to(DOWN * 1.8 + RIGHT * 3)
        matrix_label = Text("注意力权重", font="Microsoft YaHei", color=YELLOW).scale(0.5)
        matrix_label.next_to(matrix, UP, buff=0.2)
        self.play(FadeIn(matrix), Write(matrix_label))
        self.wait(0.5)

        # 4. 加权求和 -> 输出
        out_text = Text("加权求和 → 输出", font="Microsoft YaHei", color=GREEN).scale(0.5)
        out_text.move_to(DOWN * 1.8 + LEFT * 3)
        self.play(Write(out_text))
        self.wait(0.5)

        # 5. 总结
        formula = Text("Attention(Q,K,V) = softmax(QKᵀ/√d_k)V", font="Consolas", color=WHITE).scale(0.5)
        formula.to_edge(DOWN)
        self.play(Write(formula))
        self.wait(2)
'''

# ============= 2. Transformer 编码器-解码器结构 =============
ANIMS["02_transformer_arch.py"] = '''
"""
主题: Transformer 编码器-解码器结构
时长: 30-45 秒
展示: 左侧 Encoder 堆叠 + 右侧 Decoder 堆叠 + 中间注意力
运行: manim -pqh 02_transformer_arch.py TransformerArch
"""
from manim import *

class TransformerArch(Scene):
    def construct(self):
        title = Text("Transformer 编码器-解码器结构", font="Microsoft YaHei", color=BLUE_C).scale(0.65)
        title.to_edge(UP)
        self.play(Write(title))

        # 左侧 Encoder
        encoder_layers = VGroup(*[
            VGroup(
                Rectangle(width=2.4, height=0.6, color=BLUE_C, fill_opacity=0.2),
                Text(f"Encoder Layer {i+1}", font="Microsoft YaHei", color=BLUE_A).scale(0.35)
            )
            for i in range(3)
        ]).arrange(DOWN, buff=0.15)
        enc_label = Text("Encoder", font="Microsoft YaHei", color=BLUE_C).scale(0.55)
        enc_label.next_to(encoder_layers, UP, buff=0.2)
        enc_group = VGroup(encoder_layers, enc_label).move_to(LEFT * 3.5)

        # 右侧 Decoder
        decoder_layers = VGroup(*[
            VGroup(
                Rectangle(width=2.4, height=0.6, color=GREEN_C, fill_opacity=0.2),
                Text(f"Decoder Layer {i+1}", font="Microsoft YaHei", color=GREEN_A).scale(0.35)
            )
            for i in range(3)
        ]).arrange(DOWN, buff=0.15)
        dec_label = Text("Decoder", font="Microsoft YaHei", color=GREEN_C).scale(0.55)
        dec_label.next_to(decoder_layers, UP, buff=0.2)
        dec_group = VGroup(decoder_layers, dec_label).move_to(RIGHT * 3.5)

        # 中间 Cross-Attention
        cross = DoubleArrow(encoder_layers.get_right(), decoder_layers.get_left(),
                            color=YELLOW, buff=0.2, stroke_width=4)
        cross_label = Text("Cross-Attention", font="Microsoft YaHei", color=YELLOW).scale(0.4)
        cross_label.next_to(cross, UP, buff=0.1)

        # 输入/输出
        in_box = Text("输入序列", font="Microsoft YaHei", color=WHITE).scale(0.45)
        in_box.next_to(enc_group, DOWN, buff=0.3)
        out_box = Text("输出序列", font="Microsoft YaHei", color=WHITE).scale(0.45)
        out_box.next_to(dec_group, DOWN, buff=0.3)

        self.play(FadeIn(enc_group), FadeIn(dec_group))
        self.play(Create(cross), Write(cross_label))
        self.play(Write(in_box), Write(out_box))
        self.wait(2)
'''

# ============= 3. RAG 检索+生成流程 =============
ANIMS["03_rag_pipeline.py"] = '''
"""
主题: RAG 检索增强生成流程
时长: 30-45 秒
展示: 用户提问 -> 向量化 -> 知识库召回 -> Prompt 增强 -> LLM -> 答案带溯源
运行: manim -pqh 03_rag_pipeline.py RagPipeline
"""
from manim import *

class RagPipeline(Scene):
    def construct(self):
        title = Text("RAG 检索增强生成流程", font="Microsoft YaHei", color=BLUE_C).scale(0.7)
        title.to_edge(UP)
        self.play(Write(title))

        # 6 个阶段
        stages = ["用户提问", "向量化", "知识库召回", "Prompt 增强", "LLM 生成", "答案+溯源"]
        colors = [WHITE, BLUE_C, GREEN_C, YELLOW_C, RED_C, PURPLE_C]
        boxes = VGroup()
        for i, (s, c) in enumerate(zip(stages, colors)):
            box = VGroup(
                RoundedRectangle(width=1.6, height=0.8, corner_radius=0.1, color=c, fill_opacity=0.2),
                Text(s, font="Microsoft YaHei", color=c).scale(0.35)
            )
            boxes.add(box)
        boxes.arrange(RIGHT, buff=0.2).move_to(ORIGIN)

        # 知识库
        kb = VGroup(
            Rectangle(width=1.8, height=2.0, color=GREEN_A, fill_opacity=0.1),
            Text("知识库", font="Microsoft YaHei", color=GREEN_A).scale(0.4)
        ).move_to(UP * 2.5 + RIGHT * 1)
        # 知识库到"召回"的箭头
        kb_arrow = Arrow(kb.get_bottom(), boxes[2].get_top(), color=GREEN_C, buff=0.1)

        # 数据流动
        for i in range(5):
            arr = Arrow(boxes[i].get_right(), boxes[i+1].get_left(),
                        color=GREY_B, buff=0.05, stroke_width=2)
            boxes[i+1].add_updater(lambda m, i=i: None)
            self.play(FadeIn(boxes[i]), Create(arr), run_time=0.3)
        self.play(FadeIn(boxes[5]), Create(kb_arrow), FadeIn(kb), run_time=0.3)
        self.wait(2)
'''

# ============= 4. 多智能体消息传递 =============
ANIMS["04_multi_agent_msg.py"] = '''
"""
主题: 多智能体消息传递 (Planner / Tutor / Evaluator)
时长: 30-45 秒
展示: Planner -> Tutor -> 内容 -> Evaluator -> 反馈 -> Planner
运行: manim -pqh 04_multi_agent_msg.py MultiAgentMsg
"""
from manim import *

class MultiAgentMsg(Scene):
    def construct(self):
        title = Text("多智能体协作: Planner / Tutor / Evaluator", font="Microsoft YaHei", color=BLUE_C).scale(0.6)
        title.to_edge(UP)
        self.play(Write(title))

        # 三个 Agent 节点
        def make_node(name, color, pos):
            circle = Circle(radius=0.7, color=color, fill_opacity=0.3)
            label = Text(name, font="Microsoft YaHei", color=color).scale(0.45)
            node = VGroup(circle, label).move_to(pos)
            return node

        planner = make_node("Planner", BLUE_C, UP * 1.5)
        tutor = make_node("Tutor", GREEN_C, DOWN * 0.5 + LEFT * 2.5)
        evaluator = make_node("Evaluator", RED_C, DOWN * 0.5 + RIGHT * 2.5)

        # 中心黑板
        blackboard = RoundedRectangle(width=2, height=0.6, corner_radius=0.1,
                                       color=YELLOW, fill_opacity=0.2)
        blackboard_label = Text("黑板 (Context)", font="Microsoft YaHei", color=YELLOW).scale(0.4)
        blackboard_group = VGroup(blackboard, blackboard_label).move_to(DOWN * 2.2)

        self.play(FadeIn(planner), FadeIn(tutor), FadeIn(evaluator), FadeIn(blackboard_group))

        # 消息 1: Planner -> Tutor
        msg1 = Text("任务: 讲注意力机制", font="Microsoft YaHei", color=WHITE).scale(0.3)
        msg1.next_to((planner.get_center() + tutor.get_center()) / 2, UP, buff=0.1)
        arrow1 = Arrow(planner.get_bottom(), tutor.get_top(), color=GREY_B, buff=0.1)
        self.play(Create(arrow1), Write(msg1), run_time=0.6)
        self.wait(0.3)

        # 消息 2: Tutor -> Blackboard
        msg2 = Text("讲解内容", font="Microsoft YaHei", color=GREEN_C).scale(0.3)
        arrow2 = Arrow(tutor.get_bottom(), blackboard.get_left(), color=GREEN_C, buff=0.1)
        self.play(Create(arrow2), Write(msg2), run_time=0.5)
        self.wait(0.3)

        # 消息 3: Blackboard -> Evaluator
        arrow3 = Arrow(blackboard.get_right(), evaluator.get_left(), color=YELLOW, buff=0.1)
        msg3 = Text("审阅", font="Microsoft YaHei", color=YELLOW).scale(0.3)
        self.play(Create(arrow3), Write(msg3), run_time=0.5)
        self.wait(0.3)

        # 消息 4: Evaluator -> Planner
        msg4 = Text("PASSED", font="Microsoft YaHei", color=GREEN_A).scale(0.4)
        arrow4 = Arrow(evaluator.get_top(), planner.get_right(), color=GREEN_A, buff=0.1)
        self.play(Create(arrow4), Write(msg4), run_time=0.5)
        self.wait(2)
'''

# ============= 5. BKT 掌握度贝叶斯更新 =============
ANIMS["05_bkt_bayesian.py"] = '''
"""
主题: BKT 掌握度贝叶斯更新
时长: 30-45 秒
展示: 答题序列 -> 贝叶斯更新 -> P(L) 曲线变化
运行: manim -pqh 05_bkt_bayesian.py BktBayesian
"""
from manim import *
import numpy as np

class BktBayesian(Scene):
    def construct(self):
        title = Text("BKT 掌握度贝叶斯更新", font="Microsoft YaHei", color=BLUE_C).scale(0.7)
        title.to_edge(UP)
        self.play(Write(title))

        # 坐标轴
        axes = Axes(
            x_range=[0, 6, 1], y_range=[0, 1, 0.25],
            x_length=8, y_length=4,
            tips=True, axis_config={"include_numbers": True}
        ).scale(0.7).move_to(ORIGIN)
        x_label = Text("答题次数", font="Microsoft YaHei").scale(0.4).next_to(axes.x_axis, DOWN)
        y_label = Text("P(L)\\n掌握度", font="Microsoft YaHei").scale(0.4).next_to(axes.y_axis, LEFT)

        self.play(Create(axes), Write(x_label), Write(y_label))

        # 模拟 P(L) 演化: 0.2 -> 0.4 -> 0.6 -> 0.5 -> 0.65 -> 0.78
        p_L = [0.2, 0.4, 0.6, 0.5, 0.65, 0.78]
        answers = ["对", "对", "对", "错", "对", "对"]
        # 曲线
        dots = VGroup()
        labels = VGroup()
        prev_point = axes.c2p(0, p_L[0])
        for i, (p, a) in enumerate(zip(p_L, answers)):
            x = i + 1
            point = axes.c2p(x, p)
            dot = Dot(point, color=GREEN if a == "对" else RED, radius=0.08)
            dots.add(dot)
            ans_label = Text(a, font="Microsoft YaHei",
                             color=GREEN if a == "对" else RED).scale(0.3)
            ans_label.next_to(point, UP, buff=0.1)
            labels.add(ans_label)
            if i > 0:
                prev = axes.c2p(i, p_L[i-1])
                line = Line(prev, point, color=BLUE, stroke_width=3)
                self.play(Create(line), run_time=0.3)
            self.play(FadeIn(dot), Write(ans_label), run_time=0.3)
        self.wait(2)
'''

# 写文件
for fname, content in ANIMS.items():
    p = os.path.join(OUT, fname)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    n_lines = content.count("\n")
    print(f"Wrote {fname:30s} lines={n_lines}")

print()
print(f"Total manim scripts: {len(ANIMS)}")
