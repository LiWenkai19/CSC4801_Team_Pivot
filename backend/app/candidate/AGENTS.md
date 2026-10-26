# 候选人独立扩展

本目录及独立入口 app/candidate_main.py 由用户与助手在候选人开发中产生，可以维护。
复用团队 users 模块时，通过继承、导入或包装实现；不得修改 users、core、db 或原 main.py。
迁移使用 backend/candidate_alembic 与 alembic.candidate.ini；测试使用 backend/candidate_tests。
从仓库根目录执行 `.venv/Scripts/python.exe -m pytest -c pytest.candidate.ini -q`。
进度与接入边界写入独立的 docs/CANDIDATE_*.md，不编辑团队进度文档。
