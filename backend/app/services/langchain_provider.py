"""LangChain-based compliance answer provider."""
from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Optional

from app.security import sanitize_text


logger = logging.getLogger(__name__)


class LangChainUnavailable(RuntimeError):
    """LangChain 链路不可用时抛出。

    上层会捕获这个异常，然后按管理员策略尝试 Dify 或返回知识库边界提示。
    """


@dataclass(frozen=True)
class LangChainPromptContext:
    """传给 Prompt 模板的数据。

    它不是数据库模型，只是一包“生成答案需要看的材料”：用户问题、租户、
    地区、角色、回答风格、检索出来的知识库片段和免责声明。
    """

    question: str
    language: str
    tenant_code: str
    tenant_name: str
    region: str
    province: str
    city: str
    user_role: str
    answer_style: str
    context_notes: str
    source_context: str
    disclaimer: str


class LangChainComplianceProvider:
    """构建 LangChain LCEL 链路并调用模型生成答案。

    小白版理解：
    - ChatPromptTemplate：把系统规则和用户问题拼成 Prompt。
    - ChatOpenAI：调用 OpenAI-compatible 聊天模型。
    - StrOutputParser：把模型回复整理成普通字符串。
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "",
        temperature: float = 0.2,
        timeout_seconds: int = 45,
        langsmith_tracing_enabled: bool = False,
        langsmith_endpoint: str = "",
        langsmith_api_key: str = "",
        langsmith_project: str = "",
    ):
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.base_url = (base_url or "").strip()
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.langsmith_tracing_enabled = bool(langsmith_tracing_enabled)
        self.langsmith_endpoint = (langsmith_endpoint or "").strip()
        self.langsmith_api_key = (langsmith_api_key or "").strip()
        self.langsmith_project = (langsmith_project or "").strip() or "smart-labor-compliance"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def answer(self, prompt_context: LangChainPromptContext) -> str:
        if not self.configured:
            raise LangChainUnavailable("LangChain 未配置 API Key 或模型名称")

        try:
            # 这里动态 import，是为了让基础后台在未安装 LangChain 依赖时也能启动；
            # 只有真正调用 LangChain 问答时，才要求这些包存在。
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise LangChainUnavailable("LangChain 依赖未安装，请执行 python -m pip install -r requirements.txt") from exc

        try:
            # base_url 让项目可以接 OpenAI 官方接口，也可以接兼容 OpenAI 协议的私有模型网关。
            llm_kwargs = {
                "api_key": self.api_key,
                "model": self.model,
                "temperature": self.temperature,
                "timeout": self.timeout_seconds,
            }
            if self.base_url:
                llm_kwargs["base_url"] = self.base_url

            llm = ChatOpenAI(**llm_kwargs)
            # system 消息放“必须遵守的规则”，human 消息放本次问题和知识库上下文。
            # 这样模型既知道自己的角色，也能看到本次可引用的资料。
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        "\n".join(
                            [
                                "你是企业用工与社保合规智能平台的专业问答助手。",
                                "你需要面向企业 HR、法务、行政或员工，给出谨慎、可复核的中文合规建议。",
                                "必须优先使用提供的 FAQ、来源目录和租户上下文；不要编造法规条文、金额、期限或办理入口。",
                                "只能依据可用知识上下文回答；如果上下文没有明确依据，必须说明知识库未命中，不能补充外部常识。",
                                "如果来源不足，要明确写出待核验项，并建议通过当地人社、医保、税务等官方渠道复核。",
                                "回答必须结论先行，包含风险等级（high/medium/low 或 高/中/低）、依据说明、行动建议和待核验项。",
                                "不得输出身份证号、手机号、银行卡号等敏感信息；如用户提供了敏感信息，只描述已脱敏信息。",
                                "免责声明：{disclaimer}",
                            ]
                        ),
                    ),
                    (
                        "human",
                        "\n".join(
                            [
                                "租户：{tenant_name}（{tenant_code}）",
                                "语言：{language}",
                                "地区：{region}",
                                "省市：{province} {city}",
                                "用户角色：{user_role}",
                                "回答风格：{answer_style}",
                                "",
                                "补充信息：",
                                "{context_notes}",
                                "",
                                "可用知识上下文：",
                                "{source_context}",
                                "",
                                "用户问题：",
                                "{question}",
                            ]
                        ),
                    ),
                ]
            )
            # LCEL 管道：Prompt 模板 -> 聊天模型 -> 字符串输出。
            chain = prompt | llm | StrOutputParser()
            run_config = {
                "run_name": "compliance_answer",
                "tags": ["smart-labor-compliance", prompt_context.tenant_code, prompt_context.province],
                "metadata": {
                    "tenant_code": prompt_context.tenant_code,
                    "tenant_name": prompt_context.tenant_name,
                    "province": prompt_context.province,
                    "city": prompt_context.city,
                    "user_role": prompt_context.user_role,
                    "model": self.model,
                },
            }
            with self._langsmith_context(prompt_context):
                answer = chain.invoke(prompt_context.__dict__, config=run_config)
            cleaned = sanitize_text(answer) or ""
            if not cleaned:
                raise LangChainUnavailable("LangChain 未返回有效回答")
            return cleaned
        except LangChainUnavailable:
            raise
        except Exception as exc:
            message = sanitize_text(str(exc)) or exc.__class__.__name__
            if self.api_key:
                message = message.replace(self.api_key, "[API Key 已隐藏]")
            if self.langsmith_api_key:
                message = message.replace(self.langsmith_api_key, "[LangSmith API Key 已隐藏]")
            logger.warning("LangChain provider failed. model=%s base_url=%s error=%s", self.model, self.base_url, message)
            raise LangChainUnavailable(f"LangChain 调用失败: {message}") from exc

    def _langsmith_context(self, prompt_context: LangChainPromptContext):
        if not self.langsmith_tracing_enabled:
            return nullcontext()
        if not self.langsmith_api_key:
            logger.warning("LangSmith tracing is enabled but API key is not configured; tracing skipped.")
            return nullcontext()
        try:
            from langsmith import Client, tracing_context
        except ImportError:
            logger.warning("LangSmith tracing is enabled but langsmith package is not installed; tracing skipped.")
            return nullcontext()

        try:
            client = Client(
                api_url=self.langsmith_endpoint or None,
                api_key=self.langsmith_api_key,
                timeout_ms=max(self.timeout_seconds * 1000, 5000),
            )
            return tracing_context(
                enabled=True,
                project_name=self.langsmith_project,
                client=client,
                tags=["smart-labor-compliance", prompt_context.tenant_code],
                metadata={
                    "tenant_code": prompt_context.tenant_code,
                    "tenant_name": prompt_context.tenant_name,
                    "province": prompt_context.province,
                    "city": prompt_context.city,
                    "model": self.model,
                },
            )
        except Exception as exc:
            message = sanitize_text(str(exc)) or exc.__class__.__name__
            message = message.replace(self.langsmith_api_key, "[LangSmith API Key 已隐藏]")
            logger.warning("LangSmith tracing setup failed; tracing skipped. error=%s", message)
            return nullcontext()
