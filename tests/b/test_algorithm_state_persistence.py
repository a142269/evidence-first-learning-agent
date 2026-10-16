from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core import models  # noqa: F401
from backend.app.core.database import Base
from backend.app.services.cognitive_diagnosis.state_repository import StateRepository


def _repository(tmp_path) -> StateRepository:
    engine = create_engine(f"sqlite:///{tmp_path / 'algorithm-state.db'}")
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return StateRepository(sessions)


def test_bkt_state_restores_in_new_instance(tmp_path):
    from backend.app.services.cognitive_diagnosis.bkt import BKT

    repository = _repository(tmp_path)
    original = BKT(repository=repository)
    for answer in [True, True, False, True, True]:
        original.update("student-1", "kp-python", answer)

    expected = original.get_mastery("student-1", "kp-python")
    restored = BKT(repository=repository)

    assert restored.restore_user("student-1") == 1
    assert restored.get_mastery("student-1", "kp-python") == expected
    assert len(restored.get_history("student-1", "kp-python")) == 5


def test_sm2_schedule_restores_in_new_instance(tmp_path):
    from backend.app.services.spaced_repetition.sm2 import SM2

    repository = _repository(tmp_path)
    original = SM2(repository=repository)
    original.review("student-1", "item-1", quality=5)
    expected = original.review("student-1", "item-1", quality=4)

    restored = SM2(repository=repository)

    assert restored.restore_user("student-1") == 1
    schedule = restored.get_schedule("student-1", "item-1")
    assert schedule is not None
    assert schedule["repetitions"] == expected["repetitions"]
    assert schedule["interval"] == expected["interval"]
    assert schedule["easiness"] == expected["easiness"]


def test_sm2_due_items_lazily_restore_persisted_user(tmp_path):
    from backend.app.services.spaced_repetition.sm2 import SM2

    repository = _repository(tmp_path)
    repository.save_sm2_state(
        "student-1",
        "due-item",
        {
            "repetitions": 1,
            "interval": 1,
            "easiness": 2.5,
            "next_review_at": 10,
        },
    )

    restored = SM2(repository=repository)

    assert [item["item_id"] for item in restored.due_items("student-1")] == [
        "due-item"
    ]
    assert restored.stats("student-1")["total_items"] == 1


def test_sm2_retries_restore_when_user_was_initially_empty(tmp_path):
    repository = _repository(tmp_path)

    from backend.app.services.spaced_repetition.sm2 import SM2

    restored = SM2(repository=repository)
    assert restored.due_items("student-1") == []

    repository.save_sm2_state(
        "student-1",
        "late-item",
        {
            "repetitions": 0,
            "interval": 1,
            "easiness": 2.5,
            "next_review_at": 10,
        },
    )

    assert [item["item_id"] for item in restored.due_items("student-1")] == [
        "late-item"
    ]


def test_global_sm2_uses_state_repository(monkeypatch):
    from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo
    from backend.app.services.spaced_repetition import sm2 as sm2_module

    monkeypatch.setattr(sm2_module, "_sm2", None)

    assert sm2_module.get_sm2().repository is get_state_repo()


def test_dina_fit_persists_mastery_snapshot(tmp_path):
    from backend.app.services.cognitive_diagnosis.dina import DINA

    repository = _repository(tmp_path)
    model = DINA(repository=repository, max_iter=5)
    result = model.fit(
        responses={"student-1": {1: 1, 2: 0}},
        q_matrix=[[1, 0], [1, 1]],
        item_ids=[1, 2],
        kp_ids=["kp-a", "kp-b"],
        student_ids=["student-1"],
    )

    restored = DINA(repository=repository)
    snapshot = restored.restore_user("student-1")

    assert set(snapshot) == {"kp-a", "kp-b"}
    assert snapshot["kp-a"]["mastery"] == result["alpha"]["student-1"]["kp-a"]
    assert restored.diagnose("student-1")["kp-b"] == snapshot["kp-b"]["mastery"]


def test_state_repository_lists_all_sm2_schedules(tmp_path):
    repository = _repository(tmp_path)
    repository.save_sm2_state(
        "student-1",
        "item-a",
        {"repetitions": 1, "interval": 3, "easiness": 2.4, "next_review_at": 10},
    )
    repository.save_sm2_state(
        "student-1",
        "item-b",
        {"repetitions": 2, "interval": 6, "easiness": 2.5, "next_review_at": 20},
    )

    schedules = repository.load_all_sm2("student-1")

    assert set(schedules) == {"item-a", "item-b"}
    assert schedules["item-b"]["interval"] == 6
