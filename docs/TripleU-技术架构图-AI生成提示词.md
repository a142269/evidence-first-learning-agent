# Triple U · 技术架构图 · AI 生成提示词

> 用途：一次性生成用于答辩 PPT / 论文 / 技术手册的**系统技术架构图主图**。<br>
> 特色：聚焦前沿 AI 技术层，所有智能能力与开发工具口径**全部对齐讯飞**（讯飞星火大模型、讯飞 iFlyCode、讯飞 TTS、讯飞图像理解 imagev3、讯飞数字人视频）。<br>
> 风格定位：学术信息图 + 编辑设计 + 克制的 2.5D 分层，**不追求视觉花哨，追求专业性与可读性**。<br>
> 使用方式：先粘贴 §一 视觉控制词 → 再粘贴 §二 主提示词 → 加 §四 负面提示词 → 生成后按 §五 中文标签清单在 PPT 中后期添加中文文字。

---

## 一、统一视觉控制词（每次生成都先粘这段）

```text
This is a professional academic system architecture diagram for a graduate-level software engineering technical report, not a marketing poster, not a website landing page, not a sci-fi HUD. Design register: editorial infographic, restrained 2.5D vector illustration, clean typographic hierarchy, strong visual center with generous white space.

Color palette (strictly enforced): warm ivory background #F7F1E8, primary orange #E85A0C for critical paths and highlights, secondary amber #F4A20B for supporting components, deep navy #17384C for foundation and trust layers, cool warm gray #68747C for connectors and secondary labels, pure white #FFFFFF for content cards. Orange conveys motion and key data flow; navy conveys stability and infrastructure. Only these five colors, no additional hues.

Composition rules: 16:9 aspect ratio, 3840×2160, at least 8% safe margin on all sides, layered horizontal band structure (top: users; upper middle: API and orchestration; middle: capability layers; lower middle: data foundation; right side: external AI services callout). Layer bands should be visually distinguishable by subtle drop-shadow separation, not by heavy color blocking.

Visual language: thin geometric line icons with 1.5-2px stroke, small rounded rectangle component cards with 8px radius, arrows using thin lines with directional heads, dashed lines for downgrade/fallback paths, solid lines for primary data flow. Component labels appear as small monospace-style badges. Optional very subtle warm paper texture at 3% opacity in background, absolutely no glow effects.

Strict prohibitions: no neon cyberpunk aesthetic, no blue-purple gradients, no science-fiction dashboard, no robot avatars, no glass-morphism, no plastic 3D, no floating spheres, no orbital rings, no random binary numbers, no fake data charts, no watermarks, no company logos, no oversaturated colors, no dark background, no cropped content, no dense micro-text.
```

## 二、架构图主提示词（无字底图版，推荐先用这版）

> 只生成结构与形状，不生成任何中文文字（图像模型对中文文字渲染极不稳定）。生成后到 PPT 中按 §五 清单添加真实中文标签，成品更专业。

