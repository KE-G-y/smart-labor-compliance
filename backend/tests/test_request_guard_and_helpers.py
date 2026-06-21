from conftest import assert_ok


def test_request_body_size_limit_and_security_headers(client, api_base_url):
    response = client.post(
        f"{api_base_url}/api/chat",
        data="x" * 9000,
        headers={"Content-Type": "application/json", "X-Tenant-Code": "demo-sx"},
        timeout=10,
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "请求体过大"

    health = client.get(f"{api_base_url}/health", timeout=10)
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["X-Frame-Options"] == "DENY"
    assert health.headers["Referrer-Policy"] == "no-referrer"
    assert health.headers["Cache-Control"] == "no-store"


def test_service_status_hides_secret_values(client, api_base_url, super_headers):
    payload = assert_ok(client.get(f"{api_base_url}/api/admin/service-status", headers=super_headers, timeout=10))
    data = payload["data"]
    assert data["database"]["name"].endswith("auto_test")
    rendered = str(data)
    assert "Admin@123456" not in rendered
    assert "Tenant@123456" not in rendered
    assert "dify_api_key" not in rendered.lower()


def test_system_config_update_preserves_secret_semantics_and_skips_network_validation(
    client,
    api_base_url,
    super_headers,
):
    updated = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/system-config",
            headers=super_headers,
            json={
                "dify_base_url": "http://127.0.0.1:65500/v1",
                "dify_api_key": "global-dify-secret",
                "dify_timeout_seconds": 7,
                "langchain_base_url": "http://127.0.0.1:65503/v1",
                "langchain_api_key": "global-langchain-secret",
                "langchain_model": "gpt-4o-mini",
                "langchain_embedding_model": "bge-m3",
                "langchain_temperature": 0.1,
                "langchain_timeout_seconds": 9,
                "milvus_uri": "http://127.0.0.1:19530",
                "milvus_token": "milvus-secret",
                "milvus_collection": "slc_test_docs",
                "vector_search_mode": "hybrid",
                "vector_top_k": 5,
                "vector_chunk_size": 500,
                "vector_chunk_overlap": 50,
                "ragflow_web_url": "http://127.0.0.1:65501",
                "ragflow_api_key": "global-ragflow-secret",
            },
            timeout=10,
        )
    )
    assert updated["message"] == "配置更新成功"

    config = assert_ok(client.get(f"{api_base_url}/api/admin/system-config", headers=super_headers, timeout=10))
    assert config["data"]["dify_base_url"] == "http://127.0.0.1:65500/v1"
    assert config["data"]["dify_api_key_configured"] is True
    assert config["data"]["dify_timeout_seconds"] == 7
    assert config["data"]["langchain_base_url"] == "http://127.0.0.1:65503/v1"
    assert config["data"]["langchain_api_key_configured"] is True
    assert config["data"]["langchain_model"] == "gpt-4o-mini"
    assert config["data"]["langchain_embedding_model"] == "bge-m3"
    assert config["data"]["langchain_temperature"] == 0.1
    assert config["data"]["langchain_timeout_seconds"] == 9
    assert config["data"]["milvus_uri"] == "http://127.0.0.1:19530"
    assert config["data"]["milvus_token_configured"] is True
    assert config["data"]["milvus_collection"] == "slc_test_docs"
    assert config["data"]["vector_search_mode"] == "hybrid"
    assert config["data"]["vector_top_k"] == 5
    assert config["data"]["vector_chunk_size"] == 500
    assert config["data"]["vector_chunk_overlap"] == 50
    assert config["data"]["ragflow_api_key_configured"] is True

    assert_ok(
        client.put(
            f"{api_base_url}/api/admin/system-config",
            headers=super_headers,
            json={"dify_base_url": "http://127.0.0.1:65502/v1", "langchain_temperature": 1.2},
            timeout=10,
        )
    )
    config = assert_ok(client.get(f"{api_base_url}/api/admin/system-config", headers=super_headers, timeout=10))
    assert config["data"]["dify_base_url"] == "http://127.0.0.1:65502/v1"
    assert config["data"]["dify_api_key_configured"] is True
    assert config["data"]["langchain_api_key_configured"] is True
    assert config["data"]["langchain_temperature"] == 1.2

    assert_ok(
        client.put(
            f"{api_base_url}/api/admin/system-config",
            headers=super_headers,
            json={"dify_api_key": None, "langchain_api_key": None, "milvus_token": None},
            timeout=10,
        )
    )
    config = assert_ok(client.get(f"{api_base_url}/api/admin/system-config", headers=super_headers, timeout=10))
    assert config["data"]["dify_api_key_configured"] is False
    assert config["data"]["langchain_api_key_configured"] is False
    assert config["data"]["milvus_token_configured"] is False

    invalid_url = client.put(
        f"{api_base_url}/api/admin/system-config",
        headers=super_headers,
        json={"dify_base_url": "127.0.0.1/v1"},
        timeout=10,
    )
    assert invalid_url.status_code == 400

    invalid_timeout = client.put(
        f"{api_base_url}/api/admin/system-config",
        headers=super_headers,
        json={"dify_timeout_seconds": 3},
        timeout=10,
    )
    assert invalid_timeout.status_code == 400

    invalid_temperature = client.put(
        f"{api_base_url}/api/admin/system-config",
        headers=super_headers,
        json={"langchain_temperature": 2.5},
        timeout=10,
    )
    assert invalid_temperature.status_code == 400

    invalid_chunk_size = client.put(
        f"{api_base_url}/api/admin/system-config",
        headers=super_headers,
        json={"vector_chunk_size": 100},
        timeout=10,
    )
    assert invalid_chunk_size.status_code == 400


def test_stop_generation_without_registered_task_is_safe(client, api_base_url):
    payload = assert_ok(
        client.post(
            f"{api_base_url}/api/chat/stop",
            json={"generation_id": "not-registered", "tenant_code": "demo-sx"},
            timeout=10,
        )
    )
    assert payload["data"]["stopped"] is False
