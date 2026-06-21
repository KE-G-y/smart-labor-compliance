from conftest import assert_ok, unique


def _create_chat(client, api_base_url, user_id):
    payload = assert_ok(
        client.post(
            f"{api_base_url}/api/chat",
            json={"question": "员工身份证号 610103199001011234 能否直接进入知识库？", "user_id": user_id},
            timeout=20,
        )
    )
    return payload["data"]["question_id"]


def test_feedback_lifecycle_and_remark_sanitization(client, api_base_url, tenant_headers):
    user_id = unique("feedback-user")
    question_id = _create_chat(client, api_base_url, user_id)

    created = assert_ok(
        client.post(
            f"{api_base_url}/api/feedback",
            json={
                "question_id": question_id,
                "user_id": user_id,
                "is_helpful": False,
                "remark": "请联系 13812345678 或 hr@example.com 复核",
            },
            timeout=10,
        )
    )
    feedback_id = created["data"]["id"]

    feedbacks = assert_ok(
        client.get(f"{api_base_url}/api/admin/feedbacks", headers=tenant_headers, params={"is_helpful": False}, timeout=10)
    )
    row = next(item for item in feedbacks["data"]["list"] if item["id"] == feedback_id)
    assert "13812345678" not in row["remark"]
    assert "hr@example.com" not in row["remark"]
    assert "[手机号已脱敏]" in row["remark"]
    assert "[邮箱已脱敏]" in row["remark"]

    updated = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/feedbacks/{feedback_id}",
            headers=tenant_headers,
            json={"status": "resolved"},
            timeout=10,
        )
    )
    assert updated["message"] == "反馈更新成功"

    invalid = client.put(
        f"{api_base_url}/api/admin/feedbacks/{feedback_id}",
        headers=tenant_headers,
        json={"status": "closed"},
        timeout=10,
    )
    assert invalid.status_code == 400


def test_feedback_rejects_cross_tenant_or_missing_question(client, api_base_url):
    missing = client.post(
        f"{api_base_url}/api/feedback",
        json={"question_id": 99999999, "is_helpful": True},
        timeout=10,
    )
    assert missing.status_code == 404

    bad_tenant = client.post(
        f"{api_base_url}/api/feedback",
        json={"tenant_code": "not-exists", "is_helpful": True},
        timeout=10,
    )
    assert bad_tenant.status_code == 404


def test_admin_authentication_boundaries(client, api_base_url, tenant_headers):
    unauthenticated = client.get(f"{api_base_url}/api/admin/sources", timeout=10)
    assert unauthenticated.status_code == 401

    malformed = client.get(f"{api_base_url}/api/admin/verify-token", headers={"Authorization": "Bearer"}, timeout=10)
    assert malformed.status_code == 401

    wrong_scheme = client.get(f"{api_base_url}/api/admin/verify-token", headers={"Authorization": "Basic abc"}, timeout=10)
    assert wrong_scheme.status_code == 401

    bad_login = client.post(
        f"{api_base_url}/api/admin/login",
        json={"username": "admin", "password": "wrong"},
        timeout=10,
    )
    assert bad_login.status_code == 401

    verified = assert_ok(client.get(f"{api_base_url}/api/admin/verify-token", headers=tenant_headers, timeout=10))
    assert verified["data"]["username"] == "tenant_admin"
    assert "password" not in verified["data"]


def test_tenant_admin_cannot_cross_tenant_or_create_super_admin(client, api_base_url, super_headers, tenant_headers):
    tenant_code = unique("tenant")
    created = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/tenants",
            headers=super_headers,
            json={"code": tenant_code, "name": "自动化边界租户"},
            timeout=10,
        )
    )
    other_tenant_id = created["data"]["id"]

    forbidden = client.get(
        f"{api_base_url}/api/admin/sources",
        headers=tenant_headers,
        params={"tenant_id": other_tenant_id},
        timeout=10,
    )
    assert forbidden.status_code == 403

    create_super = client.post(
        f"{api_base_url}/api/admin/admins",
        headers=tenant_headers,
        json={"username": unique("bad-super"), "password": "Password@123", "role": "super_admin"},
        timeout=10,
    )
    assert create_super.status_code == 403


def test_tenant_listing_hides_dify_api_key_and_blank_update_preserves_existing_key(client, api_base_url, super_headers):
    tenant_code = unique("tenant-key")
    created = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/tenants",
            headers=super_headers,
            json={"code": tenant_code, "name": "自动化密钥租户"},
            timeout=10,
        )
    )
    tenant_id = created["data"]["id"]

    updated = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/tenants/{tenant_id}",
            headers=super_headers,
            json={"dify_api_key": "tenant-secret-key"},
            timeout=10,
        )
    )
    assert updated["data"]["dify_configured"] is True
    assert "dify_api_key" not in updated["data"]

    listed = assert_ok(
        client.get(f"{api_base_url}/api/admin/tenants", headers=super_headers, params={"keyword": tenant_code}, timeout=10)
    )
    row = listed["data"]["list"][0]
    assert row["dify_configured"] is True
    assert "dify_api_key" not in row
    assert "tenant-secret-key" not in str(listed["data"])

    renamed = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/tenants/{tenant_id}",
            headers=super_headers,
            json={"name": "自动化密钥租户已改名"},
            timeout=10,
        )
    )
    assert renamed["data"]["dify_configured"] is True

    cleared = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/tenants/{tenant_id}",
            headers=super_headers,
            json={"dify_api_key": None},
            timeout=10,
        )
    )
    assert cleared["data"]["dify_configured"] is False


def test_viewer_role_is_read_only_for_source_feedback_and_package_modules(client, api_base_url, tenant_headers):
    username = unique("viewer")
    created = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/admins",
            headers=tenant_headers,
            json={"username": username, "password": "Password@123", "role": "viewer"},
            timeout=10,
        )
    )
    assert created["data"]["role"] == "viewer"

    login = client.post(
        f"{api_base_url}/api/admin/login",
        json={"username": username, "password": "Password@123", "tenant_code": "demo-sx"},
        timeout=10,
    )
    assert login.status_code == 200, login.text
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}", "X-Tenant-Code": "demo-sx"}

    allowed_logs = client.get(f"{api_base_url}/api/admin/logs", headers=viewer_headers, timeout=10)
    assert allowed_logs.status_code == 200

    forbidden_calls = [
        ("get", "/api/admin/sources", None),
        ("post", "/api/admin/sources", {"title": "viewer source", "url": "https://example.com"}),
        ("get", "/api/admin/feedbacks", None),
        ("get", "/api/admin/knowledge-packages", None),
        ("get", "/api/admin/test-questions", None),
    ]
    for method, path, json_body in forbidden_calls:
        response = getattr(client, method)(f"{api_base_url}{path}", headers=viewer_headers, json=json_body, timeout=10)
        assert response.status_code == 403, f"{method.upper()} {path} returned {response.status_code}: {response.text}"
