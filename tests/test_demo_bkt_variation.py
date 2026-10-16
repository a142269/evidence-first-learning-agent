"""演示 BKT 初始值应自然离散，同时保持稳定且不污染真实学习数据。"""

from backend.app.services.cognitive_diagnosis.bkt import _demo_mastery_value


def test_demo_mastery_value_is_deterministic_and_bounded():
    first = _demo_mastery_value(0.72, -0.10, "demo-student-1", "AI_004")
    second = _demo_mastery_value(0.72, -0.10, "demo-student-1", "AI_004")

    assert first == second
    assert 0.1 <= first <= 0.95


def test_demo_mastery_values_are_not_a_regular_arithmetic_sequence():
    values = [
        _demo_mastery_value(0.72, offset, "demo-student-1", kp_id)
        for kp_id, offset in [
            ("AI_001", 0.00),
            ("AI_002", -0.05),
            ("AI_004", -0.10),
            ("AI_005", -0.15),
            ("AI_005_02", -0.20),
        ]
    ]
    steps = {round(values[index] - values[index - 1], 4) for index in range(1, len(values))}

    assert len(steps) >= 3

