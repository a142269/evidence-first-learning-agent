"""
将 question_bank_analytics_0708.json 的 40 道题合并到 question_bank.json
更新 _meta: total, kp_count, per_kp, bloom_distribution, type_distribution, content_hash
"""
import json
import hashlib
from collections import Counter

# 读取主库
with open(r"F:\比赛\中软杯\A3\data\question_bank.json", "r", encoding="utf-8") as f:
    main = json.load(f)

# 读取增量
with open(r"F:\比赛\中软杯\A3\data\question_bank_analytics_0708.json", "r", encoding="utf-8") as f:
    extra = json.load(f)

# 校验主库结构
assert "_meta" in main
assert "questions" in main and isinstance(main["questions"], list)
assert isinstance(extra, list)

# 校验 id 不冲突
existing_ids = {q["id"] for q in main["questions"]}
new_ids = {q["id"] for q in extra}
conflict = existing_ids & new_ids
print(f"Existing: {len(existing_ids)}, New: {len(new_ids)}, Conflict: {len(conflict)}")
if conflict:
    print(f"  Conflict ids: {conflict}")
    raise SystemExit("ID 冲突,中止")

# 合并
main["questions"].extend(extra)

# 重算 _meta
new_questions = main["questions"]
total = len(new_questions)
kp_counter = Counter(q["kp_id"] for q in new_questions)
bloom_counter = Counter(q["bloom"] for q in new_questions)
type_counter = Counter(q["type"] for q in new_questions)

main["_meta"]["total"] = total
main["_meta"]["kp_count"] = len(kp_counter)
main["_meta"]["per_kp"] = dict(kp_counter)
main["_meta"]["bloom_distribution"] = dict(bloom_counter)
main["_meta"]["type_distribution"] = dict(type_counter)

# content_hash
hash_input = json.dumps(new_questions, ensure_ascii=False, sort_keys=True).encode("utf-8")
main["_meta"]["content_hash"] = hashlib.sha1(hash_input).hexdigest()[:12]
# 更新版本号
main["_meta"]["version"] = "day4-280-v3-extra-0708-analytics"

# 写回
with open(r"F:\比赛\中软杯\A3\data\question_bank.json", "w", encoding="utf-8") as f:
    json.dump(main, f, ensure_ascii=False, indent=2)

print()
print("=" * 60)
print("合并完成")
print("=" * 60)
print(f"  total: {total}")
print(f"  kp_count: {len(kp_counter)}")
print(f"  bloom_distribution: {dict(bloom_counter)}")
print(f"  type_distribution: {dict(type_counter)}")
print(f"  new kps: {[k for k in kp_counter if k not in {'python_basics','data_structures','linear_algebra','probability_statistics','ml_basics','supervised_learning','unsupervised_learning','decision_trees','svm','neural_networks','backpropagation','cnn','rnn','lstm','attention_mechanism','transformer','nlp_basics','rag','reinforcement_learning','ai_project_practice','multi_agent_systems','multimodal_llm','ai_agent','mcp_protocol'}]}")
print(f"  content_hash: {main['_meta']['content_hash']}")
print(f"  version: {main['_meta']['version']}")
