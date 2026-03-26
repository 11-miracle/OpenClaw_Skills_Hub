"""
paths.py — 跨平台路径解析公共模块

优先级：
  1. 环境变量 OPENCLAW_WORKSPACE / OPENCLAW_SKILL_DIR（用户自定义）
  2. 平台自动推导（Mac/Linux/Windows）

用法：
  from paths import get_paths
  P = get_paths()
  print(P['workspace'])   # Mac/Linux: ~/.openclaw/workspace | Windows: %APPDATA%/openclaw/workspace
  print(P['scripts'])     # ~/openclaw/skills/amazon-insights/scripts
"""

import os
import platform
import sys


def get_paths(asin: str = "") -> dict:
    """
    返回所有关键路径字典，可选传入 asin 自动生成报告目录。

    返回字段：
      workspace   — OpenClaw 工作目录根
      reports     — 报告根目录
      batch       — 批量任务目录
      memory      — 状态/记忆文件目录
      scripts     — 当前 skill 的 scripts 目录
      skill_root  — 当前 skill 根目录
      report_dir  — 单个 ASIN 报告目录（需传 asin）
    """

    # ── 1. 优先读环境变量 ────────────────────────────────────────────────────
    env_workspace  = os.environ.get("OPENCLAW_WORKSPACE", "").strip()
    env_skill_dir  = os.environ.get("OPENCLAW_SKILL_DIR", "").strip()

    # ── 2. 按平台自动推导 ────────────────────────────────────────────────────
    system = platform.system()  # 'Darwin' | 'Linux' | 'Windows'

    if env_workspace:
        workspace = env_workspace
    elif system == "Windows":
        appdata   = os.environ.get("APPDATA") or os.path.expanduser("~")
        workspace = os.path.join(appdata, "openclaw", "workspace")
    else:
        # Mac / Linux 统一
        workspace = os.path.expanduser("~/.openclaw/workspace")

    # ── 3. Skill 脚本目录（相对本文件自动推导，兼容任意安装位置）───────────
    if env_skill_dir:
        skill_root = env_skill_dir
    else:
        # paths.py 位于 skills/amazon-insights/scripts/，上溯两级即 skill 根
        _this_file = os.path.abspath(__file__)
        skill_root = os.path.dirname(os.path.dirname(_this_file))

    scripts_dir = os.path.join(skill_root, "scripts")

    # ── 4. 组装所有路径 ──────────────────────────────────────────────────────
    paths = {
        "workspace":  workspace,
        "reports":    os.path.join(workspace, "reports"),
        "batch":      os.path.join(workspace, "batch"),
        "memory":     os.path.join(workspace, "memory"),
        "scripts":    scripts_dir,
        "skill_root": skill_root,
        "system":     system,
    }

    if asin:
        paths["report_dir"] = os.path.join(paths["reports"], asin)

    return paths


def ensure_dirs(asin: str = "") -> dict:
    """get_paths() + 自动创建所有必要目录"""
    P = get_paths(asin)
    for key in ("reports", "batch", "memory"):
        os.makedirs(P[key], exist_ok=True)
    if asin and "report_dir" in P:
        os.makedirs(P["report_dir"], exist_ok=True)
    return P


def shell_path(p: str) -> str:
    """
    输出适合当前平台 shell 使用的路径字符串。
    Windows 下转换为反斜杠（PowerShell 两种都支持，但正斜杠更安全，保持不变）。
    """
    return p.replace("\\", "/") if platform.system() != "Windows" else p


# ── CLI 调试入口 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    asin = sys.argv[1] if len(sys.argv) > 1 else ""
    P = get_paths(asin)
    print(json.dumps(P, ensure_ascii=False, indent=2))
