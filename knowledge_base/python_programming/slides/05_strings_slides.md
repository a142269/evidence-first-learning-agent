# 05: 字符串操作与正则入门 · 幻灯片大纲

> 总页数：11 页 | 建议讲解时长：30 分钟

---

## Slide 1：封面
- 标题：字符串操作与正则入门
- 副标题：Python 程序设计 · 第 6 讲

## Slide 2：本讲大纲
- 字符串本质
- f-string 格式化
- 常用方法
- str vs bytes
- 正则表达式基础
- 日志解析实战

## Slide 3：字符串本质
- Python 3 字符串 = Unicode 字符序列
- 字节串 `bytes` = 0-255 整数序列
- 不可变：所有"修改"都创建新对象
```python
s = "你好"
b = s.encode()        # b'\xe4\xbd\xa0\xe5\xa5\xbd'
s2 = b.decode()       # '你好'
```

## Slide 4：f-string 格式化
```python
f"{name} 得分: {score:.1f}"
f"{pi:.2f}"
f"{'hi':>10}|"
f"{1234567:,}"
f"{0.876:.2%}"
f"{name=}, {age=}"  # 3.8+ 自记录
```
- 首选格式化方式
- 支持表达式、对齐、精度、千分位
- [配图：f-string 格式说明符表]

## Slide 5：常用字符串方法
| 方法 | 用途 | 例子 |
|------|------|------|
| upper/lower/title | 大小写 | "hello".upper() |
| strip/lstrip/rstrip | 去除空白 | "  hi  ".strip() |
| split/join | 切分/拼接 | "a,b".split(",") |
| replace | 替换 | "hello".replace("l", "L") |
| find/index | 查找 | "hello".find("ll") |
| startswith/endswith | 前缀/后缀 | "hello".startswith("h") |
| zfill | 前导 0 | "42".zfill(5) |

## Slide 6：join vs += 性能
- `s = ""; for x in lst: s += x` → O(n²)
- `"".join(lst)` → O(n)
- 列表内 10000 个字符串,join 比 += 快 10-100 倍
- [代码示例：性能对比]

## Slide 7：str vs bytes
| 操作 | str | bytes |
|------|-----|-------|
| 字面量 | "hello" | b"hello" |
| 元素 | Unicode 字符 | 0-255 整数 |
| 编码 | 文本 I/O | 二进制 I/O |
| 转换 | `.encode("utf-8")` | `.decode("utf-8")` |

应用：网络 socket、二进制文件、哈希

## Slide 8：正则表达式基础
- 元字符：`.` `^` `$` `*` `+` `?` `[]` `()` `|` `{}`
- 速记：`\d` `\w` `\s` `\D` `\W` `\S`
- 函数：`match` / `search` / `findall` / `sub` / `split`
- 编译：`re.compile(r"\d+")` 性能更好

## Slide 9：命名组与贪婪
```python
m = re.match(
    r"(?P<year>\d{4})-(?P<month>\d{2})",
    "2026-07"
)
m.group("year")  # "2026"
m.groupdict()     # {"year": "2026", ...}
```
- 贪婪默认（尽可能多）
- 非贪婪：加 `?`（`.*?` `+?` `??`）

## Slide 10：日志解析实战
```python
pattern = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>INFO|ERROR|WARN)\s+"
    r"\[(?P<module>[\w.]+):(?P<line>\d+)\]\s+"
    r"(?P<msg>.+)"
)
for m in pattern.finditer(log):
    print(m.groupdict())
```
- [代码示例：完整日志解析器]

## Slide 11：本讲总结与作业
- 核心要点：
  1. f-string 是首选格式化
  2. join 比 += 快 10-100 倍
  3. 正则用命名组提高可读性
- 作业：
  1. 实现 `slugify(text)`
  2. 实现 `extract_emails(text)`
  3. 解析一段真实日志
