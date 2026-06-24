"""Deterministic pre-checks for chat questions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.security import sanitize_text


DOMAIN_KEYWORDS: tuple[str, ...] = (
    "劳动",
    "用工",
    "雇佣",
    "劳务",
    "劳务派遣",
    "人事",
    "hr",
    "合同",
    "试用期",
    "入职",
    "离职",
    "离任",
    "辞退",
    "裁员",
    "解除",
    "终止",
    "赔偿",
    "补偿",
    "工资",
    "薪资",
    "薪酬",
    "拖欠工资",
    "最低工资",
    "加班",
    "补休",
    "考勤",
    "旷工",
    "年假",
    "年休假",
    "休假",
    "请假",
    "产假",
    "护理假",
    "陪产假",
    "育儿假",
    "病假",
    "婚假",
    "丧假",
    "工伤",
    "社保",
    "社会保险",
    "养老",
    "失业",
    "医保",
    "医疗保险",
    "公积金",
    "五险",
    "一金",
    "参保",
    "停保",
    "补缴",
    "缴费",
    "基数",
    "待遇",
    "报销",
    "仲裁",
    "劳动争议",
    "竞业",
    "竞业限制",
    "罚款",
    "扣款",
    "规章制度",
    "企业制度",
    "违约金",
    "调岗",
    "降薪",
    "续签",
    "未签",
    "双倍工资",
    "经济补偿",
    "用人单位",
    "劳动者",
    "个人信息",
    "敏感信息",
    "脱敏",
    "身份证",
    "手机号",
    "银行卡",
    "邮箱",
    "知识库",
    "入库",
    "人社",
    "医保局",
    "税务",
)

SMALL_TALK_PATTERNS: tuple[str, ...] = (
    "你好",
    "您好",
    "hi",
    "hello",
    "hey",
    "在吗",
    "有人吗",
    "谢谢",
    "感谢",
    "辛苦了",
    "你是谁",
    "你能做什么",
    "介绍一下",
)

SYSTEM_ROLE_PATTERNS: tuple[str, ...] = (
    "你是谁",
    "你是什么",
    "你是什么系统",
    "你是干什么的",
    "你能做什么",
    "你会做什么",
    "你可以做什么",
    "能帮我什么",
    "系统能做什么",
    "平台能做什么",
    "这个系统怎么用",
    "系统怎么用",
    "怎么使用系统",
    "如何使用系统",
    "使用说明",
    "功能介绍",
    "角色介绍",
    "系统角色",
    "平台角色",
    "你的角色",
    "你的定位",
    "你的职责",
    "你的能力",
    "问答范围",
    "能回答什么",
    "可以回答什么",
    "回答依据",
    "回答规则",
    "你怎么回答",
    "数据来源",
    "知识库边界",
    "知识库范围",
    "怎么提问",
    "如何提问",
    "使用时要注意什么",
)

HIGH_RISK_OUT_OF_SCOPE_KEYWORDS: tuple[str, ...] = (
    "诊断",
    "处方",
    "吃什么药",
    "用什么药",
    "手术",
    "急救",
    "自杀",
    "自残",
    "轻生",
    "跳楼",
    "寻死",
    "结束生命",
    "不想活",
    "杀人",
    "伤害",
    "爆炸",
    "毒品",
    "枪支",
    "网赌",
    "洗钱",
    "诈骗",
    "偷税",
    "逃税",
    "内幕交易",
    "股票推荐",
    "投资建议",
    "贷款套现",
    "黑客",
    "黑进",
    "入侵",
    "攻击服务器",
    "攻击网站",
    "破解密码",
    "盗号",
    "木马",
    "病毒",
    "绕过风控",
    "作弊",
    "代考",
)

ALWAYS_DEFLECT_RISK_KEYWORDS: tuple[str, ...] = (
    "爆炸",
    "毒品",
    "枪支",
    "网赌",
    "洗钱",
    "诈骗",
    "自杀",
    "自残",
    "轻生",
    "跳楼",
    "寻死",
    "结束生命",
    "不想活",
    "偷税",
    "逃税",
    "内幕交易",
    "贷款套现",
    "黑客",
    "黑进",
    "入侵",
    "攻击服务器",
    "攻击网站",
    "破解密码",
    "盗号",
    "木马",
    "病毒",
    "绕过风控",
    "作弊",
    "代考",
)

GENERAL_OUT_OF_SCOPE_HINTS: tuple[str, ...] = (
    "天气",
    "新闻",
    "菜谱",
    "旅游",
    "电影",
    "小说",
    "写诗",
    "翻译",
    "编程",
    "代码",
    "服务器",
    "数据库",
    "股票",
    "基金",
    "房价",
)

SENSITIVE_DATA_KEYWORDS: tuple[str, ...] = (
    "身份证",
    "身份证号",
    "手机号",
    "电话",
    "银行卡",
    "银行账号",
    "邮箱",
    "个人信息",
    "敏感信息",
    "客户名单",
    "合同价格",
)

DATA_SECURITY_ACTION_KEYWORDS: tuple[str, ...] = (
    "知识库",
    "入库",
    "进入",
    "上传",
    "存储",
    "日志",
    "脱敏",
    "隐私",
    "安全",
)

PERSON_WORDS: tuple[str, ...] = ("员工", "职工", "劳动者", "用人单位", "公司", "企业")
BUSINESS_CONTEXT_WORDS: tuple[str, ...] = (
    "入职",
    "离职",
    "合同",
    "工资",
    "社保",
    "医保",
    "公积金",
    "加班",
    "考勤",
    "请假",
    "休假",
    "工伤",
    "仲裁",
    "辞退",
    "解除",
    "赔偿",
    "补偿",
    "调岗",
    "降薪",
    "罚款",
    "扣款",
    "参保",
    "停保",
    "补缴",
    "脱敏",
    "个人信息",
    "敏感信息",
    "知识库",
    "入库",
)


@dataclass(frozen=True)
class QuestionGuardDecision:
    """Pre-check result used before retrieval or model calls."""

    category: str
    should_short_circuit: bool
    answer: str = ""
    provider: str = "precheck"
    risk_level: str = "low"
    fallback_reason: str | None = None
    suggestions: list[str] = field(default_factory=list)


def _compact(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?;；:：\"'“”‘’（）()\[\]{}<>《》]+", "", text.lower())


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word.lower() in text for word in words)


def is_domain_question(question: str) -> bool:
    """Return whether the question is about labor/social-insurance compliance."""
    text = (sanitize_text(question) or "").lower()
    if _contains_any(text, DOMAIN_KEYWORDS):
        return True
    return _contains_any(text, PERSON_WORDS) and _contains_any(text, BUSINESS_CONTEXT_WORDS)


def is_simple_small_talk(question: str) -> bool:
    """Return whether the question is simple greeting/help-style chatter."""
    text = sanitize_text(question) or ""
    compact = _compact(text)
    if not compact:
        return True
    if len(compact) <= 16 and _contains_any(compact, SMALL_TALK_PATTERNS):
        return True
    return compact in {"?", "？", "help", "帮助"}


def is_system_role_question(question: str) -> bool:
    """Return whether the user is asking what this system is or how to use it."""
    text = sanitize_text(question) or ""
    compact = _compact(text)
    if not compact:
        return False
    return _contains_any(compact, SYSTEM_ROLE_PATTERNS)


def is_high_risk_out_of_scope(question: str) -> bool:
    """Return whether a non-domain question asks for high-risk advice."""
    text = sanitize_text(question) or ""
    if is_domain_question(text):
        return False
    return _contains_any(text.lower(), HIGH_RISK_OUT_OF_SCOPE_KEYWORDS)


def is_data_security_question(question: str) -> bool:
    """Return whether the question is about sensitive data handling in the platform."""
    text = sanitize_text(question) or ""
    compact = _compact(text)
    return _contains_any(compact, SENSITIVE_DATA_KEYWORDS) and _contains_any(compact, DATA_SECURITY_ACTION_KEYWORDS)


def _default_suggestions() -> list[str]:
    return [
        "陕西产假多少天？",
        "新员工入职后多久要办理社保？",
        "劳动仲裁时效是多久？",
    ]


def _small_talk_answer() -> str:
    return (
        "您好，我是企业用工与社保合规智能助手，主要面向企业 HR、员工和平台管理员，"
        "辅助查询劳动合同、入离职、工资、社保、医保、假期、工伤、劳动争议和知识库资料管理等问题。\n"
        "系统内合规问题会优先从已入库知识库、FAQ 和 Milvus 向量库中检索依据，再基于来源生成回答；"
        "如果没有检索到足够依据，我会提示补充资料，不会凭空给出合规结论。\n"
        "使用时请尽量补充地区、员工身份、发生时间、业务事实和你希望的输出格式。"
    )


def _high_risk_out_of_scope_answer() -> str:
    return (
        "这个问题不属于本系统的企业用工与社保合规知识范围，我不能提供此类高风险建议。\n"
        "建议改为咨询具备资质的专业机构或官方渠道；如果问题与劳动用工、社保医保、假期、工资或劳动争议有关，"
        "请补充具体业务事实后再提问。"
    )


def _general_out_of_scope_answer() -> str:
    return (
        "这个问题超出了本系统的企业用工与社保合规知识范围。\n"
        "我可以处理劳动合同、工资、社保、医保、假期、工伤、入离职和劳动争议等问题；"
        "如需继续，请把问题改写为相关合规场景。"
    )


def _data_security_answer() -> str:
    return (
        "结论：身份证号、手机号、银行卡号、邮箱、客户名单、合同价格等敏感信息不能以原文直接进入知识库、日志或测试数据。\n\n"
        "风险等级：高\n\n"
        "处理建议：\n"
        "1. 入库前先完成脱敏或匿名化，例如替换为 [身份证号已脱敏]、[手机号已脱敏] 等占位符。\n"
        "2. 只保留合规判断所需的最小事实，例如员工身份类型、地区、时间节点和业务场景，不保留完整证件号。\n"
        "3. 上传合同、工资单、客户名单等材料前，应由 HR/法务或管理员复核脱敏结果。\n"
        "4. 若确需保留原始材料，应放在受控业务系统中，并按租户隔离、权限审批和审计日志管理。\n\n"
        "待核验项：以企业数据安全制度、个人信息保护要求和当地监管口径为准。"
    )


def classify_question(question: str) -> QuestionGuardDecision:
    """Classify a question before expensive retrieval or model calls."""
    text = sanitize_text(question) or ""
    if _contains_any(text.lower(), ALWAYS_DEFLECT_RISK_KEYWORDS):
        return QuestionGuardDecision(
            category="high_risk_out_of_scope",
            should_short_circuit=True,
            answer=_high_risk_out_of_scope_answer(),
            risk_level="high",
            fallback_reason="high_risk_out_of_scope",
            suggestions=_default_suggestions(),
        )

    if is_system_role_question(text):
        return QuestionGuardDecision(
            category="system_role",
            should_short_circuit=True,
            answer=_small_talk_answer(),
            risk_level="low",
            fallback_reason="system_role_intro",
            suggestions=_default_suggestions(),
        )

    if is_data_security_question(text):
        return QuestionGuardDecision(
            category="data_security",
            should_short_circuit=True,
            answer=_data_security_answer(),
            risk_level="high",
            fallback_reason="sensitive_data_precheck",
            suggestions=_default_suggestions(),
        )

    domain = is_domain_question(text)
    if not domain and is_simple_small_talk(text):
        return QuestionGuardDecision(
            category="small_talk",
            should_short_circuit=True,
            answer=_small_talk_answer(),
            risk_level="low",
            fallback_reason="simple_small_talk",
            suggestions=_default_suggestions(),
        )

    if domain:
        return QuestionGuardDecision(category="domain", should_short_circuit=False)

    if is_high_risk_out_of_scope(text):
        return QuestionGuardDecision(
            category="high_risk_out_of_scope",
            should_short_circuit=True,
            answer=_high_risk_out_of_scope_answer(),
            risk_level="high",
            fallback_reason="high_risk_out_of_scope",
            suggestions=_default_suggestions(),
        )

    if _contains_any(text.lower(), GENERAL_OUT_OF_SCOPE_HINTS):
        return QuestionGuardDecision(
            category="out_of_scope",
            should_short_circuit=True,
            answer=_general_out_of_scope_answer(),
            risk_level="low",
            fallback_reason="out_of_scope",
            suggestions=_default_suggestions(),
        )

    return QuestionGuardDecision(
        category="unknown",
        should_short_circuit=True,
        answer=_general_out_of_scope_answer(),
        risk_level="low",
        fallback_reason="unknown_out_of_scope",
        suggestions=_default_suggestions(),
    )
