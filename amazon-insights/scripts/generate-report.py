#!/usr/bin/env python3
"""generate-report.py v2 — 专业化单品洞察报告"""
import json, sys, os, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import get_paths, ensure_dirs

def load(path):
    if not path or not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

def render_stars(rating):
    try:
        r = float(str(rating).split()[0])
        full = int(r); half = 1 if (r - full) >= 0.5 else 0; empty = 5 - full - half
        return '★' * full + ('½' if half else '') + '☆' * empty
    except: return '—'

def img_grid(urls, max_n=6):
    if not urls:
        return '<p style="color:#aaa;font-size:13px;padding:20px;text-align:center;background:#fafafa;border:1px dashed #ddd;">暂无图片数据</p>'
    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;">'
    for u in (urls or [])[:max_n]:
        html += (f'<a href="{u}" target="_blank">'
                 f'<img src="{u}" style="width:100%;border:1px solid #eee;display:block;" '
                 f'loading="lazy" onerror="this.parentNode.style.display=\'none\'"></a>')
    return html + '</div>'

def review_meta_block(meta):
    if not meta: return ''
    total = meta.get('total', 0); reached = meta.get('reached_minimum', True)
    note = meta.get('note', ''); domains = meta.get('domains_tried', [])
    success = meta.get('domains_success', {})
    domains_str = ' → '.join(domains) if domains else 'amazon.com'
    success_str = ' / '.join(f'{k}:{v}条' for k, v in success.items()) if success else f'{total}条'
    bg = '#e8f5e9' if reached else '#fff8e1'
    border = '#1b5e20' if reached else '#f57f17'
    icon = '✅' if reached else '⚠️'
    note_html = f'<div style="margin-top:6px;color:#b71c1c;font-size:12px;">{note}</div>' if note and not reached else ''
    return (f'<div style="background:{bg};border-left:4px solid {border};padding:10px 14px;'
            f'margin-bottom:16px;font-size:12px;line-height:1.8;">'
            f'{icon} <strong>评论采集</strong>：站点 {domains_str} &nbsp;|&nbsp; '
            f'实际获取 {success_str}{note_html}</div>')

def kano_cards(kano):
    cats = [
        ('must_be',     'Must-be 基础需求',   '未满足则用户愤怒', '#b71c1c', '#ffebee'),
        ('performance', 'Performance 期望需求', '不够好则投诉',    '#e65100', '#fff3e0'),
        ('attractive',  'Attractive 魅力需求',  '超预期的惊喜点',  '#1b5e20', '#e8f5e9'),
    ]
    html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px;">'
    for key, label, desc, color, bg in cats:
        items = kano.get(key, [])
        items_html = (''.join(
            f'<div style="padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.05);font-size:12px;color:#444;">• {it}</div>'
            for it in items)
            if items else '<div style="color:#aaa;font-size:12px;">暂无数据</div>')
        html += (f'<div style="background:{bg};border:1px solid {color};padding:14px;">'
                 f'<div style="font-weight:700;color:{color};font-size:13px;margin-bottom:4px;">{label}</div>'
                 f'<div style="font-size:11px;color:#888;margin-bottom:10px;">{desc}</div>'
                 f'{items_html}</div>')
    return html + '</div>'

def must_items(items, icon):
    if not items: return '<p style="color:#aaa;font-size:13px;">—</p>'
    return ''.join(
        f'<div style="padding:9px 0;border-bottom:1px solid #f5f5f5;font-size:13px;line-height:1.7;color:#444;">{icon} {item}</div>'
        for item in items)

