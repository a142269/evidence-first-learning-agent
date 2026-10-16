# PPT 母版生成任务书（给大模型）

> **用法**：把下面「任务书」一节整体复制给任意大模型（Kimi / DeepSeek / Claude / GPT 均可），
> 模型会返回一个 Python 脚本；运行脚本即得到母版文件。人工操作步骤见文末「拿到脚本之后」。
> 大模型无法直接输出 .pptx 二进制文件，所以交付物定义为"生成母版的 python-pptx 脚本"。

---

## 任务书（从这里开始复制给大模型）

你是一名演示文稿视觉设计师兼 Python 工程师。请为一个"多智能体个性化学习系统"生成一个 **PPT 母版文件的生成脚本**。

### 一、交付物

一个**完整、可直接运行的 Python 脚本**，要求：

- 只依赖 `python-pptx`（`pip install python-pptx`），不使用其他第三方库；
- 运行后在当前目录生成一个母版 `.pptx` 文件，文件名只用英文字母、数字、连字符（例如 `campus-indigo.pptx`）；
- 脚本自带 `if __name__ == "__main__":` 入口，打印生成的文件路径；
- 只输出这一个代码块，不要输出解释性文字。

### 二、这个母版会被怎样使用（必须理解的机制约束）

下游系统用 `python-pptx` 打开你的母版，然后**自动完成**以下动作，你的设计必须与之兼容：

1. **删除模板中所有普通幻灯片页**，只保留母版（Slide Master）、版式、主题、字体和背景。所以你的设计必须全部放在**母版层**，普通页放什么都没用；
2. **校验 16:9**：页面必须是 13.333 × 7.5 英寸（python-pptx 默认是 4:3，脚本必须显式设置 `prs.slide_width = Inches(13.333)`、`prs.slide_height = Inches(7.5)`），宽高比偏差超过 0.08 整个模板会被拒用；
3. **正文由下游渲染器用文本框绘制**（标题约 35pt、正文 18pt、代码 Consolas 14pt），**不使用你母版里的任何文字占位符**；文字颜色是深色系（接近黑 / 深蓝 / 深灰）；
4. 下游不会在页面上再涂底色，**你的母版背景会原样透出**。

### 三、设计硬约束（违反任何一条即不合格）

1. **浅色背景**：背景亮度必须很高（纯白、米白、浅灰或极浅的品牌色，L ≥ 90%），因为正文是深色字；禁止深色背景、禁止高饱和大面积色块；
2. **版心留空**：页面四周约 0.8 英寸以内是正文区，装饰元素只能放在**边缘与四角**（色条、页脚、小标识），不得在页面中部放置任何图形或水印；
3. **装饰克制**：全部装饰加起来视觉占比 ≤ 10%；若用几何纹理，透明度 ≥ 95%（即几乎不可见）；
4. **不放图片**：只用 python-pptx 的原生形状（矩形、椭圆、线条、文本框），不引用外部图片文件；
5. **文字最少化**：母版上只允许出现页脚一处小字（10pt，浅灰 #9AA3AF 左右），内容为课程/机构名占位（如 "AI 学习伙伴 · 智能教学系统"）。

### 四、设计要求（要做出的元素，全部添加到 slide master 层）

按 z 序从下到上：

1. **背景**：用 `master.background.fill.solid()` 设置纯色；如果想要极淡的双色渐变，可以改为最先向母版移入一个全幅矩形（0,0,13.333in,7.5in）并用 `fill.gradient()` 实现，渐变两端颜色差要非常小；
2. **顶部品牌色条**：全宽矩形，高 0.06-0.10 英寸，用主品牌色；
3. **底部页脚线 + 页脚文字**：一条 0.01-0.02 英寸的浅色细线（距底 0.45 英寸左右），线下方左侧放页脚文本框；
4. **右下角标识**：一个小的几何标志（例如两个叠加的圆角矩形或圆点组合），整体不超过 0.4 × 0.4 英寸，紧贴右下角（右、下边距约 0.25 英寸）；
5. **左上或右上角装饰（可选）**：1-2 个大半径、超低透明度的圆形，必须有一半以上溢出到页面外（通过负坐标实现），制造"出血"效果。

所有形状 `shadow.inherit = False`（避免 PowerPoint 默认阴影），线条形状 `line.fill.background()` 或细描边。

### 五、配色（三选一，或按此逻辑自拟）

