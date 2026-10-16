---
chapter_id: '11'
slug: mcp_protocol
title: MCP 模型上下文协议
kp_ids:
- AI_014
bloom_focus:
- Understand
- Apply
prerequisites:
- '10'
estimated_minutes: 40
---

# 11: MCP 模型上下文协议 · 统一 AI 的工具生态

> **Bloom 层级**: Understand → Apply
> **建议学时**: 40 分钟
> **前置知识**: 10-AI 智能体与工具调用

## 学习目标
1. 理解为何在 Agent 框架百花齐放的当下，迫切需要推出 MCP（Model Context Protocol）标准协议。
2. 剖析 MCP 的“Host - Client - Server”三方架构的通信与权限边界。
3. 掌握 MCP 的三大核心原语：Resources（资源）、Tools（工具）和 Prompts（提示模板）的适用场景。
4. 对比 MCP 与传统 REST API，解释 MCP 在双向通信与动态发现机制上的优势。
5. 结合 A3 教育智能体系统，设计并编写一个自定义 MCP Server 的核心伪代码。

## 11.1 协议背景与痛点
在 2024 年之前，AI Agent 的生态可以说是“军阀混战”。
OpenAI 有一套 Functions 定义，Anthropic 有一套 Tool Use 标准，而开发框架（如 LangChain、LlamaIndex、AutoGen）又各自搞了一套完全不兼容的“工具注册表”。
如果你写了一个能帮 Agent 查询 GitHub 仓库代码的工具，为了让所有平台的 AI 都能用，你必须给各个框架分别适配重写一遍。

2024 年 11 月，Anthropic 终于牵头发布了开源的 **MCP (Model Context Protocol)** 协议，定义了 AI 应用与外部数据、工具、系统进行通信的标准接口。
**比喻**：MCP 对于大模型生态的意义，就像是 **USB-C 接口统一了手机充电线**，或者 **LSP (Language Server Protocol) 统一了代码编辑器的智能补全**。它的终极目标是：**写一次 Server，任何 AI 客户端都能随插随用。**

## 11.2 MCP 的三方架构
MCP 建立在一个非常清晰且解耦的架构之上，基于 **JSON-RPC 2.0** 协议进行通信。

```
┌────────────┐        JSON-RPC 2.0       ┌────────────┐
│  MCP Host  │ ──────────────────────────→│ MCP Server │
│ (AI 应用)  │ ←──────────────────────────│  (能力提供方) │
└────────────┘    Resources/Tools/Prompts └────────────┘
       ▲                                          │
       │  内部                                     ▼
       └─ MCP Client（每个 server 一个连接）   暴露 SDK/数据库/API
```

- **Host (宿主)**：这是直接面对终端用户的 AI 应用程序（比如 Cursor 甚至我们项目的 A3 Agent Runtime）。它决定了当前对话中，用户能够调用哪些 Server。
- **Client (客户端)**：它是 Host 内部的一个代理组件。Host 如果想挂载 3 个不同的能力，就会在内部启动 3 个独立的 Client 去分别连接它们。
- **Server (服务端)**：这是真正干活的组件，它独立于 LLM 存在。比如 `postgres-server`（负责执行 SQL 查库）、`github-server`（负责拉取 PR 代码）。

## 11.3 三大核心原语 (Primitives)
MCP Server 对外暴露能力的方式，被严格限定为三种核心原语：

### 1. Resources (资源)
把它想象成挂载给 AI 的“只读虚拟文件系统”。它适合提供静态的上下文。
比如，A3 系统的讲义就可以作为一个 Resource 暴露给 AI 助教：
```json
{
  "uri": "knowledge://chapters/05_transformer_and_llm.md",
  "mimeType": "text/markdown",
  "name": "Transformer 与大语言模型"
}
```

### 2. Tools (工具)
这是 AI 改变世界的手和脚。它就是带有严格输入模式（JSON Schema）的可执行函数，通常用于引起外部状态改变或进行复杂计算。
```json
{
  "name": "query_knowledge_graph",
  "description": "在图谱中查询某知识点的前置和后继节点",
  "inputSchema": {
    "type": "object",
    "properties": {
      "kp_id": {"type": "string"},
      "depth": {"type": "integer"}
    },
    "required": ["kp_id"]
  }
}
```

