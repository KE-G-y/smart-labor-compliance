import csv
import io
import time

from conftest import assert_ok, unique


def test_faq_crud_duplicate_upsert_import_export_and_batch(client, api_base_url, tenant_headers):
    faq_code = unique("FAQAUTO")
    created = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs",
            headers=tenant_headers,
            json={
                "faq_code": faq_code,
                "question": f"{faq_code} 试用期工资是否能低于最低工资？",
                "answer": "不能低于当地最低工资标准。",
                "category": "工资",
                "risk_level": "high",
                "keywords": ["试用期", "最低工资"],
            },
            timeout=10,
        )
    )
    faq_id = created["data"]["id"]

    duplicate = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs",
            headers=tenant_headers,
            json={
                "faq_code": faq_code,
                "question": f"{faq_code} 试用期工资是否能低于最低工资？",
                "answer": "重复导入时应覆盖更新。",
                "category": "工资",
            },
            timeout=10,
        )
    )
    assert duplicate["data"]["id"] == faq_id
    assert "覆盖更新" in duplicate["message"]

    listed = assert_ok(
        client.get(f"{api_base_url}/api/admin/faqs", headers=tenant_headers, params={"keyword": faq_code}, timeout=10)
    )
    assert listed["data"]["total"] == 1

    csv_body = "faq_code,question,answer,category,risk_level\nAUTO_IMPORT,自动导入FAQ问题,自动导入FAQ答案,社保,medium\n,Bad row,,,\n"
    imported = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs/import",
            headers=tenant_headers,
            files={"file": ("faqs.csv", csv_body.encode("utf-8-sig"), "text/csv")},
            timeout=10,
        )
    )
    assert imported["data"]["imported"] >= 1
    assert imported["data"]["skipped"] == 1

    exported = client.get(f"{api_base_url}/api/admin/faqs/export", headers=tenant_headers, timeout=10)
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert any(row["faq_code"] == faq_code for row in rows)

    invalid_batch = client.post(
        f"{api_base_url}/api/admin/faqs/batch",
        headers=tenant_headers,
        json={"ids": [faq_id], "action": "set_risk", "risk_level": "critical"},
        timeout=10,
    )
    assert invalid_batch.status_code == 400

    batch = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs/batch",
            headers=tenant_headers,
            json={"ids": [faq_id], "action": "set_risk", "risk_level": "low"},
            timeout=10,
        )
    )
    assert batch["data"]["affected"] == 1


def test_source_upload_crud_review_guards_import_export_and_batch(client, api_base_url, tenant_headers):
    missing_path = client.post(
        f"{api_base_url}/api/admin/sources",
        headers=tenant_headers,
        json={"title": "无来源路径"},
        timeout=10,
    )
    assert missing_path.status_code == 422

    bad_upload = client.post(
        f"{api_base_url}/api/admin/sources/upload",
        headers=tenant_headers,
        files={"file": ("evil.exe", b"no", "application/octet-stream")},
        timeout=10,
    )
    assert bad_upload.status_code == 400

    upload = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources/upload",
            headers=tenant_headers,
            files={"file": ("../../policy.pdf", b"policy", "application/pdf")},
            timeout=10,
        )
    )
    assert upload["data"]["local_file"].startswith("tenant_")
    assert ".." not in upload["data"]["local_file"]

    source_code = unique("SRCAUTO")
    created = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources",
            headers=tenant_headers,
            json={
                "source_code": source_code,
                "title": f"{source_code} 陕西政策来源",
                "url": f"https://example.com/{source_code}",
                "issuer": "自动化测试",
                "review_status": "待人工复核",
            },
            timeout=10,
        )
    )
    source_id = created["data"]["id"]

    reviewed = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/sources/{source_id}",
            headers=tenant_headers,
            json={"review_status": "已复核"},
            timeout=10,
        )
    )
    assert reviewed["data"]["reviewed_at"]
    assert reviewed["data"]["reviewed_by"]

    locked = client.put(
        f"{api_base_url}/api/admin/sources/{source_id}",
        headers=tenant_headers,
        json={"title": "已复核后不应编辑"},
        timeout=10,
    )
    assert locked.status_code == 400

    csv_body = "source_code,title,url,issuer,review_status\nSRC_IMPORT,CSV来源,https://example.com/src-import,自动化测试,待人工复核\n,Bad,,,\n"
    imported = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources/import",
            headers=tenant_headers,
            files={"file": ("sources.csv", csv_body.encode("utf-8-sig"), "text/csv")},
            timeout=10,
        )
    )
    assert imported["data"]["imported"] >= 1
    assert imported["data"]["skipped"] == 1

    non_csv = client.post(
        f"{api_base_url}/api/admin/sources/import",
        headers=tenant_headers,
        files={"file": ("sources.txt", b"title,url\nbad,https://example.com", "text/plain")},
        timeout=10,
    )
    assert non_csv.status_code == 400

    exported = client.get(f"{api_base_url}/api/admin/sources/export", headers=tenant_headers, timeout=10)
    assert exported.status_code == 200
    assert "source_code" in exported.content.decode("utf-8-sig").splitlines()[0]

    batch_missing = client.post(
        f"{api_base_url}/api/admin/sources/batch",
        headers=tenant_headers,
        json={"ids": [], "action": "delete"},
        timeout=10,
    )
    assert batch_missing.status_code == 400


