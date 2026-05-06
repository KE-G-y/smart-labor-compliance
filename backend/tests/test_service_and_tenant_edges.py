from io import BytesIO

from conftest import assert_ok, unique


def test_disabled_knowledge_package_short_circuits_external_and_local_faq(client, api_base_url, tenant_headers):
    packages = assert_ok(client.get(f"{api_base_url}/api/admin/knowledge-packages", headers=tenant_headers, timeout=10))
    package_ids = [item["id"] for item in packages["data"]["list"]]

    for package_id in package_ids:
        assert_ok(
            client.put(
                f"{api_base_url}/api/admin/knowledge-packages/{package_id}/status",
                headers=tenant_headers,
                json={"status": "disabled"},
                timeout=10,
            )
        )

    user_id = unique("disabled-package")
    response = assert_ok(
        client.post(
            f"{api_base_url}/api/chat",
            json={"question": "陕西产假多少天？", "user_id": user_id},
            timeout=20,
        )
    )
    assert response["data"]["provider"] == "knowledge_package_disabled"
    assert "知识包已停用" in response["data"]["answer"]

    for package_id in package_ids:
        assert_ok(
            client.put(
                f"{api_base_url}/api/admin/knowledge-packages/{package_id}/status",
                headers=tenant_headers,
                json={"status": "active"},
                timeout=10,
            )
        )


def test_source_duplicate_guard_is_tenant_scoped(client, api_base_url, super_headers, tenant_headers):
    source_code = unique("TENANT_SRC")
    title = f"{source_code} 同名来源"
    url = f"https://example.com/{source_code}"

    demo_source = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources",
            headers=tenant_headers,
            json={"source_code": source_code, "title": title, "url": url, "issuer": "自动化测试"},
            timeout=10,
        )
    )
    assert demo_source["data"]["source_code"] == source_code

    other_code = unique("tenant-edge")
    tenant = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/tenants",
            headers=super_headers,
            json={
                "code": other_code,
                "name": "自动化跨租户来源",
                "admin_username": f"{other_code}_admin",
                "admin_password": "Password@123",
            },
            timeout=10,
        )
    )

    other_source = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources",
            headers=super_headers,
            params={"tenant_id": tenant["data"]["id"]},
            json={"source_code": source_code, "title": title, "url": url, "issuer": "自动化测试"},
            timeout=10,
        )
    )
    assert other_source["data"]["tenant_id"] == tenant["data"]["id"]


def test_upload_size_limit_removes_oversized_file(client, api_base_url, tenant_headers):
    response = client.post(
        f"{api_base_url}/api/admin/sources/upload",
        headers=tenant_headers,
        files={"file": ("large.pdf", BytesIO(b"x" * 70000), "application/pdf")},
        timeout=10,
    )
    assert response.status_code == 413


def test_dify_stream_parser_handles_message_workflow_and_invalid_lines(api_base_url, monkeypatch):
    import os

    os.environ["DB_NAME"] = "employment_slc_auto_test"
    from app.database import SessionLocal
    from app.models import Tenant
    from app.services import dify_service
    from app.services.dify_service import ComplianceAnswerService

    class FakeResponse:
        def iter_lines(self, decode_unicode=True):
            lines = [
                'data: {"event":"message","task_id":"task-1","conversation_id":"conv-1","message_id":"msg-1","answer":"第一段"}',
                "data: not-json",
                'event: ping',
                'data: {"event":"message","answer":"第二段"}',
                'data: {"event":"message_end","metadata":{"retriever_resources":[{"document_name":"来源A","content":"摘要"}]}}',
            ]
            yield from lines

    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == "demo-sx").first()
        service = ComplianceAnswerService(db, tenant)
        parsed = service._consume_dify_stream(FakeResponse(), "gen-edge", "key", "user")

    assert parsed["answer"] == "第一段第二段"
    assert parsed["conversation_id"] == "conv-1"
    assert parsed["metadata"]["retriever_resources"][0]["document_name"] == "来源A"

    class StopResponse:
        status_code = 204
        text = ""

    monkeypatch.setattr(dify_service.requests, "post", lambda *args, **kwargs: StopResponse())
    assert ComplianceAnswerService.stop_generation("gen-edge") is True

    class WorkflowResponse:
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"event":"workflow_finished","data":{"outputs":{"answer":"工作流最终回答"}}}'

    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == "demo-sx").first()
        service = ComplianceAnswerService(db, tenant)
        workflow = service._consume_dify_stream(WorkflowResponse(), None, "key", "user")
    assert workflow["answer"] == "工作流最终回答"


def test_dify_answer_risk_level_takes_precedence_over_question_estimate(api_base_url):
    import os

    os.environ["DB_NAME"] = "employment_slc_auto_test"
    from app.database import SessionLocal
    from app.models import Tenant
    from app.services.dify_service import ComplianceAnswerService

    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == "demo-sx").first()
        service = ComplianceAnswerService(db, tenant)

        assert service._estimate_risk("公司不发工资怎么办") == "low"
        assert service._risk_from_answer("风险等级：高\n\n结论：公司拖欠工资属于严重风险。") == "high"
        assert service._risk_from_answer("初步风险等级为：中风险。建议复核。") == "medium"
        assert service._risk_from_answer("风险等级：low") == "low"


def test_dify_context_inputs_match_enhanced_workflow(api_base_url):
    import os

    os.environ["DB_NAME"] = "employment_slc_auto_test"
    from app.database import SessionLocal
    from app.models import Tenant
    from app.services.dify_service import ComplianceAnswerService

    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.code == "demo-sx").first()
        service = ComplianceAnswerService(db, tenant)

        context = service._normalize_context(
            answer_style="按清单输出，标注待核验项",
            user_goal="风险评估",
            urgency_level="今天需要处理",
            output_format="表格 + 结论",
            known_facts="员工已离职 30 天，企业未办理社保减员",
            verification_focus="西安市社保补缴口径",
        )
        inputs = service._build_dify_inputs("enterprise_hr", "陕西省", "西安市", context)

        assert inputs["tenant_code"] == "demo-sx"
        assert inputs["tenant_name"] == tenant.name
        assert inputs["region"] == "陕西省西安市"
        assert inputs["user_role"] == "企业HR"
        assert inputs["answer_style"] == "按清单输出，标注待核验项"
        assert inputs["user_goal"] == "风险评估"
        assert inputs["urgency_level"] == "今天需要处理"
        assert inputs["output_format"] == "表格 + 结论"
        assert inputs["known_facts"] == "员工已离职 30 天，企业未办理社保减员"
        assert inputs["verification_focus"] == "西安市社保补缴口径"

        prefix = service._with_context_prefix("回答正文", "enterprise_hr", "陕西省", "西安市", context)
        assert "适用角色：企业HR" in prefix
        assert "问题目标：风险评估" in prefix
        assert "重点核验：西安市社保补缴口径" in prefix
        assert "回答正文" in prefix
        assert service._dify_file_type("政策材料.rtf", "application/rtf") == "document"
        assert service._normalize_context()["answer_style"] == "结构清晰、结论先行、引用来源、明确风险等级和待核验项"