```text
Generate an academic system architecture diagram of an educational multi-agent AI platform, with clear horizontal layered structure from top to bottom, plus a separated AI services stack docked on the right side.

Top band — Client Access Layer: four small rounded rectangle cards representing four client endpoints arranged left to right — a laptop browser icon, a mobile phone icon, a desktop application icon, and an embedded sub-application icon. Above the cards a slim horizontal bar labeled area for "clients". Thin arrows from all four cards converge downward into the next band.

Second band — Interface Gateway Layer: a wide rounded rectangle spanning most of the canvas width, subdivided into three inner cells representing three protocol channels: standard REST endpoint, streaming server-sent-events channel, and websocket channel for realtime messaging.

Third band — Orchestration Layer (the visual centerpiece): a prominent horizontal container with a subtle orange left border. Inside, arrange three interconnected component groups from left to right — an "intent router" hexagonal node, a "seven-stage conversation pipeline" horizontal chain of seven small connected boxes, and a "six-agent team" arrangement of six small circular avatars in two rows. Thin arrows show the router feeds the pipeline, and the pipeline dispatches to the six agents. This band should visually dominate the middle of the canvas.

Fourth band — Capability Layer: four side-by-side rounded rectangle super-cards of equal size, each containing 3-5 smaller component chips inside:
- Card 1: Knowledge & Retrieval — chips for vector RAG, graph-augmented retrieval, hypothetical-document retrieval, reciprocal-rank fusion, knowledge graph.
- Card 2: Cognitive Computing — chips for learner profile, bayesian knowledge tracing, cognitive diagnosis, self-attentive knowledge tracing, Bloom taxonomy, forgetting curve.
- Card 3: Multimodal Generation — chips for slide deck, mind map, code sandbox, text-to-speech, animation video, image OCR.
- Card 4: Trustworthy & Safety — chips for content filter, chain-of-verification, evidence ledger, agent debate, pedagogical safety, knowledge ingestion guard.

Fifth band — Data & Infrastructure Layer: horizontal strip with five icon-labeled slots: a relational database cylinder, a vector database cylinder, a course knowledge library folder, an artifact repository stack, and an ops badge cluster (health check, metrics, prompt cache).

Right-side vertical stack — External AI Services (visually separated from the main flow by a thin vertical divider and labeled as external): four stacked rounded cards from top to bottom, each with a subtle iFlytek-inspired accent (do not draw the actual iFlytek logo):
- Top card: iFlytek Spark large language model, the sole primary generative model.
- Second card: iFlytek text-to-speech synthesis service.
- Third card: iFlytek image understanding service.
- Bottom card: iFlytek digital-human video service.
All four cards connect to the Capability Layer via a single unified adapter arrow labeled "server-side unified adapter, API keys never leave backend".

Left margin annotation strip: a small vertical badge labeled "development-only" containing a single card representing iFlytek iFlyCode AI coding assistant, connected with a dashed line to the API layer indicating it participates only during development, not runtime. Keep this element small and unobtrusive.

Flow annotations: solid orange arrows for primary request/response paths (client → interface → orchestration → capability → external AI); dashed navy arrows for fallback/downgrade paths inside the capability layer (e.g., video service falling back to slides and TTS); a small closed-loop arrow at the capability layer showing self-verification cycle (generation → CoV verification → evidence binding → safety filter → back to output). Data persistence arrows go downward from capability into the data layer.

Reserve small white text label zones next to every component card — these zones will be filled with Chinese labels in post-production. Do not attempt to render any Chinese characters or English words as final text; the labels should appear as placeholder rectangles or as light gray placeholder text.

The final composition should look publishable in a peer-reviewed engineering journal or a national-level university software design competition final defense slide deck.
```

## 三、中文原生提示词（次选，若你希望模型直接尝试渲染中文）

> ⚠️ 图像模型对中文字符渲染仍不完美（可能出现错字或糊字），仅在你不打算做 PPT 后期时使用。生成后一定要用大图检查每个字，有错字重生成或改回 §二 无字版。

