"""将真实React组件单测纳入同一非交互测试命令。"""

from pathlib import Path
import os
import shutil
import subprocess


def test_fp_sec_3_actual_component_escapes_required_text():
    root = Path(__file__).resolve().parents[2]
    node = os.environ.get("NODE_BINARY") or shutil.which("node")
    assert node, (
        "Install Node and run npm ci in frontend before running the complete unit suite"
    )
    result = subprocess.run(
        [node, "--test", str(root / "frontend/tests/rendering.unit.mjs")],
        cwd=root / "frontend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
