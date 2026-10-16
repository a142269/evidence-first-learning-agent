# 12: CSV 与 JSON · 幻灯片大纲

> 总页数：10 页 | 建议讲解时长：30 分钟

---

## Slide 1：封面
- 标题：CSV 与 JSON 结构化数据处理
- 副标题：Python 程序设计 · 第 13 讲

## Slide 2：本讲大纲
- CSV 基础
- DictReader / DictWriter
- JSON 基础
- 类型对应
- ensure_ascii
- 自定义对象序列化
- 实战：学生成绩

## Slide 3：CSV 基础
- Comma-Separated Values
- csv.reader / csv.writer
- 每行是 list[str]
- 写时 `newline=""` 避免 Windows 双重换行
- [代码示例：基础读写]

## Slide 4：DictReader / DictWriter
```python
with open("data.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        print(row["name"])
```
- 字段名作为 key
- 写时 `writeheader()` + `writerow({...})`
- [代码示例：按列名操作]

## Slide 5：JSON 类型对应
| Python | JSON |
|--------|------|
| dict | {} |
| list | [] |
| tuple | []（不可逆） |
| str | "string" |
| int/float | number |
| True/False | true/false |
| None | null |

## Slide 6：json dumps/loads
```python
data = {"name": "张三", "age": 25}
s = json.dumps(data, ensure_ascii=False)
obj = json.loads(s)
```
- ensure_ascii=False 保留中文
- indent=2 美化输出
- sort_keys=True 按 key 排序
- [代码示例：完整读写]

## Slide 7：自定义对象
- JSON 默认只支持基本类型
- 自定义类需要 default 函数
```python
def default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(...)
```
- 配合 dataclasses.asdict

## Slide 8：JSONPath / jq
- 复杂 JSON 提取
- Python：`jmespath` 库
- Shell：`jq` 命令
```bash
cat data.json | jq '.users[0].name'
```
- [配图：jq 命令演示]

## Slide 9：实战 - 学生成绩
- 1. 从 CSV 读取
- 2. 计算 total / average
- 3. 写入 JSON
- 4. 加载回 Python
- 完整流程展示

## Slide 10：本讲总结与作业
- 核心要点：
  1. CSV 用 DictReader/DictWriter
  2. JSON ensure_ascii=False 保留中文
  3. 自定义对象用 default
- 作业：
  1. 实现 csv_to_json
  2. 实现 save_user_profile
  3. 用 jq 提取 JSON 字段
