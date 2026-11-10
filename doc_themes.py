"""문서 테마 — PPT·웹슬라이드를 만들 때 고르는 디자인 9가지.

화면 테마(static/themes)와 같은 이름·색·그림을 쓴다. 내용(설계도)과 엔진은 그대로이고 겉모습만 바뀐다.
- PPT  : 전사 스킬 ppt-master(koscom-chevron)가 만든 SVG의 색·서체를 바꾸고 표지 바탕 그림을 넣는다 → 그대로 편집 가능한 PPTX
- 웹   : 전사 스킬 koscom-webslide 덱에 테마 CSS를 얹는다(그림·서체는 CSS 안에 넣어 단일 파일 유지)
- base : 전사 스킬의 기본 모습 그대로(아무것도 바꾸지 않는다)
그림은 doc_theme_assets.py 가 static/doc_themes/ 에 만들어 둔다.
"""
import base64
import os
import re

from core import ROOT

ASSETS = os.path.join(ROOT, 'static', 'doc_themes')
APP_FONTS = os.path.join(ROOT, 'static', 'themes', '_fonts')
DEFAULT = 'base'
THEMES = [
    {'id': 'base', 'name': '원래 디자인', 'desc': '전사 스킬의 기본 모습 그대로 (셰브론)'},
    {'id': 'b', 'name': '그래파이트 스위스', 'desc': '흰 바탕, 진회색 글자, 3D 쉐브론 표지'},
    {'id': 'a', 'name': '이그제큐티브 네이비', 'desc': '딥 네이비와 야경 표지, 오렌지는 강조에만'},
    {'id': 'c', 'name': '미드나이트 콘솔', 'desc': '어두운 화면과 오렌지 데이터 흐름'},
    {'id': 'd', 'name': '증권 인쇄', 'desc': '보안 인쇄 문양과 명조 제목'},
    {'id': 'e', 'name': '코쇠 현장 노트', 'desc': '코쇠 손그림 표지와 형광펜 강조'},
    {'id': 'f', 'name': '기획서와 한 몸', 'desc': '네이비·셰브론 표지, 본선 기획서의 색'},
    {'id': 'g', 'name': '마켓 펄스', 'desc': '시세 화면 표지와 남청 틀'},
    {'id': 'h', 'name': '여의도 사옥', 'desc': '건축 사진 표지와 명조 제목, 넓은 여백'},
]
IDS = [t['id'] for t in THEMES]
NAMES = {t['id']: t['name'] for t in THEMES}


def norm(tid):
    return tid if tid in IDS else DEFAULT


def listing():
    """화면용 목록(미리보기 그림 주소 포함)."""
    out = []
    for t in THEMES:
        o = dict(t)
        for k in ('ppt', 'web'):
            p = os.path.join(ASSETS, 'thumb', f"{t['id']}_{k}.webp")
            o[k + '_thumb'] = f"/static/doc_themes/thumb/{t['id']}_{k}.webp" if os.path.exists(p) else ''
        out.append(o)
    return out


def _b64(path, mime):
    return f'data:{mime};base64,' + base64.b64encode(open(path, 'rb').read()).decode()


# ══════════════════════════ PPT ══════════════════════════
# 셰브론 템플릿이 쓰는 색 → 테마 색. (#ffffff는 자리마다 뜻이 달라 따로 다룬다)
_KEY = {'ink': '#2b2b2e', 'ink2': '#6e6e73', 'grey': '#8c8c92', 'line': '#dcdce0', 'tint': '#fad3bb', 'pale': '#f4f4f6', 'orange': '#ee6d1d', 'orange2': '#f26522',
        'chev_grey': '#ececee', 'chev_pale': '#fdeee4', 'navy': '#00338d', 'navy2': '#1f4b9b', 'navy3': '#0f499c', 'bt': '#edf4fb'}
_FB = "'KoPub돋움체 Bold', 'KoPubDotum Bold', Pretendard, 'Malgun Gothic', sans-serif"
_FM = "'KoPub돋움체 Medium', 'KoPubDotum Medium', Pretendard, 'Malgun Gothic', sans-serif"


def _pal(**kw):
    p = {'bg': '#ffffff', 'card': '#ffffff', 'title': kw.get('orange', '#ee6d1d'), **{k: v for k, v in _KEY.items()}}
    p.update(kw)
    return p


