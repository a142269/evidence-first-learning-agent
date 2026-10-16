"""
pedagogical_context.py 测试

Coverage: get_mistake_context / get_kt_context / get_evidence_context / get_full_pedagogical_context
"""
import pytest


class TestMistakeContext:
    def test_empty_user_returns_no_mistakes(self):
        from backend.app.services.pedagogical_context import get_mistake_context
        result = get_mistake_context("nonexistent_user_99999")
        assert result["has_mistakes"] is False
        assert result["unresolved_count"] == 0
        assert "error_categories" in result

    def test_error_is_graceful(self):
        from backend.app.services.pedagogical_context import get_mistake_context
        result = get_mistake_context("")  # empty user_id — should not crash
        assert "has_mistakes" in result
        assert isinstance(result["unresolved_count"], int)

    def test_returns_sample_mistakes_field(self):
        from backend.app.services.pedagogical_context import get_mistake_context
        result = get_mistake_context("demo-student-1")
        assert "sample_mistakes" in result
        assert isinstance(result["sample_mistakes"], list)


class TestKTContext:
    def test_returns_masteries_dict(self):
        from backend.app.services.pedagogical_context import get_kt_context
        result = get_kt_context("nonexistent_user_99999")
        assert "masteries" in result
        assert "trends" in result
        assert "dina_snapshot" in result
        assert isinstance(result["masteries"], dict)

    def test_specific_kp_limits_results(self):
        from backend.app.services.pedagogical_context import get_kt_context
        result = get_kt_context("nonexistent_user_99999", kp_id="kp_test_123")
        assert len(result["masteries"]) <= 1

    def test_error_is_graceful(self):
        from backend.app.services.pedagogical_context import get_kt_context
        result = get_kt_context(123)  # non-string user_id
        assert "masteries" in result


class TestEvidenceContext:
    def test_returns_all_four_sections(self):
        from backend.app.services.pedagogical_context import get_evidence_context
        result = get_evidence_context("nonexistent_user_99999")
        assert "kg_neighbors" in result
        assert "rag_chunks" in result
        assert "learning_history" in result
        assert "related_mistakes" in result

    def test_with_query_returns_rag(self):
        from backend.app.services.pedagogical_context import get_evidence_context
        result = get_evidence_context("nonexistent_user_99999", query="CNN")
        assert isinstance(result["rag_chunks"], list)

    def test_with_kp_returns_neighbors(self):
        from backend.app.services.pedagogical_context import get_evidence_context
        result = get_evidence_context("nonexistent_user_99999", kp_id="kp_test")
        assert isinstance(result["kg_neighbors"], list)
        assert isinstance(result["related_mistakes"], list)


class TestFullContext:
    def test_returns_three_sections(self):
        from backend.app.services.pedagogical_context import get_full_pedagogical_context
        result = get_full_pedagogical_context("nonexistent_user_99999")
        assert "mistake_context" in result
        assert "kt_context" in result
        assert "evidence_context" in result

    def test_nested_contexts_are_dicts(self):
        from backend.app.services.pedagogical_context import get_full_pedagogical_context
        result = get_full_pedagogical_context("nonexistent_user_99999")
        assert isinstance(result["mistake_context"], dict)
        assert isinstance(result["kt_context"], dict)
        assert isinstance(result["evidence_context"], dict)

    def test_called_with_all_params(self):
        from backend.app.services.pedagogical_context import get_full_pedagogical_context
        result = get_full_pedagogical_context(
            "demo-student-1", query="CNN卷积层", kp_id="kp_cnn"
        )
        assert "mistake_context" in result
        assert "kt_context" in result
        assert "evidence_context" in result
