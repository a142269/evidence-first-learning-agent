#!/usr/bin/env python3
"""检查题库数据"""
import json
import os

files = [
    'data/question_bank.json',
    'data/quiz_bank.json',
    'data/question_bank_analytics_0708.json',
    'data/question_bank_extra_0703.json'
]

print("=" * 60)
print("题库数据检查")
print("=" * 60)

for f in files:
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                if isinstance(data, list):
                    print(f"[OK] {f}: {len(data)} 题")
                    if len(data) > 0:
                        q = data[0].get('question', data[0].get('stem', 'N/A'))
                        print(f"  示例: {q[:50]}...")
                elif isinstance(data, dict) and 'questions' in data:
                    print(f"[OK] {f}: {len(data['questions'])} 题")
                elif isinstance(data, dict):
                    print(f"[OK] {f}: 键={list(data.keys())}")
                else:
                    print(f"[OK] {f}: 类型={type(data)}")
        except Exception as e:
            print(f"[ERR] {f}: 错误 - {e}")
    else:
        print(f"[MISS] {f}: 文件不存在")

print("\n" + "=" * 60)
print("Artifact 文件检查")
print("=" * 60)

artifact_dirs = [
    'data/artifacts/mp3',
    'data/artifacts/pptx',
    'data/artifacts/manim',
    'data/artifacts/mermaid_png'
]

for d in artifact_dirs:
    if os.path.exists(d):
        files = [f for f in os.listdir(d) if not f.startswith('_') and not f.startswith('.')]
        print(f"[OK] {d}: {len(files)} 个文件")
    else:
        print(f"[MISS] {d}: 目录不存在")
