"""설계도(blueprint) → 한글(.hwp) · PPT(.pptx) · 웹슬라이드(.html), 그리고 검수·자동 수정.

설계도 = {'title', 'sections': [{'heading', 'items': [{'label', 'text', 'children': [{'text'}]}], 'table': {'cols', 'rows'} | None}]}
"""
import base64
import html
import io
import json
import os
import re
import subprocess
import time

import checks
import corp
from core import CFG, DATA, ROOT, today_kr

OUT = os.path.join(DATA, 'out')
JOBS = os.path.join(DATA, 'jobs')
os.makedirs(OUT, exist_ok=True)
STATIC = os.path.join(ROOT, 'static')
HWP = 'koscom-hwp-report'
HWP_TEMPLATES = ['summary_base.hwp', 'summary_catalog.properties', 'detail_base.hwp', 'detail_catalog.properties']


def out_path(doc_id, ver, ext):
    d = os.path.join(OUT, doc_id)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'v{ver}.{ext}')


def job_dir(doc_id, ver):
    d = os.path.join(JOBS, f'{doc_id}_v{ver}')
    os.makedirs(d, exist_ok=True)
    return d


def _java_cp():
    root = corp.path(HWP)
    e = corp.ENTRY[HWP]
    return os.pathsep.join([os.path.join(root, *e['lib'].split('/')), os.path.join(root, *e['jar'].split('/'))])


