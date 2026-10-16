"""师生协作改造测试（7/9 两类用户方案）

覆盖:
    1. 角色体系: student/teacher/admin 登录 + 旧 counselor 兼容映射
    2. 教师资源 CRUD + 学生资源库按可见范围读取
    3. 指派资源 → 群聊出现 resource_card
    4. 推荐路径 → 学生路径列表可见 + 群聊出现 path_card
    5. 教师发消息 → 群聊出现 teacher_message
    6. Agent 配置: 内置种子 / 新增配置型 Agent / 禁用后拦截
    7. Orchestrator @配置型Agent 识别（mock LLM）
    8. group-chat 端点读写
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client(tmp_path_factory) -> TestClient:
    from backend.app.core.database import configure_database, init_db

    db_path = tmp_path_factory.mktemp("teacher") / "collab.db"
    configure_database(f"sqlite:///{db_path.as_posix()}")
    init_db()

    from backend.app.main import app
    client = TestClient(app)
    # 教师端点需要 teacher 角色 token —— 登录后全局带上
    token = client.post("/api/v1/auth/login", json={
        "account": "teacher", "password": "123456",
    }).json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ================================================================
# 1. 角色体系
# ================================================================
class TestAuthRoles:
    # 2026-07-16 身份合并：admin 与 teacher 功能一致，登录后角色归一化为 teacher
    @pytest.mark.parametrize("account,role,expected_role", [
        ("demo-student-1", "student", "student"),
        ("teacher", "teacher", "teacher"),
        ("admin", "admin", "teacher"),
    ])
    def test_login_three_roles(
        self, app_client: TestClient, account: str, role: str, expected_role: str
    ):
        r = app_client.post("/api/v1/auth/login", json={
            "account": account, "password": "123456", "role": role,
        })
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == expected_role

    def test_legacy_counselor_maps_to_teacher(self, app_client: TestClient):
        # 旧账号 counselor + 旧角色值 counselor → 登录成功且角色为 teacher
        r = app_client.post("/api/v1/auth/login", json={
            "account": "counselor", "password": "123456", "role": "counselor",
        })
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "teacher"

    def test_counselor_role_matches_teacher_account(self, app_client: TestClient):
        r = app_client.post("/api/v1/auth/login", json={
            "account": "teacher", "password": "123456", "role": "counselor",
        })
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "teacher"

    def test_role_mismatch_rejected(self, app_client: TestClient):
        r = app_client.post("/api/v1/auth/login", json={
            "account": "demo-student-1", "password": "123456", "role": "admin",
        })
        assert r.status_code == 401

    def test_student_token_rejected_on_teacher_api(self, app_client: TestClient):
        token = app_client.post("/api/v1/auth/login", json={
            "account": "demo-student-1", "password": "123456",
        }).json()["access_token"]
        r = app_client.get(
            "/api/v1/teacher/students",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    def test_me_endpoint(self, app_client: TestClient):
        token = app_client.post("/api/v1/auth/login", json={
            "account": "teacher", "password": "123456",
        }).json()["access_token"]
        r = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["role"] == "teacher"


# ================================================================
# 2. 教师资源 CRUD + 学生可见范围
# ================================================================
class TestTeacherResources:
    def test_create_edit_delete_and_student_visibility(self, app_client: TestClient):
        # 教师新增课程级已发布资源
        r = app_client.post("/api/v1/teacher/resources", json={
            "title": "机器学习基础补充讲义",
            "type": "document",
            "content": "# 补充讲义\n\n梯度下降……",
            "course": "artificial_intelligence",
            "scope": "course",
            "status": "published",
            "tags": ["机器学习"],
            "kp_ids": ["kp_ml_basic"],
        })
        assert r.status_code == 200, r.text
        rid = r.json()["resource_id"]
        assert r.json()["resource"]["metadata"]["created_by"] == "teacher"

        # 学生资源库能看到课程级已发布资源
        r = app_client.get("/api/v1/resources/list", params={"user_id": "demo-student-1"})
        ids = [item["id"] for item in r.json()["resources"]]
        assert rid in ids

        # 教师把资源下架 → 学生不可见
        r = app_client.patch(f"/api/v1/teacher/resources/{rid}", json={"status": "draft"})
        assert r.status_code == 200
        r = app_client.get("/api/v1/resources/list", params={"user_id": "demo-student-1"})
        ids = [item["id"] for item in r.json()["resources"]]
        assert rid not in ids

        # 教师视角仍能查询到（含草稿）
        r = app_client.get("/api/v1/teacher/resources", params={"status": "draft"})
        ids = [item["id"] for item in r.json()["resources"]]
        assert rid in ids

        # 删除
        r = app_client.delete(f"/api/v1/teacher/resources/{rid}")
        assert r.json()["status"] == "deleted"

    def test_student_scope_resource_only_visible_to_target(self, app_client: TestClient):
        r = app_client.post("/api/v1/teacher/resources", json={
            "title": "给 s1 的专属练习",
            "type": "quiz",
            "scope": "student",
            "status": "published",
            "target_user_ids": ["stu-1"],
        })
        rid = r.json()["resource_id"]

        visible = app_client.get("/api/v1/resources/list", params={"user_id": "stu-1"}).json()
        assert rid in [i["id"] for i in visible["resources"]]
        invisible = app_client.get("/api/v1/resources/list", params={"user_id": "stu-2"}).json()
        assert rid not in [i["id"] for i in invisible["resources"]]


class TestTeacherResourceUpload:
    def test_import_generated_pptx_artifact_and_download(
        self,
        app_client: TestClient,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from backend.app.api.v1.artifacts import registry as registry_module

        artifact_registry = registry_module.ArtifactRegistry()
        source = tmp_path / "gradient-descent.pptx"
        pptx_bytes = b"PK\x03\x04real-pptx-binary-test"
        source.write_bytes(pptx_bytes)
        artifact_registry.register(
            "pptx_teacher_studio_test",
            "pptx",
            str(source),
            metadata={"content_source": "kimi", "slides_count": 8},
            persist=False,
        )
        monkeypatch.setattr(
            registry_module,
            "get_artifact_registry",
            lambda: artifact_registry,
        )

        imported = app_client.post(
            "/api/v1/teacher/resources/from-artifact",
            json={
                "artifact_id": "pptx_teacher_studio_test",
                "title": "梯度下降进阶实战",
                "type": "ppt",
                "course": "artificial_intelligence",
                "scope": "course",
                "status": "published",
                "created_by": "王老师",
            },
        )
        assert imported.status_code == 200, imported.text
        resource = imported.json()["resource"]
        rid = resource["id"]
        assert resource["type"] == "ppt"
        assert resource["metadata"]["generated_artifact"]["binary_generated"] is True
        assert resource["metadata"]["generated_artifact"]["artifact_type"] == "pptx"
        assert resource["metadata"]["generated_artifact"]["source_metadata"]["content_source"] == "kimi"
        assert resource["metadata"]["attachment"]["filename"].endswith(".pptx")

        downloaded = app_client.get(f"/api/v1/teacher/resources/{rid}/download")
        assert downloaded.status_code == 200
        assert downloaded.content == pptx_bytes

        student_resources = app_client.get(
            "/api/v1/resources/list", params={"user_id": "demo-student-1"},
        ).json()["resources"]
        assert rid in [item["id"] for item in student_resources]
        assert app_client.delete(f"/api/v1/teacher/resources/{rid}").json()["status"] == "deleted"

    def test_artifact_import_rejects_non_ppt_video_binary(
        self,
        app_client: TestClient,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from backend.app.api.v1.artifacts import registry as registry_module

        artifact_registry = registry_module.ArtifactRegistry()
        source = tmp_path / "debug-output.txt"
        source.write_text("structured body is not a PPT or video", encoding="utf-8")
        artifact_registry.register(
            "document_teacher_studio_test",
            "document",
            str(source),
            persist=False,
        )
        monkeypatch.setattr(
            registry_module,
            "get_artifact_registry",
            lambda: artifact_registry,
        )

        rejected = app_client.post(
            "/api/v1/teacher/resources/from-artifact",
            json={"artifact_id": "document_teacher_studio_test", "type": "ppt"},
        )
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "artifact_file_type_not_publishable"

    def test_upload_download_and_delete_attachment(self, app_client: TestClient):
        upload = app_client.post(
            "/api/v1/teacher/resources/upload",
            data={
                "title": "线性回归课堂讲义",
                "resource_type": "document",
                "scope": "course",
                "status": "published",
                "tags": "机器学习,讲义",
                "kp_ids": "kp_ml_basic",
            },
            files={"file": ("linear-regression.md", b"# Linear Regression\n\nGradient descent.", "text/markdown")},
        )
        assert upload.status_code == 200, upload.text
        resource = upload.json()["resource"]
        rid = resource["id"]
        attachment = resource["metadata"]["attachment"]
        assert attachment["filename"] == "linear-regression.md"
        assert attachment["size_bytes"] > 0
        assert resource["content"].startswith("# Linear Regression")

        downloaded = app_client.get(f"/api/v1/teacher/resources/{rid}/download")
        assert downloaded.status_code == 200
        assert downloaded.content.startswith(b"# Linear Regression")

        # 发布到课程范围后，学生资源中心能看见同一资源并下载原始附件。
        student_resources = app_client.get(
            "/api/v1/resources/list", params={"user_id": "demo-student-1"},
        ).json()["resources"]
        assert rid in [item["id"] for item in student_resources]
        student_download = app_client.get(f"/api/v1/resources/{rid}/download")
        assert student_download.status_code == 200
        assert student_download.content.startswith(b"# Linear Regression")

        removed = app_client.delete(f"/api/v1/teacher/resources/{rid}")
        assert removed.json()["status"] == "deleted"
        assert app_client.get(f"/api/v1/teacher/resources/{rid}/download").status_code == 404

    def test_upload_for_one_student_respects_visibility(self, app_client: TestClient):
        upload = app_client.post(
            "/api/v1/teacher/resources/upload",
            data={
                "title": "小李补强练习",
                "resource_type": "quiz",
                "scope": "student",
                "status": "published",
                "target_user_ids": "demo-student-1",
            },
            files={"file": ("targeted-practice.txt", b"Practice only for one learner.", "text/plain")},
        )
        assert upload.status_code == 200, upload.text
        rid = upload.json()["resource_id"]

        visible = app_client.get(
            "/api/v1/resources/list", params={"user_id": "demo-student-1"},
        ).json()["resources"]
        assert rid in [item["id"] for item in visible]
        student_token = app_client.post("/api/v1/auth/login", json={
            "account": "demo-student-1", "password": "123456",
        }).json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        assert app_client.get(
            f"/api/v1/resources/{rid}/download",
            params={"user_id": "demo-student-1"},
            headers=student_headers,
        ).status_code == 200
        assert app_client.get(
            f"/api/v1/resources/{rid}/download",
            params={"user_id": "another-student"},
            headers=student_headers,
        ).status_code == 404
        assert app_client.get(
            "/api/v1/resources/list",
            params={"user_id": "another-student"},
            headers=student_headers,
        ).status_code == 403
        assert app_client.delete(f"/api/v1/teacher/resources/{rid}").json()["status"] == "deleted"

    def test_teacher_video_is_published_for_inline_student_playback(self, app_client: TestClient):
        # 路由层只验证受控类型、容量、元数据与跨端交付；真实编解码由浏览器/媒体层负责。
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42teacher-video-test"
        upload = app_client.post(
            "/api/v1/teacher/resources/upload",
            data={
                "title": "梯度下降板书讲解",
                "resource_type": "video",
                "scope": "course",
                "status": "published",
                "tags": "机器学习,教师讲解",
                "kp_ids": "kp_ml_basic",
            },
            files={"file": ("gradient-descent.mp4", fake_mp4, "video/mp4")},
        )
        assert upload.status_code == 200, upload.text
        resource = upload.json()["resource"]
        rid = resource["id"]
        attachment = resource["metadata"]["attachment"]
        assert resource["type"] == "video"
        assert resource["content_type"] == "video"
        assert attachment["media_type"] == "video/mp4"
        assert attachment["inline_preview"] is True

        student_resources = app_client.get(
            "/api/v1/resources/list", params={"user_id": "demo-student-1"},
        ).json()["resources"]
        assert rid in [item["id"] for item in student_resources]
        playback = app_client.get(f"/api/v1/resources/{rid}/download")
        assert playback.status_code == 200
        assert playback.headers["content-type"].startswith("video/mp4")
        assert playback.headers["content-disposition"].startswith("inline")
        assert playback.content == fake_mp4
        assert app_client.delete(f"/api/v1/teacher/resources/{rid}").json()["status"] == "deleted"


# ================================================================
# 3/4/5. 指派资源 / 推荐路径 / 发消息 → 群聊卡片
# ================================================================
class TestAssignmentsAndMessages:
    ROOM = "artificial_intelligence:demo-student-1"

    def test_assign_resource_writes_resource_card(self, app_client: TestClient):
        rid = app_client.post("/api/v1/teacher/resources", json={
            "title": "决策树案例代码", "type": "code", "scope": "course",
        }).json()["resource_id"]

        r = app_client.post("/api/v1/teacher/assignments/resource", json={
            "resource_id": rid,
            "user_id": "demo-student-1",
            "course": "artificial_intelligence",
            "note": "这份代码案例适合你，看完试着改写。",
        })
        assert r.status_code == 200, r.text
        assert r.json()["room_id"] == self.ROOM

        msgs = app_client.get(f"/api/v1/group-chat/{self.ROOM}/messages").json()["messages"]
        cards = [m for m in msgs if m["message_type"] == "resource_card"]
        assert cards and cards[-1]["payload"]["resource_id"] == rid
        assert cards[-1]["sender_role"] == "teacher"

        # 指派后学生个人可见
        visible = app_client.get(
            "/api/v1/resources/list", params={"user_id": "demo-student-1"},
        ).json()
        assert rid in [i["id"] for i in visible["resources"]]

    def test_assign_path_writes_path_card_and_path(self, app_client: TestClient):
        r = app_client.post("/api/v1/teacher/assignments/path", json={
            "user_id": "demo-student-1",
            "course": "artificial_intelligence",
            "title": "机器学习补强路径",
            "stages": ["线性回归", "逻辑回归", {"name": "神经网络", "desc": "重点"}],
            "note": "按这个顺序补，两周内完成。",
        })
        assert r.status_code == 200, r.text
        assigned_path = r.json()["path"]
        path_id = assigned_path["id"]
        assert assigned_path["course"] == "artificial_intelligence"
        assert assigned_path["recommended_role"] == "teacher"
        assert assigned_path["title"] == "机器学习补强路径"
        assert assigned_path["stages"][0]["title"] == assigned_path["stages"][0]["name"]
        assert assigned_path["stages"][2]["title"] == assigned_path["stages"][2]["name"]

        # 学生路径页能看到
        paths = app_client.get(
            "/api/v1/learning-path/list", params={"user_id": "demo-student-1"},
        ).json()["paths"]
        assert path_id in [p["id"] for p in paths]

        # 多阶段教师推荐应按教师指定的下一阶段继续。
        progressed = app_client.post(
            f"/api/v1/learning-path/{path_id}/progress",
            json={"stage_index": 0, "completed": True},
        ).json()["path"]
        assert len(progressed["stages"]) == 3
        assert progressed["current_stage"] == 1
        assert progressed["progress"] < 100
        assert progressed["stages"][1]["title"] == "逻辑回归"
        assert "generated_from" not in progressed["stages"][1]

        # 群聊出现路径卡片
        msgs = app_client.get(f"/api/v1/group-chat/{self.ROOM}/messages").json()["messages"]
        cards = [m for m in msgs if m["message_type"] == "path_card"]
        assert cards and cards[-1]["payload"]["path_id"] == path_id
        assert cards[-1]["payload"]["stages_count"] == 3

    def test_single_stage_teacher_path_continues_after_completion(self, app_client: TestClient):
        assigned = app_client.post("/api/v1/teacher/assignments/path", json={
            "user_id": "demo-student-1",
            "course": "artificial_intelligence",
            "title": "线性回归单阶段补强",
            "stages": ["线性回归"],
        })
        assert assigned.status_code == 200, assigned.text
        path_id = assigned.json()["path"]["id"]
        progressed = app_client.post(
            f"/api/v1/learning-path/{path_id}/progress",
            json={"stage_index": 0, "completed": True},
        ).json()["path"]
        assert len(progressed["stages"]) == 3
        assert progressed["stages"][1]["generated_from"] == "teacher_path_continuation"
        assert progressed["title"] == "线性回归单阶段补强"

    def test_teacher_message(self, app_client: TestClient):
        r = app_client.post("/api/v1/teacher/messages", json={
            "user_id": "demo-student-1",
            "course": "artificial_intelligence",
            "content": "这周的错题记得复盘。",
            "sender_name": "王老师",
        })
        assert r.status_code == 200
        msgs = app_client.get(f"/api/v1/group-chat/{self.ROOM}/messages").json()["messages"]
        teacher_msgs = [m for m in msgs if m["message_type"] == "teacher_message"]
        assert teacher_msgs and teacher_msgs[-1]["content"] == "这周的错题记得复盘。"

    def test_group_chat_post_and_incremental_read(self, app_client: TestClient):
        r = app_client.post(f"/api/v1/group-chat/{self.ROOM}/messages", json={
            "sender_id": "demo-student-1",
            "sender_name": "演示学习者",
            "sender_role": "student",
            "content": "老师收到，我今晚看。",
        })
        assert r.status_code == 200
        ts = r.json()["message"]["created_at"]
        # after 增量拉取：拉不到自己（严格大于）
        inc = app_client.get(
            f"/api/v1/group-chat/{self.ROOM}/messages", params={"after": ts},
        ).json()
        assert all(m["created_at"] > ts for m in inc["messages"])

    def test_invalid_room_and_role(self, app_client: TestClient):
        r = app_client.post(f"/api/v1/group-chat/{self.ROOM}/messages", json={
            "sender_role": "hacker", "content": "x",
        })
        assert r.status_code == 400


# ================================================================
# 学情分析聚合
# ================================================================
class TestStudentSummary:
    def test_students_list_contains_demo(self, app_client: TestClient):
        r = app_client.get("/api/v1/teacher/students")
        assert r.status_code == 200
        assert "demo-student-1" in [s["user_id"] for s in r.json()["students"]]

    def test_summary_aggregates_blocks(self, app_client: TestClient):
        r = app_client.get("/api/v1/teacher/students/demo-student-1/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        expected = {"profile", "mastery", "mistakes", "paths", "resources", "risks"}
        assert expected <= set(data.keys())
        # 前面测试推过路径，这里应能聚合到
        assert any(p.get("title") == "机器学习补强路径" for p in data["paths"])


# ================================================================
# 6/7. 配置型 Agent
# ================================================================
@pytest.fixture()
def paper_agent_key(app_client: TestClient) -> str:
    """确保「论文助教」存在且启用（用例可独立运行，不依赖执行顺序）。"""
    from backend.app.services.agent_config_service import get_agent_config_service

    svc = get_agent_config_service()
    hit = svc.find_mentioned("@论文助教 ping")
    if hit is None:
        r = app_client.post("/api/v1/teacher/agents", json={
            "name": "论文助教",
            "title": "论文写作助手",
            "system_prompt": "你是论文写作助教，帮学生梳理论文结构。",
            "capabilities": ["论文结构", "文献综述"],
        })
        assert r.status_code == 200, r.text
        return r.json()["agent"]["key"]
    svc.update(hit["key"], {"enabled": True})
    return hit["key"]


class TestConfigurableAgents:
    def test_builtin_agents_seeded(self, app_client: TestClient):
        r = app_client.get("/api/v1/teacher/agents")
        agents = r.json()["agents"]
        builtin_names = {a["name"] for a in agents if a["builtin"]}
        assert {"智狐", "智灵", "阿匠", "小龙", "团团", "球球"} <= builtin_names

    def test_builtin_prompt_not_editable_but_display_is(self, app_client: TestClient):
        r = app_client.patch("/api/v1/teacher/agents/tutor", json={
            "title": "首席讲师", "system_prompt": "HACK",
        })
        assert r.status_code == 200
        agent = r.json()["agent"]
        assert agent["title"] == "首席讲师"
        assert agent["system_prompt"] == ""  # 内置 prompt 不可改

    def test_create_custom_agent_and_mention(self, app_client: TestClient, paper_agent_key: str):
        # 重名拒绝
        dup = app_client.post("/api/v1/teacher/agents", json={"name": "论文助教"})
        assert dup.status_code == 400

        # @识别命中
        from backend.app.services.agent_config_service import get_agent_config_service
        hit = get_agent_config_service().find_mentioned("@论文助教 帮我列个提纲")
        assert hit is not None and hit["key"] == paper_agent_key
        assert hit["builtin"] is False

    @pytest.mark.asyncio
    async def test_orchestrator_routes_mention_to_configurable(
        self, app_client: TestClient, paper_agent_key: str, mock_llm_client,
    ):
        from backend.app.agents.orchestrator import AgentOrchestrator

        orch = AgentOrchestrator(mock_llm_client)
        results = await orch.process_turn(
            user_input="@论文助教 我的开题报告怎么写？",
            profile={}, context={}, session_id="t-1",
        )
        assert "cfg_0" in results
        resp = results["cfg_0"]
        assert resp.success
        assert "[MOCK]" in resp.content
        assert resp.metadata.get("configurable") is True

    @pytest.mark.asyncio
    async def test_disabled_agent_declines(
        self, app_client: TestClient, paper_agent_key: str, mock_llm_client,
    ):
        from backend.app.services.agent_config_service import get_agent_config_service
        svc = get_agent_config_service()
        svc.update(paper_agent_key, {"enabled": False})

        from backend.app.agents.orchestrator import AgentOrchestrator
        orch = AgentOrchestrator(mock_llm_client)
        results = await orch.process_turn(
            user_input="@论文助教 在吗", profile={}, context={}, session_id="t-2",
        )
        resp = results["cfg_0"]
        assert resp.metadata.get("disabled") is True
        assert "停用" in resp.content
        # 恢复启用，避免影响其他用例
        svc.update(paper_agent_key, {"enabled": True})

    def test_builtin_not_deletable(self, app_client: TestClient):
        r = app_client.delete("/api/v1/teacher/agents/tutor")
        assert r.status_code == 400


# ================================================================
# 8. 班级学情看板
# ================================================================
@pytest.fixture()
def class_board_seed(app_client: TestClient) -> dict:
    """造两名对照学生：a 弱且久未活跃（高风险）、b 强且近期活跃（幂等，可乱序运行）。"""
    import time as _time

    from backend.app.core.database import SessionLocal
    from backend.app.core.models import (
        AssessmentRecord,
        BktStateRecord,
        KnowledgePointRecord,
        MistakeRecord,
    )

    now = _time.time()
    with SessionLocal() as db:
        already = (
            db.query(BktStateRecord)
            .filter(BktStateRecord.user_id == "class-demo-a")
            .first()
        )
        if already is None:
            db.add_all([
                KnowledgePointRecord(
                    id="kp_class_demo_1", course="artificial_intelligence",
                    name="班级演示知识点一",
                ),
                KnowledgePointRecord(
                    id="kp_class_demo_2", course="artificial_intelligence",
                    name="班级演示知识点二",
                ),
                # a 弱：两 kp 均低
                BktStateRecord(user_id="class-demo-a", knowledge_point_id="kp_class_demo_1", p_learned=0.2),
                BktStateRecord(user_id="class-demo-a", knowledge_point_id="kp_class_demo_2", p_learned=0.3),
                # b 强：kp1 中等 / kp2 高 → kp1 班级均值更低
                BktStateRecord(user_id="class-demo-b", knowledge_point_id="kp_class_demo_1", p_learned=0.5),
                BktStateRecord(user_id="class-demo-b", knowledge_point_id="kp_class_demo_2", p_learned=0.9),
                # a 久未活跃（40 天前）；b 一小时前做题得 85 分
                AssessmentRecord(user_id="class-demo-a", record_type="quiz", score=40.0, timestamp=now - 40 * 24 * 3600),
                AssessmentRecord(user_id="class-demo-b", record_type="quiz", score=85.0, timestamp=now - 3600),
            ])
            db.add_all([
                MistakeRecord(
                    id=f"class_demo_mis_{i}", user_id="class-demo-a",
                    knowledge_point_id="kp_class_demo_1",
                    error_type="概念混淆" if i < 6 else "计算失误",
                    question_data={"question": f"演示错题{i}"},
                )
                for i in range(10)
            ])
            db.commit()
    return {"now": now}


class TestClassAnalytics:
    URL = "/api/v1/teacher/analytics/class"

    def test_class_analytics_aggregation(self, app_client: TestClient, class_board_seed: dict):
        r = app_client.get(self.URL)
        assert r.status_code == 200, r.text
        data = r.json()

        # KPI：至少包含 demo-student-1 + 两名种子学生
        assert data["student_count"] >= 3
        assert data["mistakes_open_total"] >= 10
        assert data["mastery"]["overall_avg"] is not None

        # 薄弱知识点按均值升序，kp1(0.35) 排在 kp2(0.6) 前
        weak_ids = [k["kp_id"] for k in data["weak_kps"]]
        assert "kp_class_demo_1" in weak_ids and "kp_class_demo_2" in weak_ids
        assert weak_ids.index("kp_class_demo_1") < weak_ids.index("kp_class_demo_2")
        kp1 = next(k for k in data["weak_kps"] if k["kp_id"] == "kp_class_demo_1")
        assert kp1["kp_name"] == "班级演示知识点一"
        assert abs(kp1["avg_mastery"] - 0.35) < 1e-6
        assert kp1["students_tracked"] == 2 and kp1["students_below_60"] == 2
        assert kp1["mistake_count"] == 10

        # 错因分布：概念混淆(6) 居首
        assert data["error_distribution"][0]["category"] == "概念混淆"
        assert data["error_distribution"][0]["count"] >= 6

        # 活跃度分桶
        assert "class-demo-b" in data["activity"]["active_7d"]
        assert "class-demo-a" in data["activity"]["inactive_30p"]

        # 风险学生：a 命中掌握度低 + 错题积压 + 不活跃 → high
        risk_a = next((s for s in data["risk_students"] if s["user_id"] == "class-demo-a"), None)
        assert risk_a is not None and risk_a["level"] == "high"
        assert len(risk_a["reasons"]) >= 2

        # 趋势：b 一小时前的活动在 30 天窗口内，归一化均分 0.85
        assert data["mastery"]["trend"]
        latest = data["mastery"]["trend"][-1]
        assert latest["activity_count"] >= 1
        assert latest["avg_score"] is not None and 0.0 < latest["avg_score"] <= 1.0

    def test_class_analytics_params(self, app_client: TestClient, class_board_seed: dict):
        r = app_client.get(self.URL, params={"weak_top": 1, "risk_top": 1})
        assert r.status_code == 200
        data = r.json()
        assert len(data["weak_kps"]) <= 1
        assert len(data["risk_students"]) <= 1
        # risk_top=1 时留下的必须是最高级别
        if data["risk_students"]:
            assert data["risk_students"][0]["level"] == "high"

    def test_class_analytics_requires_teacher_role(self, app_client: TestClient):
        token = app_client.post("/api/v1/auth/login", json={
            "account": "demo-student-1", "password": "123456",
        }).json()["access_token"]
        r = app_client.get(self.URL, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


# ================================================================
# 9. 教学共创：教师数据快照接入既有 Agent 流水线
# ================================================================
class TestTeachingCopilot:
    URL = "/api/v1/teacher/copilot/consult"

    def test_class_copilot_passes_compact_snapshot_to_pipeline(
        self, app_client: TestClient, class_board_seed: dict, monkeypatch,
    ):
        from backend.app.api.v1 import chat

        captured = {}

        async def fake_process_turn(session_id, session, message, course, **kwargs):
            captured.update({
                "session_id": session_id,
                "session": dict(session),
                "message": message,
                "course": course,
                "kwargs": kwargs,
            })
            return {
                "session_id": session_id,
                "primary_agent": "path_planner",
                "content": "## 教学建议\n\n先处理基础薄弱知识点。",
                "content_type": "markdown",
                "agents_invoked": [
                    {"name": "evaluator", "success": True, "content_type": "evaluation"},
                    {"name": "path_planner", "success": True, "content_type": "learning_path"},
                ],
                "safety": {"level": "pass", "reason": ""},
                "success": True,
            }

        monkeypatch.setattr(chat, "_process_turn", fake_process_turn)
        response = app_client.post(self.URL, json={"action": "class_diagnosis"})

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["action_label"] == "班级学情诊断"
        assert data["scope"] == "class"
        assert data["snapshot"]["student_count"] >= 3
        assert data["snapshot"]["weak_knowledge_points"]
        assert "@团团" in captured["message"] and "@智狐" in captured["message"]
        assert captured["session"]["role_view"] == "teacher"
        assert captured["session"]["user_id"] == "teacher"
        assert captured["session"]["teacher_context"]["scope"] == "class"

    def test_copilot_validates_student_scope_and_action(self, app_client: TestClient):
        missing_student = app_client.post(self.URL, json={
            "action": "student_intervention", "scope": "student",
        })
        assert missing_student.status_code == 400
        assert missing_student.json()["detail"] == "student_id_required"

        invalid_action = app_client.post(self.URL, json={"action": "anything"})
        assert invalid_action.status_code == 400
        assert invalid_action.json()["detail"] == "invalid_copilot_action"

        removed_resource_draft = app_client.post(self.URL, json={"action": "resource_draft"})
        assert removed_resource_draft.status_code == 400
        assert removed_resource_draft.json()["detail"] == "invalid_copilot_action"
