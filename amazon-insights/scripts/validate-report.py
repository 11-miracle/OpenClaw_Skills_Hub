#!/usr/bin/env python3
"""
validate-report.py — HTML 报告结构完整性校验 + fallback 生成

用法:
  python3 validate-report.py <report.html> [--type single|category] [--data <data.json>]

单品报告最低要求：核心 h2 >= 6 个，ECharts 容器 >= 2 个
品类报告最低要求：核心 h2 >= 7 个，ECharts 容器 >= 3 个，details 折叠卡片 >= 1

退出码:
  0 = 校验通过
  1 = 结构不完整（已生成 fallback 报告）
  2 = 文件不存在或为空
"""

import sys
import os
import json
import re
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import get_paths

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("report_path")
    p.add_argument("--type", default="single", choices=["single", "category"])
    p.add_argument("--data", default=None, help="data.json 路径，用于 fallback 分析生成")
    return p.parse_args()

# ─── 结构校验 ────────────────────────────────────────────────────────────────

def validate(html_path, report_type):
    """检查报告结构完整性，返回 (passed, failed_checks)"""
    if not os.path.exists(html_path):
        return False, ["文件不存在"]
    if os.path.getsize(html_path) == 0:
        return False, ["文件为空"]

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 计算各结构数量
    h2_count      = len(re.findall(r"<h2[^>]*>", content, re.IGNORECASE))
    chart_count   = len(re.findall(r'id=["\'][^"\']*chart[^"\']*["\']', content, re.IGNORECASE))
    details_count = len(re.findall(r"<details[^>]*>", content, re.IGNORECASE))
    has_echarts   = "echarts" in content.lower()

    if report_type == "single":
        checks = {
            f"h2标题数量({h2_count})>=6":   h2_count >= 6,
            f"ECharts容器({chart_count})>=2": chart_count >= 2,
            "包含ECharts脚本":               has_echarts,
        }
    else:  # category
        checks = {
            f"h2标题数量({h2_count})>=9":       h2_count >= 9,
            f"ECharts容器({chart_count})>=3":   chart_count >= 3,
            f"details折叠卡片({details_count})>=1": details_count >= 1,
            "包含ECharts脚本":                  has_echarts,
        }

    failed = [k for k, v in checks.items() if not v]
    return len(failed) == 0, failed

# ─── Fallback 分析：规则引擎（不依赖 LLM）────────────────────────────────────

def generate_fallback_analysis(data):
    """基于已有数据用规则引擎生成分析结论，无需 LLM"""
    ra   = data.get("reviews_analysis", {})
    td   = data.get("teardown", {})
    prod = data.get("product", {})

    # 提取关键信息
    top_pain_list = ra.get("keywords", [])
    top_pain = ""
    if top_pain_list:
        top = top_pain_list[0]
        top_pain = top.get("word", top) if isinstance(top, dict) else str(top)

    kano    = ra.get("kano", {})
    must_be = kano.get("must_be", [])
    appeals = ra.get("appeals", {})
    opportunity = ra.get("opportunity", "")

    # 危机方面（负面比例高的维度）
    absa = ra.get("absa", [])
    crisis = [a.get("aspect") or a.get("name", "") for a in absa
              if isinstance(a, dict) and float(a.get("neg_ratio") or a.get("negRatio") or 0) > 0.5]

    # 生成结构化结论（纯规则，不依赖 AI）
    sections = {}

    # 核心痛点
    if top_pain:
        crisis_str = "、".join(crisis[:3]) if crisis else "暂无"
        sections["核心痛点"] = (
            f"用户最常反映的问题是「{top_pain}」。"
            + (f"负面评价集中在：{crisis_str}。" if crisis else "")
        )
    else:
        sections["核心痛点"] = "评论数据不足，暂无法提炼核心痛点。"

    # 基础需求
    if must_be:
        sections["基础需求"] = (
            f"「{'、'.join(must_be[:3])}」属于用户基础预期（KANO Must-be），"
            f"当前满足度不足，是差评的主要来源，需优先改善。"
        )
    else:
        sections["基础需求"] = "暂无 KANO 基础需求数据。"

    # 机会点
    if opportunity:
        sections["机会点"] = opportunity
    elif top_pain:
        sections["机会点"] = (
            f"重点解决「{top_pain}」问题，可作为差异化突破口。"
            + (f"同时强化{appeals and list(appeals.keys())[0] or '产品'}维度竞争力。")
        )
    else:
        sections["机会点"] = "建议深入采集更多评论后进行机会点分析。"

    # Must Copy / Must Avoid
    must_copy  = td.get("must_copy",  [])
    must_avoid = td.get("must_avoid", [])

    return {
        "sections":   sections,
        "must_copy":  must_copy,
        "must_avoid": must_avoid,
        "note":       "以下分析由规则引擎生成（AI 分析暂不可用），结论基于已采集数据。"
    }

# ─── Fallback 报告生成 ───────────────────────────────────────────────────────

