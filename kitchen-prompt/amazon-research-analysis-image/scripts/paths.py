"""
paths.py — 跨平台路径解析公共模块（amazon-product-research）

优先级：
  1. 环境变量 OPENCLAW_WORKSPACE / OPENCLAW_SKILL_DIR（用户自定义）
  2. 平台自动推导（Mac/Linux/Windows）

用法：
  from paths import get_paths
  P = get_paths("wireless-earbuds")
  print(P['workspace'])   # Mac/Linux: ~/.openclaw/workspace | Windows: %APPDATA%/openclaw/workspace
  print(P['run_dir'])     # ~/.openclaw/workspace/amazon-research/wireless-earbuds
"""

import os
import platform
import sys


def get_paths(slug: str = "") -> dict:
    """
    返回所有关键路径字典，可选传入 slug 自动生成运行目录。

    返回字段：
      workspace   — OpenClaw 工作目录根
      research    — 研究根目录（amazon-research/）
      memory      — 状态/记忆文件目录
      scripts     — 当前 skill 的 scripts 目录
      skill_root  — 当前 skill 根目录
      run_dir     — 当前 slug 的运行目录（需传 slug）
    """

    # ── 1. 优先读环境变量 ────────────────────────────────────────────────────
    env_workspace = os.environ.get("OPENCLAW_WORKSPACE", "").strip()
    env_skill_dir = os.environ.get("OPENCLAW_SKILL_DIR", "").strip()

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

    # ── 3. Skill 脚本目录（相对本文件自动推导） ──────────────────────────────
    if env_skill_dir:
        skill_root = env_skill_dir
    else:
        # paths.py 位于 skills/amazon-product-research/scripts/，上溯两级即 skill 根
        _this_file = os.path.abspath(__file__)
        skill_root = os.path.dirname(os.path.dirname(_this_file))

    scripts_dir = os.path.join(skill_root, "scripts")

    # ── 4. 组装所有路径 ──────────────────────────────────────────────────────
    paths = {
        "workspace":  workspace,
        "research":   os.path.join(workspace, "amazon-research"),
        "memory":     os.path.join(workspace, "memory"),
        "scripts":    scripts_dir,
        "skill_root": skill_root,
        "system":     system,
    }

    if slug:
        paths["run_dir"]      = os.path.join(paths["research"], slug)
        paths["products_dir"] = os.path.join(paths["research"], slug, "products")
        paths["reviews_dir"]  = os.path.join(paths["research"], slug, "reviews")

    return paths


def ensure_dirs(slug: str = "") -> dict:
    """get_paths() + 自动创建所有必要目录"""
    P = get_paths(slug)
    for key in ("research", "memory"):
        os.makedirs(P[key], exist_ok=True)
    if slug:
        os.makedirs(P["products_dir"], exist_ok=True)
        os.makedirs(P["reviews_dir"],  exist_ok=True)
    return P


# ── CLI 调试入口 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    slug = sys.argv[1] if len(sys.argv) > 1 else ""
    P = get_paths(slug)
    print(json.dumps(P, ensure_ascii=False, indent=2))
