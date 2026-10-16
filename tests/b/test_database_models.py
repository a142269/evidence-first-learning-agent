from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base


EXPECTED_TABLES = {
    "profiles",
    "realtime_states",
    "learner_archetypes",
    "knowledge_points",
    "kp_relations",
    "dina_states",
    "bkt_states",
    "sm2_schedule",
    "learning_paths",
    "assessments",
    "mistakes",
    "gamification_profiles",
}


def test_b_owned_models_create_all_tables_and_round_trip_json(tmp_path):
    from backend.app.core.models import ProfileRecord

    engine = create_engine(f"sqlite:///{tmp_path / 'models.db'}")
    Base.metadata.create_all(bind=engine)

    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(
            ProfileRecord(
                user_id="student-1",
                profile_data={"knowledge_base": {"score": 0.7}},
                version=2,
            )
        )
        db.commit()

    with sessions() as db:
        stored = db.get(ProfileRecord, "student-1")
        assert stored is not None
        assert stored.profile_data["knowledge_base"]["score"] == 0.7
        assert stored.version == 2
