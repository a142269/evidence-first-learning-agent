"""B.2 间隔重复 benchmark 回归测试。"""

from scripts import benchmark_spaced_repetition as bench


def test_extract_review_sequences_preserves_global_order():
    """同一 skill 的复习序列应保留学生全局交互顺序。"""
    data = {
        "student_ids": ["stu-1"],
        "sequences": [[
            {"item_id": "kp-a", "correct": 1},
            {"item_id": "kp-b", "correct": 0},
            {"item_id": "kp-a", "correct": 1},
            {"item_id": "kp-a", "correct": 0},
        ]],
    }

    review_seqs = bench.extract_review_sequences(data, max_students=1)
    kp_a = next(seq for seq in review_seqs if seq["skill_id"] == "kp-a")

    assert [item["global_order"] for item in kp_a["interactions"]] == [0, 2, 3]


def test_simulations_report_actual_gap_proxy_mae():
    """SM-2 / FSRS 汇总里应包含真实序列间隔的 proxy MAE。"""
    review_seqs = [{
        "student_id": "stu-1",
        "skill_id": "kp-a",
        "interactions": [
            {"correct": 1, "global_order": 0},
            {"correct": 1, "global_order": 3},
            {"correct": 0, "global_order": 8},
        ],
    }]

    sm2_result = bench.run_sm2_simulation(review_seqs)
    fsrs_result = bench.run_fsrs_simulation(review_seqs)

    assert sm2_result["actual_gap_proxy_mae"] > 0
    assert fsrs_result["actual_gap_proxy_mae"] > 0