def review_cards_tagged(reviews, keywords):
    if not reviews:
        return '<p style="color:#aaa;text-align:center;font-size:13px;padding:20px;">暂无评论数据</p>'
    kw_words = [kw.get('word', str(kw)) if isinstance(kw, dict) else str(kw) for kw in keywords[:8]]
    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;">'
    for r in reviews[:9]:
        stars_n = r.get('stars') or r.get('rating') or 0
        try: stars_n = int(float(str(stars_n).split()[0]))
        except: stars_n = 2
        star_html = f'<span style="color:#e53935;">{"★"*stars_n}{"☆"*max(0,5-stars_n)}</span>'
        body = str(r.get('body') or r.get('reviewDescription') or '')[:300]
        for kw in kw_words:
            kw_clean = kw.strip()
            if kw_clean and len(kw_clean) > 1:
                body = re.sub(f'({re.escape(kw_clean)})', r'<mark style="background:#fff3e0;padding:0 2px;">\1</mark>',
                              body, flags=re.IGNORECASE, count=2)
        title_r = str(r.get('title') or '')
        date_r = str(r.get('date') or '')
        domain_r = str(r.get('domain') or '')
        domain_badge = (f'<span style="background:#e3f2fd;color:#1565c0;font-size:10px;padding:1px 5px;margin-left:6px;">{domain_r}</span>'
                        if domain_r and domain_r != 'amazon.com' else '')
        title_html = f'<div style="font-weight:600;margin-bottom:8px;font-size:13px;color:#2c3e50;">{title_r}</div>' if title_r else ''
        html += (f'<div style="border:1px solid #e0e0e0;padding:16px;background:#fff;">'
                 f'<div style="margin-bottom:6px;">{star_html}{domain_badge}</div>'
                 f'{title_html}'
                 f'<div style="font-size:13px;color:#444;line-height:1.7;">{body}</div>'
                 f'<div style="font-size:11px;color:#aaa;margin-top:10px;">{date_r}</div></div>')
    return html + '</div>'