```text
生成一张学术风格的系统技术架构图，用于研究生级软件工程技术报告与国家级大学生软件设计大赛答辩幻灯片，非营销海报，非网页设计，非科幻仪表盘。

整体版式：16:9 横向，3840×2160，四周留白至少 8%。采用分层横条式结构，自上而下依次为：客户端接入层、接口网关层、编排层、能力层、数据与基础设施层。右侧另设一列外部 AI 服务栈，与主流水线以一条竖向虚线分隔。

配色（严格控制）：暖象牙白背景 #F7F1E8，主橙 #E85A0C 用于关键数据流和视觉重心，金橙 #F4A20B 用于次级组件，深海军蓝 #17384C 用于基础设施和可信层，暖灰 #68747C 用于连接线和辅助标签，纯白 #FFFFFF 用于内容卡片。全图仅使用这五种颜色。

视觉语言：细线几何图标，圆角矩形组件卡（8px 圆角），细箭头带方向标；主流路径用橙色实线，降级路径用海军蓝虚线，闭环校验用小型环形箭头。层与层之间用极淡投影分隔，不用重色块。整体带 3% 极淡暖色纸纹作背景。

第一层"客户端接入层"：从左至右四个客户端卡片——浏览器、手机、桌面应用、内嵌子应用，箭头汇聚向下。

第二层"接口网关层"：一条横贯的宽卡，内分三格——REST 接口、SSE 流式通道、WebSocket 实时通道。

第三层"编排层"（视觉中心）：橙色左边框强调。内含三组紧密连接的组件——左侧一个六边形"意图路由器"，中部一条由七个小方块串联而成的"七阶段对话流水线"，右侧六个小圆头像排成两排代表"六智能体"。箭头从路由器指向流水线，再由流水线分发至六智能体。

第四层"能力层"：四张并排等大的圆角超级卡片，每张内含 3-5 个组件小芯片：
- 卡 1 知识与检索：向量 RAG、GraphRAG 图谱扩展、HyDE 假设答案、RRF 融合、知识图谱
- 卡 2 认知计算：学习画像、BKT 贝叶斯知识追踪、DINA 认知诊断、SAKT 自注意力追踪、Bloom 分类、遗忘曲线
- 卡 3 多模态生成：演示文稿、思维导图、代码沙箱、语音合成、动画视频、图像 OCR
- 卡 4 可信与安全：内容过滤、CoV 链式核验、证据账本、多智能体辩论、教学安全、知识入库审核

第五层"数据与基础设施"：横条中依次排列——关系数据库柱、向量数据库柱、课程知识库文件夹、Artifact 产物栈、运维徽章组（健康检查、指标、Prompt 缓存）。

右侧竖列"外部 AI 服务栈"（讯飞智能能力）：与主流水线用一条竖向虚线分隔，四张自上而下堆叠的卡片——顶：讯飞星火大模型（唯一主模型通道）；次：讯飞语音合成 TTS；再次：讯飞图像理解 imagev3；底：讯飞数字人视频。四张卡片通过一条统一箭头汇入能力层，箭头标注"服务端统一适配器 · 密钥不出后端"。

左侧边栏小徽章"仅开发期使用"：一张代表讯飞 iFlyCode AI 编码助手的小卡片，用一条虚线与接口层相连，标注"仅参与开发，不参与运行时推理"。整体小而克制。

箭头规则：主请求响应路径用橙色实线；能力层内的降级路径用海军蓝虚线（如视频服务降级到幻灯片加语音）；能力层带一个小型闭环箭头，表示"生成 → CoV 核验 → 证据绑定 → 安全过滤 → 回到输出"的自校验循环；数据持久化箭头从能力层向下指向数据层。

明确禁止：霓虹赛博朋克、蓝紫渐变、科幻仪表盘、机器人头像、玻璃拟态、塑料 3D、悬浮球体、轨道环、随机二进制数字、伪造数据图、水印、任何公司真实 Logo、过饱和色、深色背景、被裁切内容、密集小字。

成品应达到工程期刊或国家级软件设计竞赛决赛答辩可直接使用的水准。
```

## 四、负面提示词（黏在英文模型 negative prompt 字段）

```text
neon, cyberpunk, blue purple gradient, sci-fi HUD, futuristic dashboard, robot face, glassmorphism, plastic 3D, floating spheres, orbital rings, hologram, glowing lines, dark background, oversaturated, gradient background, marketing poster, website UI, dense card grid, random binary code, fake statistics, gibberish chinese text, misspelled words, random english text, watermark, real company logo, iflytek logo, spark logo, dalle watermark, midjourney watermark, cropped content, low contrast, cluttered composition, harsh glow, chromatic aberration, lens flare, motion blur, tilt shift, isometric excess
```

## 五、后期在 PPT 中添加的中文标签清单（对应 §二 底图的每个位置）

> 用 PPT 的文本框直接在生成的底图上叠加，字体推荐**思源宋体 / 思源黑体 Medium**，字号 14-18pt，正文颜色 `#17384C`，关键强调 `#E85A0C`。

### 顶部图题（居中大字）

```
Triple U 个性化学习多智能体系统 · 技术架构图
Personalized Learning Multi-Agent System · Technical Architecture
```

### 第一层 · 客户端接入层（4 张卡片，自左至右）

- 学生 / 教师浏览器（Vue 3 SPA）
- 移动 Web 端（Mobile Web）
- Electron 桌面端
- React 内嵌子应用（桃园学宫 / 驾驶舱）

### 第二层 · 接口网关层（三格标签）

