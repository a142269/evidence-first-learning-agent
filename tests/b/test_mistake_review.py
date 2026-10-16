"""
Mistake review tests: classification, variants, SM-2 enqueue, heatmap, route ordering.
"""
import pytest


class TestMistakeClassification:
    def test_empty_answer_is_knowledge_gap(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("", "42")
        assert result["error_type"] == "知识缺漏"
        assert result["source"] == "rule"

    def test_exact_match_is_carelessness(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("42", "42")
        assert result["error_type"] == "计算粗心"

    def test_close_numeric_is_carelessness(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("99.8", "100")
        assert result["error_type"] == "计算粗心"

    def test_opposite_sign_is_concept_confusion(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("-5", "5")
        assert result["error_type"] == "概念混淆"

    def test_large_deviation_is_calculation_error(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("500", "100")
        assert result["error_type"] == "计算失误"

    def test_short_text_is_comprehension(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("??", "This is a long and detailed correct answer with many words explaining the concept.")
        assert result["error_type"] == "阅读理解"

    def test_question_in_answer_is_misread(self):
        from backend.app.services.mistake_review import classify_error
        result = classify_error("这个是什么意思？", "正确答案是xxx")
        assert result["error_type"] == "审题不清"

    def test_high_overlap_is_boundary_confusion(self):
        from backend.app.services.mistake_review import classify_error
        # 80%字符重叠但不是完全相同
        result = classify_error("卷积神经网络是一种前馈神经网络", "卷积神经网络是一种深度前馈神经网络")
        # Overlap should be >0.75 due to shared characters
        assert result["error_type"] in ("概念边界混淆", "概念混淆")


class TestVariantGeneration:
    def test_generates_three_variants(self):
        from backend.app.services.mistake_review import generate_variants
        variants = generate_variants(
            question="什么是列表推导式？",
            correct_answer="列表推导式是Python中创建列表的简洁语法，如[x for x in range(10)]。",
            kp_name="Python列表推导式",
            count=3,
        )
        assert len(variants) == 3

    def test_variants_have_required_fields(self):
        from backend.app.services.mistake_review import generate_variants
        variants = generate_variants(
            question="写一个for循环",
            correct_answer="for i in range(10): print(i)",
            kp_name="Python循环",
            count=3,
        )
        for v in variants:
            assert "bloom_level" in v
            assert "question" in v
            assert "answer" in v
            assert "explanation" in v
            assert "difficulty" in v

    def test_variants_have_different_bloom_levels(self):
        from backend.app.services.mistake_review import generate_variants
        variants = generate_variants(
            question="什么是面向对象？",
            correct_answer="OOP是一种编程范式。",
            kp_name="面向对象",
            count=3,
        )
        levels = {v["bloom_level"] for v in variants}
        assert len(levels) >= 2  # At least some differentiation


class TestHeatmapMatrix:
    def test_builds_matrix(self):
        from backend.app.services.mistake_review import build_heatmap_matrix
        mistakes = [
            {"kp_id": "kp_python", "error_type": "知识缺漏"},
            {"kp_id": "kp_python", "error_type": "计算失误"},
            {"kp_id": "kp_ml", "error_type": "概念混淆"},
            {"kp_id": "kp_ml", "error_type": "概念混淆"},
        ]
        result = build_heatmap_matrix(mistakes)
        assert result["total_mistakes"] == 4
        assert len(result["kps"]) == 2
        assert len(result["categories"]) == 8
        # Find kp_python row
        python_row = next(r for r in result["matrix"] if r["kp_id"] == "kp_python")
        assert python_row["知识缺漏"] == 1
        assert python_row["total"] == 2


class TestSM2AutoEnqueue:
    def test_sm2_enqueued_on_record(self):
        """Record a mistake and verify it enters SM-2 review queue."""
        from backend.app.services.spaced_repetition.sm2 import SM2
        sm2 = SM2()
        user_id = "test_user_sm2"
        mistake_id = "mistake_test_001"

        sm2.add_to_review_queue(user_id, mistake_id)

        due = sm2.daily_review_list(user_id)
        assert mistake_id in due, f"Expected {mistake_id} in review queue, got {due}"


class TestClassifyWithLLM:
    def test_falls_back_to_rule_when_no_llm(self):
        from backend.app.services.mistake_review import classify_with_llm
        result = classify_with_llm(
            student_answer="??",
            correct_answer="A long detailed explanation of the concept",
            question="What is X?",
            llm_call=None,
        )
        assert result["source"] == "rule"
        assert "error_type" in result

    def test_llm_overrides_low_confidence(self):
        def fake_llm(system="", user=""):
            return '{"error_type": "概念混淆", "detail": "学生混淆了概念A和概念B"}'

        from backend.app.services.mistake_review import classify_with_llm
        result = classify_with_llm(
            student_answer="partially right but wrong details",
            correct_answer="The complete correct answer with many details",
            question="Explain concept X",
            llm_call=fake_llm,
        )
        # Low-confidence rule result (<0.80) should be overridden by LLM
        assert result["source"] == "llm"
        assert result["error_type"] in (
            "概念混淆", "概念边界混淆", "知识缺漏", "阅读理解",
            "审题不清", "方法选择错", "计算失误", "计算粗心",
        )


class TestRouteOrdering:
    def test_categories_not_shadowed(self):
        """FastAPI should match /categories before /{user_id}"""
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/mistakes/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) == 8

    def test_heatmap_not_shadowed(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        client = TestClient(app)
        resp = client.get("/api/v1/mistakes/heatmap?user_id=test_route")
        assert resp.status_code == 200
