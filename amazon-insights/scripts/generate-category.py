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

def build_rs_section(products):
    """第8部分：品类好差评横向对比（从所有 ASIN review_summary 聚合）"""
    # ── 聚合 ──
    from collections import Counter, defaultdict
    pos_dims = defaultdict(list)   # dim -> [{asin, insight, score, quotes}]
    neg_dims = defaultdict(list)
    verdicts = []

    for prod in products:
        asin = prod.get('asin','')
        rs   = prod.get('review_summary', {})
        if not rs:
            continue
        for item in rs.get('positive', []):
            pos_dims[item.get('dimension','')].append({
                'asin': asin, 'insight': item.get('insight',''),
                'score': item.get('sentiment_score',0),
                'quotes': item.get('quotes',[])
            })
        for item in rs.get('negative', []):
            neg_dims[item.get('dimension','')].append({
                'asin': asin, 'insight': item.get('insight',''),
                'score': item.get('sentiment_score',0),
                'quotes': item.get('quotes',[])
            })
        v = rs.get('overall_verdict','')
        if v:
            verdicts.append({'asin': asin, 'verdict': v,
                             'rating': prod.get('rating','')})

    if not pos_dims and not neg_dims:
        return ''

    def dim_block(dims_dict, side):
        sc     = '#1b5e20' if side == 'pos' else '#b71c1c'
        bg     = '#e8f5e9' if side == 'pos' else '#ffebee'
        icon   = '👍' if side == 'pos' else '👎'
        label  = '好评核心维度' if side == 'pos' else '差评核心维度'
        # 按出现次数（ASIN数）降序
        sorted_dims = sorted(dims_dict.items(), key=lambda x: -len(x[1]))
        rows = ''
        for dim, entries in sorted_dims:
            freq = len(entries)
            freq_bar = '█' * freq + '░' * (len(products) - freq)
            asin_tags = ' '.join(
                f'<span style="display:inline-block;background:{bg};color:{sc};'
                f'font-size:10px;padding:1px 5px;margin:1px;font-weight:600;">{e["asin"]}</span>'
                for e in entries
            )
            # 取最有代表性的一条 insight（score 最高）
            best = max(entries, key=lambda x: x.get('score', 0))
            insight_html = (
                f'<div style="font-size:11px;color:#444;line-height:1.5;padding:6px 8px;'
                f'background:#fafafa;border-left:3px solid {sc};margin:4px 0;">'
                f'{best["insight"]}</div>'
            )
            q_html = ''
            for q in best.get('quotes', [])[:1]:
                q_html += (
                    f'<div style="font-size:10px;color:#888;padding:2px 0 2px 8px;'
                    f'border-left:2px solid #ddd;font-style:italic;">▸ {q}</div>'
                )
            rows += (
                f'<div style="margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid #f0f0f0;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
                f'<span style="font-weight:700;font-size:13px;color:#2c3e50;">{dim}</span>'
                f'<span style="font-size:11px;color:#888;">{freq}/{len(products)} 个ASIN提及 &nbsp;'
                f'<span style="color:{sc};font-family:monospace;">{freq_bar}</span></span>'
                f'</div>'
                f'{asin_tags}'
                f'{insight_html}'
                f'{q_html}'
                f'</div>'
            )
        return (
            f'<div>'
            f'<div style="font-size:13px;font-weight:700;padding:8px 12px;background:{bg};'
            f'color:{sc};margin-bottom:14px;">{icon} {label}（按品类覆盖频次排序）</div>'
            f'{rows}</div>'
        )

    # ── verdict 卡片墙 ──
    verdict_cards = ''
    for v in verdicts:
        ra_str = v.get('rating','')
        verdict_cards += (
            f'<div style="background:#fff;border:1px solid #e0e0e0;padding:14px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span style="font-family:monospace;font-weight:700;font-size:12px;color:#2c3e50;">{v["asin"]}</span>'
            f'<span style="color:#f9a825;font-weight:700;">★{ra_str}</span>'
            f'</div>'
            f'<div style="font-size:12px;line-height:1.6;color:#444;">{v["verdict"]}</div>'
            f'</div>'
        )
    n_v = len(verdicts)
    cols_v = min(n_v, 3)
    verdict_section = ''
    if verdict_cards:
        verdict_section = (
            f'<div style="margin-top:20px;border-top:1px solid #eee;padding-top:16px;">'
            f'<div style="font-size:13px;font-weight:700;color:#2c3e50;margin-bottom:12px;">'
            f'📊 各产品整体定位评价</div>'
            f'<div style="display:grid;grid-template-columns:repeat({cols_v},1fr);gap:12px;">'
            f'{verdict_cards}</div></div>'
        )

    html = (
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:4px;">'
        f'{dim_block(pos_dims, "pos")}'
        f'{dim_block(neg_dims, "neg")}'
        f'</div>'
        f'{verdict_section}'
    )
    return html