- REST 接口 · /api/v1/*
- SSE 流式通道 · 断线重连 + 心跳
- WebSocket · 移动端实时消息

### 第三层 · 编排层（三组标签）

- **意图路由器**（Orchestrator）· 显式 @ → 关键词规则 → LLM 兜底
- **七阶段对话流水线**：校验 → 检索 → 学情 → 编排 → 辩论反思 → 聚合 → 持久化
- **六智能体**：智狐 · 智灵 · 阿匠 · 小龙 · 团团 · 球球

### 第四层 · 能力层（四张超级卡片）

**知识与检索**
- Vector RAG · GraphRAG 2-hop · HyDE · RRF k=60 · 知识图谱

**认知计算**
- 8 维学习画像 · BKT · DINA · SAKT · Bloom 分类 · Kalman 平滑

**多模态生成**
- PPTX · Mermaid · 代码沙箱 · TTS · Manim 动画 · OCR

**可信与安全（Triple U 特色）**
- 内容过滤 · CoV 链式核验 · Claim Ledger 证据账本 · 多智能体辩论 · 教学安全 · 知识入库审核

### 第五层 · 数据与基础设施层

- SQLite 业务库 · ChromaDB 向量库 · 课程知识库 · Artifact 产物库 · Prompt 缓存 · 健康检查 · 指标监控

### 右侧 · 讯飞智能能力栈（外部 AI 服务）

- **讯飞星火大模型 v4.0**（唯一主模型通道 · WebSocket）
- **讯飞语音合成 TTS**（8 音色 · WebSocket 流式）
- **讯飞图像理解 imagev3**（教材图像 OCR · 公式识别）
- **讯飞数字人视频**（教学视频生成 · 三级降级）
- **统一适配器**：密钥仅在后端，不出网关

### 左侧边栏 · 开发期工具（小徽章）

- **讯飞 iFlyCode**（AI 编码助手 · 仅开发期 · 不参与运行时推理）

### 图例（放在图右下角小字）

```
─── 主请求响应流   ─ ─ ─ 降级/回退路径   ↺ 自校验闭环
■ 客户端   ■ 接口   ■ 编排   ■ 能力   ■ 数据基础   ■ 外部 AI
```

### 图题下方脚注（一行小字，`#68747C` 灰）

```
说明：所有外部 AI 服务均通过服务端统一适配器调用，密钥与凭据仅存于后端；讯飞 iFlyCode 仅在开发阶段辅助编码，不参与运行时智能推理。
```

---

## 六、生成参数建议（不同模型的适配写法）

| 模型 | 推荐参数 | 备注 |
|-----|---------|------|
| Midjourney V6 | `--ar 16:9 --style raw --v 6 --stylize 150` | `--stylize` 值调低避免过度艺术化 |
| Stable Diffusion XL | steps 40, CFG 6-7, sampler DPM++ 2M Karras | 加载 flat vector / editorial infographic LoRA 更稳 |
| DALL·E 3 | 直接对话式提交英文 §二 版 | 自然语言遵循度最好，中文标签仍建议后期加 |
| 讯飞星火图像 | 用中文 §三 版 + "学术信息图，非科技海报" 前缀 | 与项目讯飞主线一致，答辩讲故事时可强调"图也是讯飞生成的" |

## 七、生成后的后期加工建议

1. **先出无字底图**（§二），再进 PPT 加中文文字（§五），比让模型直接渲染中文稳 3-5 倍
2. 每个组件卡片下方留 30-50px 高的白色文字带，便于叠加中文而不遮盖图标
3. 全图统一用 **思源宋体 / 思源黑体 Medium** 混排：标题黑体、正文宋体
4. 关键路径（星火调用箭头、CoV 自校验闭环）在 PPT 里再手动加粗一次，突出讲解重点
5. 如果一次生成不理想，把 §二 保留、把 §四 负面词加强"no cyberpunk, no glow, no gradient"三个词分别单独重复一遍，比整体重生成成功率高

---

## 八、答辩场合的一句话讲解模板（配这张图使用）

> 我们的架构从上到下五层：客户端接入、接口网关、多智能体编排、四大能力域、数据基础设施；右侧独立列出讯飞智能能力栈——**星火大模型是我们唯一的主推理通道，讯飞 TTS、图像理解和数字人视频构成完整多模态**。所有智能能力都由服务端统一适配器调用，密钥不出后端；开发期我们使用讯飞自家的 iFlyCode 辅助编码，运行期不涉及。中间**编排层的七阶段流水线**是我们的核心创新——每一次学习请求都经过校验、检索、学情、编排、辩论反思、聚合、持久化七步；能力层的**可信与安全域**（CoV 链式核验 + Claim Ledger + 教学安全）是我们区别于通用 AI 学习工具的关键。
