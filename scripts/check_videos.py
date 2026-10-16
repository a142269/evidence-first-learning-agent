"""查询视频资源入库情况"""
import sqlite3
import json

conn = sqlite3.connect("data/a3_learning.db")
c = conn.cursor()
rows = c.execute(
    "SELECT id, type, title, metadata FROM resources WHERE id LIKE 'vid_%' ORDER BY id"
).fetchall()

print(f"{'ID':<40} | {'Type':<6} | {'Course':<30} | {'Method':<20} | Title")
print("-" * 140)
for r in rows:
    meta = json.loads(r[3]) if r[3] else {}
    course = meta.get("course", "?")
    method = meta.get("method", "?")
    title = r[2][:50] if r[2] else ""
    print(f"{r[0]:<40} | {r[1]:<6} | {course:<30} | {method:<20} | {title}")

print(f"\nTotal video resources: {len(rows)}")

# 按课程分组统计
ai_count = sum(1 for r in rows if "artificial" in json.loads(r[3] or "{}").get("course", ""))
py_count = sum(1 for r in rows if "python" in json.loads(r[3] or "{}").get("course", ""))
print(f"  AI course videos: {ai_count}")
print(f"  Python course videos: {py_count}")

conn.close()
