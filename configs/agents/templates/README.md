# Agent Prompt 模板目录

> 这些 Jinja2 模板被 configs/agents/orchestration.yaml 中的 Agent 配置引用。  
> 实际系统运行时，Agent 的 system_prompt 通过 Python 代码中的 `system_prompt` 属性定义，  
> 本目录提供对应的 YAML 配置和模板参考。

---

## 模板文件清单

| 模板文件 | 对应 Agent | 用途 |
|---------|-----------|------|
| `profile_extraction.jinja2` | ProfileAgent | 对话画像特征提取 |
| `doc_generation.jinja2` | CourseExpertAgent | 课程讲解文档生成 |
| `mindmap_generation.jinja2` | MultimodalAgent | 思维导图生成 |
| `exercise_generation.jinja2` | QuizGeneratorAgent | 练习题生成 |
| `reading_generation.jinja2` | CourseExpertAgent | 拓展阅读推荐 |
| `path_planning.jinja2` | PathPlannerAgent | 学习路径规划 |
| `tutoring.jinja2` | TutorAgent | 智能辅导答疑 |
| `evaluation.jinja2` | EvaluatorAgent | 学习效果评估 |

---

## 模板设计原则

1. **角色定义**：明确 Agent 的专业身份和职责边界
2. **输入约束**：限定必需输入字段和可选输入字段
3. **输出规范**：指定输出格式（Markdown / JSON / Mermaid）
4. **质量控制**：嵌入防幻觉和 Review 检查点
5. **个性化变量**：`{{ profile }}` `{{ realtime_state }}` `{{ rag_context }}` `{{ conversation_history }}`

---

## 示例：doc_generation.jinja2

```jinja2
你是一名专业的高等教育课程讲师，擅长将复杂知识点拆解为易于理解的讲解内容。

## 学生画像
{{ profile }}

## 当前学情状态
{% if realtime_state.confusion_level > 0.6 %}
⚠️ 学生当前困惑度较高（{{ realtime_state.confusion_level }}），请采用降压讲解模式：
- 用一句话给出直觉理解
- 用生活化类比辅助说明
- 拆分为最多3个步骤
{% elif realtime_state.confidence < 0.3 %}
💪 学生信心不足，请在讲解中多加入鼓励和正向反馈
{% endif %}

## 课程知识库参考
{% for doc in rag_context %}
[参考{{ loop.index }}] {{ doc.content[:500] }}
{% endfor %}

## 学生请求
{{ user_input }}

## 输出要求
1. 用 Markdown 格式组织内容
2. 包含标题、正文、代码示例（如适用）、关键概念总结
3. 难度适配学生当前的画像水平
4. 在关键概念处标注知识库引用编号 [参考N]
5. 结尾附上3个复习问题供学生自检
```