def build_innovation_section(products, ai_sum):
    """第9部分：品类创新机会汇总（从所有 ASIN innovation 聚合 + ai_summary）"""
    from collections import defaultdict

    TYPE_ICON = {'功能创新': '🔧', '体验创新': '✨', '包装形式创新': '📦'}
    FC_MAP    = {'高': '#1b5e20', '中': '#e65100', '低': '#9e9e9e'}
    FB_MAP    = {'高': '#e8f5e9', '中': '#fff3e0', '低': '#f5f5f5'}

    by_type = defaultdict(list)  # type -> [opp_dict + asin]
    top_opps = []  # priority=1 & feasibility=高

    for prod in products:
        asin = prod.get('asin','')
        inn  = prod.get('innovation', {})
        if not inn:
            continue
        for opp in inn.get('opportunities', []):
            entry = dict(opp)
            entry['_asin'] = asin
            t = opp.get('type','其他')
            by_type[t].append(entry)
            if opp.get('priority') == 1 and opp.get('feasibility') == '高':
                top_opps.append(entry)

    if not by_type:
        return ''

    def opp_card(opp):
        otype = opp.get('type','')
        title = opp.get('title','')
        pain  = opp.get('user_pain','')
        how   = opp.get('how_to_improve','')
        out   = opp.get('expected_outcome','')
        feas  = opp.get('feasibility','中')
        asin  = opp.get('_asin','')
        icon  = TYPE_ICON.get(otype, '💡')
        fc    = FC_MAP.get(feas,'#9e9e9e')
        fb    = FB_MAP.get(feas,'#f5f5f5')
        return (
            f'<div style="border:1px solid #e0e0e0;padding:14px;background:#fff;">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">'
            f'<span style="font-weight:700;font-size:13px;color:#2c3e50;">{icon} {title}</span>'
            f'<span style="font-size:10px;padding:2px 6px;background:{fb};color:{fc};font-weight:600;white-space:nowrap;">'
            f'● {feas}可行性</span>'
            f'</div>'
            f'<div style="font-size:10px;color:#888;margin-bottom:8px;">来源：{asin}</div>'
            f'<div style="display:grid;grid-template-columns:60px 1fr;gap:3px 8px;font-size:11px;line-height:1.6;">'
            f'<span style="color:#888;">👤 用户说</span><span style="color:#444;">{pain}</span>'
            f'<span style="color:#888;">🔧 怎么改</span><span style="color:#444;">{how}</span>'
            f'<span style="color:#888;">📈 预期效果</span><span style="color:#1b5e20;font-weight:500;">{out}</span>'
            f'</div></div>'
        )

    # ── 按 type 分3列 ──
    type_order = ['功能创新','体验创新','包装形式创新']
    cols_html = ''
    for t in type_order:
        items = by_type.get(t,[])
        if not items:
            continue
        icon = TYPE_ICON.get(t,'💡')
        cards = ''.join(opp_card(o) for o in items)
        cols_html += (
            f'<div>'
            f'<div style="font-size:13px;font-weight:700;color:#2c3e50;padding:8px 12px;'
            f'background:#f5f5f5;border-left:3px solid #2c3e50;margin-bottom:12px;">'
            f'{icon} {t}</div>'
            f'{cards}</div>'
        )

    # ── 立刻能做的高优先级 ──
    quick_wins = ''
    if top_opps:
        qw_items = ''.join(
            f'<div style="padding:10px 14px;border-left:4px solid #1b5e20;background:#e8f5e9;margin-bottom:8px;">'
            f'<div style="font-weight:700;font-size:13px;color:#1b5e20;margin-bottom:4px;">'
            f'{TYPE_ICON.get(o.get("type",""),"💡")} {o.get("title","")}'
            f'<span style="font-size:11px;color:#888;font-weight:400;margin-left:6px;">(来源：{o["_asin"]})</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#2e7d32;line-height:1.6;">'
            f'→ {o.get("expected_outcome","")}</div>'
            f'</div>'
            for o in top_opps[:5]
        )
        quick_wins = (
            f'<div style="margin-top:20px;border-top:1px solid #eee;padding-top:16px;">'
            f'<div style="font-size:13px;font-weight:700;color:#1b5e20;margin-bottom:12px;">'
            f'⚡ 立刻能做的机会（优先级1 × 高可行性）</div>'
            f'{qw_items}</div>'
        )

    # ── 入局建议（来自 ai_summary）──
    advice_block = ''
    advice = ai_sum.get('advice','')
    opp_txt = ai_sum.get('opportunity','')
    if advice or opp_txt:
        advice_block = (
            f'<div style="margin-top:20px;border-top:1px solid #eee;padding-top:16px;">'
            f'<div style="font-size:13px;font-weight:700;color:#1565c0;margin-bottom:12px;">'
            f'🎯 入局策略建议</div>'
        )
        if opp_txt:
            advice_block += (
                f'<div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:12px 16px;'
                f'font-size:13px;line-height:1.8;color:#0d47a1;margin-bottom:10px;">'
                f'<strong>品类机会点：</strong>{opp_txt}</div>'
            )
        if advice:
            advice_block += (
                f'<div style="background:#e8f5e9;border-left:4px solid #1b5e20;padding:12px 16px;'
                f'font-size:13px;line-height:1.8;color:#1b5e20;">'
                f'<strong>入场路径：</strong>{advice}</div>'
            )
        advice_block += '</div>'

    n_types = len([t for t in type_order if by_type.get(t)])
    cols_css = f'grid-template-columns:repeat({max(1,n_types)},1fr)'
    html = (
        f'<div style="display:grid;{cols_css};gap:16px;margin-bottom:4px;">'
        f'{cols_html}</div>'
        f'{quick_wins}'
        f'{advice_block}'
    )
    return html


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
        rs     = prod.get('review_summary', {})
        inn    = prod.get('innovation', {})

        absa_chart_html = ''
        if absa_p:
            absa_chart_html = f'<div id="chart-{asin_p}" style="height:160px;margin-top:12px;"></div>'

        # ── 好差评汇总模块 ──
        rs_html = ''
        if rs:
            verdict = rs.get('overall_verdict','')
            positives = rs.get('positive', [])
            negatives = rs.get('negative', [])

            def dim_rows_cat(items, side):
                if not items:
                    return '<div style="color:#aaa;font-size:12px;padding:8px;">暂无数据</div>'
                html = ''
                for item in items:
                    dim   = item.get('dimension','')
                    score = item.get('sentiment_score','')
                    ins   = item.get('insight','')
                    quotes = item.get('quotes',[])
                    sc    = '#1b5e20' if side=='pos' else '#b71c1c'
                    icon  = '★' if side=='pos' else '●'
                    q_html = ''.join(
                        '<div style="font-size:11px;color:#555;padding:3px 0 3px 8px;border-left:2px solid #e0e0e0;margin-top:3px;">▸ ' + q + '</div>'
                        for q in quotes[:2])
                    html += (
                        '<div style="margin-bottom:14px;">'
                        '<div style="display:flex;align-items:baseline;gap:6px;margin-bottom:4px;">'
                        '<span style="font-weight:700;font-size:12px;color:#2c3e50;">[' + dim + ']</span>'
                        '<span style="font-size:11px;font-weight:600;color:' + sc + ';">' + icon + str(score) + '</span>'
                        '</div>'
                        '<div style="font-size:11px;line-height:1.6;color:#444;background:#fafafa;padding:6px 8px;border-left:3px solid ' + sc + ';">' + ins + '</div>'
                        + q_html +
                        '</div>'
                    )
                return html

            verdict_html = ''
            if verdict:
                verdict_html = (
                    '<div style="background:#f5f5f5;border-left:4px solid #607d8b;padding:10px 14px;'
                    'margin-bottom:14px;font-size:12px;line-height:1.7;color:#37474f;">'
                    '📊 <strong>整体结论：</strong>' + verdict + '</div>'
                )

            rs_html = (
                '<div style="margin-top:16px;border-top:1px solid #eee;padding-top:14px;">'
                '<div style="font-size:13px;font-weight:700;color:#2c3e50;margin-bottom:10px;">📣 好差评深度汇总</div>'
                + verdict_html +
                '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">'
                '<div>'
                '<div style="font-size:12px;font-weight:700;color:#1b5e20;padding:6px 10px;background:#e8f5e9;margin-bottom:10px;">👍 好评核心</div>'
                + dim_rows_cat(positives, 'pos') +
                '</div>'
                '<div>'
                '<div style="font-size:12px;font-weight:700;color:#b71c1c;padding:6px 10px;background:#ffebee;margin-bottom:10px;">👎 差评核心</div>'
                + dim_rows_cat(negatives, 'neg') +
                '</div>'
                '</div></div>'
            )

        # ── 产品创新点模块 ──
        inn_html = ''
        if inn:
            summary = inn.get('summary','')
            opps    = sorted(inn.get('opportunities',[]), key=lambda x: x.get('priority',99))
            fc_map  = {'高':'#1b5e20','中':'#e65100','低':'#9e9e9e'}
            fb_map  = {'高':'#e8f5e9','中':'#fff3e0','低':'#f5f5f5'}
            ti_map  = {'功能创新':'🔧','体验创新':'✨','包装形式创新':'📦'}

            sum_html = ''
            if summary:
                sum_html = (
                    '<div style="background:#e3f2fd;border-left:4px solid #1565c0;padding:10px 14px;'
                    'margin-bottom:12px;font-size:12px;line-height:1.7;color:#0d47a1;">'
                    '🔭 <strong>创新方向：</strong>' + summary + '</div>'
                )

            opps_html = ''
            for opp in opps:
                oid   = opp.get('id','')
                otype = opp.get('type','')
                title = opp.get('title','')
                pain  = opp.get('user_pain','')
                evid  = opp.get('evidence','')
                how   = opp.get('how_to_improve','')
                out   = opp.get('expected_outcome','')
                feas  = opp.get('feasibility','中')
                icon  = ti_map.get(otype,'💡')
                fc    = fc_map.get(feas,'#9e9e9e')
                fb    = fb_map.get(feas,'#f5f5f5')
                opps_html += (
                    '<div style="border:1px solid #e0e0e0;padding:12px;margin-bottom:8px;">'
                    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
                    '<div style="font-weight:700;font-size:13px;color:#2c3e50;">'
                    + icon + ' <span style="color:#888;font-size:11px;margin-right:4px;">优先级' + str(oid) + '</span>' + title +
                    '</div>'
                    '<span style="font-size:11px;font-weight:600;padding:2px 7px;background:' + fb + ';color:' + fc + ';">● ' + feas + '可行性</span>'
                    '</div>'
                    '<div style="display:grid;grid-template-columns:80px 1fr;gap:3px 8px;font-size:11px;line-height:1.6;">'
                    '<span style="color:#888;">👤 用户说：</span><span style="color:#444;">' + pain + '</span>'
                    '<span style="color:#888;">📎 依据：</span><span style="color:#555;font-style:italic;">' + evid + '</span>'
                    '<span style="color:#888;">🔧 怎么改：</span><span style="color:#444;">' + how + '</span>'
                    '<span style="color:#888;">📈 预期效果：</span><span style="color:#1b5e20;font-weight:500;">' + out + '</span>'
                    '</div></div>'
                )

            inn_html = (
                '<div style="margin-top:16px;border-top:1px solid #eee;padding-top:14px;">'
                '<div style="font-size:13px;font-weight:700;color:#2c3e50;margin-bottom:10px;">💡 产品创新机会</div>'
                + sum_html + opps_html +
                '</div>'
            )

        p.append(
            f'<details style="margin-bottom:8px;">'
            f'<summary>📦 {asin_p} &nbsp; {str(ttl)[:60]} &nbsp; '
            f'<span style="color:#f9a825;">★{ra}</span> &nbsp; '
            f'<span style="color:#888;font-size:12px;">{rc}条评论 · {pr} · 点击展开详细分析</span></summary>'
            f'<div class="detail-body">'
            f'<div style="font-size:13px;color:#444;line-height:1.7;margin-bottom:8px;">{ol or "暂无点评"}</div>'
            f'{absa_chart_html}'
            f'{rs_html}'
            f'{inn_html}'
            f'</div></details>'
        )
    p.append('</div>')

    # 第8部分：品类好差评横向对比
    rs_sec = build_rs_section(products)
    if rs_sec:
        p.append(section_header('八', '品类好差评横向对比'))
        p.append(rs_sec)
        p.append('</div>')

    # 第9部分：品类创新机会汇总
    inn_sec = build_innovation_section(products, ai_sum)
    if inn_sec:
        p.append(section_header('九', '品类创新机会汇总'))
        p.append(inn_sec)
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
