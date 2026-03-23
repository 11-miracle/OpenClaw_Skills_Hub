#!/usr/bin/env python3
"""
generate-report.py — 生成标准化 HTML 商品洞察报告
用法: python3 generate-report.py <product.json> <output.html> [reviews_meta.json]

报告结构（7模块固定顺序）：
  1. Header
  2. 基础信息（标题/价格/评分/五点/主图）
  3. 详情图 & 视觉分析
  4. 差评分析（采集说明 / 关键词 / APPEALS / KANO / 雷达图 / 机会点）
  5. 单品拆解（Must Copy / Must Avoid）
  6. 差评原声剧场
  7. Footer
"""

import json, sys, os
from datetime import datetime

def load(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def render_stars(rating):
    try:
        r = float(str(rating).split()[0])
        full = int(r)
        half = 1 if (r - full) >= 0.5 else 0
        empty = 5 - full - half
        return '★' * full + ('½' if half else '') + '☆' * empty
    except:
        return '—'

def img_grid(urls, max_n=6):
    if not urls:
        return '<p style="color:#aaa;font-size:13px;">暂无图片</p>'
    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;">'
    for u in (urls or [])[:max_n]:
        html += f'<a href="{u}" target="_blank"><img src="{u}" style="width:100%;border:1px solid #eee;" loading="lazy" onerror="this.style.display=\'none\'"></a>'
    return html + '</div>'

def kw_tags(kw_list):
    if not kw_list:
        return '<span style="color:#aaa;font-size:13px;">暂无关键词数据</span>'
    colors = ['#b71c1c','#c62828','#d32f2f','#e53935','#ef5350',
              '#1565c0','#1976d2','#1e88e5','#2196f3','#42a5f5']
    html = ''
    for i, kw in enumerate(kw_list[:20]):
        word  = kw.get('word', kw)  if isinstance(kw, dict) else kw
        count = kw.get('count', '') if isinstance(kw, dict) else ''
        color = colors[i % len(colors)]
        cnt_html = f' <small>({count})</small>' if count else ''
        html += f'<span style="display:inline-block;background:{color};color:#fff;padding:4px 10px;margin:3px;border-radius:2px;font-size:13px;">{word}{cnt_html}</span>'
    return html

def kano_rows(kano):
    rows = ''
    cats = [
        ('must_be',     'Must-be',     '基础需求（未满足用户会愤怒）', '#b71c1c'),
        ('performance', 'Performance', '期望需求（用户抱怨不够好）',   '#e65100'),
        ('attractive',  'Attractive',  '兴奋需求（超出预期的惊喜点）', '#1b5e20'),
    ]
    for key, label, desc, color in cats:
        items = kano.get(key, [])
        content = '、'.join(items) if items else '—'
        rows += f'''<tr>
          <td style="padding:10px;font-weight:bold;color:{color};white-space:nowrap;">{label}</td>
          <td style="padding:10px;color:#666;font-size:12px;">{desc}</td>
          <td style="padding:10px;font-size:13px;">{content}</td>
        </tr>'''
    return rows

def review_cards(reviews):
    if not reviews:
        return '<p style="color:#aaa;text-align:center;font-size:13px;">暂无评论数据</p>'
    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;">'
    for r in reviews[:9]:
        stars_n = r.get('stars') or r.get('rating') or r.get('ratingScore') or 0
        try: stars_n = int(float(str(stars_n).split()[0]))
        except: stars_n = 2
        star_html = '★' * stars_n + '☆' * max(0, 5 - stars_n)
        body  = str(r.get('body') or r.get('reviewDescription') or r.get('text') or '')[:280]
        title_r = str(r.get('title') or r.get('reviewTitle') or '')
        date_r  = str(r.get('date')  or r.get('reviewDate')  or '')
        domain_r = str(r.get('domain') or '')
        domain_badge = f'<span style="background:#e3f2fd;color:#1565c0;font-size:10px;padding:1px 5px;margin-left:6px;">{domain_r}</span>' if domain_r and domain_r != 'amazon.com' else ''
        html += f'''<div style="border:1px solid #eee;padding:16px;background:#fff;">
          <div style="color:#e53935;font-size:18px;margin-bottom:6px;">{star_html}{domain_badge}</div>
          <div style="font-weight:bold;margin-bottom:8px;font-size:13px;">{title_r}</div>
          <div style="font-size:13px;color:#333;line-height:1.6;">{body}</div>
          <div style="font-size:11px;color:#aaa;margin-top:8px;">{date_r}</div>
        </div>'''
    return html + '</div>'

def must_items(items, color, icon):
    if not items:
        return '<p style="color:#aaa;font-size:13px;">—</p>'
    html = ''
    for item in items:
        html += f'<div style="padding:8px 0;border-bottom:1px solid #f5f5f5;font-size:13px;line-height:1.7;color:#444;">{icon} {item}</div>'
    return html

def review_meta_block(meta):
    """评论采集说明模块"""
    if not meta:
        return ''
    total      = meta.get('total', 0)
    domains    = meta.get('domains_tried', [])
    success    = meta.get('domains_success', {})
    reached    = meta.get('reached_minimum', True)
    note       = meta.get('note', '')
    method     = meta.get('method', 'browser')

    method_label = {'browser': '浏览器自动化', 'apify': 'Apify API', 'mixed': '混合采集'}.get(method, method)
    domains_str  = ' → '.join(domains) if domains else 'amazon.com'
    success_str  = ' / '.join(f'{d}:{n}条' for d, n in success.items()) if success else f'{total}条'

    bg_color = '#e8f5e9' if reached else '#fff8e1'
    border   = '#1b5e20' if reached else '#f57f17'
    icon     = '✅' if reached else '⚠️'

    note_html = f'<div style="margin-top:8px;color:#b71c1c;font-size:13px;">{note}</div>' if note and not reached else ''

    return f'''<div style="background:{bg_color};border-left:4px solid {border};padding:12px 16px;margin-bottom:16px;font-size:13px;line-height:1.8;">
      {icon} <strong>评论采集说明</strong><br>
      采集方式：{method_label} &nbsp;|&nbsp; 尝试站点：{domains_str} &nbsp;|&nbsp; 实际获取：{success_str} &nbsp;|&nbsp; 合计：{total} 条
      {note_html}
    </div>'''

def generate_html(product, reviews_analysis, image_analysis, teardown, reviews_meta, generated_at):
    asin         = product.get('asin', 'N/A')
    domain       = product.get('domain', 'amazon.com')
    title        = product.get('title', '—')
    price        = product.get('price', '—')
    rating       = product.get('rating', '—')
    review_count = product.get('review_count', '—')
    bullets      = product.get('bullets', [])
    images       = product.get('images', [])
    aplus_images = product.get('aplus_images', [])

    keywords       = reviews_analysis.get('keywords', [])
    kano           = reviews_analysis.get('kano', {})
    opportunity    = reviews_analysis.get('opportunity', '')
    sample_reviews = reviews_analysis.get('sample_reviews', [])
    appeals        = reviews_analysis.get('appeals', {})
    must_copy      = teardown.get('must_copy', [])
    must_avoid     = teardown.get('must_avoid', [])
    identity_tag   = teardown.get('identity_tag', '')
    teardown_conclusion = teardown.get('conclusion', '')

    bullets_html = ''.join(
        f'<li style="margin-bottom:8px;line-height:1.6;">{b}</li>' for b in bullets
    ) or '<li style="color:#aaa">暂无数据</li>'

    appeals_labels = list(appeals.keys()) if appeals else ['Price','Performance','Packaging','Ease','Action','Life','Social']
    appeals_values = list(appeals.values()) if appeals else [1]*7

    # 雷达图数据（期望 vs 实测，从reviews_analysis读取或默认）
    radar_expect = reviews_analysis.get('radar_expect', [8,8,8,8,8,8])
    radar_actual = reviews_analysis.get('radar_actual', [5,5,5,5,5,5])

    price_display = f'${price}' if price and not str(price).startswith('$') else (price or '—')
    identity_badge = f'<span style="background:#e53935;color:#fff;font-size:11px;padding:2px 8px;margin-left:8px;">{identity_tag}</span>' if identity_tag else ''

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Amazon 商品洞察 — {asin}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f5f5f5; color:#2c3e50; }}
  .page {{ max-width:1200px; margin:0 auto; padding:24px; }}
  .header {{ background:#2c3e50; color:#fff; padding:24px 32px; margin-bottom:24px; }}
  .header h1 {{ font-size:22px; font-weight:700; }}
  .header .meta {{ font-size:13px; opacity:0.7; margin-top:6px; }}
  .card {{ background:#fff; border:1px solid #e0e0e0; padding:24px; margin-bottom:20px; }}
  .card h2 {{ font-size:15px; font-weight:700; color:#2c3e50; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #2c3e50; }}
  .info-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
  .info-table {{ width:100%; border-collapse:collapse; }}
  .info-table td {{ padding:8px 12px; border-bottom:1px solid #f0f0f0; font-size:13px; }}
  .info-table td:first-child {{ color:#888; width:90px; white-space:nowrap; }}
  .info-table td:last-child {{ font-weight:500; }}
  .rating-big {{ font-size:36px; font-weight:700; color:#e53935; }}
  .rating-stars {{ color:#f4a22d; font-size:20px; }}
  .section-2col {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .section-3col {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:16px; }}
  .opportunity-box {{ background:#e8f5e9; border-left:4px solid #1b5e20; padding:16px; margin-top:16px; font-size:14px; line-height:1.7; color:#1b5e20; font-weight:500; }}
  .must-box {{ border:1px solid #e0e0e0; padding:16px; }}
  .must-box h3 {{ font-size:13px; font-weight:700; padding-bottom:8px; margin-bottom:12px; border-bottom:1px solid #f0f0f0; }}
  .must-copy h3 {{ color:#1b5e20; border-color:#c8e6c9; }}
  .must-avoid h3 {{ color:#b71c1c; border-color:#ffcdd2; }}
  table.kano {{ width:100%; border-collapse:collapse; }}
  table.kano td {{ border:1px solid #eee; }}
  .teardown-conclusion {{ background:#f5f5f5; border-left:4px solid #2c3e50; padding:14px 16px; margin-top:16px; font-size:13px; line-height:1.8; color:#444; }}
  footer {{ text-align:center; font-size:12px; color:#aaa; padding:20px; }}
</style>
</head>
<body>
<div class="page">

  <!-- 1. Header -->
  <div class="header">
    <h1>📦 Amazon 商品洞察报告{identity_badge}</h1>
    <div class="meta">ASIN: {asin} &nbsp;|&nbsp; 站点: {domain} &nbsp;|&nbsp; 生成时间: {generated_at}</div>
  </div>

  <!-- 2. 基础信息 -->
  <div class="card">
    <h2>基础信息</h2>
    <div class="info-grid">
      <div>
        <table class="info-table">
          <tr><td>标题</td><td>{title}</td></tr>
          <tr><td>价格</td><td><strong style="color:#b71c1c;font-size:16px;">{price_display}</strong></td></tr>
          <tr><td>评分</td><td>
            <span class="rating-big">{rating}</span>
            <span class="rating-stars">{render_stars(rating)}</span>
            <span style="color:#888;font-size:12px;"> / {review_count} 条评论</span>
          </td></tr>
          <tr><td>链接</td><td><a href="https://www.{domain}/dp/{asin}" target="_blank" style="color:#1565c0;font-size:12px;">查看商品页面 →</a></td></tr>
        </table>
        <div style="margin-top:16px;">
          <div style="font-size:13px;color:#888;margin-bottom:8px;">五点描述</div>
          <ul style="padding-left:18px;font-size:13px;">{bullets_html}</ul>
        </div>
      </div>
      <div>
        <div style="font-size:13px;color:#888;margin-bottom:8px;">商品主图</div>
        {img_grid(images, 6)}
      </div>
    </div>
  </div>

  <!-- 3. 详情图 & 视觉分析 -->
  <div class="card">
    <h2>详情图 &amp; 视觉分析</h2>
    <div style="margin-bottom:16px;">
      <div style="font-size:13px;color:#888;margin-bottom:8px;">A+ 详情图（前5张）</div>
      {img_grid(aplus_images, 5)}
    </div>
    <div>
      <div style="font-size:13px;color:#888;margin-bottom:8px;">视觉分析 &amp; 文案提取</div>
      <div style="font-size:13px;line-height:1.8;background:#fafafa;padding:16px;border:1px solid #eee;white-space:pre-wrap;">{image_analysis or "（待 AI 分析）"}</div>
    </div>
  </div>

  <!-- 4. 差评分析 -->
  <div class="card">
    <h2>差评分析（3星及以下）</h2>
    {review_meta_block(reviews_meta)}
    <div class="section-2col">
      <div>
        <div style="font-size:13px;color:#888;margin-bottom:12px;">🔑 核心痛点关键词</div>
        <div>{kw_tags(keywords)}</div>
      </div>
      <div>
        <div style="font-size:13px;color:#888;margin-bottom:8px;">📊 $APPEALS 维度分布</div>
        <div id="appealsChart" style="height:220px;"></div>
      </div>
    </div>
    <div style="margin-top:20px;">
      <div style="font-size:13px;color:#888;margin-bottom:12px;">🧩 KANO 模型洞察</div>
      <table class="kano">{kano_rows(kano)}</table>
    </div>
    <div style="margin-top:20px;">
      <div style="font-size:13px;color:#888;margin-bottom:8px;">📡 满意度鸿沟雷达</div>
      <div id="radarChart" style="height:280px;"></div>
    </div>
    {'<div class="opportunity-box">💡 <strong>一句话机会点：</strong>' + opportunity + '</div>' if opportunity else ''}
  </div>

  <!-- 5. 单品拆解 -->
  <div class="card">
    <h2>单品拆解</h2>
    <div class="section-2col">
      <div class="must-box must-copy">
        <h3>✅ Must Copy — 必修课</h3>
        {must_items(must_copy, '#1b5e20', '✦')}
      </div>
      <div class="must-box must-avoid">
        <h3>❌ Must Avoid — 避雷针</h3>
        {must_items(must_avoid, '#b71c1c', '⚠')}
      </div>
    </div>
    {'<div class="teardown-conclusion">💡 ' + teardown_conclusion + '</div>' if teardown_conclusion else ''}
  </div>

  <!-- 6. 差评原声剧场 -->
  <div class="card">
    <h2>差评原声剧场（真实评论摘录）</h2>
    {review_cards(sample_reviews)}
  </div>

  <!-- 7. Footer -->
  <footer>由 OpenClaw amazon-insights skill 生成 · {generated_at}</footer>
</div>

<script>
// $APPEALS 玫瑰图
var c1 = echarts.init(document.getElementById('appealsChart'));
c1.setOption({{
  tooltip: {{ trigger:'item', formatter:'{{b}}: {{c}} ({{d}}%)' }},
  color: ['#b71c1c','#c62828','#d32f2f','#e53935','#1565c0','#1976d2','#1b5e20'],
  series: [{{
    type:'pie', radius:['30%','70%'], roseType:'radius',
    data: {json.dumps(appeals_labels)}.map(function(l,i){{
      return {{ name:l, value:{json.dumps(appeals_values)}[i] || 1 }};
    }}),
    itemStyle: {{ borderRadius:0, borderColor:'#fff', borderWidth:2 }},
    label: {{ fontSize:11 }}
  }}]
}});

// 满意度雷达
var c2 = echarts.init(document.getElementById('radarChart'));
c2.setOption({{
  tooltip: {{}},
  legend: {{ data:['用户期望','竞品实测'], bottom:0, textStyle:{{fontSize:12}} }},
  color: ['#1565c0','#e53935'],
  radar: {{
    indicator: ['成分安全','配方稳定','产品效果','适口性','包装质量','售后服务'].map(function(n){{return{{name:n,max:10}}}}),
    radius:'60%'
  }},
  series: [{{
    type:'radar',
    data: [
      {{ value:{json.dumps(radar_expect)}, name:'用户期望', areaStyle:{{opacity:0.1}} }},
      {{ value:{json.dumps(radar_actual)},  name:'竞品实测', areaStyle:{{color:'rgba(229,57,53,0.15)'}} }}
    ]
  }}]
}});
</script>
</body>
</html>'''

def main():
    if len(sys.argv) < 3:
        print("用法: python3 generate-report.py <product.json> <output.html> [data.json]")
        sys.exit(1)

    product_path = sys.argv[1]
    output_path  = sys.argv[2]
    data_path    = sys.argv[3] if len(sys.argv) > 3 else None

    product = load(product_path)
    # 如果传了 data.json，从中读取分析结果
    data = load(data_path) if data_path else {}

    reviews_analysis = data.get('reviews_analysis', {})
    image_analysis   = data.get('image_analysis', '')
    teardown         = data.get('teardown', {})
    reviews_meta     = data.get('reviews_meta', {})

    # 兼容：product 可能直接在 data.product 里
    if not product and data.get('product'):
        product = data['product']

    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    html = generate_html(product, reviews_analysis, image_analysis, teardown, reviews_meta, generated_at)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ 报告已生成: {output_path}")

if __name__ == '__main__':
    main()
