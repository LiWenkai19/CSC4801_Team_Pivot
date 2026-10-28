"""独立版本表、独立元数据，不导入 Settings 或团队数据库 Session。"""

from alembic import context

from app.employer.model import EmployerModel

EMPLOYER_TABLES = frozenset({"job", "job_skill", "employer_company"})


def include_object(obj, name, type_, reflected, compare_to):
    """只比较本模块自己创建的三张表；雇主资料表由团队模型描述。"""
    if type_ == "table":
        return name in EMPLOYER_TABLES
    return True


options = dict(
    target_metadata=EmployerModel.metadata,
    include_object=include_object,
    version_table="alembic_employer_version",
    compare_type=True,
    compare_server_default=True,
)

if context.is_offline_mode():
    url = context.config.attributes.get("database_url")
    if not url:
        raise ValueError("Offline migration requires an explicit database URL")
    context.configure(url=url, literal_binds=True, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is None:
        raise ValueError("Pass an explicit connection through migration.config_for")
    context.configure(connection=connection, **options)
    with context.begin_transaction():
        context.run_migrations()