def build_fallback_html(data, output_path):
    """生成降级版报告（纯文字，无图表），确保用户拿到分析结论"""
    analysis = generate_fallback_analysis(data)
    prod     = data.get("product", {})
    meta     = data.get("reviews_meta", {})
    asin     = prod.get("asin", "N/A")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections_html = ""
    for title, content in analysis["sections"].items():
        sections_html += f"""
        <div style="background:#fff;border:1px solid #e0e0e0;padding:20px;margin-bottom:16px;">
          <div style="font-size:14px;font-weight:700;color:#2c3e50;margin-bottom:10px;">{title}</div>
          <div style="font-size:13px;line-height:1.8;color:#444;">{content}</div>
        </div>"""

    def list_items(items, icon):
        if not items:
            return '<div style="color:#aaa;font-size:13px;">暂无数据</div>'
        return "".join(
            f'<div style="padding:8px 0;border-bottom:1px solid #f5f5f5;font-size:13px;color:#444;">'
            f'{icon} {item}</div>' for item in items
        )

    note_html = ""
    if meta.get("note"):
        note_html = f"""
        <div style="background:#fff8e1;border-left:4px solid #f57f17;padding:12px 16px;
                    margin-bottom:20px;font-size:13px;line-height:1.8;">
          {meta["note"]}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Amazon 商品洞察（降级版）— {asin}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
          background:#f5f5f5; color:#2c3e50; }}
  .page {{ max-width:960px; margin:0 auto; padding:24px; }}
  .header {{ background:#2c3e50; color:#fff; padding:24px 32px; margin-bottom:24px; }}
  .header h1 {{ font-size:20px; font-weight:700; }}
  .header .meta {{ font-size:13px; opacity:0.7; margin-top:6px; }}
  .card {{ background:#fff; border:1px solid #e0e0e0; padding:24px; margin-bottom:20px; }}
  .card h2 {{ font-size:15px; font-weight:700; color:#2c3e50; margin-bottom:16px;
              padding-bottom:8px; border-bottom:2px solid #2c3e50; }}
  .section-2col {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  footer {{ text-align:center; font-size:12px; color:#aaa; padding:20px; }}
</style>
</head>
<body>
<div class="page">
  <div class="header">
    <h1>📦 Amazon 商品洞察报告（降级版）</h1>
    <div class="meta">ASIN: {asin} &nbsp;|&nbsp;
      站点: {prod.get("domain","amazon.com")} &nbsp;|&nbsp;
      生成时间: {generated_at}</div>
  </div>

  <div style="background:#e3f2fd;border-left:4px solid #1565c0;
              padding:12px 16px;margin-bottom:20px;font-size:13px;line-height:1.8;">
    ℹ️ {analysis["note"]}
  </div>

  {note_html}

  <!-- 基础信息 -->
  <div class="card">
    <h2>基础信息</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <tr><td style="padding:8px 12px;color:#888;width:90px;">标题</td>
          <td style="padding:8px 12px;">{prod.get("title","—")}</td></tr>
      <tr><td style="padding:8px 12px;color:#888;">价格</td>
          <td style="padding:8px 12px;font-weight:600;color:#b71c1c;">
            ${prod.get("price","—")}</td></tr>
      <tr><td style="padding:8px 12px;color:#888;">评分</td>
          <td style="padding:8px 12px;">{prod.get("rating","—")} / 5.0</td></tr>
      <tr><td style="padding:8px 12px;color:#888;">评论数</td>
          <td style="padding:8px 12px;">{prod.get("review_count","—")}</td></tr>
    </table>
  </div>

  <!-- 分析结论 -->
  <div class="card">
    <h2>差评分析结论</h2>
    {sections_html}
  </div>

  <!-- 单品拆解 -->
  <div class="card">
    <h2>单品拆解</h2>
    <div class="section-2col">
      <div style="border:1px solid #c8e6c9;padding:16px;">
        <div style="font-size:13px;font-weight:700;color:#1b5e20;
                    padding-bottom:8px;margin-bottom:12px;
                    border-bottom:1px solid #c8e6c9;">✅ Must Copy</div>
        {list_items(analysis["must_copy"], "✦")}
      </div>
      <div style="border:1px solid #ffcdd2;padding:16px;">
        <div style="font-size:13px;font-weight:700;color:#b71c1c;
                    padding-bottom:8px;margin-bottom:12px;
                    border-bottom:1px solid #ffcdd2;">❌ Must Avoid</div>
        {list_items(analysis["must_avoid"], "⚠")}
      </div>
    </div>
  </div>

  <footer>由 OpenClaw amazon-insights skill 生成（降级版）· {generated_at}</footer>
</div>
</body>
</html>"""

    # fallback 报告存到同目录，文件名加 -fallback 后缀
    fallback_path = output_path.replace(".html", "-fallback.html")
    os.makedirs(os.path.dirname(os.path.abspath(fallback_path)), exist_ok=True)
    with open(fallback_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Fallback 报告已生成: {fallback_path}")
    return fallback_path

# ─── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if not os.path.exists(args.report_path):
        print(f"❌ 文件不存在: {args.report_path}")
        # 如果有 data.json，直接生成 fallback
        if args.data and os.path.exists(args.data):
            data = json.load(open(args.data, "r", encoding="utf-8"))
            fallback_path = build_fallback_html(data, args.report_path)
            print(f"✅ 已生成 fallback 报告: {fallback_path}")
        sys.exit(2)

    passed, failed_checks = validate(args.report_path, args.type)

    if passed:
        print(f"✅ 报告结构校验通过: {args.report_path}")
        sys.exit(0)
    else:
        print(f"⚠️  报告结构不完整，失败项: {', '.join(failed_checks)}")
        # 尝试生成 fallback
        if args.data and os.path.exists(args.data):
            data = json.load(open(args.data, "r", encoding="utf-8"))
            fallback_path = build_fallback_html(data, args.report_path)
            print(f"✅ 已生成 fallback 报告: {fallback_path}")
        else:
            print("ℹ️  未提供 --data，跳过 fallback 生成")
        sys.exit(1)

if __name__ == "__main__":
    main()
