"""查询 Python 课程的错题数据"""
import sqlite3
import json

conn = sqlite3.connect("data/a3_learning.db")
c = conn.cursor()

# mistakes 表字段: id, user_id, knowledge_point_id, question_data, error_type, analysis, created_at, resolved_at

# 统计总错题数
total = c.execute("SELECT COUNT(*) FROM mistakes").fetchone()[0]
print(f"总错题数: {total}")

# Python 错题 (py_ 前缀的知识点)
py_count = c.execute(
    "SELECT COUNT(*) FROM mistakes WHERE knowledge_point_id LIKE 'py_%'"
).fetchone()[0]
print(f"Python 课程错题 (py_ 前缀): {py_count} 条")

# AI 错题 (非 py_ 前缀)
ai_count = c.execute(
    "SELECT COUNT(*) FROM mistakes WHERE knowledge_point_id NOT LIKE 'py_%'"
).fetchone()[0]
print(f"AI 课程错题 (非 py_ 前缀): {ai_count} 条")

# Python 错题按知识点统计
print("\n--- Python 错题按知识点统计 ---")
py_kp_rows = c.execute(
    "SELECT knowledge_point_id, COUNT(*) as cnt FROM mistakes "
    "WHERE knowledge_point_id LIKE 'py_%' "
    "GROUP BY knowledge_point_id ORDER BY cnt DESC"
).fetchall()
for r in py_kp_rows:
    print(f"  {r[0]:40s}: {r[1]:4d} 条")

# Python 错题按错误类型统计
print("\n--- Python 错题按错误类型统计 ---")
py_err_rows = c.execute(
    "SELECT error_type, COUNT(*) as cnt FROM mistakes "
    "WHERE knowledge_point_id LIKE 'py_%' "
    "GROUP BY error_type ORDER BY cnt DESC"
).fetchall()
for r in py_err_rows:
    print(f"  {r[0] or '(空)':40s}: {r[1]:4d} 条")

# Python 错题按学生统计
print("\n--- Python 错题按学生统计 (前10) ---")
py_user_rows = c.execute(
    "SELECT user_id, COUNT(*) as cnt FROM mistakes "
    "WHERE knowledge_point_id LIKE 'py_%' "
    "GROUP BY user_id ORDER BY cnt DESC LIMIT 10"
).fetchall()
for r in py_user_rows:
    print(f"  {r[0]:30s}: {r[1]:4d} 条")

# Python 错题示例 (前5条)
print("\n--- Python 错题示例 (前5条) ---")
py_samples = c.execute(
    "SELECT id, user_id, knowledge_point_id, error_type, "
    "substr(question_data, 1, 200) as q_preview, "
    "substr(analysis, 1, 100) as a_preview, "
    "created_at, resolved_at FROM mistakes "
    "WHERE knowledge_point_id LIKE 'py_%' LIMIT 5"
).fetchall()
for r in py_samples:
    print(f"  id={r[0]}")
    print(f"  user={r[1]}, kp={r[2]}, error_type={r[3]}")
    print(f"  question: {r[4][:100]}...")
    print(f"  analysis: {r[5][:80]}..." if r[5] else "  analysis: (空)")
    print(f"  created={r[6]}, resolved={r[7]}")
    print()

# 已解决 vs 未解决
resolved = c.execute(
    "SELECT COUNT(*) FROM mistakes "
    "WHERE knowledge_point_id LIKE 'py_%' AND resolved_at IS NOT NULL"
).fetchone()[0]
unresolved = py_count - resolved
print(f"Python 错题已解决: {resolved} 条, 未解决: {unresolved} 条")

conn.close()