def _java(*args, timeout=60):
    r = subprocess.run(['java', '-Dfile.encoding=UTF-8', '-cp', _java_cp(), *args], capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')


def hwp_ready():
    try:
        return bool(corp.info(HWP)) and os.path.exists(os.path.join(corp.path(HWP), 'scripts', 'koscom-hwp.jar'))
    except Exception:
        return False


def num(s):
    m = re.fullmatch(r'\s*([-+]?[\d,]*\.?\d+)\s*(%|건|명|억|억원|만원|원|개|점|천만원)?\s*', str(s))
    return float(m.group(1).replace(',', '')) if m else None


# ───────────── 한글 ─────────────
# 양식 preset 으로 한글 스킬의 서식을 고른다: detail(상세보고·투자계획서) · draft(기안문 본문) · form:<사양 경로>(신청서) · 그 밖은 요약보고
DRAFT_TEMPLATES = ['draft_base.hwp', 'draft_catalog.properties']
FORM_AUTO = ('담당', '팀장', '부서장', '부서', '신청일', '요청일', '합계')     # 신청서에서 앱이 채우는 칸
FORM_ME = ('신청자', '요청자', '출장자')                                       # 비어 있으면 작성자로
PH = re.compile(r'\{\{([^{}]+)\}\}')


def hwp_kind(template):
    p = template.get('preset') or ''
    return 'form' if p.startswith('form:') else p if p in ('detail', 'draft') else 'summary'


def _hwp_items(s, table_style=2):
    """설계도의 장 하나 → 렌더러 항목(표를 먼저, 그다음 ㅇ 항목과 하위 -)."""
    items = []
    if s.get('table'):
        t = s['table']
        items.append({'type': 'table', **({'style': table_style} if table_style else {}), 'rows': [t['cols']] + t['rows']})
    for it in s['items']:
        o = {'type': 'o', 'text': it['text']}
        if it.get('label'):
            o['label'] = it['label']
        if it.get('children'):
            o['children'] = [{'type': 'dash', 'text': c['text']} for c in it['children']]
        items.append(o)
    return items


def to_report(bp, template, people):
    """people = {'담당','팀장','부서장','dept','hq'}"""
    kind = hwp_kind(template)
    if kind == 'detail':
        return to_detail(bp, people)
    if kind == 'draft':
        return to_draft(bp)
    if kind == 'form':
        return to_form(bp, template['preset'][5:], people)
    secs = [{'heading': s['heading'], 'items': _hwp_items(s) or [{'type': 'o', 'text': '(내용 없음)'}]} for s in bp['sections']]
    rep = {'type': 'summary', 'title': bp['title'], 'date': today_kr(), 'dept': people.get('dept') or '○○팀',
           'approval': {k: people.get(k, '') for k in ('담당', '팀장', '부서장')}, 'sections': secs}
    if template.get('preset'):
        rep['preset'] = template['preset']
    return rep


def to_detail(bp, people):
    """상세보고(투자계획서 양식): 설계도의 장 → I, II … 장. 라벨 있는 항목이 둘 이상이면 라벨이 대제목(1. 2.),
    아니면 첫 항목을 □ 문장으로 두고 나머지를 ㅇ 항목으로."""
    chapters = []
    for s in bp['sections']:
        items = _hwp_items(s) or [{'type': 'o', 'text': '(내용 없음)'}]
        if sum(1 for o in items if o.get('label')) >= 2:
            secs, lead = [], []
            for o in items:
                if o.get('label'):
                    secs.append({'heading': o.pop('label'), 'items': [o]})
                elif secs:
                    secs[-1]['items'].append(o)
                else:
                    lead.append(o)                       # 첫 라벨 앞(표 등)은 장 끝에 둔다
            secs[-1]['items'] += lead
        else:
            first = next((o for o in items if o['type'] == 'o'), None)
            if first is None:
                secs = [{'style': 'box', 'heading': s['heading'], 'items': items}]
            else:
                rest = [{'type': 'o', 'text': c['text']} for c in first.get('children', [])] + [o for o in items if o is not first]
                head = f"{first['label']} : {first['text']}" if first.get('label') else first['text']
                secs = [{'style': 'box', 'heading': head, 'items': rest}]
        chapters.append({'title': s['heading'], 'sections': secs})
    y, m = today_kr().split('. ')[:2]
    return {'type': 'detail', 'title': bp['title'], 'date': f'{y}.{m}', 'hq': people.get('hq') or people.get('dept') or '○○본부',
            'dept': people.get('dept') or '○○팀',
            'approval': {'담당': people.get('담당', ''), '팀장': people.get('팀장', ''), '부장': people.get('부서장', '')}, 'chapters': chapters}


def draft_purpose(title):
    """기안 제목 → 「아래와 같이 ○○을/를 추진하고자」의 ○○ (끝의 (안)·건·추진을 뗀다)."""
    t = re.sub(r'\s*\(안\)$', '', title.strip())
    t = re.sub(r'(\s+|의\s*)건$', '', t)
    return re.sub(r'\s+추진$', '', t).strip() or title


def to_draft(bp):
    """기안문 본문: 「…근거」 장의 항목 → 관련 근거, 제목 → 추진하는 일, 나머지 장 → 「아래」 번호 항목."""
    basis, secs = [], []
    for s in bp['sections']:
        if '근거' in s['heading']:
            basis += [it['text'] for it in s['items'] if it['text'].strip() and '확인 필요' not in it['text']]
        else:
            secs.append({'heading': s['heading'], 'items': _hwp_items(s, None) or [{'type': 'o', 'text': '(내용 없음)'}]})
    return {'type': 'draft', 'basis': basis, 'purpose': draft_purpose(bp['title']), 'sections': secs}


def form_fields(path):
    """신청서 사양(한글 스킬의 {{칸}} report.json)에서 사람이 채울 칸 이름 — 나오는 순서, 앱이 채우는 칸은 뺀다."""
    out = []
    for m in PH.finditer(corp.read_text(HWP, path)):
        n = m.group(1).strip()
        if n not in out and n not in FORM_AUTO:
            out.append(n)
    return out


def form_prefill(bp, people):
    """신청서 초안: 작성자 칸(신청자·요청자·출장자)이 비었거나 (확인 필요)면 작성자로 — 편집 화면과 검수에도 보이게."""
    for s in bp['sections']:
        for it in s['items']:
            if it.get('label') in FORM_ME and people.get('담당') and (not it['text'].strip() or '확인 필요' in it['text']):
                it['text'] = people['담당']
    return bp


def form_total(spec, vals):
    """「합계」 칸 = 같은 표·같은 열에서 위쪽 {{칸}} 금액의 합(「-」는 0). 값이 없거나 금액이 아닌 칸이 하나라도 있으면 None(못 셈)."""
    for sec in spec.get('sections', []):
        for it in sec.get('items', []):
            rows = it.get('rows') if it.get('type') == 'table' else None
            for i, r in enumerate(rows or []):
                for j, c in enumerate(r):
                    if str(c).strip() != '{{합계}}':
                        continue
                    tot, seen = 0, False
                    for above in rows[:i]:
                        m = PH.fullmatch(str(above[j]).strip()) if j < len(above) else None
                        v = vals.get(m.group(1).strip()) if m else '-'
                        if v == '-':
                            continue
                        if v is None or num(v) is None:
                            return None
                        tot, seen = tot + num(v), True
                    if seen:
                        return f'{int(tot):,}' if tot == int(tot) else f'{tot:,.2f}'
    return None


def to_form(bp, path, people):
    """신청서: 설계도의 「라벨 : 값」 → {{칸}} 값. 결재라인·날짜·부서는 작성자 정보, 합계는 계산, 못 채운 칸은 (확인 필요)."""
    spec = json.loads(corp.read_text(HWP, path))
    vals = {it['label'].strip(): it['text'].strip() for s in bp['sections'] for it in s['items'] if it.get('label') and it['text'].strip()}
    me = people.get('담당', '')
    for k in FORM_ME:
        if not vals.get(k) or '확인 필요' in vals[k]:
            vals[k] = me
    vals = {'담당': me, '팀장': people.get('팀장', ''), '부서장': people.get('부서장', ''), '부서': people.get('dept', ''),
            '신청일': today_kr(), '요청일': today_kr(), **vals}
    if '합계' not in vals:
        vals['합계'] = form_total(spec, vals) or '(확인 필요)'
    s = PH.sub(lambda m: json.dumps(vals.get(m.group(1).strip(), '(확인 필요)'), ensure_ascii=False)[1:-1], json.dumps(spec, ensure_ascii=False))
    return json.loads(s)


def make_hwp(bp, template, people, path, jd):
    rep = to_report(bp, template, people)
    jp = os.path.join(jd, 'report.json')
    json.dump(rep, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 기본 양식은 매번 git 객체에서 새로 꺼낸다(사내 보호 도구가 캐시 파일을 암호화해도 영향 없음)
    tdir = os.path.join(jd, 'templates')
    names = HWP_TEMPLATES + (DRAFT_TEMPLATES if rep['type'] == 'draft' else [])
    corp.fresh_copy(HWP, [f'templates/{n}' for n in names], tdir)
    code, out = _java('Renderer', jp, path, tdir)
    if code != 0 or not os.path.exists(path):
        raise RuntimeError('한글 렌더링 실패: ' + out.strip()[-300:])
    return [l[5:].strip() for l in out.splitlines() if l.startswith('WARN')]


def make_hwp_fill(bp, info, path, jd):
    """서식 채우기형 한글 스킬(목적별: 계약서·공문 등)로 만든다 — 설계도의 칸 값을 서식(.hwp)에 넣는다.
    info = 양식의 skill 정보({'corp': 전사 스킬 id, 'fill': form.yaml})."""
    import fillform
    cid, form = info['corp'], info['fill']
    values = fillform.to_values(bp, form)
    vp = os.path.join(jd, 'values.json')
    json.dump(values, open(vp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 서식은 매번 git 객체에서 새로 꺼낸다(사내 보호 도구가 캐시 파일을 암호화해도 영향 없음)
    tpl = corp.fresh_copy(cid, [form['template']], os.path.join(jd, 'templates'))[0]
    root = corp.path(cid)
    cp = os.pathsep.join(os.path.join(root, *p.split('/')) for p in (form.get('lib') or 'lib/hwplib-1.1.9.jar', form['jar']))
    r = subprocess.run(['java', '-Dfile.encoding=UTF-8', '-cp', cp, 'FillRenderer', tpl, vp, path], capture_output=True, timeout=60)
    out = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError('한글 서식 채우기 실패: ' + out.strip()[-300:])
    return [l[5:].strip() for l in out.splitlines() if l.startswith('WARN')]


def hwp_text(path):
    """한글 파일의 문단 텍스트를 뽑는다(Inspect 출력의 따옴표 안)."""
    code, out = _java('Inspect', path)
    lines = []
    for l in out.splitlines():
        m = re.search(r'"(.*)"\s*$', l)
        if m and m.group(1).strip():
            lines.append(m.group(1).strip())
    return lines


# ───────────── PPT (Koscom Chevron) ─────────────
C = dict(orange=(0xEE, 0x6D, 0x1D), navy=(0x00, 0x33, 0x8D), navy_mid=(0x1F, 0x4B, 0x9B), ink=(0x2B, 0x2B, 0x2E),
         ink2=(0x6E, 0x6E, 0x73), grey=(0xEC, 0xEC, 0xEE), pale=(0xFD, 0xEE, 0xE4), white=(0xFF, 0xFF, 0xFF), tint=(0xED, 0xF4, 0xFB))
F_B, F_M = 'KoPub돋움체 Bold', 'KoPub돋움체 Medium'


def _kosoe_png():
    p = os.path.join(DATA, 'kosoe.png')
    if not os.path.exists(p):
        from PIL import Image
        Image.open(os.path.join(STATIC, 'kosoe.webp')).save(p)
    return p


def make_pptx(bp, template, people, path):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Pt

    rgb = lambda k: RGBColor(*C[k])
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    W, H = prs.slide_width, prs.slide_height
    px = lambda v: Emu(int(v * 12192000 / 1280))   # 1280×720 좌표계
    blank = prs.slide_layouts[6]

    def font(run, size, bold=True, color='ink'):
        run.font.size = Pt(size)
        run.font.bold = False
        run.font.color.rgb = rgb(color)
        name = F_B if bold else F_M
        run.font.name = name
        rpr = run._r.get_or_add_rPr()
        for tag in ('a:ea', 'a:cs'):
            el = rpr.find(qn(tag))
            if el is None:
                el = rpr.makeelement(qn(tag), {})
                rpr.append(el)
            el.set('typeface', name)

    def box(s, x, y, w, h, fill=None, shape=MSO_SHAPE.RECTANGLE):
        sh = s.shapes.add_shape(shape, px(x), px(y), px(w), px(h))
        sh.line.fill.background()
        if fill:
            sh.fill.solid()
            sh.fill.fore_color.rgb = rgb(fill)
        else:
            sh.fill.background()
        sh.shadow.inherit = False
        return sh

    def text(s, x, y, w, h, parts, size=16, color='ink', bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
        tb = s.shapes.add_textbox(px(x), px(y), px(w), px(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        paras = parts if isinstance(parts, list) else [[(parts, {})]]
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            for t, o in para:
                r = p.add_run()
                r.text = t
                font(r, o.get('size', size), o.get('bold', bold), o.get('color', color))
            if i:
                p.space_before = Pt(o.get('gap', 6))
        return tb

    def chevrons(s, x, y, h, n=3, colors=('orange', 'orange', 'pale')):
        for i in range(n):
            box(s, x + i * h * 0.55, y, h * 0.7, h, colors[min(i, len(colors) - 1)], MSO_SHAPE.CHEVRON)

    def footer(s, n):
        box(s, 0, 708, 1280, 12, 'navy')
        text(s, 60, 676, 600, 20, [[('KOSCOM', {'bold': True, 'size': 10, 'color': 'navy'}), ('   ' + bp['title'], {'size': 10, 'color': 'ink2', 'bold': False})]])
        text(s, 1120, 676, 100, 20, f'{n:02d}', size=10, color='ink2', align=PP_ALIGN.RIGHT)

    # 1. 표지 — 흰 바탕, 오른쪽 큰 셰브런 위 코쇠
    s = prs.slides.add_slide(blank)
    box(s, 0, 0, 1280, 720, 'white')
    for i, (c, a) in enumerate((('grey', 0), ('pale', 1), ('orange', 2))):
        box(s, 700 + i * 115, 120, 300, 480, c, MSO_SHAPE.CHEVRON)
    s.shapes.add_picture(_kosoe_png(), px(930), px(255), px(180), px(180))
    box(s, 80, 210, 64, 8, 'orange')
    text(s, 80, 240, 680, 200, bp['title'], size=40, bold=True, color='ink', anchor=MSO_ANCHOR.TOP, spacing=1.05)
    text(s, 80, 470, 640, 60, [[(template['name'], {'size': 16, 'color': 'orange', 'bold': True})],
                               [(f"{people.get('dept', '')}  ·  {people.get('담당', '')}  ·  {today_kr()}", {'size': 14, 'color': 'ink2', 'bold': False, 'gap': 8})]])
    box(s, 0, 680, 1280, 40, 'navy')
    text(s, 80, 688, 300, 24, 'KOSCOM', size=14, bold=True, color='white', anchor=MSO_ANCHOR.MIDDLE)

    # 2. 목차
    s = prs.slides.add_slide(blank)
    box(s, 0, 0, 420, 720, 'navy')
    text(s, 70, 110, 300, 60, 'CONTENTS', size=34, bold=True, color='white')
    chevrons(s, 70, 190, 36, 3, ('orange', 'orange', 'navy_mid'))
    secs = bp['sections']
    step = min(90, 520 / max(1, len(secs)))
    for i, sec in enumerate(secs):
        y = 110 + i * step
        text(s, 500, y, 90, 50, f'{i + 1:02d}', size=30, bold=True, color='orange')
        text(s, 600, y + 6, 600, 50, sec['heading'], size=22, bold=True, color='ink')
        box(s, 500, y + step - 16, 700, 1.5, 'grey')

    # 3. 본문 — 장마다 한 장
    for i, sec in enumerate(secs):
        s = prs.slides.add_slide(blank)
        chevrons(s, 60, 52, 34, 2)
        text(s, 130, 46, 900, 50, [[(f'{i + 1:02d}  ', {'color': 'orange', 'size': 26, 'bold': True}), (sec['heading'], {'size': 26, 'bold': True})]])
        box(s, 60, 112, 1160, 2, 'grey')
        tb = sec.get('table')
        has_tb = bool(tb and tb.get('cols') and tb.get('rows'))
        left_w = 520 if has_tb else 1160
        y = 140
        paras = []
        for it in sec['items']:
            p = [('■ ', {'color': 'orange', 'size': 15, 'bold': True})]
            if it.get('label'):
                p.append((it['label'] + '  ', {'color': 'navy', 'size': 17, 'bold': True}))
            p.append((it['text'], {'size': 17, 'bold': False}))
            paras.append(p)
            for c in it.get('children') or []:
                paras.append([('    - ' + c['text'], {'size': 14, 'color': 'ink2', 'bold': False, 'gap': 2})])
        if paras:
            text(s, 60, y, left_w, 520, paras, size=17, spacing=1.3 if len(paras) < 5 else 1.2)
        if has_tb:
            cols, rws = tb['cols'], tb['rows'][:10]
            numeric = [j for j in range(1, len(cols)) if all(num(r[j]) is not None for r in rws if j < len(r))]
            tx, tw = (620 if paras else 60), (600 if paras else 1160)
            wordy = any(len(str(c)) > 18 for r in rws for c in r)
            th = min(46 * (len(rws) + 1), 300 if numeric else 520)
            g = s.shapes.add_table(len(rws) + 1, len(cols), px(tx), px(140), px(tw), px(th)).table
            for j, c in enumerate(cols):
                cell = g.cell(0, j)
                cell.fill.solid(); cell.fill.fore_color.rgb = rgb('navy')
                cell.text = str(c)
                font(cell.text_frame.paragraphs[0].runs[0], 13, True, 'white')
                cell.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            for r_i, r in enumerate(rws):
                for j in range(len(cols)):
                    cell = g.cell(r_i + 1, j)
                    cell.fill.solid(); cell.fill.fore_color.rgb = rgb('tint' if r_i % 2 else 'white')
                    cell.text = str(r[j]) if j < len(r) else ''
                    runs = cell.text_frame.paragraphs[0].runs
                    if runs:
                        font(runs[0], 12 if not wordy else 11, j == 0, 'ink')
                    # 긴 문장 칸은 왼쪽 정렬, 숫자·짧은 값은 가운데
                    short = num(cell.text) is not None or len(cell.text) <= 10
                    cell.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER if (j and short) else PP_ALIGN.LEFT
            if numeric:
                cd = CategoryChartData()
                cd.categories = [str(r[0]) for r in rws]
                for j in numeric[:3]:
                    cd.add_series(str(cols[j]), [num(r[j]) or 0 for r in rws])
                ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, px(tx), px(160 + th), px(tw), px(640 - 160 - th), cd).chart
                ch.has_legend = len(numeric) > 1
                if ch.has_legend:
                    ch.legend.position = XL_LEGEND_POSITION.TOP
                    ch.legend.include_in_layout = False
                for k, ser in enumerate(ch.series):
                    ser.format.fill.solid()
                    ser.format.fill.fore_color.rgb = rgb(('orange', 'navy', 'ink2')[k])
                ch.value_axis.has_major_gridlines = False
                ch.font.size = Pt(10)
        footer(s, i + 3)

    # 4. 마무리
    s = prs.slides.add_slide(blank)
    box(s, 0, 0, 1280, 720, 'navy')
    for i, c in enumerate(('navy_mid', 'orange', 'orange')):
        box(s, 760 + i * 100, 180, 240, 360, c, MSO_SHAPE.CHEVRON)
    text(s, 100, 290, 700, 80, '감사합니다', size=48, bold=True, color='white')
    text(s, 100, 380, 700, 40, f"{people.get('dept', '')} {people.get('담당', '')}", size=16, color='white', bold=False)
    prs.save(path)
    return len(prs.slides)


def pptx_text(path):
    from pptx import Presentation
    out = []
    for s in Presentation(path).slides:
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                out.append(sh.text_frame.text.strip())
            if sh.has_table:
                for r in sh.table.rows:
                    out.append(' | '.join(c.text for c in r.cells))
    return out


# ───────────── 웹슬라이드 ─────────────
def _b64(name):
    return base64.b64encode(open(os.path.join(STATIC, name), 'rb').read()).decode()


WEB_CSS = '''
@font-face{font-family:KoPub;font-weight:700;src:url(data:font/woff2;base64,__B__) format('woff2')}
@font-face{font-family:KoPub;font-weight:500;src:url(data:font/woff2;base64,__M__) format('woff2')}
:root{--o:#ee6d1d;--n:#00338d;--ink:#2b2b2e;--ink2:#6e6e73;--g:#ececee;--p:#fdeee4}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0b1830;font-family:KoPub,'Malgun Gothic',sans-serif;color:var(--ink);word-break:keep-all;overflow-wrap:break-word}
#deck{height:100%;overflow-y:auto;scroll-snap-type:y mandatory}
.s{height:100vh;scroll-snap-align:start;display:flex;align-items:center;justify-content:center;padding:3vh 3vw}
.card{position:relative;width:min(100%,calc(94vh*16/9));aspect-ratio:16/9;background:#fff;border-radius:14px;overflow:hidden;
 padding:5.5% 6%;box-shadow:0 30px 80px rgba(0,0,0,.35);transform:perspective(1400px) rotateX(var(--rx,0deg)) rotateY(var(--ry,0deg));transition:transform .25s ease-out}
.card.navy{background:var(--n);color:#fff}
.chev{position:absolute;width:30%;height:70%;clip-path:polygon(0 0,62% 0,100% 50%,62% 100%,0 100%,38% 50%);transition:transform .6s cubic-bezier(.2,.8,.2,1)}
.cover .chev{top:15%;width:24%}
.cover .c1{right:30%;background:var(--g)}.cover .c2{right:20%;background:var(--p)}.cover .c3{right:10%;background:var(--o)}
.cover img{position:absolute;right:12%;top:33%;width:15%;animation:bob 3.2s ease-in-out infinite}
@keyframes bob{50%{transform:translateY(-4%) rotate(-3deg)}}
.cover .bar{width:5%;height:1.1%;background:var(--o);margin-bottom:3%}
h1{position:relative;z-index:2;font-size:clamp(20px,3.2vw,50px);line-height:1.15;max-width:46%;font-weight:700}
.meta{margin-top:3%;font-size:clamp(11px,1.15vw,18px);color:var(--ink2);font-weight:500}.meta b{color:var(--o)}
.foot{position:absolute;left:0;right:0;bottom:0;height:5.5%;background:var(--n);color:#fff;font-weight:700;font-size:clamp(9px,.9vw,14px);display:flex;align-items:center;padding:0 6%}
.hd{display:flex;align-items:baseline;gap:1.2%;border-bottom:2px solid var(--g);padding-bottom:1.6%;margin-bottom:3%}
.hd i{font-style:normal;color:var(--o);font-weight:700;font-size:clamp(16px,2.2vw,34px)}
.hd h2{font-size:clamp(16px,2.2vw,34px)}
.body{display:grid;grid-template-columns:1fr;gap:4%;height:76%}.body.two{grid-template-columns:1fr 1.1fr}
ul{list-style:none;display:flex;flex-direction:column;gap:3.5%}
li{font-size:clamp(11px,1.35vw,21px);line-height:1.5;font-weight:500;opacity:0;transform:translateY(14px);transition:.5s ease}
.on li{opacity:1;transform:none}.on li:nth-child(2){transition-delay:.1s}.on li:nth-child(3){transition-delay:.2s}.on li:nth-child(4){transition-delay:.3s}
li:before{content:'';display:inline-block;width:.55em;height:.55em;background:var(--o);margin-right:.6em;vertical-align:.1em;clip-path:polygon(0 0,60% 0,100% 50%,60% 100%,0 100%,40% 50%)}
li b{color:var(--n);margin-right:.5em}li small{display:block;margin:.3em 0 0 1.2em;color:var(--ink2);font-size:.82em}
li:hover{color:var(--n)}
table{border-collapse:collapse;width:100%;font-size:clamp(9px,1.05vw,16px)}
th{background:var(--n);color:#fff;padding:.55em .6em;font-weight:700}td{padding:.5em .6em;text-align:center;border-bottom:1px solid var(--g);font-weight:500}
td:first-child,td.l{text-align:left}td:first-child{font-weight:700}tr:hover td{background:var(--p)}
.vis{display:flex;flex-direction:column;gap:4%;min-height:0}.vis canvas{flex:1;min-height:0}
.end{display:flex;flex-direction:column;justify-content:center}.end h1{color:#fff}.end .chev{top:20%}
.end .c1{right:26%;background:#1f4b9b}.end .c2{right:16%;background:var(--o)}.end .c3{right:6%;background:var(--o)}
#nav{position:fixed;right:18px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:8px}
#nav a{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.35)}#nav a.cur{background:var(--o);height:22px;border-radius:5px}
'''

WEB_JS = '''
const deck=document.getElementById('deck'),ss=[...document.querySelectorAll('.s')],nav=document.getElementById('nav');
ss.forEach((s,i)=>{const a=document.createElement('a');a.href='#';a.onclick=e=>{e.preventDefault();s.scrollIntoView({behavior:'smooth'})};nav.appendChild(a)});
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){const i=ss.indexOf(e.target);e.target.classList.add('on');
 [...nav.children].forEach((a,j)=>a.classList.toggle('cur',j==i));const c=e.target.querySelector('canvas');if(c&&!c._c)draw(c)}}),{threshold:.6});ss.forEach(s=>io.observe(s));
document.addEventListener('keydown',e=>{const i=[...nav.children].findIndex(a=>a.classList.contains('cur'));
 if(['ArrowDown','PageDown',' ','ArrowRight'].includes(e.key)){e.preventDefault();ss[Math.min(i+1,ss.length-1)].scrollIntoView({behavior:'smooth'})}
 if(['ArrowUp','PageUp','ArrowLeft'].includes(e.key)){e.preventDefault();ss[Math.max(i-1,0)].scrollIntoView({behavior:'smooth'})}});
document.querySelectorAll('.card').forEach(c=>{c.onmousemove=e=>{const r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
 c.style.setProperty('--ry',(x*4)+'deg');c.style.setProperty('--rx',(-y*4)+'deg');c.querySelectorAll('.chev').forEach((v,k)=>v.style.transform=`translate(${x*(k+1)*14}px,${y*(k+1)*10}px)`)};
 c.onmouseleave=()=>{c.style.setProperty('--ry','0deg');c.style.setProperty('--rx','0deg');c.querySelectorAll('.chev').forEach(v=>v.style.transform='')}});
function draw(c){if(!window.Chart)return;const d=JSON.parse(c.dataset.chart);const pal=['#ee6d1d','#00338d','#8c8c92'];
 c._c=new Chart(c,{type:'bar',data:{labels:d.labels,datasets:d.series.map((s,k)=>({label:s.name,data:s.data,backgroundColor:pal[k],borderRadius:6}))},
 options:{maintainAspectRatio:false,animation:{duration:1100,easing:'easeOutQuart'},plugins:{legend:{display:d.series.length>1}},scales:{y:{grid:{color:'#ececee'}},x:{grid:{display:false}}}}});
 c.parentElement.onmouseenter=()=>{c._c.reset();c._c.update()}}
'''


def make_web(bp, template, people, path):
    e = html.escape
    chart_js = ''
    slides = [f'''<section class="s"><div class="card cover"><div class="chev c1"></div><div class="chev c2"></div><div class="chev c3"></div>
<img alt="" src="data:image/webp;base64,{_b64('kosoe.webp')}"><div class="bar"></div><h1>{e(bp['title'])}</h1>
<p class="meta"><b>{e(template['name'])}</b> · {e(people.get('dept', ''))} · {e(people.get('담당', ''))} · {today_kr()}</p><div class="foot">KOSCOM</div></div></section>''']
    for i, sec in enumerate(bp['sections']):
        lis = ''.join(f"<li>{'<b>' + e(it['label']) + '</b>' if it.get('label') else ''}{e(it['text'])}"
                      + ''.join(f"<small>– {e(c['text'])}</small>" for c in it.get('children') or []) + '</li>' for it in sec['items'])
        vis = ''
        tb = sec.get('table')
        if tb and tb.get('cols') and tb.get('rows'):
            cols, rws = tb['cols'], tb['rows'][:10]
            vis = '<table><tr>' + ''.join(f'<th>{e(str(c))}</th>' for c in cols) + '</tr>' + ''.join(
                '<tr>' + ''.join(f'<td{" class=l" if j < len(r) and num(r[j]) is None and len(str(r[j])) > 10 else ""}>{e(str(r[j]) if j < len(r) else "")}</td>' for j in range(len(cols))) + '</tr>' for r in rws) + '</table>'
            numeric = [j for j in range(1, len(cols)) if all(num(r[j]) is not None for r in rws if j < len(r))]
            if numeric:
                d = {'labels': [str(r[0]) for r in rws], 'series': [{'name': str(cols[j]), 'data': [num(r[j]) or 0 for r in rws]} for j in numeric[:3]]}
                vis += f"<canvas data-chart='{e(json.dumps(d, ensure_ascii=False))}'></canvas>"
                chart_js = open(os.path.join(STATIC, 'chart.umd.min.js'), encoding='utf-8').read()
            vis = f'<div class="vis">{vis}</div>'
        two = ' two' if (vis and lis) else ''
        slides.append(f'''<section class="s"><div class="card"><div class="hd"><i>{i + 1:02d}</i><h2>{e(sec['heading'])}</h2></div>
<div class="body{two}">{'<ul>' + lis + '</ul>' if lis else ''}{vis}</div><div class="foot">KOSCOM &nbsp;·&nbsp; {e(bp['title'])}</div></div></section>''')
    slides.append(f'''<section class="s"><div class="card navy end"><div class="chev c1"></div><div class="chev c2"></div><div class="chev c3"></div>
<h1>감사합니다</h1><p class="meta" style="color:#fff">{e(people.get('dept', ''))} {e(people.get('담당', ''))}</p></div></section>''')
    css = WEB_CSS.replace('__B__', _b64('KoPubDotum-Bold.woff2')).replace('__M__', _b64('KoPubDotum-Medium.woff2'))
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(bp["title"])}</title><style>{css}</style></head><body><main id="deck">{"".join(slides)}</main><nav id="nav"></nav>'
            f'<script>{chart_js}</script><script>{WEB_JS}</script></body></html>')
    open(path, 'w', encoding='utf-8').write(page)
    return len(slides)


# ───────────── 검수 ─────────────
BAD_END = re.compile(r'(습니다|입니다|합니다|됩니다|했다|한다|이다|있다|없다|된다)\.?$')
DATE_RX = checks.DATE_RX


def _all_items(bp):
    for s in bp['sections']:
        for it in s['items']:
            yield it
            for c in it.get('children') or []:
                yield c


def check(bp, warns=(), style=None, fixed=()):
    """문체 검수. style이 없으면 코스콤 보고 문법, 있으면 그 스킬의 문체(대표 문서에서 잰 기준).
    fixed(스킬의 고정 문구)는 글자 그대로 넣어야 하는 글이라 문체 검사에서 뺀다."""
    st = checks.norm_style(style)
    fixed = [str(f) for f in fixed]
    slots = checks.slots_of(fixed)                       # 고정 문구의 [칸 이름] — 안 채워진 채 남으면 '확인 필요'
    all_items = list(_all_items(bp))
    items = [it for it in all_items if not checks.is_fixed_item(it['text'], fixed)]
    out = []
    if st['date'] != 'any':
        dates = [m.group(0) for it in items for m in DATE_RX.finditer(it['text']) if not checks.date_ok(m, st['date'])]
        out.append({'id': 'date', 'name': f"날짜 형식 ({checks.fmt_date(2026, 10, 28, st['date'])})", 'ok': not dates, 'detail': ', '.join(dates[:3]), 'fix': bool(dates)})
    if st['max_len']:
        long = [it['text'] for it in items if len(it['text']) > st['max_len']]
        out.append({'id': 'long', 'name': f"항목 길이 {st['max_len']}자 이내", 'ok': not long, 'detail': f'{len(long)}개 초과' if long else '', 'fix': bool(long)})
    if st['ending'] != 'any':
        bad = BAD_END if st['ending'] == 'noun' else checks.NOUN_END
        ends = [it['text'] for it in items if bad.search(it['text'].strip())]
        out.append({'id': 'end', 'name': checks.ENDINGS[st['ending']], 'ok': not ends,
                    'detail': (f'{len(ends)}개 문장형' if st['ending'] == 'noun' else f'{len(ends)}개 개조식(~함·~임)') if ends else '', 'fix': bool(ends)})
    todo = [it['text'] for it in all_items if '확인 필요' in it['text'] or '반영 예정' in it['text'] or any(s in it['text'] for s in slots)]
    empty = [s['heading'] for s in bp['sections'] if not s['items'] and not s.get('table')]
    return out + [
        {'id': 'empty', 'name': '빈 장 없음', 'ok': not empty, 'detail': ', '.join(empty), 'fix': False},
        {'id': 'todo', 'name': '확인 필요 표시 없음', 'ok': not todo, 'detail': f'{len(todo)}곳 — 직접 확인해 주세요' if todo else '', 'fix': False},
        {'id': 'render', 'name': '한글 쪽 넘침·서식 경고 없음', 'ok': not warns, 'detail': '; '.join(warns)[:200], 'fix': any('[제목]' in w for w in warns)},
    ]


ENDS = [('했습니다', '했음'), ('하였습니다', '하였음'), ('되었습니다', '되었음'), ('합니다', '함'), ('됩니다', '됨'), ('입니다', '임'),
        ('습니다', '음'), ('한다', '함'), ('된다', '됨'), ('이다', '임'), ('있다', '있음'), ('없다', '없음'), ('했다', '했음')]
# 서술형 문체(계약서·공문 등)로 되돌릴 때: 개조식 → 평서문 / 존댓말
ENDS_PLAIN = [('하였음', '하였다'), ('되었음', '되었다'), ('했음', '했다'), ('있음', '있다'), ('없음', '없다'), ('함', '한다'), ('됨', '된다'), ('임', '이다')]
ENDS_POLITE = [('하였음', '하였습니다'), ('되었음', '되었습니다'), ('했음', '했습니다'), ('있음', '있습니다'), ('없음', '없습니다'), ('함', '합니다'),
               ('됨', '됩니다'), ('임', '입니다')]


def _noun_end(t):
    """문장형 끝(~합니다 · ~한다 · ~이다 …) → 개조식(~함 · ~임). 동사 어미만 바꾸므로 뜻은 그대로다."""
    t = t.strip().rstrip('.')
    for a, z in ENDS:
        if t.endswith(a):
            return t[: -len(a)] + z
    return t


def fix_endings(bp, style=None, fixed=()):
    """AI가 쓴 설계도를 명사형 문체(개조식)에 맞춘다 — 지침을 줘도 AI가 가끔 「~고자 합니다」처럼 끝내는 항목이 있어서.
    검수 자동 수정과 같은 규칙 변환(AI 호출 없음). 고정 문구 · 필수 문구는 글자 그대로 둔다.
    서술형 문체로 되돌리는 변환은 「포함 · 책임」 같은 명사를 잘못 바꿀 수 있어 여기서는 하지 않는다(검수 자동 수정에서만)."""
    if checks.norm_style(style)['ending'] != 'noun':
        return bp
    fixed = [str(f).strip() for f in fixed if str(f).strip()]
    b = json.loads(json.dumps(bp))
    for it in _all_items(b):        # 고정 문구가 들어 있는 항목(AI가 다른 글과 이어 붙인 것 포함)은 손대지 않는다
        if BAD_END.search(it['text'].strip()) and not any(checks.fixed_present(f, it['text']) for f in fixed):
            it['text'] = _noun_end(it['text'])
    return b


def autofix(bp, shorten_fn, warns=(), style=None, fixed=()):
    st = checks.norm_style(style)
    fixed = [str(f) for f in fixed]
    b = json.loads(json.dumps(bp))
    items = [it for it in _all_items(b) if not checks.is_fixed_item(it['text'], fixed)]
    for it in items:
        t = it['text']
        if st['date'] != 'any':
            t = DATE_RX.sub(lambda m: m.group(0) if checks.date_ok(m, st['date']) else checks.fmt_date(*checks.date_parts(m), st['date']), t)
        t = t.strip()
        if st['ending'] == 'noun':
            t = _noun_end(t)
        elif st['ending'] in ('plain', 'polite'):
            core = t.rstrip('.')
            for a, z in (ENDS_PLAIN if st['ending'] == 'plain' else ENDS_POLITE):
                if core.endswith(a):
                    t = core[: -len(a)] + z + '.'
                    break
        it['text'] = t
    long = [it for it in items if st['max_len'] and len(it['text']) > st['max_len']]
    meta = None
    if long:
        short, meta = shorten_fn([it['text'] for it in long])
        for it, s in zip(long, short):
            it['text'] = s
    if any('[제목]' in w for w in warns):
        b['title'] = short_title(b['title'])
    return b, meta


def short_title(t, n=22):
    """제목 칸(한 줄 약 22자)에 맞게 단어 단위로 자른다."""
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) <= n:
        return t
    out = ''
    for w in t.split(' '):
        if len((out + ' ' + w).strip()) > n:
            break
        out = (out + ' ' + w).strip()
    return out or t[:n]


if __name__ == '__main__':           # 자체검사(전사 스킬 없이): 신청서 합계 · 기안 목적 · 기안문/상세보고 변환
    spec = {'sections': [{'items': [{'type': 'table', 'rows': [['항목', '금액'], ['교통비', '{{교통비}}'], ['숙박비', '{{숙박비}}'], ['합계', '{{합계}}']]}]}]}
    assert form_total(spec, {'교통비': '119,600', '숙박비': '90,000'}) == '209,600'
    assert form_total(spec, {'교통비': '119,600', '숙박비': '-'}) == '119,600'
    assert form_total(spec, {'교통비': '119,600', '숙박비': '(확인 필요)'}) is None and form_total(spec, {}) is None
    assert form_total(spec, {'교통비': '119,600'}) is None          # 숙박비 칸 값이 없으면 합계를 셀 수 없다
    assert [draft_purpose(t) for t in ('회의실 장비 교체 추진(안)', '회의실 장비 교체의 건', '보안 사건 대응 계획')] == \
        ['회의실 장비 교체', '회의실 장비 교체', '보안 사건 대응 계획']
    bp = {'title': 'X 추진', 'sections': [
        {'heading': '관련 근거', 'items': [{'text': '총무2026-1(2026. 1. 2. : 보고)'}, {'text': '(확인 필요)'}]},
        {'heading': '추진 개요', 'items': [{'label': '배경', 'text': 'a', 'children': [{'text': 'b'}]}], 'table': {'cols': ['c'], 'rows': [['1']]}}]}
    d = to_draft(bp)
    assert d['basis'] == ['총무2026-1(2026. 1. 2. : 보고)'] and d['purpose'] == 'X'
    assert d['sections'][0]['items'][0] == {'type': 'table', 'rows': [['c'], ['1']]}
    det = to_detail({**bp, 'sections': bp['sections'][1:] + [{'heading': '효과', 'items': [{'label': '가', 'text': '1'}, {'label': '나', 'text': '2'}]}]},
                    {'dept': '팀'})
    assert det['chapters'][0]['sections'][0]['style'] == 'box' and det['chapters'][0]['sections'][0]['heading'] == '배경 : a'
    assert [s['heading'] for s in det['chapters'][1]['sections']] == ['가', '나'] and det['hq'] == '팀'
    # 명사형 문체: AI가 문장형으로 끝낸 항목만 개조식으로, 고정 문구 · 다른 문체는 그대로
    fx = '본 자료는 참고용이며 책임지지 않습니다.'
    bp = {'title': 't', 'sections': [{'heading': 'h', 'table': None, 'items': [
        {'label': '', 'text': '시범 운영을 추진하고자 합니다.', 'children': [{'text': '예산은 3억원이다'}]},
        {'label': '', 'text': '부가세 포함', 'children': []}, {'label': '', 'text': fx, 'children': []},
        {'label': '', 'text': '세부 내용은 붙임 참조. ' + fx, 'children': []}]}]}
    out = fix_endings(bp, None, [fx])
    assert [it['text'] for it in _all_items(out)] == ['시범 운영을 추진하고자 함', '예산은 3억원임', '부가세 포함', fx, '세부 내용은 붙임 참조. ' + fx]
    assert bp['sections'][0]['items'][0]['text'].endswith('합니다.')                       # 원본은 그대로(복사본을 고침)
    assert [c['detail'] for c in check(out, (), None, [fx]) if c['id'] == 'end'] == ['1개 문장형']    # 고정 문구를 이어 붙인 항목만 남는다
    assert fix_endings(bp, {'ending': 'plain'}) is bp and fix_endings(bp, {'ending': 'any'}) is bp
    print('engines selftest OK')


def engine_of(fmt, preset=''):
    """화면 표시용: 이 형식을 만드는 전사 스킬과 고정 버전(양식 preset 이 고른 서식·덱·원고까지)."""
    import ppt_chevron
    import webslide
    cid = {'hwp': HWP, 'ppt': 'koscom-doc-pack', 'web': 'koscom-webslide'}[fmt]
    c = corp.info(cid) or {}
    kind = hwp_kind({'preset': preset})
    name = {'hwp': 'koscom-hwp-report' + ('' if kind == 'summary' else ' · ' + {'detail': '상세보고', 'draft': '기안문', 'form': '신청서'}[kind]),
            'ppt': 'ppt-master · ' + ppt_chevron.deck_name(preset),
            'web': 'koscom-webslide' + ('' if webslide.template_id(preset) == 'kosoe' else ' · ' + webslide.template_id(preset))}[fmt]
    return {'corp': cid, 'name': name, 'sha': (c.get('sha') or '')[:7]}


def fill_engine(cid):
    c = corp.info(cid) or {}
    return {'corp': cid, 'name': f'{cid} · 서식 채우기', 'sha': (c.get('sha') or '')[:7]}


def themable(fmt, template):
    """문서 테마를 입힐 수 있는 문서인가. 테마는 기본 디자인(PPT koscom-chevron 덱 · 웹 kosoe 원고)의 색·도형을 바꾸는 것이라,
    한글과 덱·원고를 따로 고른 양식(preset deck:… · web:…)은 그 디자인 그대로 둔다 — 입히면 두 디자인이 섞인다."""
    import ppt_chevron
    import webslide
    p = template.get('preset') or ''
    return (fmt == 'ppt' and ppt_chevron.deck_name(p) == ppt_chevron.DECKS[0]) or (fmt == 'web' and webslide.template_id(p) == 'kosoe')


def make(fmt, bp, template, people, doc_id, ver, theme=None):
    """theme: 문서 테마(doc_themes) — PPT·웹의 겉모습만 바꾼다. 한글은 양식 그대로."""
    t0 = time.time()
    theme = theme if themable(fmt, template) else None
    ext = {'hwp': 'hwp', 'ppt': 'pptx', 'web': 'html'}[fmt]
    path = out_path(doc_id, ver, ext)
    jd = job_dir(doc_id, ver)
    warns = []
    engine = engine_of(fmt, template.get('preset') or '')
    info = template.get('skill') or {}
    if isinstance(info, str):
        info = json.loads(info or '{}') or {}
    if fmt == 'hwp' and info.get('fill'):          # 목적별 한글 스킬(서식 채우기형)
        engine = fill_engine(info['corp'])
        warns = make_hwp_fill(bp, info, path, jd)
    elif fmt == 'hwp':
        warns = make_hwp(bp, template, people, path, jd)
    elif fmt == 'ppt':
        try:
            if CFG['ppt_engine'] != 'ppt-master':
                raise RuntimeError('설정: 경량 PPT 엔진')
            import ppt_chevron
            ppt_chevron.make(bp, template, people, path, jd, theme)
        except Exception as e:
            import run_ppt_master
            run_ppt_master.patch()
            make_pptx(bp, template, people, path)
            warns.append(f'[PPT] 전사 ppt-master 변환 대신 경량 렌더러 사용: {str(e)[:120]}')
            engine = {**engine, 'name': '경량 Chevron 렌더러(대체)'}
    else:
        try:
            import webslide
            webslide.make(bp, template, people, path, jd, template.get('chain_names'), theme)
        except Exception as e:
            make_web(bp, template, people, path)
            warns.append(f'[웹] 전사 webslide 대신 경량 웹 렌더러 사용: {str(e)[:120]}')
            engine = {**engine, 'name': '경량 웹 렌더러(대체)'}
    return path, warns, int((time.time() - t0) * 1000), engine
