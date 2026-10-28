# 雇主独立扩展

本目录及独立入口 app/employer_main.py 由雇主模块实现产生，可以维护。
复用团队 users 模块与组员 candidate 模块时，通过导入或包装实现；不得修改他人已跟踪文件。
数据库迁移使用本目录的 database/ 独立链，测试使用 backend/employer_tests。
从仓库根目录执行 `.venv/Scripts/python.exe -m pytest -c pytest.employer.ini -q`。
进度与接入边界写入独立的 docs/EMPLOYER_*.md，不编辑团队或组员的进度文档。
