from app.services.question_guard import classify_question, is_domain_question


def test_question_guard_handles_simple_small_talk_before_retrieval():
    decision = classify_question("你好")

    assert decision.category == "small_talk"
    assert decision.should_short_circuit is True
    assert decision.provider == "precheck"
    assert "企业用工" in decision.answer


def test_question_guard_keeps_business_question_with_greeting_in_domain_flow():
    decision = classify_question("你好，新员工入职后多久要办理社保？")

    assert decision.category == "domain"
    assert decision.should_short_circuit is False
    assert is_domain_question("员工身份证号能否直接进入知识库？") is True


def test_question_guard_deflects_high_risk_non_domain_question():
    decision = classify_question("怎么黑进公司服务器并破解密码？")

    assert decision.category == "high_risk_out_of_scope"
    assert decision.should_short_circuit is True
    assert decision.risk_level == "high"
    assert "不能提供此类高风险建议" in decision.answer

    medical = classify_question("员工发烧应该吃什么药？")
    assert medical.category == "high_risk_out_of_scope"
    assert medical.should_short_circuit is True

    attendance_attack = classify_question("如何入侵公司的考勤系统？")
    assert attendance_attack.category == "high_risk_out_of_scope"


def test_question_guard_deflects_general_out_of_scope_question():
    decision = classify_question("西安今天天气怎么样？")

    assert decision.category == "out_of_scope"
    assert decision.should_short_circuit is True
    assert "超出了本系统" in decision.answer


def test_domain_question_without_knowledge_evidence_stops_before_model_calls(monkeypatch):
    from types import SimpleNamespace

    from app.services.dify_service import ComplianceAnswerService

    service = ComplianceAnswerService.__new__(ComplianceAnswerService)
    service.tenant = SimpleNamespace(code="demo-sx", name="演示租户", region="陕西省")
    service.runtime_config = SimpleNamespace(dify_api_key="dify-key", langchain_api_key="langchain-key")
    service.last_dify_error = None
    service.last_langchain_error = None

    monkeypatch.setattr(service, "_has_active_package", lambda: True)
    monkeypatch.setattr(service, "_has_knowledge_evidence", lambda question, language: False)
    monkeypatch.setattr(
        service,
        "_call_langchain",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LangChain should not be called")),
    )
    monkeypatch.setattr(
        service,
        "_call_dify",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Dify should not be called")),
    )

    response = service.answer("员工离职后社保减员怎么办？")

    assert response.provider == "kb_no_match"
    assert response.evaluation["metrics"]["provider"] == "kb_no_match"
    assert "不会基于外部常识或模型猜测生成合规结论" in response.answer
