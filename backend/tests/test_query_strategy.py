from io import BytesIO
from types import SimpleNamespace

import pytest
import requests

from app.schemas.chat import ChatResponse
from app.services.dify_service import ChatAttachment, ComplianceAnswerService, dify_attachment_capability
from app.services.runtime_config import DEFAULT_QUERY_STRATEGY, normalize_config_update


def _service_with_strategy(strategy: str) -> ComplianceAnswerService:
    service = ComplianceAnswerService.__new__(ComplianceAnswerService)
    service.db = SimpleNamespace()
    service.tenant = SimpleNamespace(
        id=1,
        code="demo-sx",
        name="演示租户",
        region="陕西省",
        dify_api_key="",
    )
    service.runtime_config = SimpleNamespace(
        query_strategy=strategy,
        dify_api_key="dify-key",
        langchain_api_key="langchain-key",
    )
    service.last_dify_error = None
    service.last_langchain_error = None
    return service


def _patch_common_service_guards(monkeypatch, service: ComplianceAnswerService) -> None:
    monkeypatch.setattr(service, "_has_active_package", lambda: True)
    monkeypatch.setattr(service, "_has_knowledge_evidence", lambda question, language: True)
    monkeypatch.setattr(
        service,
        "_knowledge_boundary_fallback",
        lambda question, language, allow_fallback=True: ChatResponse(
            answer="知识库边界回答",
            sources=None,
            related_tasks=[],
            response_time=0,
            provider="kb_no_match",
            risk_level="medium",
            suggestions=[],
        ),
    )


def test_query_strategy_config_accepts_only_known_values():
    assert normalize_config_update("query_strategy", "dify_only") == "dify_only"
    assert normalize_config_update("query_strategy", "") == DEFAULT_QUERY_STRATEGY

    with pytest.raises(ValueError):
        normalize_config_update("query_strategy", "unexpected_provider")

    assert normalize_config_update("unknown_config", "dify_only") is None


def test_dify_only_strategy_does_not_call_langchain(monkeypatch):
    service = _service_with_strategy("dify_only")
    _patch_common_service_guards(monkeypatch, service)
    calls = []

    monkeypatch.setattr(
        service,
        "_call_langchain",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LangChain should not be called")),
    )

    def fake_dify(*args, **kwargs):
        calls.append(kwargs)
        return ChatResponse(
            answer="风险等级：中\n\nDify 回答",
            sources=[],
            related_tasks=[],
            response_time=0,
            provider="dify",
            risk_level="medium",
            suggestions=[],
        )

    monkeypatch.setattr(service, "_call_dify", fake_dify)

    response = service.answer("劳动合同最晚什么时候签？")

    assert response.provider == "dify"
    assert calls
    assert calls[0]["require_sources"] is True


def test_dify_first_strategy_falls_back_to_langchain(monkeypatch):
    service = _service_with_strategy("dify_first")
    _patch_common_service_guards(monkeypatch, service)
    calls = []

    def failed_dify(*args, **kwargs):
        calls.append("dify")
        service.last_dify_error = "Dify 测试失败"
        return None

    def fake_langchain(*args, **kwargs):
        calls.append("langchain")
        return ChatResponse(
            answer="风险等级：低\n\nLangChain 回答",
            sources=[],
            related_tasks=[],
            response_time=0,
            provider="langchain",
            risk_level="low",
            suggestions=[],
        )

    monkeypatch.setattr(service, "_call_dify", failed_dify)
    monkeypatch.setattr(service, "_call_langchain", fake_langchain)

    response = service.answer("劳动合同最晚什么时候签？")

    assert response.provider == "langchain"
    assert calls == ["dify", "langchain"]


def test_langchain_only_attachment_does_not_call_dify(monkeypatch):
    service = _service_with_strategy("langchain_only")
    _patch_common_service_guards(monkeypatch, service)
    attachment = ChatAttachment(
        filename="policy.pdf",
        content_type="application/pdf",
        file=BytesIO(b"%PDF-1.4"),
    )

    monkeypatch.setattr(
        service,
        "_call_dify",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Dify should not be called")),
    )
    monkeypatch.setattr(
        service,
        "_call_langchain",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LangChain cannot handle attachments")),
    )

    response = service.answer("请解析这份劳动合同附件", attachment=attachment)

    assert response.provider == "provider_disabled"
    assert response.fallback_reason == "query_strategy=langchain_only"
    assert "不允许调用 Dify 文件解析链路" in response.answer
    assert response.evaluation["metrics"]["provider"] == "provider_disabled"


def test_dify_attachment_capability_hides_when_strategy_disables_dify(monkeypatch):
    monkeypatch.setattr(
        "app.services.dify_service.get_runtime_config",
        lambda db: SimpleNamespace(
            query_strategy="langchain_only",
            dify_base_url="http://127.0.0.1:65500/v1",
            dify_api_key="dify-key",
        ),
    )

    result = dify_attachment_capability(SimpleNamespace(), SimpleNamespace(dify_api_key=""))

    assert result["available"] is False
    assert result["reason"] == "strategy_disabled"


def test_dify_attachment_capability_requires_key_and_online_service(monkeypatch):
    monkeypatch.setattr(
        "app.services.dify_service.get_runtime_config",
        lambda db: SimpleNamespace(
            query_strategy="langchain_first",
            dify_base_url="http://127.0.0.1:65500/v1",
            dify_api_key="",
        ),
    )

    missing_key = dify_attachment_capability(SimpleNamespace(), SimpleNamespace(dify_api_key=""))
    assert missing_key["available"] is False
    assert missing_key["reason"] == "not_configured"

    monkeypatch.setattr(
        "app.services.dify_service.get_runtime_config",
        lambda db: SimpleNamespace(
            query_strategy="langchain_first",
            dify_base_url="http://127.0.0.1:65500/v1",
            dify_api_key="dify-key",
        ),
    )
    monkeypatch.setattr(
        "app.services.dify_service.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.RequestException("offline")),
    )

    offline = dify_attachment_capability(SimpleNamespace(), SimpleNamespace(dify_api_key=""))
    assert offline["available"] is False
    assert offline["reason"] == "offline"

    monkeypatch.setattr(
        "app.services.dify_service.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=404),
    )

    online = dify_attachment_capability(SimpleNamespace(), SimpleNamespace(dify_api_key=""))
    assert online["available"] is True
    assert online["reason"] == "available"
