# PPT 模板接入指南

系统的 PPT 流程为：Kimi K2.6（thinking 模式）单次调用同时生成教学叙事大纲与逐页内容，最后由内置版式或原生 PPTX 模板渲染。母版的设计要求与完整制作步骤见 [09-PPT母版设计与添加指南.md](09-PPT母版设计与添加指南.md)。

## 设置默认模板

模板必须是 16:9 的 `.pptx` 文件。任选一种方式：

1. 将模板保存为 `data/pptx_templates/default.pptx`；
2. 在 `.env` 中设置 `PPTX_TEMPLATE_PATH=模板绝对路径`。

生成器会删除模板中的示例幻灯片，但保留母版、主题、字体、背景和品牌装饰，然后生成新的教学页面。非 16:9 模板会自动回退到内置版式。

## 按名称选择模板

把模板放入 `data/pptx_templates/`，例如 `data/pptx_templates/tech-blue.pptx`，调用 `/api/v1/artifacts/generate/multi` 时传入：

```json
{
  "topic": "二分查找",
  "types": ["pptx"],
  "pptx_template": "tech-blue"
}
```

请求参数只接受模板名，不接受任意文件路径，避免路径穿越。资源元数据中的 `template_name`、`outline_source`、`content_source` 可用于确认实际使用的模板和模型链路。
