"""独立版本表、独立元数据，不导入 Settings 或团队数据库 Session。"""

from alembic import context

from app.candidate.database.model import OwnedModel, include_object

# 独立迁移只比较本项目的元数据，使用自己的版本表并检查类型及默认值。
options = dict(
    target_metadata=OwnedModel.metadata,
    include_object=include_object,
    version_table="alembic_owned_version",
    compare_type=True,
    compare_server_default=True,
)

if context.is_offline_mode():
    # 离线模式生成 SQL，不连接数据库，因此必须明确提供目标数据库 URL。
    url = context.config.attributes.get("database_url")
    if not url:
        raise ValueError("Offline migration requires an explicit database URL")
    context.configure(url=url, literal_binds=True, **options)
    with context.begin_transaction():
        context.run_migrations()
else:
    # 在线模式复用调用方显式传入的连接，在事务中执行迁移。
    connection = context.config.attributes.get("connection")
    if connection is None:
        raise ValueError("Pass an explicit connection through migration.config_for")
    context.configure(connection=connection, **options)
    with context.begin_transaction():
        context.run_migrations()