下游有三套文字主题（深蓝学术 / 紫粉现代 / 黑橙高对比），母版品牌色需与它们协调：

| 方案 | 背景 | 品牌色条 | 页脚字色 | 装饰色 |
|---|---|---|---|---|
| 学术蓝灰（默认推荐） | `#FCFDFF` | `#1E40AF` | `#94A3B8` | `#DBEAFE` |
| 紫调现代 | `#FDFCFF` | `#7C3AED` | `#9CA3AF` | `#EDE9FE` |
| 中性暖灰 | `#FDFCFA` | `#374151` | `#A8A29E` | `#F5F5F4` |

### 六、关键技术限制与脚本骨架（必须照此模式写）

**python-pptx（1.x）的 `master.shapes` 没有 `add_shape`/`add_textbox` 方法**，直接调用会
`AttributeError`。正确做法是：先在一张临时普通页上创建并样式化形状，再把形状的 XML 元素
移入母版的 spTree（lxml 的 `append` 会自动改变父节点），最后删除临时页。以下骨架已实测可用：

```python
"""生成 16:9 PPT 母版：<方案名>。运行后产出 <文件名>.pptx"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

PAGE_W, PAGE_H = Inches(13.333), Inches(7.5)

def build(path: str = "campus-indigo.pptx") -> str:
    prs = Presentation()
    prs.slide_width, prs.slide_height = PAGE_W, PAGE_H
    master = prs.slide_masters[0]

    # 1) 背景（master.background 可直接使用）
    master.background.fill.solid()
    master.background.fill.fore_color.rgb = RGBColor(0xFC, 0xFD, 0xFF)

    # 临时页：形状先建在这里，再移入母版
    temp = prs.slides.add_slide(prs.slide_layouts[6])

    def move_to_master(shape):
        master.shapes._spTree.append(shape._element)

    # 2) 顶部品牌色条
    bar = temp.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, PAGE_W, Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = RGBColor(0x1E, 0x40, 0xAF)
    bar.line.fill.background(); bar.shadow.inherit = False
    move_to_master(bar)

    # 3) 页脚线 + 页脚文字（add_textbox 同样先建在 temp 上再移入）...
    # 4) 右下角标识 ...
    # 5) 出血装饰圆（可选，负坐标）...

    # 删除临时页（母版文件不应包含任何普通页）
    slide_ids = prs.slides._sldIdLst
    for sid in list(slide_ids):
        prs.part.drop_rel(sid.rId)
        slide_ids.remove(sid)

    prs.save(path)
    return path

if __name__ == "__main__":
    print("saved:", build())
```

### 七、输出前自检清单（逐条核对后再输出）

- [ ] 显式设置了 13.333 × 7.5 英寸；
- [ ] 形状全部通过"临时页创建 → 移入母版 spTree"的模式添加（没有调用不存在的 `master.shapes.add_shape`），且脚本结尾删除了临时页；
- [ ] 背景是浅色，页面中部没有任何形状；
- [ ] 没有引用图片文件、没有 python-pptx 之外的 import；
- [ ] 所有可见形状设置了 `shadow.inherit = False`；
- [ ] 文件名是纯 ASCII；
- [ ] 脚本可以直接 `python xxx.py` 运行成功。

## ——任务书到此结束——

---

## 拿到脚本之后（人工操作）

1. 把脚本保存为任意 `.py` 文件，`pip install python-pptx` 后运行，得到 `.pptx`；
2. 把文件放入 `data/pptx_templates/`：
   - 命名为 `default.pptx` → 成为全局默认母版；
   - 或保留自定义名（如 `campus-indigo.pptx`）→ 调用 `/api/v1/artifacts/generate/multi` 时传 `"pptx_template": "campus-indigo"`，或在聊天里说"使用 campus-indigo 模板"；
   - 也可以在 `.env` 里设 `PPTX_TEMPLATE_PATH=<绝对路径>` 指定默认模板；
3. 生成一份测试 PPT 验收：
   - 结果 metadata 里 `template_name` 应等于模板名（是 `built-in-editorial` 说明没生效）；
   - `lint_warnings` 里不应出现 `[template_ratio]`（出现说明不是 16:9）；
   - 打开 PPT 肉眼检查：背景与装饰正常透出、正文深色字清晰可读、装饰未与正文重叠。

想换风格时，把任务书中「五、配色」的方案换掉（或直接告诉模型你的品牌色），重新生成一次即可。
