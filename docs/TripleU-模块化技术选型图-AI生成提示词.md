# Triple U · 模块化技术选型图 · AI 生成提示词

## 一、图片生成提示词（复制整段投喂给 AI 生图模型）

```text
生成一张扁平化矢量学术技术架构信息图，参考主流"模块化技术实现方案"信息图风格：多个白色圆角矩形块正交排布，每块顶部有一条彩色横条（内含字母编号 A~H + 中文标题），块内一行横排放 3-6 个真实的技术官方 Logo，每个 Logo 正下方紧跟 4-8 字的中文技术名，副标题一行灰色小字。整体 16:9 横向，暖象牙白背景 #F7F1E8，无 3D、无渐变、无发光、无赛博朋克。

【顶部大标题】Triple U · 模块化技术实现方案

【A · WEB 前端】薄荷青 #4FB3A9 头条。横排 6 个 Logo：Vue.js 绿色三角、Vite 紫色闪电、TypeScript 蓝色 TS 方块、Apache ECharts 彩色柱状、Mermaid 蓝色人鱼图标、HTML5 橙色盾牌。中文名依次："Vue 3"、"Vite"、"TypeScript"、"ECharts"、"Mermaid"、"HTML5/CSS3"。副标题："响应式界面 · 可视化看板 · 交互持久化"。

【B · 多端载体】薄荷青头条。3 个 Logo：Electron 蓝色原子、手机浏览器图标、React 蓝色原子。中文名："Electron 桌面"、"Mobile Web"、"React 内嵌"。副标题："三端一云 · 同一后端 · 同一学习状态"。

【C · API 网关 / 服务编排】薄荷青头条。5 个 Logo：FastAPI 青色闪电、Uvicorn 紫色 U、Pydantic 红色 P、SSE 流式波纹、WebSocket 双向箭头。中文名："FastAPI"、"Uvicorn"、"Pydantic"、"SSE 流式"、"WebSocket"。副标题："REST + SSE + WebSocket 三通道"。

【D · 智能服务后端】深海军蓝 #17384C 头条。放在画面中央偏左，块内分四行：
第一行 3 个 Logo："Python 蓝黄蛇、asyncio 齿轮、Pytest 绿色勾"—中文名 Python、asyncio、Pytest；
第二行 4 个 Logo："SQLAlchemy 红色 S、Alembic 音符、NumPy 蓝色 N、Pandas 紫色熊猫"—中文名 SQLAlchemy、Alembic、NumPy、Pandas；
第三行 3 个 Logo："scikit-learn 橙色 O、PyTorch 红色火焰、NetworkX 网络"—中文名 scikit-learn、PyTorch、NetworkX；
第四行 3 个 Logo："python-pptx 幻灯片、Manim 数学动画、Mermaid CLI"—中文名 python-pptx、Manim、Mermaid CLI。
副标题："多智能体编排 · 认知诊断 · 多模态资源工厂"。

【E · 讯飞智能能力中枢】深橙色 #E85A0C 头条，位置放在画面正中央 D 块的右侧，全图最大最醒目的一块。块内 5 张卡片横排：
卡 1（比其他大）：讯飞星火 Logo，中文三行"讯飞星火 3.5 / generalv3.5 / WebSocket 流式"，小字任务："课程问答 · 学习路径 · 资源草稿 · 练习讲解 · 多智能体汇总"；
卡 2：讯飞图像 Logo，中文"讯飞图像 imagev3"，小字："资料 OCR · 公式识别"；
卡 3：讯飞语音 Logo，中文"讯飞 TTS 语音"，小字："课程讲解语音播报"；
卡 4：讯飞数字人 Logo，中文"讯飞数字人视频"，小字："教学讲解视频化"；
卡 5：Manim Logo，中文"Manim 动画"，小字："抽象概念动画化"。
卡 2 到卡 5 底部有一条粗橙色横线，横线上白字："图 · 文 · 声 · 影 四通道多模态呈现"。

【F · 检索与知识层】薄荷青头条，位置放在 E 块右侧。4 个 Logo：ChromaDB 紫色图标、Embedding 向量图标、HyDE+RRF 融合箭头、知识图谱节点。中文名："ChromaDB"、"Embedding 向量"、"HyDE + RRF 融合"、"知识图谱"。副标题："向量 + 图谱 + 假设答案三路融合"。

【G · 结果输出】浅边框块，位置在最右侧。4 个 Logo：Markdown 灰色 M、PDF 红色图标、SVG 蓝色图标、多媒体文件组合图标。中文名："Markdown"、"PDF"、"SVG"、"PPTX / MP3 / MP4"。副标题："学习报告 · 多模态产物 · 结构化结果"。

【H · 数据与运维基础】暖灰 #68747C 头条，横贯画面底部。6 个 Logo：SQLite 蓝色数据库、Docker 蓝色鲸鱼、Docker Compose 图标、Git 橙色分支、Nginx 绿色 N、Prometheus 火焰。中文名："SQLite"、"Docker"、"Docker Compose"、"Git"、"Nginx"、"Prometheus"。副标题："容器化部署 · 版本管理 · 可观测性"。

【左侧边缘小徽章】虚线边框小卡片：讯飞 iFlyCode Logo + 中文"讯飞 iFlyCode"，顶部一个红色小胶囊标签："仅开发期 · 不参与运行时"。用一条橙色虚线连到 C 块。徽章要明显小于中央讯飞能力中枢。

【箭头】主橙色 #E85A0C 实线：A→B→C→D 竖向；D ↔ E 用双向粗箭头（强调后端所有智能任务都调 E）；D→F、D→G、D→H 用实线。iFlyCode 徽章到 C 用虚线。

【右下角图例小字】"→ 主请求 / 数据流   ─ ─ ─ 开发期辅助（不入运行时）"。

【图题下方一行灰字脚注】"所有智能能力统一选用科大讯飞产品栈；讯飞 iFlyCode 仅开发期辅助编码，运行期由讯飞星火 3.5 提供智能推理，配合讯飞 imagev3、TTS、数字人视频与 Manim 共同构成图·文·声·影四通道多模态。"

严格要求：所有 Logo 使用各技术官方真实样式（颜色和形状正确），不要凭空捏造；中文字号足够大清晰无错字；只用白 / 暖米 / 薄荷青 / 深海军蓝 / 深橙 / 暖灰六种颜色；无发光、无渐变、无 3D、无科幻风。像技术期刊内页或高校研究组网站的架构说明图。
```

## 二、负面词

```text
赛博朋克, 蓝紫渐变, 发光, 3D 透视, 玻璃拟态, 深色背景, 悬浮球体, 轨道环, 全息, 科幻仪表盘, 营销海报, 网站首页, 密集小字, 中文错字, 中文糊字, 伪造品牌 Logo, OpenAI Logo, ChatGPT Logo, DeepSeek Logo, Kimi Logo, 通义 Logo, Google Logo, AWS Logo, 摄影, 真人, 卡通形象, 过饱和, 密集卡片墙
```

## 三、答辩讲解一句话

> Triple U 以科大讯飞为智能核心——**讯飞星火 3.5 承担全部生成推理**，配合讯飞图像 imagev3、TTS 语音、数字人视频与 Manim 共同构成"**图 · 文 · 声 · 影**"四通道多模态；开发期使用**讯飞 iFlyCode** 辅助编码；前端、后端、检索、数据、运维全部选用主流开源生态，形成"讯飞为脑 · 开源为骨"的完整技术选型。
