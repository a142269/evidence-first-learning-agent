# 11: 文件读写与 pathlib · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：35 分钟

---

## Slide 1：封面
- 标题：文件读写与 pathlib
- 副标题：Python 程序设计 · 第 12 讲

## Slide 2：本讲大纲
- open() 基础
- 文件模式
- 读写方法
- with 语句
- 文本 vs 二进制
- pathlib 路径操作
- glob 模式匹配

## Slide 3：open() 基础
```python
with open("data.txt", "r", encoding="utf-8") as f:
    content = f.read()
```
- file: 文件路径
- mode: 模式（默认 r）
- encoding: 推荐显式 utf-8
- buffering: 缓冲策略

## Slide 4：文件模式
| 模式 | 含义 |
|------|------|
| r | 读（默认） |
| w | 写（覆盖） |
| a | 追加 |
| x | 排他创建 |
| b | 二进制 |
| t | 文本（默认） |
| + | 同时读写 |

可组合：rb / w+b / a+

## Slide 5：读写方法
- 读：read() / readline() / readlines() / for line in f
- 写：write() / writelines()
- 指针：tell() / seek()
- [代码示例：逐行处理大文件]

## Slide 6：with 语句
- 异常也保证关闭
- 等价于 try/finally
- 推荐所有文件操作都用 with
```python
# ❌ 错误
f = open("x"); data = f.read(); f.close()
# ✅ 正确
with open("x") as f: data = f.read()
```

## Slide 7：文本 vs 二进制
| 维度 | 文本 | 二进制 |
|------|------|--------|
| 读写类型 | str | bytes |
| 编码 | 显式 | 原始 |
| 换行 | 自动转换 | 保留 |
| 适用 | .txt / .csv | 图片/网络 |

## Slide 8：pathlib 路径操作
```python
from pathlib import Path
p = Path("data") / "sub" / "file.txt"
p.name       # 'file.txt'
p.suffix     # '.txt'
p.parent     # PosixPath('data/sub')
p.exists()   # True
p.read_text("utf-8")
p.write_text("hello", "utf-8")
```
- 面向对象 API
- 跨平台（自动处理 / 与 \）
- 推荐替代 os.path

## Slide 9：glob 模式匹配
```python
Path(".").glob("*.py")      # 当前层
Path(".").rglob("*.py")     # 递归
Path("src").glob("**/*.md") # 递归 src 下
```
- `*` 任意字符
- `**` 任意层目录
- 应用：批量处理、代码统计

## Slide 10：编码问题
- Windows 默认 GBK
- 跨平台代码必须显式 `encoding="utf-8"`
- 解码失败：`UnicodeDecodeError`
- 处理：`errors="replace"` / chardet
- [代码示例：处理混合编码文件]

## Slide 11：本讲总结与作业
- 核心要点：
  1. with 是文件操作标准
  2. 显式 encoding 避免乱码
  3. pathlib 替代 os.path
- 作业：
  1. 用 pathlib 统计 .py 文件
  2. 实现 merge_logs
  3. 处理 GBK / UTF-8 混合文件