PPT = {
    'a': {'pal': _pal(ink='#1b2a3d', ink2='#6b7480', grey='#8a93a0', line='#e3e7ed', tint='#e4eaf2', pale='#f4f6f9', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#e9edf2', chev_pale='#fff0e6', navy='#0e2340', navy2='#19395f', navy3='#0a1a31', bt='#dfe8f2', title='#0e2340'),
          'cover': 'dark', 'decor': '<rect x="0" y="0" width="1280" height="12" fill="#0e2340"/>'},
    'b': {'pal': _pal(ink='#333333', ink2='#5d6060', grey='#8b8e8e', line='#d9dbdb', tint='#ececec', pale='#f6f6f6', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#e6e7e7', chev_pale='#fff1e8', navy='#2e3333', navy2='#4a4f4f', navy3='#171b1b', bt='#f1f2f2', title='#333333'),
          'cover': 'light', 'decor': '<rect x="0" y="0" width="1280" height="6" fill="#f06e1e"/>'},
    'c': {'pal': _pal(bg='#0f1215', card='#1a2027', ink='#e6e8ea', ink2='#9aa3ab', grey='#7d8791', line='#2a323a', tint='#27323c', pale='#1a2027', orange='#f06e1e',
                      orange2='#f06e1e', chev_grey='#1c232a', chev_pale='#2a1a10', navy='#151a1f', navy2='#27323c', navy3='#1c232a', bt='#d7dde3', title='#f06e1e'),
          'cover': 'dark', 'decor': ''},
    'd': {'pal': _pal(bg='#fbfbfa', ink='#23292b', ink2='#5d6060', grey='#858b8c', line='#c7cdcc', tint='#e9eeed', pale='#f2f4f3', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#e4e7e6', chev_pale='#fff1e8', navy='#2c424c', navy2='#405a66', navy3='#59717d', bt='#edf2f4', title='#23292b'),
          'cover': 'light', 'fb': "'KoPub바탕체 Bold', 'KoPubBatang Bold', '바탕', serif",
          'decor': '<rect x="24" y="24" width="1232" height="672" fill="none" stroke="#c7cdcc" stroke-width="1"/><rect x="30" y="30" width="1220" height="660" fill="none" stroke="#c7cdcc" stroke-width="0.5"/>'},
    'e': {'pal': _pal(ink='#2f3535', ink2='#5d6060', grey='#8a8e8e', line='#c9cdcd', tint='#ffe4d1', pale='#f6f7f7', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#e7e9e9', chev_pale='#fff2e8', navy='#2f3535', navy2='#5d6060', navy3='#171b1b', bt='#f0f2f2', title='#2f3535'),
          'cover': 'light', 'fb': "'나눔고딕 ExtraBold', 'NanumGothic ExtraBold', '맑은 고딕', sans-serif", 'fm': "'나눔고딕', 'NanumGothic', '맑은 고딕', sans-serif",
          'decor': '<rect x="76" y="131" width="300" height="20" fill="#ffd4b8"/>', 'decor_on': ('body',)},
    'f': {'pal': _pal(title='#00338d'), 'cover': 'dark', 'decor': '<rect x="0" y="0" width="16" height="720" fill="#00338d"/>'},
    'g': {'pal': _pal(ink='#303b48', ink2='#697482', grey='#8a95a3', line='#d5dbe2', tint='#dff0f6', pale='#f5f7fa', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#e5e9ee', chev_pale='#fff1e7', navy='#13233a', navy2='#1b2f4a', navy3='#0c1828', bt='#e9f5f9', title='#13233a'),
          'cover': 'dark', 'fb': "'나눔고딕 ExtraBold', 'NanumGothic ExtraBold', '맑은 고딕', sans-serif", 'fm': "'나눔고딕', 'NanumGothic', '맑은 고딕', sans-serif",
          'decor': '<rect x="0" y="0" width="1280" height="44" fill="#13233a"/><rect x="0" y="44" width="1280" height="3" fill="#3fa7c9"/>'},
    'h': {'pal': _pal(bg='#f4f4f1', ink='#262a2b', ink2='#5d6060', grey='#8b8d8a', line='#c9cac7', tint='#e3e3df', pale='#e9e9e6', orange='#f06e1e', orange2='#f06e1e',
                      chev_grey='#d6d7d4', chev_pale='#fff3ec', navy='#262a2b', navy2='#3e4344', navy3='#171a1b', bt='#f1f1ef', title='#262a2b'),
          'cover': 'light', 'fb': "'나눔명조', 'NanumMyeongjo', '바탕', serif", 'fb_bold': True, 'decor': ''},
}
_cover_cache = {}


def _cover_uri(tid):
    if tid not in _cover_cache:
        p = os.path.join(ASSETS, 'ppt', f'{tid}_cover.jpg')
        _cover_cache[tid] = _b64(p, 'image/jpeg') if os.path.exists(p) else ''
    return _cover_cache[tid]


def _wrap_cover_title(svg, width=600):
    """그림이 오른쪽에 놓이는 표지: 제목이 그림을 덮지 않게 왼쪽 600px 안에서 두 줄로 나눈다."""
    import html

    import ppt_chevron
    m = re.search(r'<text id="title-carrier"([^>]*?)font-size="52"([^>]*)>([^<]*)</text>', svg)
    if not m:
        return svg
    title = html.unescape(m.group(3))
    if sum(ppt_chevron._w(c, 52) for c in title) <= width:
        return svg
    lines = ppt_chevron.wrap(title, width, 44, 2)
    ys = ['392'] if len(lines) == 1 else ['366', '422']
    out = ''
    for i, (ln, y) in enumerate(zip(lines, ys)):
        attrs = re.sub(r'\sy="[^"]*"', f' y="{y}"', m.group(1) + 'font-size="44"' + m.group(2))
        out += f'<text{" id=" + chr(34) + "title-carrier" + chr(34) if i == 0 else ""}{attrs}>{html.escape(ln)}</text>'
    return svg[:m.start()] + out + svg[m.end():]


def ppt_apply(svg, tid, kind):
    """셰브론 SVG 한 장에 테마를 입힌다. kind: cover · agenda · body · closing"""
    t = PPT.get(norm(tid))
    if not t:
        return svg
    p = t['pal']
    cover_img = _cover_uri(tid) if kind == 'cover' else ''
    if cover_img:                                   # 표지: 셰브론 도형 대신 바탕 그림 한 장
        svg = re.sub(r'<polygon id="layout-chevron-[a-z]+"[^>]*/>\s*', '', svg)
        svg = re.sub(r'(<rect id="master-bg"[^>]*/>)', lambda m: m.group(1) + f'\n  <image id="theme-cover" href="{cover_img}" x="0" y="0" width="1280" height="720" preserveAspectRatio="xMidYMid slice"/>', svg, count=1)
        svg = _wrap_cover_title(svg)
        if t['cover'] == 'dark':                    # 어두운 사진 위 글자는 흰색 계열
            for old, new in ((_KEY['ink'], '#fffffe'), (_KEY['ink2'], '#e8eef4'), (_KEY['grey'], '#c6cfd9')):
                svg = svg.replace(old, new)
    elif t.get('decor') and kind in t.get('decor_on', ('body', 'agenda')):
        svg = re.sub(r'(<rect id="master-bg"[^>]*/>)', lambda m: m.group(1) + '\n  ' + t['decor'], svg, count=1)
    # 흰색은 자리마다 다르다: 바탕 · 카드 · (오렌지/남색 위) 글자
    svg = re.sub(r'(<rect id="master-bg"[^>]*fill=")#ffffff', lambda m: m.group(1) + p['bg'], svg)
    svg = re.sub(r'(<rect [^>]*fill=")#ffffff("[^>]*stroke=)', lambda m: m.group(1) + p['card'] + m.group(2), svg)
    if kind == 'body':
        svg = re.sub(r'(<text id="title-carrier"[^>]*fill=")#ee6d1d', lambda m: m.group(1) + '#TITLE#', svg)
    back = {v: p[k] for k, v in _KEY.items()}
    svg = re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: back.get(m.group(0).lower(), m.group(0)), svg)
    svg = svg.replace('#TITLE#', p['title']).replace('#fffffe', '#ffffff')
    fb = t.get('fb')
    if fb:
        svg = svg.replace(f'font-family="{_FB}"', f'font-family="{fb}"' + (' font-weight="bold"' if t.get('fb_bold') else ''))
    if t.get('fm'):
        svg = svg.replace(f'font-family="{_FM}"', f'font-family="{t["fm"]}"')
    return svg


# ══════════════════════════ 웹슬라이드 ══════════════════════════
_img_cache = {}


def _img(tid, name):
    k = f'{tid}_{name}'
    if k not in _img_cache:
        _img_cache[k] = _b64(os.path.join(ASSETS, 'img', k + '.webp'), 'image/webp')
    return _img_cache[k]


def _font(path):
    return _b64(path, 'font/woff2')


def _pretendard():
    d = os.path.join(ASSETS, 'fonts')
    return ''.join(f"@font-face{{font-family:Pretendard;font-weight:{w};font-display:swap;src:url({_font(os.path.join(d, f))}) format('woff2')}}\n"
                   for w, f in (('400 500', 'Pretendard-Regular.woff2'), ('600 700', 'Pretendard-SemiBold.woff2'), ('800 900', 'Pretendard-ExtraBold.woff2')))


def _photo_cover(uri, ov, pos='center'):
    return f'''
.slide.cover{{background:#0b1016 url({uri}) {pos}/cover no-repeat;color:#fff}}
.slide.cover::before{{content:"";position:absolute;inset:0;background:{ov}}}
.slide.cover .cover-chevs{{display:none}}
.slide.cover .sub{{color:#fff}}
.slide.cover .line{{color:rgba(255,255,255,.84)!important}}
.slide.cover .kick{{color:rgba(255,255,255,.72)}}
.slide.cover .tag{{background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.35);color:#fff}}
.slide.cover .tag.solid{{background:var(--or);border-color:var(--or)}}
.slide.cover .cta.ghost{{background:transparent;color:#fff;border-color:rgba(255,255,255,.55)}}
'''


def _dark_chrome(rgb):
    return (f'#stage[data-theme=navy] .topbar,#stage[data-theme=navy] .bottombar{{background:rgba({rgb},.62)}}\n'
            '.slide.navy .chevs svg:first-child polygon{fill:rgba(255,255,255,.07)}\n')


def _radius(r):
    return f'.card,.sum5 .sc,.illu,.cta,.side-link,.tag,.ev{{border-radius:{r}}}\n'


_TABLE = 'table.map th{border-bottom-color:var(--ink)}\n'


def _web_css(tid):
    if tid == 'a':
        return f''':root{{--canvas:#ffffff;--surface:#f4f6f9;--hair:#e3e7ed;--chev:#e9edf2;--or:#f06e1e;--or2:#d95f15;--ort:#f8cdb0;--orp:#fff0e6;
 --navy:#0e2340;--navy2:#19395f;--navy3:#0a1a31;--bt:#dfe8f2;--ink:#1b2a3d;--ink2:#6b7480;--grey:#8a93a0;--chart-navy:#19395f;--chart-grey:#cfd7e1}}
html,body{{background:#d7dde5}}
{_radius('7px')}.card{{background:#fff;box-shadow:0 1px 2px rgba(14,35,64,.05),0 8px 24px rgba(14,35,64,.07)}}
h2.t{{letter-spacing:-.03em;color:var(--navy)}}.kick .no{{background:var(--navy)}}.tag.solid{{background:var(--navy);border-color:var(--navy)}}
.topbar{{background:var(--navy)!important;color:#fff;border-color:transparent}}.topbar .brand small{{color:#9fb1c7}}.topbar .brand .div{{background:rgba(255,255,255,.25)}}
.topbar .pill,.topbar .iconbtn{{border-color:rgba(255,255,255,.28)}}
.slide.black{{background:var(--navy)}}
{_dark_chrome('14,35,64')}{_photo_cover(_img('a', 'hero'), 'linear-gradient(90deg,rgba(8,25,49,.97) 0%,rgba(14,35,64,.88) 46%,rgba(14,35,64,.38) 100%)', 'right center')}'''
    if tid == 'b':
        return f''':root{{--canvas:#ffffff;--surface:#f6f6f6;--hair:#d9dbdb;--chev:#e6e7e7;--or:#f06e1e;--or2:#d95e12;--ort:#f9cfb3;--orp:#fff1e8;
 --navy:#2e3333;--navy2:#5d6060;--navy3:#171b1b;--bt:#f1f2f2;--ink:#333333;--ink2:#5d6060;--grey:#8b8e8e;--chart-navy:#4a4f4f;--chart-grey:#d0d2d2}}
html,body{{background:#e3e4e4}}
{_radius('3px')}h2.t{{letter-spacing:-.045em;font-size:44px}}.cover h1{{letter-spacing:-.055em}}
.topbar::before{{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:var(--or)}}
.kick .no{{border-radius:2px;background:var(--ink)}}.card{{border-top:3px solid var(--ink)}}
.slide.black{{background:#171b1b}}
{_dark_chrome('46,51,51')}.slide.cover{{background:#efefef url({_img('b', 'hero')}) right -40px center/auto 96% no-repeat}}
.slide.cover::before{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#fff 0%,rgba(255,255,255,.97) 38%,rgba(255,255,255,0) 68%)}}
.slide.cover .cover-chevs{{display:none}}'''
    if tid == 'c':
        return f''':root{{--canvas:#0f1215;--surface:#1a2027;--hair:#2a323a;--chev:#1c232a;--or:#f06e1e;--or2:#ff8640;--ort:#7a3a12;--orp:#2a1a10;
 --navy:#8fb6d6;--navy2:#6f97b8;--navy3:#151a1f;--bt:#d7dde3;--ink:#e6e8ea;--ink2:#9aa3ab;--grey:#7d8791;--chart-navy:#6f97b8;--chart-grey:#3a444e}}
html,body{{background:#050607}}
{_radius('7px')}.topbar,.bottombar{{background:rgba(21,26,31,.94)!important;border-color:#232b33!important;color:var(--ink)}}
.brand small{{color:#7d8791}}.pill,.iconbtn,.navbtn,.kbd{{border-color:#39444d}}.pager .lab{{color:var(--ink)!important}}
.card{{background:#1a2027;border-color:#2a323a}}.card:hover{{background:#202831}}
.tag{{background:#151a1f;color:#b9c0c6;border-color:#2a323a}}.side-link,.cta.ghost{{background:transparent}}.cta.ghost{{color:#fff;border-color:#5a646e}}
.illu{{background:#fff}}.k-say{{background:#1a2027;color:#fff;border-color:#5a646e}}.slide.navy,.slide.black{{background:#151a1f}}
table.map th{{color:var(--ink2);border-color:#5a646e}}table.map td{{border-color:#2a323a}}
.side-page{{background:#12161a;color:var(--ink)}}.sp-head{{border-color:#5a646e}}.agenda.mini,.agenda .agrow{{border-color:#2a323a}}
{_dark_chrome('21,26,31')}{_photo_cover(_img('c', 'hero'), 'linear-gradient(90deg,rgba(10,13,16,.94) 0%,rgba(10,13,16,.78) 44%,rgba(10,13,16,.25) 100%)', 'right center')}'''
    if tid == 'd':
        return f'''@font-face{{font-family:KoPubBatang;font-weight:500;font-display:swap;src:url({_font(os.path.join(APP_FONTS, 'KoPubBatang-Medium.woff2'))}) format('woff2')}}
@font-face{{font-family:KoPubBatang;font-weight:700;font-display:swap;src:url({_font(os.path.join(APP_FONTS, 'KoPubBatang-Bold.woff2'))}) format('woff2')}}
:root{{--canvas:#fbfbfa;--surface:#f2f4f3;--hair:#c7cdcc;--chev:#e4e7e6;--or:#f06e1e;--or2:#d9560b;--ort:#f6cfb4;--orp:#fff1e8;
 --navy:#405a66;--navy2:#59717d;--navy3:#2c424c;--bt:#edf2f4;--ink:#23292b;--ink2:#5d6060;--grey:#858b8c;--chart-navy:#59717d;--chart-grey:#cfd5d4}}
html,body{{background:#dfe3e2;font-variant-numeric:tabular-nums}}
#stage{{background-color:var(--canvas);background-image:radial-gradient(circle at 1px 1px,rgba(35,41,43,.11) .6px,transparent .7px);background-size:7px 7px}}
{_radius('2px')}h1,h2,h3,h4,.kpi .v{{font-family:KoPubBatang,serif;letter-spacing:-.025em}}
.card{{background:#fff;outline:1px solid rgba(93,96,96,.24);outline-offset:-5px}}.kick .no{{border-radius:2px;background:var(--ink)}}
.slide.navy,.slide.black{{background:var(--navy3)}}
{_dark_chrome('44,66,76')}.slide.cover{{background:#f7f8f7 url({_img('d', 'hero')}) right center/auto 100% no-repeat}}
.slide.cover::before{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#fbfbfa 0%,rgba(251,251,250,.96) 40%,rgba(251,251,250,0) 70%)}}
.slide.cover .cover-chevs{{display:none}}'''
    if tid == 'e':
        return f'''{_pretendard()}:root{{--font:Pretendard,'Malgun Gothic',sans-serif;--canvas:#ffffff;--surface:#f6f7f7;--hair:#c9cdcd;--chev:#e7e9e9;--or:#f06e1e;--or2:#d95a0d;--ort:#f7ccb0;--orp:#fff2e8;
 --navy:#2f3535;--navy2:#5d6060;--navy3:#171b1b;--bt:#f0f2f2;--ink:#2f3535;--ink2:#5d6060;--grey:#8a8e8e;--chart-navy:#5d6060;--chart-grey:#d3d7d7}}
html,body{{background:#e4e6e6}}h1,h2{{font-weight:800}}
#stage{{background-color:var(--canvas);background-image:radial-gradient(circle at 1px 1px,#d9dddd 1px,transparent 1.2px);background-size:22px 22px}}
{_radius('6px')}h2.t em,.cover h1 em{{color:var(--ink);background:linear-gradient(transparent 60%,#ffd4b8 60%)}}
.card{{background:#fff;border:1.5px solid var(--ink)}}.kick .no{{background:#fff;color:var(--ink);border:1.5px solid var(--ink)}}
.slide.black{{background:#2f3535}}
{_dark_chrome('47,53,53')}.slide.cover{{background:#fff url({_img('e', 'hero')}) right 36px bottom 84px/620px auto no-repeat}}
.slide.cover .cover-chevs{{display:none}}'''
    if tid == 'f':
        return f'''h2.t{{color:var(--navy)}}.kick .no{{background:var(--navy)}}.slide.black{{background:var(--navy)}}
{_dark_chrome('0,51,141')}{_photo_cover(_img('f', 'hero'), 'linear-gradient(90deg,rgba(0,40,120,.92) 0%,rgba(0,40,120,.62) 44%,rgba(0,40,120,0) 82%)', 'right center')}'''
    if tid == 'g':
        return f'''{_pretendard()}:root{{--font:Pretendard,'Malgun Gothic',sans-serif;--canvas:#ffffff;--surface:#f5f7fa;--hair:#d5dbe2;--chev:#e5e9ee;--or:#f06e1e;--or2:#d9580d;--ort:#f8cdb0;--orp:#fff1e7;
 --navy:#13233a;--navy2:#126b8b;--navy3:#0c1828;--bt:#e9f5f9;--ink:#303b48;--ink2:#697482;--grey:#8a95a3;--cyan:#3fa7c9;--chart-navy:#3fa7c9;--chart-grey:#cdd5de}}
html,body{{background:#0c1828;font-variant-numeric:tabular-nums}}h1,h2,.kpi .v{{font-weight:800}}
{_radius('6px')}.topbar,.bottombar{{background:var(--navy)!important;color:#fff;border-color:transparent!important}}
.brand small{{color:#8fa3bb}}.brand .div{{background:rgba(255,255,255,.25)}}.pill,.iconbtn,.navbtn,.kbd{{border-color:rgba(255,255,255,.28)}}
.pager{{color:#8fa3bb}}.pager .lab{{color:#fff!important}}#prog{{background:var(--cyan)}}.kick .no{{background:var(--navy)}}
.slide.navy,.slide.black{{background:var(--navy) url({_img('g', 'banner')}) right bottom/cover no-repeat}}
.slide.navy::before,.slide.black::before{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(19,35,58,.97) 0%,rgba(19,35,58,.9) 58%,rgba(19,35,58,.55) 100%)}}
.slide.navy .chevs,.slide.black .wave{{display:none}}
{_dark_chrome('19,35,58')}{_photo_cover(_img('g', 'hero'), 'linear-gradient(90deg,rgba(19,35,58,.96) 0%,rgba(19,35,58,.76) 50%,rgba(19,35,58,.28) 100%)')}'''
    if tid == 'h':
        return f'''{_pretendard()}@font-face{{font-family:NanumMyeongjo;font-weight:700;font-display:swap;src:url({_font(os.path.join(APP_FONTS, 'NanumMyeongjo-Bold.woff2'))}) format('woff2')}}
:root{{--font:Pretendard,'Malgun Gothic',sans-serif;--canvas:#f4f4f1;--surface:#e9e9e6;--hair:#c9cac7;--chev:#d6d7d4;--or:#f06e1e;--or2:#d85b12;--ort:#f3c9ae;--orp:#fff3ec;
 --navy:#262a2b;--navy2:#5d6060;--navy3:#171a1b;--bt:#f1f1ef;--ink:#262a2b;--ink2:#5d6060;--grey:#8b8d8a;--chart-navy:#5d6060;--chart-grey:#c9cac7}}
html,body{{background:#cfd0cc}}h1,h2{{font-family:NanumMyeongjo,serif;font-weight:700;letter-spacing:-.03em}}
h2.t{{font-size:43px;padding-bottom:12px;border-bottom:1px solid var(--ink)}}
{_radius('2px')}.topbar,.bottombar{{background:rgba(244,244,241,.94)}}.kick{{letter-spacing:.32em}}
.kick .no{{background:transparent;color:var(--ink);border:1px solid var(--ink)}}.card{{background:#fff}}
.slide.black{{background:#262a2b}}
{_dark_chrome('38,42,43')}.slide.cover .cover-chevs{{display:none}}
.slide.cover::after{{content:"";position:absolute;right:0;top:64px;bottom:64px;width:41%;background:url({_img('h', 'hero')}) center/cover no-repeat}}'''
    return ''


_HEAD = '''<meta name="viewport" content="width=1440">
<script>
/* 스크립트가 도는 환경이면 발표 화면. 휴대폰 세로 화면이면 세로 읽기(kt-read). ?view=read|stage 로 고를 수 있다. */
(function () {
  var d = document.documentElement, mm = window.matchMedia ? function (q) { return matchMedia(q).matches; } : function () { return false; };
  d.className = d.className.replace('kt-nojs', 'kt-js');
  var q = /[?&]view=(read|stage)/.exec(location.search);
  var touch = mm('(hover:none) and (pointer:coarse)');
  var read = q ? q[1] === 'read' : (touch && mm('(orientation:portrait)'));
  if (read) d.className += ' kt-read';
  else { var m = document.querySelector('meta[name=viewport]'); if (m) m.setAttribute('content', 'width=device-width, initial-scale=1'); }
  if (touch && !q && window.matchMedia) {
    var mq = matchMedia('(orientation:portrait)'), f = function () { location.reload(); };
    if (mq.addEventListener) mq.addEventListener('change', f); else if (mq.addListener) mq.addListener(f);
  }
})();
</script>'''
_READ_CSS = '''
<style id="kt-read-css">
/* 세로 읽기(휴대폰 세로) · 스크립트가 꺼진 미리보기(아이폰 '파일' 앱 등): 장을 세로로 이어 보여 준다 */
html.kt-nojs,html.kt-read{height:auto}
html.kt-nojs body,html.kt-read body{height:auto;overflow:auto;-webkit-text-size-adjust:100%}
html.kt-nojs #stage,html.kt-read #stage{position:relative;width:1440px;height:auto;left:0!important;top:0!important;transform:none!important;overflow:visible;background:transparent;box-shadow:none;margin:0 auto}
html.kt-nojs .slide,html.kt-read .slide{position:relative;inset:auto;top:auto;left:auto;right:auto;bottom:auto;width:1440px;height:810px;visibility:visible;opacity:1;pointer-events:auto;overflow:hidden;margin:0 0 16px;padding-top:64px;padding-bottom:52px;padding-left:96px}
html.kt-nojs .slide:not(.navy):not(.black),html.kt-read .slide:not(.navy):not(.black){background-color:var(--canvas)}
html.kt-nojs .slide .a,html.kt-read .slide .a{opacity:1;animation:none}
html.kt-nojs .cover-chevs .cv-group,html.kt-nojs .cover-chevs .cv,html.kt-nojs .kosoe{animation:none;opacity:1;transform:none}
html.kt-nojs .topbar,html.kt-nojs .rail,html.kt-nojs .bottombar,html.kt-nojs #cursor,html.kt-nojs .side-scrim,html.kt-nojs .side-links,html.kt-nojs .cta,
html.kt-read .topbar,html.kt-read .rail,html.kt-read .bottombar,html.kt-read #cursor,html.kt-read .side-scrim,html.kt-read .side-links{display:none}
html.kt-nojs body::before,html.kt-read body::before{display:block;width:1440px;margin:0 auto;padding:22px 96px;font-size:30px;line-height:1.5;background:#2b2b2e;color:#fff}
html.kt-read body::before{content:"세로 읽기 화면입니다. 위아래로 넘겨 보세요. 휴대폰을 가로로 돌리면 발표 화면이 됩니다."}
html.kt-nojs body::before{content:"미리보기 화면입니다. 차트와 움직임은 보이지 않습니다. 인터넷 주소(링크)로 열면 발표 화면으로 보입니다."}
</style>
'''


def web_apply(s, tid):
    """웹슬라이드 index.html에 (1) 휴대폰·스크립트 꺼짐 대응 (2) 테마용 차트 색 (3) 테마 CSS를 넣는다.
    엔진 글자가 바뀌어 자리를 못 찾으면 그 부분만 건너뛴다(덱은 그대로 만들어진다)."""
    tid = norm(tid)

    def rep(old, new):
        nonlocal s
        if old in s:
            s = s.replace(old, new, 1)
            return True
        return False

    if 'kt-nojs' not in s:
        if rep('<html lang="ko">', '<html lang="ko" class="kt-nojs">') and rep('<meta name="viewport" content="width=device-width, initial-scale=1">', _HEAD):
            rep('</head>', _READ_CSS + '</head>')
            rep("(document.fonts ? document.fonts.ready : Promise.resolve()).then(() => {",
                "const KT_READ = document.documentElement.classList.contains('kt-read');\n"
                "  Promise.race([document.fonts ? document.fonts.ready : Promise.resolve(), new Promise(r => setTimeout(r, 1500))]).then(() => {")
            rep("    go(start);\n    updateBar();",
                "    go(start);\n    if (typeof KT_READ !== 'undefined' && KT_READ) slides.forEach(sl => { sl.querySelectorAll('canvas').forEach(cv => make(cv.id)); });\n    updateBar();")
            rep("    const sl = slides[i];\n    sl.classList.add('active');",
                "    const sl = slides[i];\n    sl.classList.add('active');\n"
                "    if (cur >= 0 && document.documentElement.classList.contains('kt-read')) sl.scrollIntoView({behavior: 'smooth', block: 'start'});")
        m = re.search(r"  const C = \{or:'#ee6d1d'[^\n]*\};\n", s)
        if m:
            s = s[:m.start()] + (
                "  const cssv = (n, d) => { const v = (getComputedStyle(document.documentElement).getPropertyValue(n) || '').trim(); return /^#[0-9a-f]{6}$/i.test(v) ? v : d; };\n"
                "  const C = {or: cssv('--or', '#ee6d1d'), or2: cssv('--or2', '#f26522'), ort: cssv('--ort', '#fad3bb'), orp: cssv('--orp', '#fdeee4'), navy: cssv('--navy', '#00338d'), navy2: cssv('--chart-navy', cssv('--navy2', '#1f4b9b')),\n"
                "    hair: cssv('--chart-grey', cssv('--hair', '#dcdce0')), surf: cssv('--surface', '#f5f5f7'), ink: cssv('--ink', '#2b2b2e'), ink2: cssv('--ink2', '#6e6e73'), grey: cssv('--grey', '#8c8c92')};\n"
            ) + s[m.end():]
            rep("  const FONT = \"'KoPub Dotum','KoPub돋움체 Medium','Malgun Gothic',sans-serif\";",
                "  const FONT = (getComputedStyle(document.documentElement).getPropertyValue('--font') || '').trim() || \"'KoPub Dotum','KoPub돋움체 Medium','Malgun Gothic',sans-serif\";")
    css = _web_css(tid)
    if css:
        rep('</head>', f'<style id="kt-theme">/* 문서 테마 {tid} · {NAMES[tid]} */\n{css}\n</style>\n</head>')
        if tid in ('a', 'c', 'f', 'g'):             # 어두운 표지: 상단·하단 띠도 어둡게
            s = re.sub(r'(<section class="slide cover"[^>]*?)>', lambda m: m.group(1) + (' data-theme="navy">' if 'data-theme' not in m.group(1) else '>'), s, count=1)
    return s