def build_html(product, reviews_analysis, image_analysis, teardown, reviews_meta, generated_at):
    asin         = product.get('asin', 'N/A')
    domain       = product.get('domain', 'amazon.com')
    title        = product.get('title', '—')
    price        = product.get('price', '—')
    rating       = product.get('rating', '—')
    review_count = product.get('review_count', '—')
    bullets      = product.get('bullets', [])
    images       = product.get('images', [])
    aplus_images = product.get('aplus_images') or product.get('apluses') or []

    keywords    = reviews_analysis.get('keywords', [])
    kano        = reviews_analysis.get('kano', {})
    opportunity = reviews_analysis.get('opportunity', '')
    sample_revs = reviews_analysis.get('sample_reviews', [])
    appeals     = reviews_analysis.get('appeals', {})
    absa        = reviews_analysis.get('absa', [])
    must_copy   = teardown.get('must_copy', [])
    must_avoid  = teardown.get('must_avoid', [])
    identity_tag = teardown.get('identity_tag', '')
    conclusion   = teardown.get('conclusion', '')

    price_display = ('$' + str(price)) if price and not str(price).startswith('$') else (price or '—')
    identity_badge = (f'<span style="background:#e53935;color:#fff;font-size:11px;padding:2px 8px;margin-left:10px;">{identity_tag}</span>'
                      if identity_tag else '')
    bullets_html = (''.join(f'<li style="margin-bottom:7px;line-height:1.6;font-size:13px;">{b}</li>' for b in bullets)
                    or '<li style="color:#aaa">暂无数据</li>')

    try: rc_int = int(''.join(filter(str.isdigit, str(review_count))))
    except: rc_int = 0
    neg_count = reviews_meta.get('total', len(sample_revs))
    top_pain  = (keywords[0].get('word', '—') if keywords and isinstance(keywords[0], dict) else str(keywords[0])) if keywords else '—'

    # 图表数据
    appeals_labels = list(appeals.keys()) if appeals else []
    appeals_values = [int(v) if isinstance(v, (int, float)) else 1 for v in appeals.values()] if appeals else []
    kw_names = [(kw.get('word', str(kw)) if isinstance(kw, dict) else str(kw)) for kw in keywords[:10]]
    kw_vals  = [(kw.get('count', 1) if isinstance(kw, dict) else 1) for kw in keywords[:10]]
    absa_names, absa_pos, absa_neg, absa_mix = [], [], [], []
    for item in (absa or [])[:8]:
        absa_names.append(item.get('name', ''))
        absa_pos.append(item.get('positive', 0))
        absa_neg.append(item.get('negative', 0))
        absa_mix.append(item.get('mixed', 0))
    radar_expect = reviews_analysis.get('radar_expect', [8,8,8,8,8,8])
    radar_actual = reviews_analysis.get('radar_actual', [5,5,5,5,5,5])

    CSS = '''<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f5;color:#2c3e50}
.page{max-width:1400px;margin:0 auto;padding:24px}
.header{background:#2c3e50;color:#fff;padding:28px 32px;margin-bottom:20px}
.header h1{font-size:22px;font-weight:700;margin-bottom:6px}
.header .meta{font-size:13px;opacity:.7}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:20px}
.kpi{background:#fff;border:1px solid #e0e0e0;padding:20px;text-align:center}
.kpi-val{font-size:30px;font-weight:700;color:#2c3e50}
.kpi-label{font-size:12px;color:#666;margin-top:4px}
.card{background:#fff;border:1px solid #e0e0e0;padding:24px;margin-bottom:16px}
.card h2{font-size:15px;font-weight:700;color:#2c3e50;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #2c3e50}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.info-table{width:100%;border-collapse:collapse}
.info-table td{padding:8px 12px;border-bottom:1px solid #f0f0f0;font-size:13px}
.info-table td:first-child{color:#888;width:80px;white-space:nowrap}
.must-box{border:1px solid #e0e0e0;padding:16px}
.must-box h3{font-size:13px;font-weight:700;padding-bottom:8px;margin-bottom:12px;border-bottom:1px solid #f0f0f0}
mark{background:#fff3e0;padding:0 2px}
footer{text-align:center;font-size:12px;color:#aaa;padding:24px}
</style>'''

    p = []
    p.append(f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
             f'<title>Amazon 商品洞察 — {asin}</title>'
             f'<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'
             f'{CSS}</head><body><div class="page">')

    # Header
    p.append(f'<div class="header"><h1>📦 Amazon 商品洞察报告{identity_badge}</h1>'
             f'<div class="meta">ASIN: {asin} &nbsp;|&nbsp; 站点: {domain} &nbsp;|&nbsp; 生成时间: {generated_at}</div></div>')

    # KPI 摘要
    p.append('<div class="kpi-row">')
    p.append(f'<div class="kpi"><div class="kpi-val">{rating}</div><div class="kpi-label">综合评分 ★</div></div>')
    p.append(f'<div class="kpi"><div class="kpi-val">{review_count}</div><div class="kpi-label">评论总数</div></div>')
    p.append(f'<div class="kpi"><div class="kpi-val" style="color:#b71c1c;">{neg_count}</div><div class="kpi-label">差评数 (≤3★)</div></div>')
    p.append(f'<div class="kpi"><div class="kpi-val" style="color:#e65100;font-size:20px;padding-top:4px;">{top_pain}</div><div class="kpi-label">TOP 痛点</div></div>')
    p.append('</div>')

    # 基础信息
    p.append('<div class="card"><h2>基础信息</h2><div class="grid2"><div>')
    p.append(f'<table class="info-table">'
             f'<tr><td>标题</td><td style="font-weight:500;">{title}</td></tr>'
             f'<tr><td>价格</td><td><strong style="color:#b71c1c;font-size:16px;">{price_display}</strong></td></tr>'
             f'<tr><td>评分</td><td><span style="font-size:28px;font-weight:700;color:#e53935;">{rating}</span>'
             f'<span style="color:#f9a825;font-size:18px;margin-left:6px;">{render_stars(rating)}</span>'
             f'<span style="color:#888;font-size:12px;margin-left:6px;">/ {review_count} 条评论</span></td></tr>'
             f'<tr><td>链接</td><td><a href="https://www.{domain}/dp/{asin}" target="_blank" '
             f'style="color:#1565c0;font-size:12px;">查看商品页面 →</a></td></tr>'
             f'</table>')
    p.append(f'<div style="margin-top:16px;"><div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">五点描述</div>'
             f'<ul style="padding-left:18px;">{bullets_html}</ul></div></div>')
    p.append(f'<div><div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">商品主图</div>'
             f'{img_grid(images, 6)}</div></div></div>')

    # 详情图
    aplus_html = img_grid(aplus_images, 5) if aplus_images else '<p style="color:#aaa;font-size:13px;padding:20px;text-align:center;background:#fafafa;border:1px dashed #ddd;">暂无 A+ 图片（Amazon 限制懒加载，可手动补充）</p>'
    img_analysis_html = str(image_analysis or '（待 AI 分析）')
    p.append(f'<div class="card"><h2>详情图 &amp; 视觉分析</h2>'
             f'<div style="margin-bottom:16px;">'
             f'<div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">A+ 详情图（前5张）</div>'
             f'{aplus_html}</div>'
             f'<div><div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">视觉分析 &amp; 文案提取</div>'
             f'<div style="font-size:13px;line-height:1.8;background:#fafafa;padding:16px;border:1px solid #eee;white-space:pre-wrap;">{img_analysis_html}</div>'
             f'</div></div>')

    return p, {
        'appeals_labels': appeals_labels, 'appeals_values': appeals_values,
        'kw_names': kw_names, 'kw_vals': kw_vals,
        'absa_names': absa_names, 'absa_pos': absa_pos, 'absa_neg': absa_neg, 'absa_mix': absa_mix,
        'radar_expect': radar_expect, 'radar_actual': radar_actual,
        'kano': kano, 'opportunity': opportunity, 'sample_revs': sample_revs,
        'keywords': keywords, 'must_copy': must_copy, 'must_avoid': must_avoid, 'conclusion': conclusion,
        'reviews_meta': reviews_meta, 'asin': asin, 'generated_at': generated_at,
    }