### 3. Prompts (提示模板)
供用户在前端界面（如斜杠命令 `/summarize`）快捷调用的指令模板，它也可以在后端由 Server 动态注入系统参数（如当前的时间、版本号）。

## 11.4 MCP 为什么不是 REST API？
你可能会问，我们已经有了成熟的 HTTP REST API 甚至 OpenAPI (Swagger)，为什么还要发明 MCP？

| 维度 | MCP 协议 | REST API |
|------|---------|----------|
| **通信链路** | JSON-RPC 2.0。原生支持 `stdio` (本地子进程通信，0 延迟极安全) 和 HTTP+SSE。 | HTTP/1.1。必须走网络协议栈，且是无状态的单向请求。 |
| **发现机制** | **动态握手发现**：Client 连上 Server 后，发一个 `tools/list`，Server 自动把所有可用的工具全盘托出。 | 强依赖外部的 OpenAPI 静态 JSON 文件，文档和代码极易脱节。 |
| **主动推送** | **双向通信**：Server 可以主动通知 Client“喂，我这里的数据更新了，你重新查一下”。 | Client 必须自己写死循环去轮询 (Polling) Server 状态。 |
| **核心定位** | 专为大语言模型 (LLM) 的 Function Calling 特性量身定制，附带系统提示词规范。 | 给人或者传统前后端微服务通信用的，LLM 直接理解成本极高。 |

## 11.5 教育智能体场景案例 (A3 系统)
在构建 A3 的过程中，我们有大量的教育专用工具（如生成随堂测试、生成思维导图）。如果我们把这些代码强耦合写死在 Agent 调度代码里，未来换一个 Agent 框架就全废了。
**最佳实践**：把这些能力封装成一个独立的 **A3 MCP Server**。
这不仅让 A3 自己的 Agent 可以调用，如果学生在本地使用带 MCP 插件的 IDE（如 Cursor），他们甚至能让 Cursor 直接连上我们的 A3 服务器，在写代码遇到 bug 时，直接调用我们的 `bloom_quiz` 工具给自己出一道题！

```python
# 伪代码：在 A3 系统中极速搭建一个 MCP Server
import mcp_sdk as mcp
from a3_core import PPTXBuilder, parse_outline

# 只需要加一个装饰器，这个函数就瞬间变成了全网 AI 通用的 MCP Tool
@mcp.tool(name="generate_pptx", description="根据传入的大纲，为学生自动生成并下载复习 PPT")
async def generate_pptx(outline_json: str, session_id: str) -> dict:
    # 业务逻辑代码
    deck_spec = outline_to_deck_spec(parse_outline(outline_json))
    return PPTXBuilder().build(deck_spec, session_id)

# 启动 Server 监听 (基于 stdio 标准流通信)
mcp.run_stdio_server()
```

## 11.6 常见误区
- **误区 1：MCP 是一种新的大语言模型训练技术。**
  - **为什么错**：MCP 完全不涉及任何模型训练或神经网络。它纯粹就是一层**网络通信和接口约束的工程协议**，它规定了 JSON 的长相，而不是神经元的结构。
- **误区 2：在生产环境中，把 MCP Server 和大模型应用直接裸连就可以了。**
  - **为什么错**：**极度危险**。MCP Server 一旦启动，默认拥有启动账户的所有系统权限。如果它暴露了 `execute_shell_command` 的工具，恶意用户可以通过 Prompt 注入，让你的大模型直接在服务器上执行 `rm -rf /`。生产环境中，Host 必须对调用的 Server 进行严格的白名单鉴权，并且 Server 应该在 Docker 等沙箱中运行。
- **误区 3：如果我要让 Agent 查天气，使用 MCP Resource 比 Tool 更好。**
  - **为什么错**：Resource 适合那些“静态的、可直接读取的文档”。查天气需要传入参数（如经纬度、日期）去触发一个动态的第三方 API 查询动作，它显然是一个需要传参的**动作 (Tool)**。

