import unittest

import httpx

from models import ActionItem, MemberProfile, Team
from services.auth_service import SessionUserStore
from services.progress_service import member_progress_key
from services.supabase_service import SupabaseService
from services.workplan_service import add_contact, create_default_workplan, replace_weekly_goals


class SupabaseServiceTests(unittest.TestCase):
    def test_save_team_invite_uses_restricted_rpc(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(204)

        service = SupabaseService(
            "https://project.supabase.co",
            "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )

        service.save_team_invite(
            {"access_token": "access-token"},
            "TEAM-01",
            "INVITE123",
        )

        self.assertEqual(
            requests[0].url.path,
            "/rest/v1/rpc/getexpert_set_team_invite",
        )
        self.assertEqual(
            requests[0].read().decode(),
            '{"target_team_id":"TEAM-01","new_invite_code":"INVITE123"}',
        )

    def test_remove_team_member_uses_restricted_rpc(self) -> None:
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(204)

        service = SupabaseService(
            "https://project.supabase.co",
            "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )

        service.remove_team_member(
            {"access_token": "access-token"},
            "TEAM-01",
            "Member@Example.com",
        )

        self.assertEqual(
            requests[0].url.path,
            "/rest/v1/rpc/getexpert_remove_team_member",
        )
        self.assertEqual(
            requests[0].read().decode(),
            '{"target_team_id":"TEAM-01","target_member_email":"member@example.com"}',
        )

    def test_leader_query_filters_public_users_by_role(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/rest/v1/users")
            self.assertEqual(request.url.params["role"], "eq.Leader")
            self.assertEqual(request.url.params["order"], "full_name.asc")
            self.assertEqual(request.headers["authorization"], "Bearer access-token")
            return httpx.Response(200, json=[{
                "email": "mirthailandnetwork@gmail.com",
                "full_name": "MIR Thailand Network",
                "role": "Leader",
            }])

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )

        rows = service.list_users_by_role("Leader", "access-token")

        self.assertEqual(rows[0]["email"], "mirthailandnetwork@gmail.com")
        self.assertEqual(rows[0]["role"], "Leader")

    def test_login_succeeds_with_existing_schema_without_extra_plan_table(self) -> None:
        requested_paths = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested_paths.append(request.url.path)
            if request.url.path.endswith("/auth/v1/token"):
                return httpx.Response(200, json={
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "user": {"id": "user-1", "user_metadata": {"full_name": "สมาชิก"}},
                })
            if request.url.path.endswith("/rest/v1/users"):
                return httpx.Response(200, json=[{
                    "email": "member@example.com", "full_name": "สมาชิก", "role": "Member",
                }])
            if request.url.path.endswith("/rest/v1/teams"):
                return httpx.Response(200, json=[])
            if request.url.path.endswith("/rest/v1/member_profiles"):
                return httpx.Response(200, json=[])
            return httpx.Response(404, json={"code": "PGRST205", "message": "missing table"})

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        store = SessionUserStore({}, service)

        user = store.authenticate("member@example.com", "password")

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user.role, "Member")
        self.assertEqual(
            set(requested_paths),
            {"/auth/v1/token", "/rest/v1/users", "/rest/v1/teams", "/rest/v1/member_profiles"},
        )

    def test_sign_in_uses_supabase_auth_and_loads_role(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/auth/v1/token"):
                return httpx.Response(200, json={
                    "access_token": "access-token", "refresh_token": "refresh-token",
                    "user": {"id": "user-1", "user_metadata": {"full_name": "สมาชิก"}},
                })
            if request.url.path.endswith("/rest/v1/users"):
                self.assertEqual(request.headers["authorization"], "Bearer access-token")
                return httpx.Response(200, json=[{
                    "email": "leader@example.com", "full_name": "ผู้นำ ทีม", "role": "Leader",
                }])
            return httpx.Response(404)

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        user = service.sign_in("leader@example.com", "password")

        self.assertEqual(user["role"], "Leader")
        self.assertEqual(user["access_token"], "access-token")
        self.assertEqual(user["user_id"], "user-1")

    def test_schema_verification_reports_missing_tables(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/rest/v1/pp_scores"):
                return httpx.Response(404, json={"code": "PGRST205", "message": "missing"})
            return httpx.Response(200, json=[])

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        self.assertEqual(service.verify_schema(), ("pp_scores",))

    def test_load_user_data_restores_profile_crm_workplan_progress_and_chats(self) -> None:
        profile = MemberProfile(
            name="สมาชิก Supabase", occupation="เจ้าของกิจการ", team_name="ทีมถาวร",
            team_id="TEAM-SB", team_leader="หัวหน้าทีม", role="Member",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            table = request.url.path.rsplit("/", 1)[-1]
            params = dict(request.url.params)
            if table == "teams":
                return httpx.Response(200, json=[{
                    "team_id": "TEAM-SB", "team_data": Team("ทีมถาวร", "TEAM-SB", "หัวหน้าทีม").to_dict(),
                }])
            if table == "member_profiles":
                return httpx.Response(200, json=[{
                    "email": "member@example.com", "team_id": "TEAM-SB", "profile_data": profile.to_dict(),
                }])
            if table == "prospects":
                return httpx.Response(200, json=[{
                    "prospect_data": {"id": "p1", "name": "ผู้มุ่งหวัง A", "category": "A", "status": "นัดหมายแล้ว"},
                }])
            if table == "workplan_targets":
                return httpx.Response(200, json=[{
                    "target_type": "sponsor", "week": 1, "target": 4, "actual": 2,
                }])
            if table == "thirty_day_progress":
                return httpx.Response(200, json=[{
                    "day": 1,
                    "completed": True,
                    "profile_signature": ["สมาชิก Supabase", 25, "เจ้าของกิจการ", 1.0, 30000.0, "ยังไม่มีประสบการณ์"],
                    "plan_item": {
                        "day": 1, "phase": "เริ่มต้น", "focus": "วางเป้าหมาย",
                        "tasks": ["เขียนเป้าหมาย"], "success_metric": "เขียนเสร็จ",
                    },
                }])
            if table == "pp_scores":
                return httpx.Response(200, json=[{"pp_score": 10}])
            if table == "ai_chat_history":
                chat_type = params.get("chat_type")
                if chat_type == "eq.member":
                    return httpx.Response(200, json=[{
                        "role": "assistant", "content": "คำตอบเดิม", "sources": ["คู่มือ"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }])
                return httpx.Response(200, json=[{
                    "role": "user", "content": "คำถามทีม", "team_id": "TEAM-SB",
                    "created_at": "2026-01-01T00:00:00Z",
                }])
            if table == "content_history":
                return httpx.Response(200, json=[{"channel": "Facebook", "content": "โพสต์เดิม"}])
            return httpx.Response(200, json=[])

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        state = {}
        auth = {"email": "member@example.com", "access_token": "access-token"}

        service.load_user_data(state, auth)

        key = member_progress_key(profile)
        self.assertEqual(state["member_profile"]["name"], "สมาชิก Supabase")
        self.assertEqual(state["teams"]["TEAM-SB"]["name"], "ทีมถาวร")
        self.assertEqual(state["workplan_by_member"][key]["contacts"][0]["name"], "ผู้มุ่งหวัง A")
        self.assertEqual(state["workplan_by_member"][key]["goals"]["sponsor"][0]["actual"], 2)
        self.assertTrue(state["plan_completion_by_member"][key]["1"])
        self.assertEqual(state["pp_scores_by_member"][key], 10)
        self.assertEqual(state["action_plan"][0].focus, "วางเป้าหมาย")
        self.assertEqual(state["action_plan_signature"][0], "สมาชิก Supabase")
        self.assertEqual(state["coach_messages"][0]["content"], "คำตอบเดิม")
        self.assertEqual(state["team_coach_messages_by_team"]["TEAM-SB"][0]["content"], "คำถามทีม")
        self.assertEqual(state["content_history"][0]["content"], "โพสต์เดิม")

    def test_save_workplan_persists_prospects_and_weekly_targets(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path, request.content.decode("utf-8")))
            return httpx.Response(201 if request.method == "POST" else 204, json={})

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        workplan = add_contact(
            create_default_workplan(), {"id": "p1", "name": "ผู้มุ่งหวัง", "category": "A"}
        )
        workplan = replace_weekly_goals(
            workplan, "income", [{"week": 1, "target": 10000, "actual": 2500}]
        )
        service.save_workplan(
            {"email": "member@example.com", "access_token": "access-token"}, workplan
        )

        paths = [(method, path) for method, path, _ in calls]
        self.assertIn(("DELETE", "/rest/v1/prospects"), paths)
        self.assertIn(("POST", "/rest/v1/prospects"), paths)
        self.assertIn(("DELETE", "/rest/v1/workplan_targets"), paths)
        self.assertIn(("POST", "/rest/v1/workplan_targets"), paths)

    def test_save_action_plan_uses_progress_rows_and_preserves_completion(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path, request.content.decode("utf-8")))
            if request.method == "GET":
                return httpx.Response(200, json=[{"day": 1, "completed": True}])
            return httpx.Response(201, json={})

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        plan = [ActionItem(1, "เริ่มต้น", "วางเป้าหมาย", ("เขียนเป้าหมาย",), "เขียนเสร็จ")]

        service.save_action_plan(
            {"email": "member@example.com", "access_token": "access-token"},
            plan,
            ("สมาชิก", 30, "เจ้าของกิจการ"),
        )

        self.assertEqual(calls[0][0:2], ("GET", "/rest/v1/thirty_day_progress"))
        self.assertEqual(calls[1][0:2], ("POST", "/rest/v1/thirty_day_progress"))
        payload = calls[1][2].replace(" ", "")
        self.assertIn('"focus":"วางเป้าหมาย"', payload)
        self.assertIn('"completed":true', payload)

    def test_assign_leader_updates_user_role_and_member_profile(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path, dict(request.url.params), request.content.decode("utf-8")))
            return httpx.Response(201 if request.method == "POST" else 204, json={})

        service = SupabaseService(
            "https://project.supabase.co", "anon-key",
            httpx.Client(transport=httpx.MockTransport(handler)),
        )
        profile = MemberProfile(
            name="หัวหน้าทีม", occupation="เจ้าของกิจการ", team_name="ทีม A",
            team_id="TEAM-A", team_leader="หัวหน้าทีม", role="Leader",
        )

        service.assign_user_to_team(
            {"email": "admin@example.com", "access_token": "access-token"},
            "leader@example.com", profile, "Leader",
        )

        self.assertEqual(calls[0][0:2], ("PATCH", "/rest/v1/users"))
        self.assertEqual(calls[0][2]["email"], "eq.leader@example.com")
        self.assertIn('"role":"Leader"', calls[0][3].replace(" ", ""))
        self.assertEqual(calls[1][0:2], ("POST", "/rest/v1/member_profiles"))
        self.assertIn('"team_id":"TEAM-A"', calls[1][3].replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
