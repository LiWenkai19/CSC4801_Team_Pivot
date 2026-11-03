# 候选人独立扩展

本目录由用户与助手在候选人开发中产生，可以维护。
用户于 2026-11-03 更新协作规则：优先在职责相符的已有文件中添加功能，包括队友文件，但不得修改队友已有代码逻辑；详见工作区根目录 AGENTS.md。
共享入口为 app/main.py；总 Alembic 使用 backend/alembic.ini、backend/alembic/env.py 和统一版本目录；测试使用 backend/tests/candidate。
从仓库根目录执行 `.venv/Scripts/python.exe -m pytest -o pythonpath=backend backend/tests/candidate -q`。
进度与接入边界写入独立的 docs/CANDIDATE_*.md，不编辑团队进度文档。