def test_knowledge_packages_status_import_export_batch_and_test_questions(client, api_base_url, tenant_headers):
    packages = assert_ok(client.get(f"{api_base_url}/api/admin/knowledge-packages", headers=tenant_headers, timeout=10))
    assert packages["data"]["total"] >= 1
    package_id = packages["data"]["list"][0]["id"]

    invalid_status = client.put(
        f"{api_base_url}/api/admin/knowledge-packages/{package_id}/status",
        headers=tenant_headers,
        json={"status": "archived"},
        timeout=10,
    )
    assert invalid_status.status_code == 400

    updated = assert_ok(
        client.put(
            f"{api_base_url}/api/admin/knowledge-packages/{package_id}/status",
            headers=tenant_headers,
            json={"status": "active"},
            timeout=10,
        )
    )
    assert updated["message"] == "状态更新成功"

    csv_body = "name,region,version,status,categories\n自动化知识包,陕西,v-test,active,社保|工资\n"
    imported = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/knowledge-packages/import",
            headers=tenant_headers,
            files={"file": ("packages.csv", csv_body.encode("utf-8-sig"), "text/csv")},
            timeout=10,
        )
    )
    assert imported["data"]["imported"] >= 1

    exported = client.get(f"{api_base_url}/api/admin/knowledge-packages/export", headers=tenant_headers, timeout=10)
    assert exported.status_code == 200
    assert "knowledge-packages.csv" in exported.headers.get("content-disposition", "")

    test_questions = assert_ok(client.get(f"{api_base_url}/api/admin/test-questions", headers=tenant_headers, timeout=10))
    assert test_questions["data"]["total"] >= 4


def test_admin_catalog_lists_return_newest_records_first(client, api_base_url, tenant_headers):
    faq_prefix = unique("ORDER_FAQ")
    first_faq = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs",
            headers=tenant_headers,
            json={
                "faq_code": f"{faq_prefix}_1",
                "question": f"{faq_prefix} 第一条排序测试问题",
                "answer": "第一条排序测试答案",
            },
            timeout=10,
        )
    )["data"]
    time.sleep(1)
    second_faq = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/faqs",
            headers=tenant_headers,
            json={
                "faq_code": f"{faq_prefix}_2",
                "question": f"{faq_prefix} 第二条排序测试问题",
                "answer": "第二条排序测试答案",
            },
            timeout=10,
        )
    )["data"]

    faqs = assert_ok(
        client.get(
            f"{api_base_url}/api/admin/faqs",
            headers=tenant_headers,
            params={"keyword": faq_prefix, "page": 1, "page_size": 10},
            timeout=10,
        )
    )["data"]["list"]
    assert [item["id"] for item in faqs[:2]] == [second_faq["id"], first_faq["id"]]

    source_prefix = unique("ORDER_SRC")
    first_source = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources",
            headers=tenant_headers,
            json={
                "source_code": f"{source_prefix}_1",
                "title": f"{source_prefix} 第一条排序测试来源",
                "url": f"https://example.com/{source_prefix}/1",
            },
            timeout=10,
        )
    )["data"]
    time.sleep(1)
    second_source = assert_ok(
        client.post(
            f"{api_base_url}/api/admin/sources",
            headers=tenant_headers,
            json={
                "source_code": f"{source_prefix}_2",
                "title": f"{source_prefix} 第二条排序测试来源",
                "url": f"https://example.com/{source_prefix}/2",
            },
            timeout=10,
        )
    )["data"]

    sources = assert_ok(
        client.get(
            f"{api_base_url}/api/admin/sources",
            headers=tenant_headers,
            params={"keyword": source_prefix, "page": 1, "page_size": 10},
            timeout=10,
        )
    )["data"]["list"]
    assert [item["id"] for item in sources[:2]] == [second_source["id"], first_source["id"]]
