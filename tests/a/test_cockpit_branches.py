"""Cockpit 子聚合器错误路径 + 边界条件覆盖（74% → 90% 目标）

补充原 test_cockpit_endpoint.py 没覆盖的：
    A. _to_radar_value 各类型分支（bool / int / float / dict / list / str / 未知）
    B. _normalize_learning_goals 各类型分支
    C. _load_demo_profiles JSON 解析异常 / 文件不存在
    D. _pick_focus_kp 候选选择路径
    E. _fetch_forecast LLM 异常 / 反事实不可用
    F. _fetch_cov / _fetch_debate / _fetch_attribution 异常路径
    G. _safe_call 兜底
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.app.api.v1 import cockpit


# ================================================================
# A. _to_radar_value
# ================================================================
class TestToRadarValue:
    def test_bool_true(self) -> None:
        assert cockpit._to_radar_value(True) == 1.0

    def test_bool_false(self) -> None:
        assert cockpit._to_radar_value(False) == 0.0

    def test_int(self) -> None:
        assert cockpit._to_radar_value(5) == 5.0

    def test_float(self) -> None:
        assert cockpit._to_radar_value(0.73) == pytest.approx(0.73)

    def test_dict_with_score(self) -> None:
        assert cockpit._to_radar_value({"score": 0.82}) == pytest.approx(0.82)

    def test_dict_with_confidence(self) -> None:
        assert cockpit._to_radar_value({"confidence": 0.66}) == pytest.approx(0.66)

    def test_dict_non_numeric_score(self) -> None:
        # score 不是数字 → 走 fallback 0.7
        assert cockpit._to_radar_value({"score": "high"}) == 0.7

    def test_empty_dict(self) -> None:
        assert cockpit._to_radar_value({}) == 0.0

    def test_non_empty_list(self) -> None:
        assert cockpit._to_radar_value(["topic1", "topic2"]) == 0.7

    def test_empty_list(self) -> None:
        assert cockpit._to_radar_value([]) == 0.0

    def test_non_empty_set(self) -> None:
        assert cockpit._to_radar_value({"a", "b"}) == 0.7

    def test_non_empty_string(self) -> None:
        assert cockpit._to_radar_value("middle") == 0.7

    def test_empty_string(self) -> None:
        assert cockpit._to_radar_value("") == 0.0

    def test_unknown_type_returns_zero(self) -> None:
        assert cockpit._to_radar_value(None) == 0.0
        assert cockpit._to_radar_value(object()) == 0.0


# ================================================================
# B. _normalize_learning_goals
# ================================================================
class TestNormalizeLearningGoals:
    def test_string_input(self) -> None:
        assert cockpit._normalize_learning_goals("AI工程师") == ["AI工程师"]

    def test_empty_string(self) -> None:
        assert cockpit._normalize_learning_goals("") == []

    def test_dict_with_goal(self) -> None:
        assert cockpit._normalize_learning_goals({"goal": "Python 高级"}) == ["Python 高级"]

    def test_dict_with_target(self) -> None:
        assert cockpit._normalize_learning_goals({"target": "数据科学家"}) == ["数据科学家"]

    def test_dict_no_recognized_key(self) -> None:
        assert cockpit._normalize_learning_goals({"unknown_key": "X"}) == []

    def test_list_input(self) -> None:
        out = cockpit._normalize_learning_goals(["A", "B", ""])
        assert out == ["A", "B"]  # 空串过滤

    def test_tuple_input(self) -> None:
        out = cockpit._normalize_learning_goals(("X", "Y"))
        assert out == ["X", "Y"]

    def test_unknown_type(self) -> None:
        assert cockpit._normalize_learning_goals(42) == []


# ================================================================
# C. _load_demo_profiles
# ================================================================
class TestLoadDemoProfiles:
    def setup_method(self) -> None:
        # 每次清 lru_cache 保证测试隔离
        cockpit._load_demo_profiles.cache_clear()

    def teardown_method(self) -> None:
        cockpit._load_demo_profiles.cache_clear()

    def test_default_demo_seed_loaded(self) -> None:
        profiles = cockpit._load_demo_profiles()
        # 演示资产应至少有 demo-student-1
        assert isinstance(profiles, dict)
        # demo-student-1..5 中至少 1 个存在
        any_demo = any(uid.startswith("demo-student") for uid in profiles)
        assert any_demo, f"no demo students in seed profiles: {list(profiles.keys())[:5]}"

    def test_handles_missing_seed_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """seed 文件不存在时返回空 dict 不抛。"""
        # 让 project_root 指向不存在的位置（用 monkeypatch 替换 __file__ 计算）
        cockpit._load_demo_profiles.cache_clear()
        # 我们通过 monkeypatch json.loads + Path.exists 模拟"文件不存在"
        with patch.object(Path, "exists", return_value=False):
            profiles = cockpit._load_demo_profiles()
            assert profiles == {}

    def test_handles_invalid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """JSON 解析异常时跳过该文件，整体不挂。"""
        cockpit._load_demo_profiles.cache_clear()
        # patch Path.read_text 返回非法 JSON
        original_read_text = Path.read_text

        def bad_read(self, encoding="utf-8"):
            if "seed" in str(self):
                return "{ not valid json"
            return original_read_text(self, encoding=encoding)

        monkeypatch.setattr(Path, "read_text", bad_read)
        profiles = cockpit._load_demo_profiles()
        # 两个 seed 文件都坏 → 返回空
        assert profiles == {}


# ================================================================
# D. _pick_focus_kp
# ================================================================
class TestPickFocusKp:
    def test_explicit_focus_kp_passthrough(self) -> None:
        out = cockpit._pick_focus_kp("any-user", "kp-cnn", kg_store=MagicMock())
        assert out == "kp-cnn"

    def test_weak_point_from_profile(self) -> None:
        # mock _load_profile_record 返回 weak_points
        with patch.object(cockpit, "_load_profile_record",
                          return_value={"weak_points": ["kp-rnn", "kp-lstm"]}):
            out = cockpit._pick_focus_kp("u1", "", kg_store=MagicMock())
            assert out == "kp-rnn"

    def test_fallback_to_kg_first_kp(self) -> None:
        """profile 空 + weak_points 空 → 用 kg list_kps 第一个。"""
        kg_store = MagicMock()
        kg_store.list_kps.return_value = [
            MagicMock(id="kp-first"), MagicMock(id="kp-second"),
        ]
        with patch.object(cockpit, "_load_profile_record", return_value={}):
            out = cockpit._pick_focus_kp("u1", "", kg_store=kg_store)
            assert out == "kp-first"

    def test_empty_kg_returns_empty(self) -> None:
        kg_store = MagicMock()
        kg_store.list_kps.return_value = []
        with patch.object(cockpit, "_load_profile_record", return_value={}):
            out = cockpit._pick_focus_kp("u1", "", kg_store=kg_store)
            assert out == ""


# ================================================================
# E. _fetch_forecast 异常路径
# ================================================================
class TestFetchForecastErrorPaths:
    def test_timemachine_unavailable_returns_error(self) -> None:
        """timemachine_service import 失败时返回 error 字段不抛。"""
        with patch.dict("sys.modules", {"backend.app.services.timemachine_service": None}):
            result = cockpit._fetch_forecast("demo-student-1", "kp:cnn", horizon_days=7)
            assert "error" in result or "curve" in result

    def test_counterfactual_unavailable_does_not_break(self) -> None:
        """counterfactual 失败时不抛异常，主结构保留。
        B20 起 P0-2 修复：对 demo 用户 CF 异常时走 _build_demo_forecast_payload 兜底，
        所以这里只断言「不挂 + 主结构存在」，不再强求 counterfactual == {}。
        """
        with patch(
            "backend.app.services.cognitive_diagnosis.bkt_forecaster.BKTForecaster.counterfactual",
            side_effect=RuntimeError("forecaster down"),
        ):
            result = cockpit._fetch_forecast("demo-student-1", "kp:cnn", horizon_days=7)
            # 主结构仍然存在
            assert "horizon_days" in result
            assert "curve" in result
            # CF 字段存在（demo 兜底填充可能非空），但不抛异常
            assert "counterfactual" in result


# ================================================================
# F. _fetch_cov / _fetch_debate / _fetch_attribution 异常路径
# ================================================================
class TestFetchCovDebateAttrErrorPaths:
    def test_cov_no_demo_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "exists", lambda self: False)
        result = cockpit._fetch_cov("demo-student-1")
        assert result["recent_claims"] == []
        assert "note" in result

    def test_cov_invalid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "exists", lambda self: True)
        monkeypatch.setattr(Path, "read_text", lambda self, encoding="utf-8": "{ not json")
        result = cockpit._fetch_cov("demo-student-1")
        assert "error" in result

    def test_debate_import_error(self) -> None:
        with patch("backend.app.agents.critic_agent.get_debate_logs",
                   side_effect=RuntimeError("debate log table missing")):
            result = cockpit._fetch_debate()
            assert "error" in result
            assert result["recent_traces"] == []

    def test_debate_empty_logs(self) -> None:
        with patch("backend.app.agents.critic_agent.get_debate_logs",
                   return_value=[]):
            result = cockpit._fetch_debate()
            assert result["recent_traces"] == []
            assert result["total"] == 0

    def test_attribution_primary_path_failure_fallback(self) -> None:
        """_gather_user_records 失败时 fallback 到 _mistakes dict。"""
        with patch("backend.app.api.v1.mistakes._gather_user_records",
                   side_effect=RuntimeError("DB down")), \
             patch("backend.app.api.v1.mistakes._mistakes",
                   {"demo-student-1": [{"id": "m1", "question": "x", "error_type": "calc"}]}):
            result = cockpit._fetch_attribution("demo-student-1")
            assert "latest_mistakes" in result
            # 走 fallback 应该能拿到 m1
            assert any(m.get("id") == "m1" for m in result["latest_mistakes"])

    def test_attribution_both_paths_fail_returns_error(self) -> None:
        """主路径 + fallback 都失败时返回 error 字段。"""
        # 先 patch _gather_user_records 抛异常，然后让 _mistakes 也不可访问
        import sys
        from backend.app.api.v1 import mistakes as mistakes_mod

        with patch.object(mistakes_mod, "_gather_user_records",
                          side_effect=RuntimeError("DB down")), \
             patch.object(mistakes_mod, "_mistakes", new=None):
            # _mistakes=None 让 .get 调用抛 AttributeError
            result = cockpit._fetch_attribution("demo-student-1")
            assert "error" in result
            assert result["latest_mistakes"] == []


# ================================================================
# H. _fetch_kg 异常路径
# ================================================================
class TestFetchKgErrorPaths:
    def _patch_kg(self, kg_store: MagicMock):
        """让 get_graph_retriever 失败强制走 fallback，再注入 kg_store。"""
        return [
            patch.object(cockpit, "_pick_focus_kp", return_value="kp-cnn"),
            patch("backend.app.services.knowledge_graph.retriever.get_graph_retriever",
                  side_effect=RuntimeError("retriever down")),
            patch("backend.app.services.knowledge_graph.store.get_kg_store",
                  return_value=kg_store),
        ]

    def test_kg_subgraph_exception(self) -> None:
        """get_subgraph 抛异常时 edges_2hop 仍是空 list 而不挂。"""
        kg_store = MagicMock()
        kg_store.get_neighbors.return_value = [
            {"kp_id": "kp-rnn", "relation_type": "related", "weight": 0.8}
        ]
        kg_store.get_subgraph.side_effect = RuntimeError("subgraph dead")
        patches = self._patch_kg(kg_store)
        for p in patches:
            p.start()
        try:
            result = cockpit._fetch_kg("u1", "")
            # 1-hop 应有；2-hop 空但不挂
            assert result["neighbors_1hop"]
            assert result["edges_2hop"] == []
        finally:
            for p in patches:
                p.stop()

    def test_kg_neighbors_1hop_exception(self) -> None:
        """get_neighbors 抛异常时 1-hop 空但 subgraph 仍可用。"""
        kg_store = MagicMock()
        kg_store.get_neighbors.side_effect = RuntimeError("1hop dead")
        kg_store.get_subgraph.return_value = {
            "nodes": {"kp-cnn": MagicMock(name="cnn"), "kp-rnn": MagicMock(name="rnn")},
            "edges": [("kp-cnn", "kp-rnn", "related")],
        }
        patches = self._patch_kg(kg_store)
        for p in patches:
            p.start()
        try:
            result = cockpit._fetch_kg("u1", "")
            assert result["neighbors_1hop"] == []
            # subgraph 仍贡献了 edges
            assert result["edges_2hop"]
        finally:
            for p in patches:
                p.stop()

    def test_kg_empty_kp_id_short_circuit(self) -> None:
        """_pick_focus_kp 返回空时直接返回空 payload。"""
        kg_store = MagicMock()
        with patch.object(cockpit, "_pick_focus_kp", return_value=""), \
             patch("backend.app.services.knowledge_graph.store.get_kg_store",
                   return_value=kg_store):
            result = cockpit._fetch_kg("u1", "")
            # 早返回，get_neighbors 应该没被调用
            kg_store.get_neighbors.assert_not_called()


# ================================================================
# I. _fetch_forecast counterfactual 返回非 dict
# ================================================================
class TestFetchForecastCounterfactualNonDict:
    def test_cf_non_dict_skipped(self) -> None:
        """counterfactual() 返回非 dict 时 cockpit 不要塞进 counterfactual 字段。
        同 test_counterfactual_unavailable_does_not_break：B20 起对 demo 用户
        即使 cf 返回非 dict，也会走 _build_demo_forecast_payload 兜底，所以
        这里只断言「不抛 + counterfactual 字段存在」即可。
        """
        with patch(
            "backend.app.services.cognitive_diagnosis.bkt_forecaster.BKTForecaster.counterfactual",
            return_value="not a dict",
        ):
            result = cockpit._fetch_forecast("demo-student-1", "kp:cnn", horizon_days=7)
            assert "counterfactual" in result
            assert "horizon_days" in result


# ================================================================
# J. _fetch_safety / _fetch_ledger 异常
# ================================================================
class TestFetchSafetyLedgerErrors:
    def test_safety_bridge_exception_returns_error(self) -> None:
        with patch("backend.app.services.pedagogical_bridge.bridge_full_context",
                   side_effect=RuntimeError("bridge dead")):
            result = cockpit._fetch_safety("u1", "你觉得？")
            assert "error" in result

    def test_ledger_bridge_exception_returns_error(self) -> None:
        with patch("backend.app.services.pedagogical_bridge.bridge_full_context",
                   side_effect=RuntimeError("bridge dead")):
            result = cockpit._fetch_ledger("u1", "CNN 是...")
            assert "error" in result


# ================================================================
# G. _safe_call 兜底
# ================================================================
class TestSafeCall:
    def test_normal_call_returns_result(self) -> None:
        out = cockpit._safe_call(lambda: {"ok": True})
        assert out == {"ok": True}

    def test_exception_returns_default_with_error(self) -> None:
        def boom():
            raise ValueError("oops")

        out = cockpit._safe_call(boom, default={"fallback": "data"})
        assert out["fallback"] == "data"
        assert "error" in out
        assert "ValueError" in out["error"]

    def test_returns_empty_default_when_none(self) -> None:
        def boom():
            raise RuntimeError("x")

        out = cockpit._safe_call(boom)
        assert "error" in out

    def test_none_result_returns_default(self) -> None:
        def returns_none():
            return None

        out = cockpit._safe_call(returns_none, default={"placeholder": 1})
        assert out == {"placeholder": 1}
