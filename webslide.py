"""웹 어댑터 — 전사 스킬 koscom-webslide로 설계도를 움직이는 단일 HTML 웹슬라이드로 만든다.

1) new_deck.py로 원고 원본을 복사(기본 kosoe: 표지·요약·맺음만 / 양식 preset web:<id>의 motion·scrolline·three: 표지·맺음만, 부록·요약 모션 제외)
2) 표지·목차·본문·맺음을 설계도로 다시 쓰고, 표의 숫자는 deck-data charts(kind: vbar)로
3) build_single.py --referenced-only 로 서체·그림·Chart.js까지 넣은 단일 파일
엔진(CSS·JS·편집 모드·차트·자동 배율)은 전사 스킬 것을 그대로 쓴다.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys

import corp
from core import today_kr

E = html.escape
WS = 'koscom-webslide'
TEMPLATES = ('kosoe', 'motion', 'scrolline', 'three')      # 원고 원본 — 양식 preset "web:<id>"로 고른다
SEC = re.compile(r'\n(?:  <!-- [^\n]*-->\n)?  <section class="slide[\s"].*?</section>\n', re.S)   # 스킬 new_deck.SEC 와 같은 장 자르기
NOTES = re.compile(r'\s*<aside class="notes">.*?</aside>', re.S)


def template_id(preset):
    t = preset[4:] if (preset or '').startswith('web:') else ''
    return t if t in TEMPLATES else 'kosoe'


def _num(s):
    m = re.fullmatch(r'\s*([-+]?[\d,]*\.?\d+)\s*(%|건|명|억|억원|만원|원|개|점|천만원|시간|분)?\s*', str(s))
    return float(m.group(1).replace(',', '')) if m else None


def _em_last(t):
    w = t.rsplit(' ', 1)
    return E(t) if len(w) < 2 else f'{E(w[0])} <em>{E(w[1])}</em>'


def _items_html(items):
    out = []
    for it in items:
        ch = ''.join(f'<br><small style="color:var(--ink2)">– {E(c["text"])}</small>' for c in it.get('children') or [])
        if it.get('label'):
            out.append(f'<div class="fact" style="grid-template-columns:120px 1fr"><b>{E(it["label"])}</b><span>{E(it["text"])}{ch}</span></div>')
        else:
            out.append(f'<div class="fact" style="grid-template-columns:22px 1fr"><b style="color:var(--or)">›</b><span>{E(it["text"])}{ch}</span></div>')
    return ''.join(out)


def _cards_html(items):
    cards = []
    for i, it in enumerate(items, 1):
        ch = ''.join(f'<p style="margin-top:8px;color:var(--ink2);font-size:15px">– {E(c["text"])}</p>' for c in it.get('children') or [])
        h4 = f'<h4 style="font-size:22px;margin:8px 0 10px">{E(it["label"])}</h4>' if it.get('label') else '<div style="height:10px"></div>'
        cards.append(f'<div class="card tilt" data-tilt><div style="color:var(--or);font-weight:700;font-size:15px">{i:02d}</div>'
                     f'{h4}<p style="font-size:17px;line-height:1.55">{E(it["text"])}</p>{ch}</div>')
    return f'<div style="display:grid;grid-template-columns:repeat({len(items)},1fr);gap:24px;margin-top:34px">{"".join(cards)}</div>'


def _table_html(tb):
    cols, rws = tb['cols'], tb['rows'][:10]
    head = ''.join(f'<th>{E(str(c))}</th>' for c in cols)
    body = ''.join('<tr>' + ''.join(f'<td style="{"text-align:right" if j and _num(r[j] if j < len(r) else "") is not None else ""}">'
                                    f'{E(str(r[j]) if j < len(r) else "")}</td>' for j in range(len(cols))) + '</tr>' for r in rws)
    return f'<table class="map ftab"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _chart(tb, cid):
    cols, rws = tb['cols'], tb['rows'][:10]
    numeric = [j for j in range(1, len(cols)) if rws and all(_num(r[j]) is not None for r in rws if j < len(r))]
    if not numeric or len(rws) < 2:
        return None
    j = numeric[0]
    vals = [_num(r[j]) or 0 for r in rws]
    mx = max(vals)
    return {'title': f'{cols[j]}', 'kind': 'vbar', 'cols': [str(cols[0]), str(cols[j]), '색'], 'types': ['t', 'n', 'c'],
            'rows': [[str(r[0]), v, '오렌지' if v == mx else '회색'] for r, v in zip(rws, vals)]}


def _section(i, sec, form, charts):
    items = list(sec.get('items') or [])
    tb = sec.get('table') if sec.get('table') and sec['table'].get('cols') and sec['table'].get('rows') else None
    lead = ''
    if items and (tb or len(items) > 3) and len(items[0]['text']) <= 70 and not items[0].get('children'):
        it = items.pop(0)
        lead = f'<p class="lead a">{"<b>" + E(it["label"]) + "</b> " if it.get("label") else ""}{E(it["text"])}</p>'
    if tb:
        cid = f'kc{i}'
        ch = _chart(tb, cid)
        right = _table_html(tb) + (f'<div class="chart-box" style="height:230px;margin-top:22px"><canvas id="{cid}"></canvas></div>' if ch else '')
        if ch:
            charts[cid] = ch
        body = (f'<div class="a" style="display:grid;grid-template-columns:1fr 1.15fr;gap:44px;margin-top:26px;align-items:start">'
                f'<div>{_items_html(items)}</div><div>{right}</div></div>') if items else f'<div class="a" style="margin-top:26px">{right}</div>'
    elif 2 <= len(items) <= 3 and all(len(x['text']) <= 90 for x in items):
        body = f'<div class="a">{_cards_html(items)}</div>'
    else:
        body = f'<div class="a" style="margin-top:22px;max-width:1080px">{_items_html(items)}</div>'
    return (f'\n  <section class="slide" data-sec="{i}" data-label="{E(sec["heading"])}">\n'
            f'    <div class="kick a"><span class="no">{i + 2:02d}</span>{E(form)}</div>\n'
            f'    <h2 class="t a">{E(sec["heading"])}</h2>\n    {lead}\n    {body}\n  </section>\n')


def _agenda(secs):
    rows = ''.join(f'<div class="agrow" role="button" tabindex="0" data-go="{i + 2}"><span class="n">{i + 1:02d}</span>'
                   f'<span class="h">{E(s["heading"])}</span><span class="d">{E(" · ".join(x.get("label") for x in s["items"] if x.get("label"))[:60])}</span>'
                   f'<span class="p">{i + 3:02d}</span><span class="ar">→</span></div>' for i, s in enumerate(secs))
    return (f'\n  <section class="slide" data-sec="0" data-label="목차">\n    <div class="kick a"><span class="no">02</span>CONTENTS</div>\n'
            f'    <h2 class="t a">목차</h2>\n    <div class="agenda mini a" style="margin-top:40px">{rows}</div>\n  </section>\n')


def _other(s, bp, template, people, chips, body):
    """kosoe 밖의 원고(motion · scrolline · three): 표지 다음에 목차·본문을 넣고, 표지·맺음의 글을 이 문서로 바꾼다.
    원고의 표본 장식(표본 낱말·숫자가 든 흐르는 글줄·연도 레일·효과 상자·52% 링)은 이 문서 값으로 바꾸거나 뺀다."""
    form, title, dept = template['name'], bp['title'], people.get('dept', '')
    who = f'{dept} · {people.get("담당", "")}'
    heads = [x['heading'] for x in bp['sections']]
    secs = list(SEC.finditer(s))
    cover, close = secs[0].group(0), secs[-1].group(0)
    one = lambda pat, rep, x: re.sub(pat, rep, x, count=1, flags=re.S)  # noqa: E731
    # 표지: 공통(h1 · kick · sub · line) → motion(fo · 흐르는 글줄 ks r1·r2·r3) → scrolline(연도 레일)
    cover = one(r'(<h1\b[^>]*>).*?(</h1>)', lambda m: m.group(1) + _em_last(title) + m.group(2), cover)
    cover = one(r'(<div class="kick[^"]*">\s*<span class="bar"></span>).*?(</div>)', lambda m: m.group(1) + E(form) + m.group(2), cover)
    cover = one(r'(<p class="(?:sub|sl-sub)\b[^"]*">).*?(</p>)', lambda m: m.group(1) + E(template.get('desc', '')) + m.group(2), cover)
    cover = one(r'(<p class="line\b[^"]*">).*?(</p>)', lambda m: m.group(1) + E(f'{who} · {today_kr()}') + m.group(2), cover)
    cover = one(r'(<div class="fo"><b>).*?(</b>).*?(</div>)', lambda m: m.group(1) + E(form) + m.group(2) + E(f'{dept} · {today_kr()}') + m.group(3), cover)
    words = title.split()
    key = (f'<span class="kl">{E(" · ".join(words[:-1]))} ·&nbsp;</span>' if len(words) > 1 else '') + f'<em>{E(words[-1])}</em><span class="kr">&nbsp;· {E(form)}</span>'
    cover = one(r'(<div class="ks r1"[^>]*>).*?(</div>)', lambda m: m.group(1) + E(' · '.join(heads * 2)) + m.group(2), cover)
    cover = one(r'(<div class="ks r2"[^>]*>).*?(</div>)', lambda m: m.group(1) + key + m.group(2), cover)
    cover = one(r'(<div class="ks r3"[^>]*>).*?(</div>)', lambda m: m.group(1) + E(' · '.join([form, dept, today_kr()] * 2)) + m.group(2), cover)
    lis = ''.join(('<li class="on">' if i == 0 else '<li>') + f'<b>{i + 1:02d}</b><span>{E(h)}</span></li>' for i, h in enumerate(heads[:4]))
    cover = one(r'(<ol class="sl-years">).*?(</ol>)', lambda m: m.group(1) + lis + m.group(2), cover)
    # 맺음: h2 = 제목, 첫 lead·line = 작성 부서·담당, kick = CLOSING, 칩 = 스킬 사슬 / 표본 효과 상자·52% 링은 뺀다
    n = 1 + (1 if len(heads) >= 3 else 0) + len(heads) + 1
    close = one(r'(<h2\b[^>]*>).*?(</h2>)', lambda m: m.group(1) + _em_last(title) + m.group(2), close)
    close = one(r'(<p class="(?:lead|line)\b[^"]*"[^>]*>).*?(</p>)', lambda m: m.group(1) + E(who) + m.group(2), close)
    close = one(r'(<div class="kick[^"]*">\s*<span class="bar"></span>).*?(</div>)', lambda m: m.group(1) + 'CLOSING' + m.group(2), close)
    close = one(r'(<div class="fo"><b>)\d+(</b>)', lambda m: m.group(1) + f'{n:02d}' + m.group(2), close)
    close = one(r'(<div class="chip-row a"[^>]*>).*?(</div>)', lambda m: m.group(1) + chips + m.group(2), close)
    close = one(r'\n\s*<div class="sl-effects">.*?(?=\n\s*<p class="sl-thanks">)', '', close)
    close = one(r'\n\s*<div class="cl-ring"[^>]*>.*?<div class="mm-label">.*?</div>\s*</div>', '', close)
    return s[:secs[0].start()] + NOTES.sub('', cover) + body + NOTES.sub('', close) + s[secs[-1].end():]


def make(bp, template, people, path, job_dir, chain=None):
    root = corp.path(WS)
    tid = template_id(template.get('preset'))
    deck = os.path.join(job_dir, 'web')
    if os.path.isdir(deck):
        shutil.rmtree(deck, ignore_errors=True)
    if tid == 'kosoe':
        keep, drop = '1,2,23', 'basis,sources,qa,gallery,video,live'
    else:   # 표지(1장)와 맺음(마지막 장)만 남긴다
        n = len(SEC.findall(open(os.path.join(root, 'templates', tid, 'index.html'), encoding='utf-8').read()))
        keep, drop = f'1,{n}', 'basis,sources'
    r = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'new_deck.py'), deck, '--template', tid, '--title', bp['title'],
                        '--keep', keep, '--drop-side', drop, '--no-motion'], capture_output=True, timeout=120,
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if r.returncode != 0:
        raise RuntimeError('웹 템플릿 복사 실패: ' + r.stderr.decode('utf-8', 'replace')[-300:])
    ip = os.path.join(deck, 'index.html')
    s = open(ip, encoding='utf-8').read()
    form = template['name']
    secs = bp['sections']
    charts = {}

    # 상단 바 · 문서 정보
    s = re.sub(r'<title>.*?</title>', f'<title>{E(bp["title"])}</title>', s, count=1, flags=re.S)
    s = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + E(f'{form} · {people.get("dept", "")}'), s, count=1)
    s = re.sub(r'(<div class="brand">\s*<svg.*?</svg>)\s*.*?(</div>)', lambda m: m.group(1) + f'\n      KOSCOM<span class="div"></span><small>{E(form)}</small>\n    ' + m.group(2), s, count=1, flags=re.S)
    s = re.sub(r'<span class="pill">.*?</span>\s*(?=<button)', f'<span class="pill"><i>웹</i>{E(people.get("dept", ""))} · {today_kr()}</span>\n      ', s, count=1, flags=re.S)

    chips = ''.join(f'<span class="tag solid">{E(c)}</span>' for c in (chain or [])[:4])
    body = (_agenda(secs) if len(secs) >= 3 else '') + ''.join(_section(i, sec, form, charts) for i, sec in enumerate(secs, 1))
    if tid == 'three':      # 3D 무대 원고: 본문 장은 원고의 글 위주 장처럼 멀리서 본 무대(overview)·남색 테마 — 입체가 글을 가리지 않게.
        #                     목차는 원고처럼 세로 목록(폭 780px 제한이라 가로 축약형은 넘친다), 밝은 카드의 제목은 잉크색(남색 장의 흰 글자 대신)
        body = (body.replace('<section class="slide" ', '<section class="slide navy" data-theme="navy" data-scene="overview" ')
                .replace('class="agenda mini a"', 'class="agenda a"')
                .replace('<h4 style="font-size:22px;margin:8px 0 10px">', '<h4 style="font-size:22px;margin:8px 0 10px;color:var(--ink)">'))
    if tid != 'kosoe':
        s = _other(s, bp, template, people, chips, body)
    else:
        s = _kosoe(s, bp, template, people, chips, body)

    # deck-data
    def dd(m):
        data = json.loads(m.group(2))
        data['charts'] = charts
        return m.group(1) + json.dumps(data, ensure_ascii=False) + m.group(3)
    s = re.sub(r'(<script type="application/json" id="deck-data">)(.*?)(</script>)', dd, s, count=1, flags=re.S)
    open(ip, 'w', encoding='utf-8').write(s)

    r = subprocess.run([sys.executable, os.path.join(root, 'scripts', 'build_single.py'), deck, path, '--referenced-only'],
                       capture_output=True, timeout=300, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError('웹 단일 파일 만들기 실패: ' + (r.stdout + r.stderr).decode('utf-8', 'replace')[-300:])
    return len(secs) + (3 if len(secs) >= 3 else 2)


def _kosoe(s, bp, template, people, chips, body):
    """kosoe 원고: 표지·한 장 요약·맺음만 남긴 덱에서 표지와 맺음을 다시 쓰고, 한 장 요약 자리에 목차·본문을 넣는다."""
    form = template['name']
    # 표지
    cover = (f'<div style="position:relative;display:flex;flex-direction:column;justify-content:center;height:100%;max-width:640px">\n'
             f'      <div class="kick a"><span class="bar"></span>{E(form)}</div>\n'
             f'      <h1 class="a" style="font-size:{60 if len(bp["title"]) <= 14 else 46}px;line-height:1.2">{_em_last(bp["title"])}</h1>\n'
             f'      <p class="sub a">{E(template.get("desc", ""))}</p>\n'
             f'      <p class="line a">{E(people.get("dept", ""))} · {E(people.get("담당", ""))} · {today_kr()}</p>\n'
             f'      <div class="chip-row a" style="margin-top:26px">{chips}</div>\n'
             f'      <div class="a"><button class="cta" data-go="1">펼쳐 보기 <span>↗</span></button></div>\n    </div>\n  </section>')
    s = re.sub(r'<div style="position:relative;display:flex;flex-direction:column;justify-content:center;height:100%;max-width:640px">.*?</section>',
               lambda m: cover, s, count=1, flags=re.S)
    s = re.sub(r'<div class="k-say">.*?</div>', '<div class="k-say">회사 양식대로<br>만들었어요</div>', s, count=1, flags=re.S)

    # 요약 장 → 목차 + 본문
    s = re.sub(r'<!-- 02 ONE-PAGE SUMMARY.*?</section>', lambda m: body, s, count=1, flags=re.S)

    # 맺음
    s = re.sub(r'(<section class="slide black"[^>]*>.*?<h2 class="a"[^>]*>).*?(</h2>)', lambda m: m.group(1) + f'{E(bp["title"])}' + m.group(2), s, count=1, flags=re.S)
    s = re.sub(r'(<section class="slide black".*?<p class="lead a"[^>]*>).*?(</p>)', lambda m: m.group(1) + E(f'{people.get("dept", "")} · {people.get("담당", "")}') + m.group(2), s, count=1, flags=re.S)
    s = re.sub(r'(<section class="slide black".*?<div class="chip-row a"[^>]*>).*?(</div>)', lambda m: m.group(1) + chips + m.group(2), s, count=1, flags=re.S)
    # 남긴 원본 장(표지·맺음)의 표본 대본은 뺀다 — 발표자 보기(S)에 원고 표본 대사가 나오지 않게
    secs = list(SEC.finditer(s))
    for m in reversed([secs[0], secs[-1]]):
        s = s[:m.start()] + NOTES.sub('', m.group(0)) + s[m.end():]
    return s