## 11.7 本章小结
1. MCP 的诞生旨在终结 LLM 工具生态的碎片化，实现了“一次编写 Server，全平台 Agent 随时调用”的愿景。
2. 通过 Host-Client-Server 三方解耦架构，MCP 将大模型的大脑与外部世界的手脚物理隔离。
3. Resources 暴露只读数据，Tools 提供带参的执行动作，Prompts 定义快捷调用的指令。
4. 基于 JSON-RPC over stdio 的极简底层，让 MCP 在本地工具调用上具备远超 REST API 的极速体验与动态发现能力。
5. 将核心业务能力封装为 MCP Server，是 A3 系统等新一代 AI 原生应用必须掌握的工程典范。

## 11.10 可运行代码示例

下面手写一个最简 MCP 消息样例：客户端用 JSON-RPC 风格向服务器请求列出可用工具、调用某个工具。完整展示协议帧结构。

```python
'''11 章 · MCP 协议消息格式示例 — JSON-RPC 风格'''
import json

# MCP 协议消息都是 JSON-RPC 2.0 风格
# 三种核心原语：tools/list, tools/call, resources/read

# 1. 客户端 → 服务器：列出可用工具
req_list = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
}

# 2. 服务器 → 客户端：返回工具列表
resp_list = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {
                "name": "bloom_quiz",
                "description": "基于 Bloom 认知层级生成练习题",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "kp_id": {"type": "string"},
                        "bloom_level": {"type": "string", "enum": ["Apply", "Analyze", "Evaluate"]},
                    },
                    "required": ["kp_id"]
                }
            },
            {
                "name": "generate_pptx",
                "description": "根据大纲生成 PPT",
                "inputSchema": {"type": "object", "properties": {"outline": {"type": "string"}}}
            }
        ]
    }
}

# 3. 客户端 → 服务器：调用 bloom_quiz 工具
req_call = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "bloom_quiz",
        "arguments": {"kp_id": "transformer", "bloom_level": "Analyze"}
    }
}

# 4. 服务器 → 客户端：返回工具执行结果
resp_call = {
    "jsonrpc": "2.0",
    "id": 2,
    "result": {
        "content": [
            {"type": "text", "text": "Q1: 解释 Self-Attention 中的 QKV 含义。\\nA: Q=查询, K=键, V=值。"}
        ]
    }
}

# 打印消息流
print("=" * 60)
print("MCP 消息流（stdio / HTTP+SSE 均可承载）")
print("=" * 60)
print("\n[1] Client -> Server (tools/list):")
print(json.dumps(req_list, indent=2, ensure_ascii=False))
print("\n[2] Server -> Client (tools/list response):")
print(json.dumps(resp_list, indent=2, ensure_ascii=False)[:400], "...")
print("\n[3] Client -> Server (tools/call):")
print(json.dumps(req_call, indent=2, ensure_ascii=False))
print("\n[4] Server -> Client (tools/call result):")
print(json.dumps(resp_call, indent=2, ensure_ascii=False))

print("\n→ MCP 把『工具』变成可被任意 LLM 客户端调用的标准化资源。")
```
\n## 11.8 练习思考
1. **架构分析**：在 MCP 协议中，官方强烈推荐在本地桌面端开发时使用 `stdio` (标准输入输出) 作为传输层，而不是通过 `HTTP`。你能列举出 `stdio` 通信在此类场景下的两个显著优势吗？
2. **安全攻防**：假设你编写了一个能读取本地所有文件内容的 MCP Server `filesystem-server`。一个攻击者通过向大模型输入一段特殊的乱码，诱导大模型调用该工具读取了服务器上的 `/etc/shadow` 密码文件。在不修改大模型代码的前提下，你应该在 MCP 的哪一层、用什么技术切断这种攻击？
3. **生态对比**：MCP 与之前盛行一时的 "OpenAI GPTs (Plugins)" 相比，在开放性和生态系统构建上有什么本质的不同？
4. **场景设计**：如果要为 A3 项目设计一个能够帮学生查询“近三个月错题本”的 MCP Server，请试着写出这个 Tool 对应的完整 JSON Schema（参考 11.3 节），需要考虑传入哪些过滤参数（如日期范围、学科）？

## 11.9 拓展阅读
- MCP 协议官方规范与白皮书：访问官网 `modelcontextprotocol.io`。
- 探索全网可用的 MCP Server 列表：在 GitHub 搜索 `mcp-servers` (官方核心库) 或民间维护的 awesome 榜单。
- 从零构建 MCP 应用教程：阅读 Anthropic 官方的 `Building your first MCP Server` 快速入门指南。
