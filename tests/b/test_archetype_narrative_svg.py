"""
Archetype + Narrative + SVG 测试
"""
import pytest


class TestLearnerArchetype:
    def test_identify_high_achiever(self):
        from backend.app.services.learner_archetype import LearnerArchetypeService
        svc = LearnerArchetypeService()
        dims = {k: 0.85 for k in
                ["knowledge_base", "learning_preference", "weak_points",
                 "time_management", "self_efficacy", "cognitive_style",
                 "learning_goal", "interaction_pattern"]}
        result = svc.identify(dims)
        assert "code" in result
        assert "archetype" in result
        assert "traits" in result

    def test_all_nine_codes_exist(self):
        from backend.app.services.learner_archetype import LearnerArchetypeService
        svc = LearnerArchetypeService()
        assert len(svc.ARCHETYPES) == 9

    def test_low_dims_output(self):
        from backend.app.services.learner_archetype import LearnerArchetypeService
        svc = LearnerArchetypeService()
        dims = {k: 0.2 for k in
                ["knowledge_base", "learning_preference", "weak_points",
                 "time_management", "self_efficacy", "cognitive_style",
                 "learning_goal", "interaction_pattern"]}
        result = svc.identify(dims)
        assert "code" in result


class TestNarrativeGenerator:
    def test_build_summary_five_fields(self):
        from backend.app.services.narrative_generator import get_narrative_generator
        ng = get_narrative_generator()
        row = {"user_id": "demo", "bkt_masteries": {"kp_a": 0.75}}
        summary = ng.build_summary(row)
        assert "state_overview" in summary
        assert "trend_overview" in summary
        assert "statement" in summary

    def test_empty_input_graceful(self):
        from backend.app.services.narrative_generator import get_narrative_generator
        ng = get_narrative_generator()
        summary = ng.build_summary({})
        assert "statement" in summary


class TestSVGVisualization:
    def test_radar_generates(self):
        from backend.app.services.svg_visualization import get_svg_visualizer
        viz = get_svg_visualizer()
        radar = viz.profile_radar({"知识基础": 0.8, "学习偏好": 0.6})
        assert "<svg" in radar
        assert len(radar) > 500

    def test_forecast_svg_generates(self):
        from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster
        from backend.app.services.svg_visualization import get_svg_visualizer
        f = BKTForecaster()
        forecast = f.forecast(0.3, 30)
        ms = f.find_milestones(forecast)
        viz = get_svg_visualizer()
        svg = viz.mastery_forecast_svg(
            [fp.__dict__ for fp in forecast], ms,
            history=[{"day": -5, "p_learned": 0.25}, {"day": 0, "p_learned": 0.3}],
        )
        assert "<svg" in svg
        assert len(svg) > 1000

    def test_to_data_uri(self):
        from backend.app.services.svg_visualization import get_svg_visualizer
        viz = get_svg_visualizer()
        uri = viz.to_data_uri("<svg></svg>")
        assert uri.startswith("data:image/svg+xml;base64,")
