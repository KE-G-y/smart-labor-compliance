"""演示租户、政策来源与测试问题初始化。"""

from sqlalchemy.orm import Session

from app.database import settings
from app.models import Admin, KnowledgePackage, Source, Tenant, TestQuestion
from app.security import get_password_hash


SOURCE_SEED = []


TEST_QUESTIONS = [
    {
        "question": "如果员工问陕西产假和生育津贴，回答里必须提醒哪些风险？",
        "category": "假期",
        "difficulty": "normal",
        "expected_points": ["说明演示口径", "提示核验最新政策", "区分产假工资和生育津贴"],
    },
    {
        "question": "员工身份证号 610103199001011234 和手机号 13812345678 能否直接进入知识库？",
        "category": "数据安全",
        "difficulty": "edge",
        "expected_points": ["不能直接入库", "应脱敏", "避免个人敏感信息泄露"],
    },
    {
        "question": "A 租户能查看 B 租户的问答日志吗？",
        "category": "多租户",
        "difficulty": "edge",
        "expected_points": ["不能", "后端按 tenant_id 过滤", "超级管理员仅用于平台运维"],
    },
    {
        "question": "试用期工资低于最低工资有什么风险？",
        "category": "工资",
        "difficulty": "normal",
        "expected_points": ["最低工资", "劳动合同法", "补差或争议风险"],
    },
]


def _get_or_create_demo_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.code == settings.default_tenant_code).first()
    if tenant:
        return tenant

    tenant = Tenant(
        code=settings.default_tenant_code,
        name="陕西演示企业",
        industry="企业服务 / 人力资源",
        region="陕西",
        contact_name="演示管理员",
        contact_email="demo@example.com",
        status="active",
        is_demo=True,
        notes="系统初始化演示租户，用于首期陕西用工与社保合规 MVP。",
    )
    db.add(tenant)
    db.flush()
    return tenant


def _seed_admins(db: Session, tenant: Tenant) -> None:
    existing = db.query(Admin).filter(Admin.username == settings.initial_admin_username).first()
    if not existing:
        db.add(
            Admin(
                username=settings.initial_admin_username,
                password_hash=get_password_hash(settings.initial_admin_password),
                role="super_admin",
                display_name="平台超级管理员",
                is_active=True,
            )
        )

    tenant_admin = db.query(Admin).filter(Admin.username == "tenant_admin", Admin.tenant_id == tenant.id).first()
    if not tenant_admin:
        db.add(
            Admin(
                tenant_id=tenant.id,
                username="tenant_admin",
                password_hash=get_password_hash("Tenant@123456"),
                role="tenant_admin",
                display_name="陕西演示企业管理员",
                is_active=True,
            )
        )


def _seed_sources(db: Session, tenant: Tenant) -> None:
    existing = db.query(Source).filter(Source.tenant_id == tenant.id).order_by(Source.id.asc()).all()
    by_code = {item.source_code: item for item in existing if item.source_code}
    by_title = {item.title: item for item in existing}

    for index, item in enumerate(SOURCE_SEED):
        source = by_code.get(item["source_code"]) or by_title.get(item["title"])
        if not source and index < len(existing):
            source = existing[index]
        if source:
            for field, value in item.items():
                setattr(source, field, value)
        else:
            db.add(Source(tenant_id=tenant.id, **item))
    db.flush()


def _seed_packages(db: Session, tenant: Tenant) -> None:
    if db.query(KnowledgePackage).filter(KnowledgePackage.tenant_id == tenant.id).count():
        return
    db.add(
        KnowledgePackage(
            tenant_id=tenant.id,
            name="陕西用工与社保合规知识包",
            region="陕西",
            version="mvp-2026.05",
            description="首期 MVP 演示知识包，包含劳动合同、工资、社保、医保、假期、仲裁等高频场景。",
            categories=["劳动合同", "工资", "社保", "医保", "假期", "仲裁", "数据安全"],
            status="active",
        )
    )


def _seed_test_questions(db: Session, tenant: Tenant) -> None:
    if db.query(TestQuestion).filter(TestQuestion.tenant_id == tenant.id).count():
        return
    for item in TEST_QUESTIONS:
        db.add(TestQuestion(tenant_id=tenant.id, region="陕西", **item))


def seed_initial_data(db: Session) -> None:
    """初始化演示数据，幂等执行。"""
    tenant = _get_or_create_demo_tenant(db)
    _seed_admins(db, tenant)
    _seed_sources(db, tenant)
    _seed_packages(db, tenant)
    _seed_test_questions(db, tenant)
    db.commit()