def build_analysis_section(p, ctx):
    """差评分析 + 单品拆解 + 评论剧场"""
    kano        = ctx['kano']
    opportunity = ctx['opportunity']
    sample_revs = ctx['sample_revs']
    keywords    = ctx['keywords']
    must_copy   = ctx['must_copy']
    must_avoid  = ctx['must_avoid']
    conclusion  = ctx['conclusion']
    reviews_meta = ctx['reviews_meta']
    absa_names  = ctx['absa_names']

    # 差评分析 card
    p.append('<div class="card"><h2>差评分析（3星及以下）</h2>')
    p.append(review_meta_block(reviews_meta))
    p.append('<div class="grid2">')

    # 左：关键词横向条形图
    p.append('<div><div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">🔑 核心痛点关键词（频次）</div>'
             '<div id="kwChart" style="height:260px;"></div></div>')

    # 右：APPEALS 玫瑰图
    p.append('<div><div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">📊 $APPEALS 维度分布</div>'
             '<div id="appealsChart" style="height:260px;"></div></div>')
    p.append('</div>')

    # ABSA（若有数据）
    if absa_names:
        p.append('<div style="margin-top:20px;">'
                 '<div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">📈 ABSA 方面级情感分析</div>'
                 '<div id="absaChart" style="height:' + str(max(200, len(absa_names)*36)) + 'px;"></div>'
                 '</div>')

    # KANO 彩色卡片
    p.append('<div style="margin-top:20px;">'
             '<div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">🧩 KANO 模型分类</div>'
             + kano_cards(kano) + '</div>')

    # 雷达图
    p.append('<div style="margin-top:20px;">'
             '<div style="font-size:12px;color:#888;margin-bottom:8px;font-weight:600;">📡 满意度鸿沟雷达</div>'
             '<div id="radarChart" style="height:280px;"></div></div>')

    # 机会点
    if opportunity:
        p.append(f'<div style="background:#e8f5e9;border-left:4px solid #1b5e20;padding:14px 16px;'
                 f'margin-top:16px;font-size:13px;line-height:1.8;color:#1b5e20;font-weight:500;">'
                 f'💡 <strong>一句话机会点：</strong>{opportunity}</div>')
    p.append('</div>')  # end card

    # 单品拆解 card
    p.append('<div class="card"><h2>单品拆解</h2><div class="grid2">')
    p.append('<div class="must-box"><h3 style="color:#1b5e20;border-color:#c8e6c9;">✅ Must Copy — 必修课</h3>'
             + must_items(must_copy, '✦') + '</div>')
    p.append('<div class="must-box"><h3 style="color:#b71c1c;border-color:#ffcdd2;">❌ Must Avoid — 避雷针</h3>'
             + must_items(must_avoid, '⚠') + '</div>')
    p.append('</div>')
    if conclusion:
        p.append(f'<div style="background:#f5f5f5;border-left:4px solid #2c3e50;padding:14px 16px;'
                 f'margin-top:16px;font-size:13px;line-height:1.8;color:#444;">💡 {conclusion}</div>')
    p.append('</div>')

    # 差评原声剧场 card
    p.append('<div class="card"><h2>差评原声剧场（真实评论摘录）</h2>'
             + review_cards_tagged(sample_revs, keywords) + '</div>')


