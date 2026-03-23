#!/usr/bin/env python3
"""
generate-batch-summary.py — 生成50个ASIN汇总总览 HTML
用法: python3 generate-batch-summary.py [status.json] [output.html]
"""
import json, os, sys
from datetime import datetime

STATUS_FILE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.openclaw/workspace/batch/status.json")
OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.openclaw/workspace/reports/batch-summary.html")
REPORT_BASE = os.path.expanduser("~/.openclaw/workspace/reports")

d = json.load(open(STATUS_FILE)) if os.path.exists(STATUS_FILE) else {}
total = len(d)
done  = sum(1 for v in d.values() if v.get('status') == 'done')
generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')

status_badge = {
    'done':             ('<span style="background:#1b5e20;color:#fff;padding:2px 8px;font-size:11px;">完成</span>', '#e8f5e9'),
    'failed':           ('<span style="background:#b71c1c;color:#fff;padding:2px 8px;font-size:11px;">失败</span>', '#ffebee'),
    'pending':          ('<span style="background:#757575;color:#fff;padding:2px 8px;font-size:11px;">待处理</span>', '#fafafa'),
    'pending_analysis': ('<span style="background:#e65100;color:#fff;padding:2px 8px;font-size:11px;">分析中</span>', '#fff8e1'),
    'scraping_product': ('<span style="background:#1565c0;color:#fff;padding:2px 8px;font-size:11px;">采集中</span>', '#e3f2fd'),
    'scraping_reviews': ('<span style="background:#1565c0;color:#fff;padding:2px 8px;font-size:11px;">爬评论</span>', '#e3f2fd'),
}

def get_product_info(asin):
    p_file = os.path.join(REPORT_BASE, asin, f"{asin}-product.json")
    if not os.path.exists(p_file):
        return {}, None
    try:
        p = json.load(open(p_file))
        img = (p.get('images') or [None])[0]
        return p, img
    except:
        return {}, None

def get_opportunity(asin):
    d_file = os.path.join(REPORT_BASE, asin, f"{asin}-data.json")
    if not os.path.exists(d_file):
        return ''
    try:
        data = json.load(open(d_file))
        return data.get('reviews_analysis', {}).get('opportunity', '')[:120]
    except:
        return ''

rows_html = ''
for i, (asin, v) in enumerate(sorted(d.items()), 1):
    st = v.get('status', 'unknown')
    badge, row_bg = status_badge.get(st, ('<span style="background:#9e9e9e;color:#fff;padding:2px 8px;font-size:11px;">未知</span>', '#fafafa'))
    product, img_url = get_product_info(asin)
    title   = (product.get('title') or '—')[:60]
    rating  = product.get('rating') or '—'
    price   = product.get('price') or '—'
    reviews = v.get('reviews') or '—'
    oppo    = get_opportunity(asin)
    report_link = os.path.join(REPORT_BASE, asin, f"{asin}-report.html")
    has_report  = os.path.exists(report_link)
    img_html = f'<img src="{img_url}" style="width:48px;height:48px;object-fit:cover;border:1px solid #eee;" onerror="this.style.display=\'none\'">' if img_url else '<div style="width:48px;height:48px;background:#f5f5f5;"></div>'
    link_html = f'<a href="{report_link}" target="_blank" style="color:#1565c0;font-size:12px;">查看报告 →</a>' if has_report else '<span style="color:#bbb;font-size:12px;">未生成</span>'

    rows_html += f'''<tr style="background:{row_bg};">
      <td style="padding:10px 12px;font-size:13px;color:#888;">{i}</td>
      <td style="padding:10px 12px;">{img_html}</td>
      <td style="padding:10px 12px;font-weight:600;font-size:13px;font-family:monospace;">{asin}</td>
      <td style="padding:10px 12px;font-size:13px;max-width:300px;">{title}</td>
      <td style="padding:10px 12px;text-align:center;font-size:13px;">{badge}</td>
      <td style="padding:10px 12px;text-align:center;font-size:13px;font-weight:600;color:#e53935;">{rating}</td>
      <td style="padding:10px 12px;text-align:center;font-size:13px;">{price}</td>
      <td style="padding:10px 12px;text-align:center;font-size:13px;">{reviews}</td>
      <td style="padding:10px 12px;font-size:12px;color:#555;">{oppo}</td>
      <td style="padding:10px 12px;">{link_html}</td>
    </tr>'''

