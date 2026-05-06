"""Dify 与本地 FAQ 的统一问答服务。"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, BinaryIO, Optional, cast

import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import settings
from app.models import FAQ, KnowledgePackage, Source, Tenant
from app.schemas.chat import ChatResponse, SourceInfo, TaskInfo
from app.security import sanitize_text


logger = logging.getLogger(__name__)

DISCLAIMER = (
    "本回答用于企业合规辅助和演示，不替代正式法律意见。涉及具体待遇、金额、期限或争议处理时，"
    "请以当地人社、医保、税务等官方经办口径及企业制度最终复核为准。"
)

USER_ROLE_LABELS = {
    "enterprise_hr": "企业HR",
    "administrator_staff": "行政人员",
    "legal_staff": "法务人员",
    "employee": "员工",
    "admin_user": "管理员",
}

DEFAULT_ANSWER_STYLE = "结构清晰、结论先行、引用来源、明确风险等级和待核验项"
CONTEXT_FIELD_LIMITS = {
    "answer_style": 600,
    "user_goal": 160,
    "urgency_level": 80,
    "output_format": 120,
    "known_facts": 1000,
    "verification_focus": 600,
}
CONTEXT_FIELD_LABELS = {
    "user_goal": "问题目标",
    "urgency_level": "紧急程度",
    "output_format": "输出格式",
    "known_facts": "已知事实",
    "verification_focus": "重点核验",
}


_generation_tasks: dict[str, dict[str, str]] = {}
_generation_tasks_lock = threading.Lock()


@dataclass
class ChatAttachment:
    """待转交给 Dify 的用户附件。"""

    filename: str
    content_type: str
    file: BinaryIO


class ComplianceAnswerService:
    """先尝试 Dify，失败或未配置时回退到本地 FAQ。"""

    def __init__(self, db: Session, tenant: Tenant):
        self.db = db
        self.tenant = tenant

    def answer(
        self,
        question: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        language: str = "zh-CN",
        user_role: str = "employee",
        province: str = "陕西省",
        city: str = "西安市",
        attachment: Optional[ChatAttachment] = None,
        generation_id: Optional[str] = None,
        answer_style: Optional[str] = None,
        user_goal: Optional[str] = None,
        urgency_level: Optional[str] = None,
        output_format: Optional[str] = None,
        known_facts: Optional[str] = None,
        verification_focus: Optional[str] = None,
    ) -> ChatResponse:
        question = sanitize_text(question) or ""
        context = self._normalize_context(
            answer_style=answer_style,
            user_goal=user_goal,
            urgency_level=urgency_level,
            output_format=output_format,
            known_facts=known_facts,
            verification_focus=verification_focus,
        )
        start_time = int(time.time() * 1000)
        if not self._has_active_package():
            response = ChatResponse(
                answer=self._with_context_prefix(
                    self._inactive_package_answer(question),
                    user_role,
                    province,
                    city,
                    context,
                ),
                sources=None,
                related_tasks=[],
                response_time=int(time.time() * 1000) - start_time,
                provider="knowledge_package_disabled",
                risk_level=self._estimate_risk(question),
                suggestions=[],
                disclaimer=DISCLAIMER,
            )
            return response

        tenant_dify_key_value = getattr(self.tenant, "dify_api_key", None)
        tenant_dify_key = str(tenant_dify_key_value).strip() if tenant_dify_key_value is not None else ""
        dify_key = tenant_dify_key if tenant_dify_key != "" else str(settings.dify_api_key or "")
        if dify_key != "":
            dify_response = self._call_dify(
                question,
                dify_key,
                user_id,
                conversation_id,
                user_role,
                province,
                city,
                attachment,
                generation_id,
                context,
            )
            if dify_response:
                dify_response.response_time = int(time.time() * 1000) - start_time
                return dify_response

        if attachment:
            return ChatResponse(
                answer=self._with_context_prefix(
                    "已收到附件，但文件内容解析必须由 Dify 完成。当前 Dify 未配置或调用失败，"
                    "系统未对附件内容进行本地解析，请检查 Dify 应用密钥、文件上传能力和工作流配置后重试。",
                    user_role,
                    province,
                    city,
                    context,
                ),
                sources=None,
                related_tasks=[],
                response_time=int(time.time() * 1000) - start_time,
                provider="dify_unavailable",
                risk_level=self._estimate_risk(question),
                suggestions=[],
                disclaimer=DISCLAIMER,
            )

        local_response = self._answer_from_faq(question, language)
        local_response.answer = self._with_context_prefix(local_response.answer, user_role, province, city, context)
        local_response.response_time = int(time.time() * 1000) - start_time
        return local_response

    def _call_dify(
        self,
        question: str,
        api_key: str,
        user_id: Optional[str],
        conversation_id: Optional[str],
        user_role: str,
        province: str,
        city: str,
        attachment: Optional[ChatAttachment] = None,
        generation_id: Optional[str] = None,
        context: Optional[dict[str, str]] = None,
    ) -> Optional[ChatResponse]:
        try:
            payload = {
                "query": question,
                "user": user_id or "anonymous",
                "response_mode": "streaming",
                "inputs": self._build_dify_inputs(user_role, province, city, context),
            }
            if conversation_id:
                payload["conversation_id"] = conversation_id
            if attachment:
                upload_file_id = self._upload_file_to_dify(api_key, user_id, attachment)
                if not upload_file_id:
                    logger.warning("Dify file upload failed; falling back to local FAQ. filename=%s", attachment.filename)
                    return None
                payload["files"] = [
                    {
                        "type": self._dify_file_type(attachment.filename, attachment.content_type),
                        "transfer_method": "local_file",
                        "upload_file_id": upload_file_id,
                    }
                ]

            response = requests.post(
                f"{settings.dify_base_url.rstrip('/')}/chat-messages",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                stream=True,
                timeout=settings.dify_timeout_seconds,
            )
            if response.status_code != 200:
                logger.warning(
                    "Dify chat request failed; falling back to local FAQ. status=%s body=%s",
                    response.status_code,
                    response.text[:1000],
                )
                return None

            data = self._consume_dify_stream(response, generation_id, api_key, user_id or "anonymous")
            if not data:
                return None

            metadata = data.get("metadata") or {}
            sources = []
            for resource in metadata.get("retriever_resources", []):
                sources.append(
                    SourceInfo(
                        title=resource.get("document_name") or resource.get("title") or "Dify 知识库来源",
                        url=resource.get("url"),
                        snippet=(resource.get("content") or "")[:220],
                    )
                )
            answer = self._normalize_answer(data.get("answer") or "")
            return ChatResponse(
                answer=answer,
                sources=sources or None,
                related_tasks=self._extract_tasks(question),
                response_time=0,
                conversation_id=data.get("conversation_id"),
                question_id=None,
                provider="dify",
                risk_level=self._risk_from_answer(answer) or self._estimate_risk(question),
                suggestions=self._suggestions(question),
                disclaimer=DISCLAIMER,
            )
        except requests.Timeout as exc:
            logger.warning(
                "Dify chat request timed out after %ss; falling back to local FAQ. url=%s error=%s",
                settings.dify_timeout_seconds,
                f"{settings.dify_base_url.rstrip('/')}/chat-messages",
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.warning("Dify chat request failed; falling back to local FAQ. error=%s", exc)
            return None
        finally:
            if generation_id:
                self._unregister_generation(generation_id)

    def _consume_dify_stream(
        self,
        response: requests.Response,
        generation_id: Optional[str],
        api_key: str,
        user_id: str,
    ) -> Optional[dict]:
        answer_parts: list[str] = []
        final_data: dict = {}
        metadata: dict = {}
        task_id = ""

        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            if raw_line.startswith("event:"):
                continue
            if not raw_line.startswith("data:"):
                continue

            try:
                event = json.loads(raw_line[5:].strip())
            except json.JSONDecodeError:
                logger.warning("Failed to decode Dify stream line: %s", raw_line[:300])
                continue

            task_id = task_id or str(event.get("task_id") or "")
            if generation_id and task_id:
                self._register_generation(generation_id, task_id, api_key, user_id)

            event_type = event.get("event")
            if event_type == "message":
                answer_parts.append(event.get("answer") or "")
                final_data["conversation_id"] = event.get("conversation_id") or final_data.get("conversation_id")
                final_data["message_id"] = event.get("message_id") or final_data.get("message_id")
            elif event_type == "message_end":
                metadata = event.get("metadata") or {}
                final_data["conversation_id"] = event.get("conversation_id") or final_data.get("conversation_id")
                final_data["message_id"] = event.get("message_id") or final_data.get("message_id")
            elif event_type == "workflow_finished":
                data = event.get("data") or {}
                outputs = data.get("outputs") or {}
                if outputs.get("answer"):
                    answer_parts = [outputs["answer"]]
            elif event_type == "error":
                logger.warning("Dify stream returned error: %s", event)
                return None

        final_data["answer"] = "".join(answer_parts)
        final_data["metadata"] = metadata
        return final_data if final_data["answer"] else None

    @classmethod
    def _register_generation(cls, generation_id: str, task_id: str, api_key: str, user_id: str) -> None:
        with _generation_tasks_lock:
            _generation_tasks[generation_id] = {
                "task_id": task_id,
                "api_key": api_key,
                "user_id": user_id,
            }

    @classmethod
    def _unregister_generation(cls, generation_id: str) -> None:
        with _generation_tasks_lock:
            _generation_tasks.pop(generation_id, None)

    @classmethod
    def stop_generation(cls, generation_id: str) -> bool:
        with _generation_tasks_lock:
            task = _generation_tasks.get(generation_id)

        if not task:
            return False

        try:
            response = requests.post(
                f"{settings.dify_base_url.rstrip('/')}/chat-messages/{task['task_id']}/stop",
                headers={"Authorization": f"Bearer {task['api_key']}", "Content-Type": "application/json"},
                json={"user": task["user_id"]},
                timeout=10,
            )
            if response.status_code >= 400:
                logger.warning("Dify stop request failed. status=%s body=%s", response.status_code, response.text[:500])
                return False
            return True
        except requests.RequestException as exc:
            logger.warning("Dify stop request failed. generation_id=%s error=%s", generation_id, exc)
            return False
        finally:
            cls._unregister_generation(generation_id)

    def _upload_file_to_dify(
        self,
        api_key: str,
        user_id: Optional[str],
        attachment: ChatAttachment,
    ) -> Optional[str]:
        try:
            if hasattr(attachment.file, "seek"):
                attachment.file.seek(0)
            response = requests.post(
                f"{settings.dify_base_url.rstrip('/')}/files/upload",
                headers={"Authorization": f"Bearer {api_key}"},
                data={"user": user_id or "anonymous"},
                files={
                    "file": (
                        attachment.filename,
                        attachment.file,
                        attachment.content_type or "application/octet-stream",
                    )
                },
                timeout=settings.dify_timeout_seconds,
            )
            if response.status_code not in (200, 201):
                logger.warning(
                    "Dify file upload returned non-success status. status=%s body=%s",
                    response.status_code,
                    response.text[:1000],
                )
                return None
            data = response.json()
            return data.get("id")
        except requests.Timeout as exc:
            logger.warning(
                "Dify file upload timed out after %ss. filename=%s error=%s",
                settings.dify_timeout_seconds,
                attachment.filename,
                exc,
            )
            return None
        except requests.RequestException as exc:
            logger.warning("Dify file upload failed. filename=%s error=%s", attachment.filename, exc)
            return None

    def _dify_file_type(self, filename: str, content_type: str) -> str:
        content_type = (content_type or "").lower()
        suffix = Path(filename or "").suffix.lower().lstrip(".")
        if content_type.startswith("image/"):
            return "image"
        if content_type.startswith("audio/"):
            return "audio"
        if content_type.startswith("video/"):
            return "video"
        if suffix in {
            "pdf",
            "txt",
            "md",
            "markdown",
            "html",
            "htm",
            "csv",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
            "rtf",
        }:
            return "document"
        return "custom"

    def _answer_from_faq(self, question: str, language: str) -> ChatResponse:
        faq = self._best_faq_match(question, language)
        if faq:
            faq_obj = cast(Any, faq)
            answer = self._normalize_answer(str(faq_obj.answer or ""))
            source_ids = faq_obj.source_ids if isinstance(faq_obj.source_ids, list) else []
            source_infos = self._source_infos(source_ids)
            return ChatResponse(
                answer=answer,
                sources=source_infos or None,
                related_tasks=self._extract_tasks(question),
                response_time=0,
                provider="local_faq",
                risk_level=str(faq_obj.risk_level or "medium"),
                suggestions=self._suggestions(question),
                disclaimer=DISCLAIMER,
            )

        return ChatResponse(
            answer=self._fallback_answer(question),
            sources=self._source_infos([]) or None,
            related_tasks=self._extract_tasks(question),
            response_time=0,
            provider="local_faq",
            risk_level=self._estimate_risk(question),
            suggestions=self._suggestions(question),
            disclaimer=DISCLAIMER,
        )

    def _best_faq_match(self, question: str, language: str) -> Optional[FAQ]:
        keyword = f"%{question[:80]}%"
        candidates = (
            self.db.query(FAQ)
            .filter(FAQ.tenant_id == self.tenant.id)
            .filter(or_(FAQ.language == language, FAQ.language == "zh-CN"))
            .filter(or_(FAQ.question.like(keyword), FAQ.answer.like(keyword), FAQ.category.like(keyword)))
            .limit(20)
            .all()
        )

        if not candidates:
            candidates = self.db.query(FAQ).filter(FAQ.tenant_id == self.tenant.id).all()

        best_score = 0.0
        best = None
        normalized_question = question.lower()
        for faq_item in candidates:
            faq = cast(Any, faq_item)
            terms = [faq.question, *(faq.aliases or []), *(faq.keywords or [])]
            score = max(SequenceMatcher(None, normalized_question, term.lower()).ratio() for term in terms if term)
            if any(term and term in question for term in terms):
                score += 0.35
            if score > best_score:
                best_score = score
                best = faq
        return best if best_score >= 0.18 else None

    def _source_infos(self, source_ids: list[int]) -> list[SourceInfo]:
        if not self._has_active_package():
            return []
        query = self.db.query(Source).filter(Source.tenant_id == self.tenant.id)
        if source_ids:
            query = query.filter(Source.id.in_(source_ids))
        else:
            query = query.order_by(Source.created_at.desc()).limit(3)
        sources = query.all()
        result = []
        for item in sources:
            source = cast(Any, item)
            result.append(
                SourceInfo(
                    title=str(source.title or ""),
                    url=str(source.url) if source.url else None,
                    snippet=str(source.description) if source.description else None,
                )
            )
        return result

    def _extract_tasks(self, question: str) -> list[TaskInfo]:
        if not any(word in question for word in ["仲裁", "办理", "申请", "共济", "医保"]):
            return []
        return [
            TaskInfo(
                title="合规办理建议路径",
                steps=[
                    "确认适用地区、员工身份、时间节点和企业制度版本。",
                    "准备劳动合同、考勤、工资、社保缴费或医保参保等证据材料。",
                    "通过当地人社、医保、税务等官方渠道核验最新办理入口。",
                    "对高风险事项保留书面处理记录，必要时交由 HR/法务复核。",
                ],
                url=settings.ragflow_web_url,
            )
        ]

    def _normalize_answer(self, answer: str) -> str:
        answer = sanitize_text(answer) or ""
        if DISCLAIMER not in answer:
            answer = f"{answer.strip()}\n\n风险提示：{DISCLAIMER}"
        return answer

    def _normalize_context(
        self,
        *,
        answer_style: Optional[str] = None,
        user_goal: Optional[str] = None,
        urgency_level: Optional[str] = None,
        output_format: Optional[str] = None,
        known_facts: Optional[str] = None,
        verification_focus: Optional[str] = None,
    ) -> dict[str, str]:
        raw_context = {
            "answer_style": answer_style,
            "user_goal": user_goal,
            "urgency_level": urgency_level,
            "output_format": output_format,
            "known_facts": known_facts,
            "verification_focus": verification_focus,
        }
        context: dict[str, str] = {}
        for key, value in raw_context.items():
            cleaned = sanitize_text(value) if value is not None else ""
            cleaned = (cleaned or "").strip()
            if key == "answer_style" and not cleaned:
                cleaned = DEFAULT_ANSWER_STYLE
            limit = CONTEXT_FIELD_LIMITS[key]
            if cleaned:
                context[key] = cleaned[:limit]
        return context

    def _build_dify_inputs(
        self,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        region = f"{province}{city}" if province and city else (province or city or self.tenant.region)
        inputs = {
            "tenant_code": self.tenant.code,
            "tenant_name": self.tenant.name,
            "region": region,
            "province": province,
            "city": city,
            "user_role": USER_ROLE_LABELS.get(user_role, user_role),
            "answer_style": DEFAULT_ANSWER_STYLE,
        }
        inputs.update(context or {})
        return inputs

    def _with_context_prefix(
        self,
        answer: str,
        user_role: str,
        province: str,
        city: str,
        context: Optional[dict[str, str]] = None,
    ) -> str:
        role = USER_ROLE_LABELS.get(user_role, user_role or "员工")
        region = f"{province}{city}" if province and city else (province or city or self.tenant.region)
        lines = [f"适用角色：{role}", f"所在地区：{region}"]
        for key in ("user_goal", "urgency_level", "output_format", "known_facts", "verification_focus"):
            value = (context or {}).get(key)
            if value:
                lines.append(f"{CONTEXT_FIELD_LABELS[key]}：{value}")
        return f"{chr(10).join(lines)}\n\n{answer}"

    def _has_active_package(self) -> bool:
        return (
            self.db.query(KnowledgePackage.id)
            .filter(KnowledgePackage.tenant_id == self.tenant.id, KnowledgePackage.status == "active")
            .first()
            is not None
        )

    def _inactive_package_answer(self, question: str) -> str:
        risk = self._estimate_risk(question)
        return (
            "当前租户的知识包已停用，系统不会调用知识库文件或外部知识包检索。\n"
            "请先在管理后台启用知识包，或由管理员确认当前资料可用后再进行智能问答。\n"
            f"本次问题仅做通用风险识别，初步风险等级为：{risk}。\n\n"
            f"风险提示：{DISCLAIMER}"
        )

    def _fallback_answer(self, question: str) -> str:
        risk = self._estimate_risk(question)
        return (
            "当前问题未命中已复核 FAQ，系统已按通用合规口径给出处理建议：\n"
            "1. 先确认适用地区、时间口径、员工身份、合同和企业制度版本。\n"
            "2. 涉及工资、社保、医保、假期、仲裁等事项时，应引用官方政策或经办规则，避免只凭经验答复。\n"
            "3. 对包含身份证号、手机号、银行卡号等个人信息的材料，应先脱敏再进入知识库或日志。\n"
            f"4. 本问题初步风险等级为：{risk}。建议由 HR 或法务复核后再对外确认。"
        )

    def _estimate_risk(self, question: str) -> str:
        high_words = ["仲裁", "工伤", "解除", "赔偿", "最低工资", "未签", "违法", "身份证", "手机号"]
        medium_words = ["社保", "医保", "产假", "护理假", "加班", "离职", "补缴"]
        if any(word in question for word in high_words):
            return "high"
        if any(word in question for word in medium_words):
            return "medium"
        return "low"

    def _risk_from_answer(self, answer: str) -> Optional[str]:
        text = sanitize_text(answer) or ""
        patterns = [
            r"风险等级\s*[:：]\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)",
            r"初步风险等级\s*为\s*[:：]?\s*(?:\*\*)?\s*(高风险|中风险|低风险|高|中|低|high|medium|low)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return self._normalize_risk_level(match.group(1))
        return None

    def _normalize_risk_level(self, value: str) -> Optional[str]:
        normalized = (sanitize_text(value) or "").strip().lower().strip("*：:，,。.;；")
        mapping = {
            "高": "high",
            "高风险": "high",
            "high": "high",
            "中": "medium",
            "中风险": "medium",
            "中等": "medium",
            "中等风险": "medium",
            "medium": "medium",
            "低": "low",
            "低风险": "low",
            "low": "low",
        }
        return mapping.get(normalized)

    def _suggestions(self, question: str) -> list[str]:
        if "产假" in question or "护理假" in question:
            return ["陕西护理假多少天？", "生育津贴和产假工资如何衔接？", "企业制度低于地方假期规定怎么办？"]
        if "仲裁" in question:
            return ["劳动仲裁时效是多久？", "仲裁申请需要哪些材料？", "员工所在地和公司所在地哪个有管辖权？"]
        if "社保" in question or "医保" in question:
            return ["新员工入职后多久要办理社保？", "居民医保断缴后还能报销吗？", "社保补缴有什么风险？"]
        return ["试用期工资可以低于最低工资吗？", "劳动合同最晚什么时候签？", "周末加班工资怎么算？"]


def check_external_services() -> dict:
    """探测本机 Dify 与 RAGFlow 服务状态。"""
    services = {
        "dify": {"name": "Dify", "url": settings.dify_base_url, "configured": bool(settings.dify_api_key)},
        "ragflow": {"name": "RAGFlow", "url": settings.ragflow_web_url, "configured": bool(settings.ragflow_api_key)},
    }
    for key, item in services.items():
        probe_url = item["url"]
        try:
            response = requests.get(probe_url, timeout=3)
            item["online"] = response.status_code < 500
            item["status_code"] = response.status_code
        except requests.RequestException:
            item["online"] = False
            item["status_code"] = None
    return services