def build_scripts(ctx):
    """返回所有 ECharts JS"""
    al = json.dumps(ctx['appeals_labels'])
    av = json.dumps(ctx['appeals_values'])
    kn = json.dumps(ctx['kw_names'][::-1])   # 倒序让高频在顶
    kv = json.dumps(ctx['kw_vals'][::-1])
    an = json.dumps(ctx['absa_names'])
    ap = json.dumps(ctx['absa_pos'])
    ag = json.dumps(ctx['absa_neg'])
    am = json.dumps(ctx['absa_mix'])
    re_exp = json.dumps(ctx['radar_expect'])
    re_act = json.dumps(ctx['radar_actual'])
    has_absa = len(ctx['absa_names']) > 0

    absa_js = ''
    if has_absa:
        absa_js = f'''
var ca=echarts.init(document.getElementById('absaChart'));
ca.setOption({{
  tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},
  legend:{{data:['正面','负面','混合'],bottom:0,textStyle:{{fontSize:11}}}},
  grid:{{left:'18%',right:'5%',top:'5%',bottom:'30px'}},
  xAxis:{{type:'value',axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'category',data:{an},axisLabel:{{fontSize:11}}}},
  color:['#1b5e20','#b71c1c','#e65100'],
  series:[
    {{name:'正面',type:'bar',stack:'total',data:{ap}}},
    {{name:'负面',type:'bar',stack:'total',data:{ag}}},
    {{name:'混合',type:'bar',stack:'total',data:{am}}}
  ]
}});'''

    return f'''<script>
// 关键词横向条形图
var ck=echarts.init(document.getElementById('kwChart'));
ck.setOption({{
  tooltip:{{trigger:'axis'}},
  grid:{{left:'20%',right:'8%',top:'5%',bottom:'5%'}},
  xAxis:{{type:'value',axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'category',data:{kn},axisLabel:{{fontSize:11}}}},
  series:[{{type:'bar',data:{kv},itemStyle:{{color:'#b71c1c'}},barMaxWidth:24}}]
}});

// APPEALS 玫瑰图
var c1=echarts.init(document.getElementById('appealsChart'));
c1.setOption({{
  tooltip:{{trigger:'item',formatter:'{{b}}: {{c}} ({{d}}%)'}},
  color:['#b71c1c','#c62828','#d32f2f','#e53935','#1565c0','#1976d2','#1b5e20'],
  series:[{{type:'pie',radius:['25%','65%'],roseType:'radius',
    data:{al}.map(function(l,i){{return{{name:l,value:{av}[i]||1}}}}),
    itemStyle:{{borderColor:'#fff',borderWidth:2}},label:{{fontSize:11}}
  }}]
}});

// 满意度雷达
var c2=echarts.init(document.getElementById('radarChart'));
c2.setOption({{
  tooltip:{{}},
  legend:{{data:['用户期望','竞品实测'],bottom:0,textStyle:{{fontSize:12}}}},
  color:['#1565c0','#e53935'],
  radar:{{
    indicator:['成分安全','配方稳定','产品效果','适口性','包装质量','售后服务'].map(function(n){{return{{name:n,max:10}}}}),
    radius:'60%'
  }},
  series:[{{type:'radar',data:[
    {{value:{re_exp},name:'用户期望',areaStyle:{{opacity:0.1}}}},
    {{value:{re_act},name:'竞品实测',areaStyle:{{color:'rgba(229,57,53,0.15)'}}}}
  ]}}]
}});
{absa_js}
</script>'''


def main():
    if len(sys.argv) < 3:
        print("用法: python3 generate-report.py <data.json> <output.html>")
        print("  或: python3 generate-report.py <product.json> <output.html> <data.json>")
        sys.exit(1)
    first_path   = sys.argv[1]
    output_path  = sys.argv[2]
    third_path   = sys.argv[3] if len(sys.argv) > 3 else None

    # 智能读取：若只传一个 json，判断是否为 data.json（含 product 子字段）
    first_obj = load(first_path)
    if third_path:
        # 三参数：第1个是 product.json，第3个是 data.json
        product = first_obj
        data    = load(third_path)
        # 兼容：若 product 为空，从 data.product 补
        if not product.get('title') and data.get('product'):
            product = data['product']
    else:
        # 两参数：第1个既可能是 data.json（含 product 子字段）也可能是纯 product.json
        if first_obj.get('product'):
            data    = first_obj
            product = first_obj['product']
        else:
            data    = {}
            product = first_obj

    reviews_analysis = data.get('reviews_analysis', {})
    image_analysis   = data.get('image_analysis', '')
    teardown         = data.get('teardown', {})
    reviews_meta     = data.get('reviews_meta', {})

    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    p, ctx = build_html(product, reviews_analysis, image_analysis, teardown, reviews_meta, generated_at)
    build_analysis_section(p, ctx)
    p.append(f'<footer>由 OpenClaw amazon-insights skill 生成 · {generated_at}</footer>')
    p.append(build_scripts(ctx))
    p.append('</div></body></html>')

    ensure_dirs()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(p))
    print(f"✅ 报告已生成: {output_path}")

if __name__ == '__main__':
    main()
