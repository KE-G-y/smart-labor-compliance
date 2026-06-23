"""项目说明文档中心。

这个路由只读取下面白名单中的 Markdown 文件。前端传入的 `doc_id`
不会直接拼接成文件路径，因此可以避免路径穿越和误读服务器文件。
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.response import ok

router = APIRouter(prefix="/api/project-docs", tags=["项目文档"])

MAX_DOCUMENT_BYTES = 1024 * 1024


def _detect_project_root() -> Path:
    """兼容本地 `backend/` 启动和 Docker `/app` 启动两种目录结构。"""
    file_path = Path(__file__).resolve()
    candidates = (
        Path.cwd().resolve(),
        file_path.parents[3],
        file_path.parents[2],
    )
    for candidate in candidates:
        if (candidate / "README.md").is_file() and (candidate / "docs").is_dir():
            return candidate
    return file_path.parents[3]


PROJECT_ROOT = _detect_project_root()


@dataclass(frozen=True)
class ProjectDocument:
    id: str
    title: str
    path: str
    category: str
    summary: str
    accuracy_status: str = "已按当前代码梳理"
    last_reviewed: str = "2026-06-23"
    audience: str = "项目成员"
    notes: str = ""
    renderable: bool = True


DOCUMENTS: tuple[ProjectDocument, ...] = (
    ProjectDocument(
        id="documentation-index",
        title="项目文档总索引",
        path="docs/DOCUMENTATION_INDEX.md",
        category="文档索引",
        summary="统一说明各文档用途、可信状态、维护边界和访问入口。",
        audience="项目成员/运维/验收人员",
    ),
    ProjectDocument(
        id="readme",
        title="项目总览 README",
        path="README.md",
        category="快速开始",
        summary="项目定位、技术栈、启动方式、初始账号和核心文档入口。",
        audience="首次接手项目人员",
    ),
    ProjectDocument(
        id="operation",
        title="操作文档",
        path="docs/OPERATION.md",
        category="快速开始",
        summary="本地一键启动、参数来源、账号、服务地址、模型配置和日常运维。",
        audience="开发/运维/演示人员",
    ),
    ProjectDocument(
        id="docker-deployment",
        title="Docker 部署说明",
        path="docs/DOCKER_DEPLOYMENT.md",
        category="部署运维",
        summary="Docker Compose 服务栈、环境变量、向量构建工具和常用部署命令。",
        audience="部署/运维人员",
    ),
    ProjectDocument(
        id="technical-architecture",
        title="技术架构总览",
        path="docs/TECHNICAL_ARCHITECTURE.md",
        category="架构与链路",
        summary="前端、FastAPI、MySQL、Milvus、LangChain、Dify/RAGFlow 的整体关系和流程图。",
        audience="研发/架构/交付人员",
    ),
    ProjectDocument(
        id="langchain-refactor",
        title="LangChain 重构说明",
        path="docs/LANGCHAIN_REFACTOR.md",
        category="架构与链路",
        summary="LangChain/Milvus RAG 链路、前置问题判断、答案评估和 FAQ 向量管理。",
        audience="后端/AI 链路维护人员",
    ),
    ProjectDocument(
        id="chat-response-time-optimization",
        title="问答耗时记录与优化方案",
        path="docs/CHAT_RESPONSE_TIME_OPTIMIZATION.md",
        category="架构与链路",
        summary="说明每次问答耗时的记录口径、查看位置、慢请求分级和优化方案。",
        audience="后端/AI 链路维护/运维人员",
    ),
    ProjectDocument(
        id="knowledge-vectorization",
        title="知识库向量化整理说明",
        path="docs/KNOWLEDGE_BASE_VECTORIZATION.md",
        category="知识库与向量库",
        summary="资料去重、标准 Markdown 生成、manifest 字段、批量入库和版本管理。",
        audience="知识库运营/后端人员",
    ),
    ProjectDocument(
        id="kb-import-readme",
        title="LangChain/Milvus 知识库转换资料 README",
        path="knowledge_base/langchain_vector_import/README.md",
        category="知识库与向量库",
        summary="当前已整理的法规、政策、企业制度和 FAQ 入库资料统计与使用方法。",
        audience="知识库运营人员",
    ),
    ProjectDocument(
        id="kb-excluded-files",
        title="未纳入向量库资料说明",
        path="knowledge_base/langchain_vector_import/excluded_files.md",
        category="知识库与向量库",
        summary="说明哪些资料不建议直接入库，避免接口、测试、商业材料污染业务问答。",
        audience="知识库运营/审核人员",
    ),
    ProjectDocument(
        id="dify-ragflow",
        title="Dify 与 RAGFlow 配合开发指南",
        path="docs/DIFY_RAGFLOW_GUIDE.md",
        category="架构与链路",
        summary="Dify 工作流输入输出、RAGFlow 资料整理建议和外部服务连接口径。",
        audience="AI 工作流配置人员",
    ),
    ProjectDocument(
        id="security-tenancy",
        title="安全与多租户设计说明",
        path="docs/SECURITY_AND_TENANCY.md",
        category="安全与多租户",
        summary="租户隔离、角色权限、脱敏、限流、数据库连接池和生产上线检查。",
        audience="后端/运维/安全复核人员",
    ),
    ProjectDocument(
        id="automated-test-report",
        title="自动化测试报告",
        path="docs/AUTOMATED_TEST_REPORT.md",
        category="测试验收",
        summary="后端接口、前端契约、安全边界和多轮回归测试覆盖说明。",
        audience="测试/验收人员",
    ),
    ProjectDocument(
        id="backend-readme",
        title="后端 README",
        path="backend/README.md",
        category="前后端说明",
        summary="FastAPI 后端启动、配置、初始化和 LangChain/Milvus/Dify 相关配置。",
        audience="后端开发人员",
    ),
    ProjectDocument(
        id="frontend-readme",
        title="前端 README",
        path="frontend/README.md",
        category="前后端说明",
        summary="Vue 前端启动、页面路由、构建方式和前端技术栈说明。",
        audience="前端开发人员",
    ),
    ProjectDocument(
        id="frontend-requirements",
        title="前端需求文档",
        path="前端需求文档.md",
        category="需求与方案",
        summary="前端页面、交互、管理后台和可视化需求说明。",
        accuracy_status="需求基线文档，部分实现已在代码中迭代",
        audience="产品/前端/验收人员",
    ),
    ProjectDocument(
        id="backend-requirements",
        title="后端需求文档",
        path="后端需求文档.md",
        category="需求与方案",
        summary="后端接口、数据模型、权限和外部系统接入需求说明。",
        accuracy_status="需求基线文档，部分实现已在代码中迭代",
        audience="产品/后端/验收人员",
    ),
    ProjectDocument(
        id="business-proposal",
        title="商业化项目书",
        path="企业用工与社保合规智能平台项目书_商业化正式版.md",
        category="需求与方案",
        summary="平台商业化定位、价值、交付范围和推广方案。",
        accuracy_status="方案材料，技术细节以 docs/ 与 README 为准",
        audience="项目负责人/商务/交付人员",
    ),
    ProjectDocument(
        id="debug-vector-ingest-error",
        title="向量入库错误排查记录",
        path="debug-vector-ingest-error.md",
        category="排障记录",
        summary="历史排障记录，用于理解向量入库问题定位过程。",
        accuracy_status="历史记录，仅作排障参考",
        audience="后端/运维人员",
    ),
    ProjectDocument(
        id="debug-milvus-offline-status",
        title="Milvus 离线状态排查记录",
        path="debug-milvus-offline-status.md",
        category="排障记录",
        summary="历史排障记录，用于理解 Milvus 服务状态定位过程。",
        accuracy_status="历史记录，仅作排障参考",
        audience="后端/运维人员",
    ),
    ProjectDocument(
        id="debug-normal-query-no-match",
        title="普通问题未命中排查记录",
        path="debug-normal-query-no-match.md",
        category="排障记录",
        summary="历史排障记录，用于理解知识库未命中和问答边界问题。",
        accuracy_status="历史记录，仅作排障参考",
        audience="后端/AI 链路维护人员",
    ),
)

DOCUMENTS_BY_ID = {document.id: document for document in DOCUMENTS}


def _resolve_document_path(document: ProjectDocument) -> Path:
    candidate = (PROJECT_ROOT / document.path).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(PROJECT_ROOT):
        raise HTTPException(status_code=404, detail="文档不存在")
    return candidate


def _document_meta(document: ProjectDocument, include_content: bool = False) -> dict:
    file_path = _resolve_document_path(document)
    stat = file_path.stat()
    meta = asdict(document)
    meta.update(
        {
            "size_bytes": stat.st_size,
            "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
    )
    if include_content:
        if stat.st_size > MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="文档过大，暂不支持在线预览")
        meta["content"] = file_path.read_text(encoding="utf-8")
    return meta


@router.get("", response_model=dict)
async def list_project_docs():
    docs = [_document_meta(document) for document in DOCUMENTS]
    categories: dict[str, list[dict]] = {}
    for item in docs:
        categories.setdefault(item["category"], []).append(item)
    return ok({"list": docs, "categories": categories})


@router.get("/{doc_id}", response_model=dict)
async def get_project_doc(doc_id: str):
    document: Optional[ProjectDocument] = DOCUMENTS_BY_ID.get(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ok(_document_meta(document, include_content=True))
