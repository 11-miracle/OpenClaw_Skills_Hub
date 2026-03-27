#!/usr/bin/env python3
"""
generate-category.py — 品类总览报告（对齐 report-PSPS 样式）
用法: python3 generate-category.py <batch_data.json> <output.html>
"""
import json, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import get_paths, ensure_dirs

def load(path):
    if not path or not os.path.exists(path): return {}
    with open(path, 'r', encoding='utf-8') as f: return json.load(f)

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
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.chart-box{background:#fff;border:1px solid #e0e0e0;padding:16px}
.chart-box h3{font-size:13px;font-weight:700;color:#2c3e50;margin-bottom:12px}
.section{background:#fff;border:1px solid #e0e0e0;padding:24px;margin-bottom:16px}
.section h2{font-size:15px;font-weight:700;color:#2c3e50;margin-bottom:16px;padding-bottom:8px;border-bottom:2px solid #2c3e50}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#2c3e50;color:#fff;padding:8px 10px;text-align:left;font-weight:600}
td{padding:7px 10px;border-bottom:1px solid #f0f0f0}
tr:hover td{background:#fafafa}
.badge{display:inline-block;padding:2px 7px;font-size:11px;font-weight:600}
.b-red{background:#ffebee;color:#b71c1c}
.b-orange{background:#fff3e0;color:#e65100}
.b-green{background:#e8f5e9;color:#1b5e20}
.b-blue{background:#e3f2fd;color:#1565c0}
.b-gray{background:#f5f5f5;color:#666}
.ai-card{background:#fff;border:1px solid #e0e0e0;padding:20px}
.ai-card .ai-title{font-size:14px;font-weight:700;color:#2c3e50;margin-bottom:10px}
.pain-col{background:#ffebee;border:1px solid #e57373;padding:14px}
.joy-col{background:#e8f5e9;border:1px solid #66bb6a;padding:14px}
.itch-col{background:#fff8e1;border:1px solid #ffa726;padding:14px}
.col-title{font-weight:700;font-size:13px;margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(0,0,0,0.1)}
details summary{cursor:pointer;padding:12px 16px;background:#f5f5f5;border:1px solid #e0e0e0;
  font-weight:600;font-size:13px;list-style:none;display:flex;align-items:center;gap:8px}
details summary::-webkit-details-marker{display:none}
details[open] summary{background:#2c3e50;color:#fff}
details .detail-body{padding:16px;border:1px solid #e0e0e0;border-top:none;background:#fff}
footer{text-align:center;font-size:12px;color:#aaa;padding:24px}
</style>'''

def section_header(num, title):
    return f'<div class="section"><h2>第{num}部分：{title}</h2>'

def pain_joy_itch_cols(pji):
    pain = pji.get('pain', []); joy = pji.get('joy', []); itch = pji.get('itch', [])
    def items(lst, color):
        return ''.join(f'<div style="padding:5px 0;border-bottom:1px solid rgba(0,0,0,0.06);font-size:12px;color:#444;">• {i}</div>' for i in lst) or '<div style="color:#aaa;font-size:12px;">暂无</div>'
    return (f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">'
            f'<div class="pain-col"><div class="col-title" style="color:#b71c1c;">😤 痛点（Pains）</div>{items(pain,"#b71c1c")}</div>'
            f'<div class="joy-col"><div class="col-title" style="color:#1b5e20;">😊 爽点（Joys）</div>{items(joy,"#1b5e20")}</div>'
            f'<div class="itch-col"><div class="col-title" style="color:#e65100;">🤔 痒点（Itches）</div>{items(itch,"#e65100")}</div>'
            f'</div>')

def kano_table(kano):
    cat_map = [
        ('must_be',     'Must-be',     'b-red',    '基础需求'),
        ('performance', 'Performance', 'b-orange', '期望需求'),
        ('attractive',  'Attractive',  'b-green',  '魅力需求'),
        ('indifferent', 'Indifferent', 'b-gray',   '无差异需求'),
        ('reverse',     'Reverse',     'b-blue',   '反向需求'),
    ]
    rows = ''
    for key, label, badge_cls, desc in cat_map:
        items = kano.get(key, [])
        content = '、'.join(items) if items else '—'
        rows += (f'<tr><td><span class="badge {badge_cls}">{label}</span></td>'
                 f'<td style="color:#888;font-size:12px;">{desc}</td>'
                 f'<td>{content}</td></tr>')
    return f'<table><thead><tr><th>类别</th><th>含义</th><th>具体需求</th></tr></thead><tbody>{rows}</tbody></table>'

def journey_cards(journey):
    if not journey: return '<p style="color:#aaa;font-size:13px;">暂无旅程数据</p>'
    cards = ''.join(
        f'<div style="background:#fff;border:1px solid #e0e0e0;padding:12px;text-align:center;">'
        f'<div style="font-size:12px;color:#888;margin-bottom:6px;">{j.get("stage","")}</div>'
        f'<div style="font-size:20px;font-weight:700;color:#2c3e50;">{j.get("score",0)}</div>'
        f'<div style="font-size:11px;color:#e65100;margin-top:6px;">{j.get("friction","")}</div></div>'
        for j in journey)
    n = len(journey)
    return f'<div style="display:grid;grid-template-columns:repeat({min(n,6)},1fr);gap:10px;margin-bottom:16px;">{cards}</div>'

def build_category_html(data, generated_at):
    meta     = data.get('meta', {})
    products = data.get('products', [])
    ca       = data.get('category_analysis', {})
    psps     = ca.get('psps', {})
    absa     = ca.get('absa', [])
    appeals  = ca.get('appeals', {})
    kano     = ca.get('kano', {})
    pji      = ca.get('pain_joy_itch', {})
    journey  = ca.get('journey', [])
    ai_sum   = ca.get('ai_summary', {})

    total_products = meta.get('total_products', len(products))
    avg_rating     = meta.get('avg_rating', '—')
    total_reviews  = meta.get('total_reviews', '—')
    neg_rate       = meta.get('neg_rate', '—')

    # 价格分布数据（从 products 动态计算）
    price_buckets = {'$0-20':0,'$20-40':0,'$40-60':0,'$60-100':0,'$100+':0}
    for prod in products:
        try:
            pv = float(''.join(c for c in str(prod.get('price','0')) if c.isdigit() or c=='.'))
            if pv < 20: price_buckets['$0-20'] += 1
            elif pv < 40: price_buckets['$20-40'] += 1
            elif pv < 60: price_buckets['$40-60'] += 1
            elif pv < 100: price_buckets['$60-100'] += 1
            else: price_buckets['$100+'] += 1
        except: pass

    # 评分分布
    rating_buckets = {'1★':0,'2★':0,'3★':0,'4★':0,'5★':0}
    for prod in products:
        try:
            rv = float(str(prod.get('rating','0')).split()[0])
            key = f'{int(rv)}★'
            if key in rating_buckets: rating_buckets[key] += 1
        except: pass

    # ABSA 数据
    absa_names = [a.get('name','') for a in absa[:10]]
    absa_pos   = [a.get('positive',0) for a in absa[:10]]
    absa_neg   = [a.get('negative',0) for a in absa[:10]]
    absa_mix   = [a.get('mixed',0) for a in absa[:10]]

    # APPEALS
    ap_labels = list(appeals.keys()) if appeals else []
    ap_values = [int(v) if isinstance(v,(int,float)) else 1 for v in appeals.values()] if appeals else []

    # PSPS 条形图数据 — 支持 [{label,count}] 或 [str] 两种格式
    def _psps_parse(items, limit=8):
        labels, counts = [], []
        for item in (items or [])[:limit]:
            if isinstance(item, dict):
                labels.append(str(item.get('label', item.get('name', ''))))
                counts.append(int(item.get('count', item.get('value', 1))))
            else:
                labels.append(str(item))
                counts.append(1)
        return labels, counts
    persona_list,  persona_counts  = _psps_parse(psps.get('persona', []))
    scenario_list, scenario_counts = _psps_parse(psps.get('scenario', []))
    pain_list,     pain_counts     = _psps_parse(psps.get('pain', []))

    # 旅程折线数据
    journey_stages = [j.get('stage','') for j in journey]
    journey_scores = [j.get('score', 5) for j in journey]

    p = []
    p.append(f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
             f'<title>Amazon 品类总览报告</title>'
             f'<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>'
             f'{CSS}</head><body><div class="page">')

    # Header
    p.append(f'<div class="header"><h1>📊 Amazon 品类洞察总览报告</h1>'
             f'<div class="meta">商品数：{total_products} &nbsp;|&nbsp; 生成时间：{generated_at}</div></div>')

    # 第0部分 Dashboard
    p.append('<div class="section"><h2>第0部分：品类总览 Dashboard</h2>')
    p.append('<div class="kpi-row">')
    p.append(f'<div class="kpi"><div class="kpi-val">{total_products}</div><div class="kpi-label">商品总数</div></div>')
    p.append(f'<div class="kpi"><div class="kpi-val">{avg_rating}</div><div class="kpi-label">平均评分 ★</div></div>')
    p.append(f'<div class="kpi"><div class="kpi-val">{str(total_reviews)}</div><div class="kpi-label">评论总数</div></div>')
    neg_color = '#1b5e20' if isinstance(neg_rate,(int,float)) and neg_rate < 15 else '#b71c1c'
    p.append(f'<div class="kpi"><div class="kpi-val" style="color:{neg_color};">{neg_rate}%</div><div class="kpi-label">负评率 (≤3星)</div></div>')
    p.append('</div>')
    p.append('<div class="chart-row">')
    p.append('<div class="chart-box"><h3>价格分布</h3><div id="chart-price" style="height:240px;"></div></div>')
    p.append('<div class="chart-box"><h3>评分分布（商品数）</h3><div id="chart-rating" style="height:240px;"></div></div>')
    p.append('</div>')

    # 商品总览表
    if products:
        p.append('<h3 style="font-size:13px;font-weight:700;color:#2c3e50;margin:16px 0 10px;">商品总览</h3>')
        p.append('<table><thead><tr><th>ASIN</th><th>商品名称</th><th>价格</th><th>评分</th><th>评论数</th><th>一句话点评</th></tr></thead><tbody>')
        for prod in products:
            asin_p = prod.get('asin','—')
            ttl = str(prod.get('title','—'))[:60] + ('…' if len(str(prod.get('title',''))) > 60 else '')
            pr  = prod.get('price','—')
            ra  = prod.get('rating','—')
            rc  = prod.get('review_count','—')
            ol  = str(prod.get('one_liner',''))
            p.append(f'<tr><td style="font-family:monospace;">{asin_p}</td><td>{ttl}</td>'
                     f'<td style="white-space:nowrap;">{pr}</td>'
                     f'<td style="color:#f9a825;font-weight:700;">{ra}</td>'
                     f'<td>{rc}</td><td style="font-size:12px;color:#666;">{ol}</td></tr>')
        p.append('</tbody></table>')
    p.append('</div>')  # end section 0

    # AI 总结
    if any(ai_sum.values()):
        p.append('<div class="section"><h2>品类总体分析总结</h2>')
        p.append(f'<div style="margin-bottom:8px;font-size:13px;color:#666;">基于 {total_products} 款商品数据，AI 综合推断生成，供决策参考。</div>')
        p.append('<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;">')
        ai_items = [
            ('📊 竞争格局', ai_sum.get('competition','')),
            ('👤 用户画像', ai_sum.get('persona','')),
            ('💡 机会点',   ai_sum.get('opportunity','')),
            ('⚠️ 风险点',   ai_sum.get('risk','')),
        ]
        for title_ai, content_ai in ai_items:
            if content_ai:
                p.append(f'<div class="ai-card"><div class="ai-title">{title_ai}</div>'
                         f'<div style="font-size:13px;line-height:1.7;color:#444;">{content_ai}</div></div>')
        p.append('</div>')
        advice = ai_sum.get('advice','')
        if advice:
            p.append(f'<div style="background:#e8f5e9;border-left:4px solid #1b5e20;padding:14px 16px;'
                     f'font-size:13px;line-height:1.8;color:#1b5e20;">'
                     f'🎯 <strong>入场建议：</strong>{advice}</div>')
        p.append('</div>')

    # 第1部分 PSPS
    p.append(section_header('一', 'PSPS 用户画像（品类级）'))
    p.append('<div class="chart-row">')
    p.append('<div class="chart-box"><h3>用户画像 Persona</h3><div id="chart-persona" style="height:220px;"></div></div>')
    p.append('<div class="chart-box"><h3>使用场景 Scenario</h3><div id="chart-scenario" style="height:220px;"></div></div>')
    p.append('</div>')
    p.append('<div class="chart-box" style="margin-bottom:0;"><h3>用户痛点 Pain（品类级）</h3><div id="chart-pain" style="height:220px;"></div></div>')
    p.append('</div>')

    # 第2部分 ABSA
    p.append(section_header('二', 'ABSA 方面级情感分析（汇总）'))
    p.append('<div id="chart-absa" style="height:' + str(max(240, len(absa_names)*36)) + 'px;"></div>')
    p.append('</div>')

    # 第3部分 APPEALS
    p.append(section_header('三', '$APPEALS 8维竞争力分析'))
    p.append('<div class="chart-row">')
    p.append('<div class="chart-box"><h3>南丁格尔玫瑰图</h3><div id="chart-appeals" style="height:320px;"></div></div>')
    p.append('<div class="chart-box"><h3>维度说明</h3>'
             '<table style="font-size:12px;"><thead><tr><th>维度</th><th>含义</th><th>权重</th></tr></thead><tbody>')
    dims = [('Price','价格竞争力'),('Performance','性能/效果'),('Packaging','包装/外观'),
            ('Ease','使用便捷性'),('Assurances','品牌/认证'),('LifeCycle','耐久性/售后'),('Social','社交/口碑')]
    for dim, meaning in dims:
        val = appeals.get(dim, 0)
        p.append(f'<tr><td style="font-weight:600;">{dim}</td><td style="color:#666;">{meaning}</td>'
                 f'<td style="text-align:right;font-weight:700;color:#2c3e50;">{val}</td></tr>')
    p.append('</tbody></table></div></div>')
    p.append('</div>')

    # 第4部分 KANO
    p.append(section_header('四', 'KANO 需求分类（品类级）'))
    p.append(kano_table(kano))
    p.append('</div>')

    # 第5部分 痛爽痒
    p.append(section_header('五', '痛爽痒三维图谱'))
    p.append(pain_joy_itch_cols(pji))
    p.append('</div>')

    # 第6部分 用户旅程
    p.append(section_header('六', '用户旅程摩擦分析'))
    p.append(journey_cards(journey))
    if journey_stages:
        p.append('<div id="chart-journey" style="height:220px;"></div>')
    p.append('</div>')

    # 第7部分 ASIN拆解
    p.append(section_header('七', '逐品 ASIN 拆解（点击展开）'))
    for prod in products:
        asin_p = prod.get('asin','—')
        ttl    = prod.get('title','—')
        pr     = prod.get('price','—')
        ra     = prod.get('rating','—')
        rc     = prod.get('review_count','—')
        ol     = prod.get('one_liner','')
        absa_p = prod.get('absa', [])
        absa_chart_html = ''
        if absa_p:
            absa_chart_html = f'<div id="chart-{asin_p}" style="height:160px;margin-top:12px;"></div>'
        p.append(f'<details style="margin-bottom:8px;">'
                 f'<summary>📦 {asin_p} &nbsp; {str(ttl)[:60]} &nbsp; '
                 f'<span style="color:#f9a825;">★{ra}</span> &nbsp; '
                 f'<span style="color:#888;font-size:12px;">{rc}条评论 · {pr}</span></summary>'
                 f'<div class="detail-body">'
                 f'<div style="font-size:13px;color:#444;line-height:1.7;">{ol or "暂无点评"}</div>'
                 f'{absa_chart_html}</div></details>')
    p.append('</div>')

    p.append(f'<footer>由 OpenClaw amazon-insights skill 生成 · {generated_at}</footer>')

    return p, {
        'price_buckets': price_buckets, 'rating_buckets': rating_buckets,
        'absa_names': absa_names, 'absa_pos': absa_pos, 'absa_neg': absa_neg, 'absa_mix': absa_mix,
        'ap_labels': ap_labels, 'ap_values': ap_values,
        'persona_list': persona_list, 'persona_counts': persona_counts,
        'scenario_list': scenario_list, 'scenario_counts': scenario_counts,
        'pain_list': pain_list, 'pain_counts': pain_counts,
        'journey_stages': journey_stages, 'journey_scores': journey_scores,
        'products': products,
    }

def build_category_scripts(ctx):
    pb = json.dumps(list(ctx['price_buckets'].keys()))
    pv = json.dumps(list(ctx['price_buckets'].values()))
    rb = json.dumps(list(ctx['rating_buckets'].keys()))
    rv = json.dumps(list(ctx['rating_buckets'].values()))
    an = json.dumps(ctx['absa_names'][::-1])
    ap = json.dumps(ctx['absa_pos'][::-1])
    ag = json.dumps(ctx['absa_neg'][::-1])
    am = json.dumps(ctx['absa_mix'][::-1])
    al = json.dumps(ctx['ap_labels'])
    av = json.dumps(ctx['ap_values'])
    pn = json.dumps(ctx['persona_list'][::-1])
    sn = json.dumps(ctx['scenario_list'][::-1])
    dn = json.dumps(ctx['pain_list'][::-1])
    pv_ones = json.dumps(ctx['persona_counts'][::-1])
    sv_ones = json.dumps(ctx['scenario_counts'][::-1])
    dv_ones = json.dumps(ctx['pain_counts'][::-1])
    js = json.dumps(ctx['journey_stages'])
    jsc = json.dumps(ctx['journey_scores'])
    has_journey = len(ctx['journey_stages']) > 0

    bar_opt = lambda names, vals, color: (
        f'{{tooltip:{{trigger:"axis"}},grid:{{left:"30%",right:"8%",top:"5%",bottom:"5%"}},'
        f'xAxis:{{type:"value",axisLabel:{{fontSize:10}}}},'
        f'yAxis:{{type:"category",data:{names},axisLabel:{{fontSize:11}}}},'
        f'series:[{{type:"bar",data:{vals},itemStyle:{{color:"{color}"}},barMaxWidth:20}}]}}'
    )

    journey_js = ''
    if has_journey:
        journey_js = f'''
var cj=echarts.init(document.getElementById('chart-journey'));
cj.setOption({{
  tooltip:{{trigger:'axis'}},
  grid:{{left:'5%',right:'5%',top:'10%',bottom:'10%'}},
  xAxis:{{type:'category',data:{js},axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'value',min:0,max:10,axisLabel:{{fontSize:11}}}},
  series:[{{type:'line',data:{jsc},smooth:true,symbol:'circle',symbolSize:8,
    lineStyle:{{color:'#2c3e50',width:2}},
    itemStyle:{{color:'#f9a825'}},
    areaStyle:{{color:'rgba(44,62,80,0.06)'}}}}]
}});'''

    # ASIN 拆解内的小 ABSA 图
    asin_charts_js = ''
    for prod in ctx['products']:
        asin_p = prod.get('asin','')
        absa_p = prod.get('absa',[])
        if absa_p and asin_p:
            pn2 = json.dumps([a.get('name','') for a in absa_p[:6]][::-1])
            pp2 = json.dumps([a.get('positive',0) for a in absa_p[:6]][::-1])
            pg2 = json.dumps([a.get('negative',0) for a in absa_p[:6]][::-1])
            pm2 = json.dumps([a.get('mixed',0) for a in absa_p[:6]][::-1])
            eid = f'chart-{asin_p}'
            asin_charts_js += f'''
if(document.getElementById('{eid}')){{
  var c_{asin_p.replace('-','_')}=echarts.init(document.getElementById('{eid}'));
  c_{asin_p.replace('-','_')}.setOption({{
    tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},
    legend:{{data:['正面','负面','混合'],bottom:0,textStyle:{{fontSize:10}}}},
    grid:{{left:'25%',right:'5%',top:'5%',bottom:'25px'}},
    xAxis:{{type:'value',axisLabel:{{fontSize:10}}}},
    yAxis:{{type:'category',data:{pn2},axisLabel:{{fontSize:10}}}},
    color:['#1b5e20','#b71c1c','#e65100'],
    series:[
      {{name:'正面',type:'bar',stack:'t',data:{pp2}}},
      {{name:'负面',type:'bar',stack:'t',data:{pg2}}},
      {{name:'混合',type:'bar',stack:'t',data:{pm2}}}
    ]
  }});
}}'''

    return f'''<script>
// 价格分布
var cp=echarts.init(document.getElementById('chart-price'));
cp.setOption({{
  tooltip:{{trigger:'axis'}},
  grid:{{left:'15%',right:'8%',top:'10%',bottom:'10%'}},
  xAxis:{{type:'category',data:{pb},axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'value',axisLabel:{{fontSize:11}}}},
  series:[{{type:'bar',data:{pv},itemStyle:{{color:'#2c3e50'}},barMaxWidth:40}}]
}});
// 评分分布
var cr=echarts.init(document.getElementById('chart-rating'));
cr.setOption({{
  tooltip:{{trigger:'axis'}},
  grid:{{left:'10%',right:'8%',top:'10%',bottom:'10%'}},
  xAxis:{{type:'category',data:{rb},axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'value',axisLabel:{{fontSize:11}}}},
  series:[{{type:'bar',data:{rv},itemStyle:{{color:'#f9a825'}},barMaxWidth:40}}]
}});
// PSPS
var cps=echarts.init(document.getElementById('chart-persona'));
cps.setOption({bar_opt(pn, pv_ones, '#1565c0')});
var css2=echarts.init(document.getElementById('chart-scenario'));
css2.setOption({bar_opt(sn, sv_ones, '#1b5e20')});
var cpain=echarts.init(document.getElementById('chart-pain'));
cpain.setOption({bar_opt(dn, dv_ones, '#b71c1c')});
// ABSA
var ca=echarts.init(document.getElementById('chart-absa'));
ca.setOption({{
  tooltip:{{trigger:'axis',axisPointer:{{type:'shadow'}}}},
  legend:{{data:['正面','负面','混合'],bottom:0,textStyle:{{fontSize:11}}}},
  grid:{{left:'20%',right:'5%',top:'5%',bottom:'30px'}},
  xAxis:{{type:'value',axisLabel:{{fontSize:11}}}},
  yAxis:{{type:'category',data:{an},axisLabel:{{fontSize:11}}}},
  color:['#1b5e20','#b71c1c','#e65100'],
  series:[
    {{name:'正面',type:'bar',stack:'total',data:{ap}}},
    {{name:'负面',type:'bar',stack:'total',data:{ag}}},
    {{name:'混合',type:'bar',stack:'total',data:{am}}}
  ]
}});
// APPEALS 玫瑰图
var cal=echarts.init(document.getElementById('chart-appeals'));
cal.setOption({{
  tooltip:{{trigger:'item',formatter:'{{b}}: {{c}} ({{d}}%)'}},
  color:['#b71c1c','#c62828','#d32f2f','#e53935','#1565c0','#1976d2','#1b5e20'],
  series:[{{type:'pie',radius:['25%','65%'],roseType:'radius',
    data:{al}.map(function(l,i){{return{{name:l,value:{av}[i]||1}}}}),
    itemStyle:{{borderColor:'#fff',borderWidth:2}},label:{{fontSize:11}}
  }}]
}});
{journey_js}
{asin_charts_js}
</script>'''


def main():
    if len(sys.argv) < 3:
        print("用法: python3 generate-category.py <batch_data.json> <output.html>")
        sys.exit(1)
    data_path   = sys.argv[1]
    output_path = sys.argv[2]
    data = load(data_path)
    generated_at = datetime.now().strftime('%Y-%m-%d %H:%M')
    p, ctx = build_category_html(data, generated_at)
    p.append(build_category_scripts(ctx))
    p.append('</div></body></html>')
    ensure_dirs()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(''.join(p))
    print(f"✅ 品类报告已生成: {output_path}")

if __name__ == '__main__':
    main()