pct = int(done / total * 100) if total else 0

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="60">
<title>批量分析总览 · {done}/{total} 完成</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f5f5f5; color:#2c3e50; }}
  .header {{ background:#2c3e50; color:#fff; padding:24px 32px; }}
  .header h1 {{ font-size:22px; font-weight:700; }}
  .header .meta {{ font-size:13px; opacity:0.7; margin-top:6px; }}
  .page {{ max-width:1400px; margin:0 auto; padding:24px; }}
  .card {{ background:#fff; border:1px solid #e0e0e0; padding:24px; margin-bottom:20px; }}
  .card h2 {{ font-size:15px; font-weight:700; color:#2c3e50; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #2c3e50; }}
  .progress-bar {{ background:#e0e0e0; height:12px; width:100%; margin:12px 0; }}
  .progress-fill {{ background:#2c3e50; height:12px; width:{pct}%; transition:width .3s; }}
  .kpi-row {{ display:grid; grid-template-columns:repeat(5,1fr); gap:16px; margin-bottom:20px; }}
  .kpi {{ background:#fff; border:1px solid #e0e0e0; padding:16px; text-align:center; }}
  .kpi .num {{ font-size:28px; font-weight:700; color:#b71c1c; }}
  .kpi .label {{ font-size:12px; color:#888; margin-top:4px; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th {{ background:#2c3e50; color:#fff; padding:10px 12px; text-align:left; white-space:nowrap; }}
  td {{ border-bottom:1px solid #f0f0f0; vertical-align:middle; }}
  tr:hover td {{ background:#f9f9f9 !important; }}
  footer {{ text-align:center; font-size:12px; color:#aaa; padding:20px; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 Amazon 批量分析总览</h1>
  <div class="meta">共 {total} 个 ASIN &nbsp;|&nbsp; 完成 {done} 个 &nbsp;|&nbsp; 生成时间: {generated_at} &nbsp;|&nbsp; 每60秒自动刷新</div>
</div>
<div class="page">

  <div class="kpi-row">
    <div class="kpi"><div class="num">{total}</div><div class="label">总 ASIN 数</div></div>
    <div class="kpi"><div class="num" style="color:#1b5e20;">{done}</div><div class="label">已完成</div></div>
    <div class="kpi"><div class="num" style="color:#e65100;">{sum(1 for v in d.values() if v.get('status')=='pending_analysis')}</div><div class="label">分析中</div></div>
    <div class="kpi"><div class="num" style="color:#1565c0;">{sum(1 for v in d.values() if 'scraping' in v.get('status',''))}</div><div class="label">采集中</div></div>
    <div class="kpi"><div class="num" style="color:#b71c1c;">{sum(1 for v in d.values() if v.get('status')=='failed')}</div><div class="label">失败</div></div>
  </div>

  <div class="card">
    <h2>进度总览</h2>
    <div style="font-size:13px;color:#888;">完成率 {pct}% ({done}/{total})</div>
    <div class="progress-bar"><div class="progress-fill"></div></div>
  </div>

  <div class="card">
    <h2>ASIN 详细列表</h2>
    <table>
      <thead>
        <tr>
          <th>#</th><th>图片</th><th>ASIN</th><th>商品名</th><th>状态</th>
          <th>评分</th><th>价格</th><th>差评数</th><th>核心机会点</th><th>报告</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

</div>
<footer>由 OpenClaw amazon-insights skill 生成 · {generated_at}</footer>
</body>
</html>'''

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"✅ 汇总报告已生成: {OUTPUT_FILE}")
