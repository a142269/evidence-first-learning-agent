from __future__ import annotations


def test_demo_bkt_prefers_persisted_state_over_static_fallback(monkeypatch):
    from backend.app.services.cognitive_diagnosis import bkt as bkt_module
    from backend.app.services.cognitive_diagnosis import state_repository

    class _Repo:
        @staticmethod
        def load_all_bkt(user_id: str):
            if user_id != "demo-student-1":
                return {}
            return {
                "AI_001": {
                    "p_learned": 0.91,
                    "p_transit": 0.1,
                    "p_slip": 0.1,
                    "p_guess": 0.2,
                    "history": [],
                }
            }

        @staticmethod
        def save_bkt_state(*_args, **_kwargs):
            return None

    monkeypatch.setattr(state_repository, "get_state_repo", lambda: _Repo())
    monkeypatch.setattr(bkt_module, "_bkt_instance", None)
    monkeypatch.setattr(bkt_module, "_bkt_seeded", False)

    service = bkt_module.get_bkt()

    assert service.get_all_masteries("demo-student-1")["AI_001"] == 0.91
