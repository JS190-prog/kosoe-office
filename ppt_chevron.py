"""PPT 어댑터 — 전사 스킬 ppt-master의 덱(기본 koscom-chevron)으로 설계도를 편집 가능한 PPTX로 만든다.

1) 표지·목차·맺음: 덱 템플릿 SVG의 {{빈칸}}을 채운다.
2) 본문: 같은 덱의 06_card_grid 머리말·꼬리말 위에 항목·카드·표·막대그래프를 그 덱의 색·서체·자리로 그린다
   (카드 자리·글 영역은 06_card_grid 에서, 강조색은 design_spec.md 의 primary_color 에서 읽는다).
3) ppt-master `svg_to_pptx.py`로 네이티브 DrawingML PPTX로 변환한다(도형·글자 단위 편집 가능).
"""
import html
import os
import re
import subprocess
import sys

import corp
from core import ROOT, today_kr

# 같은 장 구성(01_cover · 02_agenda · 06_card_grid · 10_closing, 같은 {{빈칸}})인 덱만 쓴다. 양식 preset "deck:<이름>"으로 고른다.
DECKS = ('koscom-chevron', 'gradient-mesh', 'midnight-panel', 'open-road', 'polarity', 'signal-green', 'warm-doc')
DECK_DIR = '.claude/skills/ppt-master/templates/decks/{}/templates'
GUIDE = re.compile(r'\s*<g id="[\w-]*guide">.*?</g>', re.S)     # 템플릿 작성용 안내(open-road 표지 photo-guide 「replace this plate with an image」) — 슬라이드에서 뺀다
FB = "'KoPub돋움체 Bold', 'KoPubDotum Bold', Pretendard, 'Malgun Gothic', sans-serif"
FM = "'KoPub돋움체 Medium', 'KoPubDotum Medium', Pretendard, 'Malgun Gothic', sans-serif"
ORANGE, INK, INK2, LINE = '#ee6d1d', '#2b2b2e', '#6e6e73', '#dcdce0'
BRAND = 'koscom'
E = html.escape


def deck_name(preset):
    n = preset[5:] if (preset or '').startswith('deck:') else ''
    return n if n in DECKS else 'koscom-chevron'


def _w(ch, fs):
    o = ord(ch)
    if ch == ' ':
        return fs * 0.3
    if 0xAC00 <= o <= 0xD7A3 or 0x3130 <= o <= 0x318F or 0x4E00 <= o <= 0x9FFF or 0xFF00 <= o <= 0xFFEF:
        return fs * 0.98
    if ch in 'il.,:;|!\'"·()[]':
        return fs * 0.3
    return fs * 0.56


def wrap(text, width, fs, max_lines=99):
    """단어 단위 줄바꿈(한국어 keep-all). 넘치면 마지막 줄을 …으로."""
    words = str(text).split(' ')
    lines, cur, cw = [], '', 0
    for w in words:
        ww = sum(_w(c, fs) for c in w)
        add = ww + (_w(' ', fs) if cur else 0)
        if cur and cw + add > width:
            lines.append(cur)
            cur, cw = w, ww
        else:
            cur, cw = (cur + ' ' + w) if cur else w, cw + add
        while cw > width and len(cur) > 1:          # 한 단어가 폭보다 길면 글자 단위로
            cut = ''
            acc = 0
            for c in cur:
                if acc + _w(c, fs) > width:
                    break
                cut += c
                acc += _w(c, fs)
            lines.append(cut)
            cur = cur[len(cut):]
            cw = sum(_w(c, fs) for c in cur)
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()[:-1] + '…'
    return lines or ['']          # 빈 글(표의 빈 칸 등)도 빈 줄 하나 — 첫 줄([0])을 쓰는 곳이 넘어지지 않게


def fill(svg, vals):
    return re.sub(r'\{\{([A-Z_0-9]+)\}\}', lambda m: E(str(vals.get(m.group(1), ''))), svg)


def num(s):
    m = re.fullmatch(r'\s*([-+]?[\d,]*\.?\d+)\s*(%|건|명|억|억원|만원|원|개|점|천만원|시간|분)?\s*', str(s))
    return float(m.group(1).replace(',', '')) if m else None


def _attrs(tag):
    return dict(re.findall(r'([\w:-]+)="([^"]*)"', tag))


def _n(v):
    """SVG 좌표: 정수면 정수로(셰브론 결과를 바꾸지 않게)."""
    v = float(v)
    return int(v) if v.is_integer() else v


def _mix(a, b, t):
    """색 a를 색 b 쪽으로 t만큼 섞는다(#rrggbb)."""
    ca, cb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * t):02x}' for x, y in zip(ca, cb))


class Theme:
    """덱 하나의 본문 그리기 값 — 06_card_grid.svg 의 카드·글 자리·색·서체와 design_spec.md 의 primary_color."""

    def __init__(self, card_svg, spec_md=''):
        def tag(ph):
            m = re.search(r'<text\b[^>]*>\{\{' + ph + r'\}\}</text>', card_svg)
            return _attrs(m.group(0)) if m else {}
        t1, b1 = tag('CARD_1_TITLE'), tag('CARD_1_BODY')
        self.ink, self.ink2 = t1.get('fill', INK).lower(), b1.get('fill', INK2).lower()
        self.fb, self.fm = t1.get('font-family', FB), b1.get('font-family', FM)
        self.cards = []
        for n, g in re.findall(r'<g id="card-(\d+)">(.*?)</g>', card_svg, re.S):
            r = _attrs(re.search(r'<rect\b[^>]*>', g).group(0))
            tt, bt = tag(f'CARD_{n}_TITLE'), tag(f'CARD_{n}_BODY')
            self.cards.append({k: _n(v) for k, v in (('x', r['x']), ('y', r['y']), ('w', r['width']), ('h', r['height']),
                                                    ('tx', tt['x']), ('tfs', tt['font-size']),
                                                    ('bx', bt['x']), ('by', bt['y']), ('bfs', bt['font-size']))})
            if n == '1':
                self.line = r.get('stroke', LINE).lower()
        c0, cn = self.cards[0], self.cards[-1]
        self.left, self.right = c0['x'], _n(cn['x'] + cn['w'])
        self.top, self.bottom = c0['y'], _n(float(tag('BRAND_MARK').get('y', 674)) - 34)
        m = re.search(r'primary_color:\s*"?(#[0-9A-Fa-f]{6})', spec_md or '')
        self.accent = m.group(1).lower() if m else ORANGE
        bg = re.findall(r'<rect\b[^>]*\bwidth="1280" height="720"[^>]*\bfill="(#[0-9A-Fa-f]{6})"', card_svg)
        self.tint = _mix(self.accent, (bg[-1] if bg else '#ffffff').lower(), .7)     # 표 머리행: 강조색을 배경 쪽으로 70%


class Deck:
    def __init__(self, name='koscom-chevron'):
        self.name, self.base, self.tpl = name, DECK_DIR.format(name), {}
        try:
            spec = corp.read_text('koscom-doc-pack', f'{self.base}/design_spec.md')
        except Exception:
            spec = ''
        self.th = Theme(self.t('06_card_grid.svg'), spec)

    def t(self, name):
        if name not in self.tpl:
            self.tpl[name] = GUIDE.sub('', corp.read_text('koscom-doc-pack', f'{self.base}/{name}'))
        return self.tpl[name]

    def text(self, x, y, s, fs=16, fill=None, bold=False, anchor='start'):
        return (f'<text x="{x:.0f}" y="{y:.0f}" font-family="{self.th.fb if bold else self.th.fm}" font-size="{fs}" fill="{fill or self.th.ink}"'
                + (f' text-anchor="{anchor}"' if anchor != 'start' else '') + f'>{E(str(s))}</text>')

    def lines(self, x, y, lines, fs, fill=None, bold=False, lh=1.45):
        return ''.join(self.text(x, y + i * fs * lh, l, fs, fill, bold) for i, l in enumerate(lines)), y + len(lines) * fs * lh

    # ── 앵커 페이지 ──
    def cover(self, bp, form, people):
        title = bp['title']
        return fill(self.t('01_cover.svg'), {'BRAND_MARK': BRAND, 'KICKER': form, 'TITLE': title if len(title) <= 22 else title[:21] + '…',
                                              'SUBTITLE': people.get('subtitle', ''), 'META_LINE': f"{today_kr()} | {people.get('dept', '')} {people.get('담당', '')}".strip(),
                                              'CTA_LABEL': people.get('dept', ''), 'PAGE_LABEL': '01'})

    def agenda(self, secs, page):
        svg = self.t('02_agenda.svg')
        vals = {'BRAND_MARK': BRAND, 'KICKER': 'CONTENTS', 'TITLE': '목 차', 'SUBTITLE': 'Table of Contents', 'PAGE_LABEL': f'{page:02d}'}
        for i in range(1, 6):
            if i <= len(secs):
                s = secs[i - 1]
                tag = ' · '.join(it.get('label') for it in s['items'] if it.get('label'))[:40]
                vals.update({f'ITEM_{i}_NO': f'{i:02d}', f'ITEM_{i}_TITLE': s['heading'], f'ITEM_{i}_TAG': tag})
            else:
                svg = re.sub(rf'<g id="agenda-item-{i}">.*?</g>', '', svg, flags=re.S)
        return fill(svg, vals)

    def section(self, no, title, lead, page):
        return fill(self.t('03_section.svg'), {'BRAND_MARK': BRAND, 'SECTION_NO': f'{no:02d}', 'KICKER': 'CHAPTER', 'TITLE': title,
                                                'LEAD': lead, 'PAGE_LABEL': f'{page:02d}'})

    def closing(self, line, contact, page):
        return fill(self.t('10_closing.svg'), {'BRAND_MARK': BRAND, 'CLOSING_LINE': line, 'CONTACT_LINE': contact, 'PAGE_LABEL': f'{page:02d}'})

    # ── 본문 페이지 ──
    def body(self, no, sec, form, page):
        th = self.th
        items = sec.get('items') or []
        tb = sec.get('table') if sec.get('table') and sec['table'].get('cols') and sec['table'].get('rows') else None
        base = self.t('06_card_grid.svg')
        head = {'BRAND_MARK': BRAND, 'KICKER': f'{no:02d}. {form}', 'TITLE': sec['heading'], 'PAGE_LABEL': f'{page:02d}'}
        cardable = (not tb and 2 <= len(items) <= len(th.cards) and all(len(it['text']) <= 80 for it in items))
        if cardable:
            head['LEAD'] = ''
            svg = base
            for i, c in enumerate(th.cards, 1):
                if i > len(items):
                    svg = re.sub(rf'<g id="card-{i}">.*?</g>', '', svg, flags=re.S)
                    continue
                it = items[i - 1]
                head[f'CARD_{i}_TITLE'] = it.get('label') or wrap(it['text'], c['w'] - (c['tx'] - c['x']) - 16, c['tfs'], 1)[0]
                head[f'CARD_{i}_BODY'] = '__BODY%d__' % i
            svg = fill(svg, head)
            for i, it in enumerate(items, 1):
                c = th.cards[i - 1]
                x, fs, bw = c['bx'], c['bfs'], c['w'] - 2 * (c['bx'] - c['x'])
                if it.get('label'):
                    body = it['text']
                else:
                    first = wrap(it['text'], c['w'] - (c['tx'] - c['x']) - 16, c['tfs'], 1)[0]
                    body = it['text'][len(first):].strip()
                ml = max(2, int((c['y'] + c['h'] - c['by'] - 20) / (fs * 1.45)))
                parts, y = self.lines(x, c['by'], wrap(body, bw, fs, ml), fs, th.ink2) if body else ('', c['by'] - fs)
                for ch in (it.get('children') or [])[:2]:
                    cl, y = self.lines(x, y + 8, wrap('– ' + ch['text'], bw, fs - 2, 3), fs - 2, th.ink2)
                    parts += cl
                svg = re.sub(rf'<text[^>]*>__BODY{i}__</text>', lambda m: parts, svg)
            return svg
        # 일반 본문: 카드 묶음을 지우고 직접 그린다
        svg = re.sub(r'<g id="card-\d">.*?</g>\s*', '', base, flags=re.S)
        lead_item = None
        if items and (tb or len(items) > 3) and len(items[0]['text']) <= 70 and not items[0].get('children'):
            lead_item, items = items[0], items[1:]
        head['LEAD'] = (lead_item['label'] + ' ' if lead_item and lead_item.get('label') else '') + (lead_item['text'] if lead_item else '')
        svg = fill(svg, head)
        parts = []
        L, W, top, bottom = th.left, th.right - th.left, th.top, th.bottom
        if tb:
            bw = int(W * .42)
            bx, bw = (L, bw) if items else (None, 0)
            tx, tw = (L + bw + 40, W - bw - 40) if items else (L, W)
            if items:
                parts.append(self.bullets(items, bx, top, bw, bottom, 17))
            y = self.table(parts, tb, tx, top, tw)
            self.bars(parts, tb, tx, y + 24, tw, bottom)
        else:
            if len(items) > 5:
                half = (len(items) + 1) // 2
                parts.append(self.bullets(items[:half], L, top, W // 2 - 20, bottom, 17))
                parts.append(self.bullets(items[half:], L + W // 2 + 20, top, W // 2 - 20, bottom, 17))
            else:
                parts.append(self.bullets(items, L, top, W, bottom, 19))
        return svg.replace('</svg>', '\n'.join(parts) + '\n</svg>')

    def bullets(self, items, x, y, w, bottom, fs):
        th = self.th
        out = []
        for it in items:
            if y > bottom - fs:
                break
            out.append(f'<rect x="{x}" y="{y - fs * 0.62:.0f}" width="8" height="8" fill="{th.accent}"/>')
            tx = x + 22
            if it.get('label'):
                out.append(self.text(tx, y, it['label'], fs, th.ink, True))
                lw = sum(_w(c, fs) for c in it['label']) + fs * 0.8
                first = wrap(it['text'], w - 22 - lw, fs)[0]
                out.append(self.text(tx + lw, y, first, fs, th.ink))
                rest = it['text'][len(first):].strip()
                ls = wrap(rest, w - 22, fs, 3) if rest else []
                s, y = self.lines(tx, y + fs * 1.45, ls, fs, th.ink)
                out.append(s)
            else:
                s, y = self.lines(tx, y, wrap(it['text'], w - 22, fs, 4), fs, th.ink)
                out.append(s)
            for c in (it.get('children') or [])[:3]:
                s, y = self.lines(tx + 6, y + 2, wrap('– ' + c['text'], w - 28, fs - 3, 2), fs - 3, th.ink2)
                out.append(s)
            y += fs * 0.9
        return ''.join(out)

    def table(self, parts, tb, x, y, w):
        th = self.th
        cols, rws = [str(c) for c in tb['cols']], [[str(c) for c in r] for r in tb['rows'][:9]]
        n = len(cols)
        lens = [max([len(cols[j])] + [len(r[j]) if j < len(r) else 0 for r in rws]) + 2 for j in range(n)]
        tot = sum(lens)
        ws = [w * l / tot for l in lens]
        fs = 14 if n <= 4 else 12
        hh, rh = 40, 34
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" fill="{th.tint}"/>')
        cx = x
        for j, c in enumerate(cols):
            parts.append(self.text(cx + 12, y + 26, wrap(c, ws[j] - 16, fs, 1)[0], fs, th.ink, True))
            cx += ws[j]
        yy = y + hh
        for r in rws:
            cx = x
            for j in range(n):
                v = r[j] if j < len(r) else ''
                if num(v) is not None and j:
                    parts.append(self.text(cx + ws[j] - 12, yy + 22, v, fs, th.ink, False, 'end'))
                else:
                    parts.append(self.text(cx + 12, yy + 22, wrap(v, ws[j] - 16, fs, 1)[0], fs, th.ink, j == 0))
                cx += ws[j]
            yy += rh
            parts.append(f'<line x1="{x}" y1="{yy}" x2="{x + w}" y2="{yy}" stroke="{th.line}" stroke-width="1"/>')
        parts.append(f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{th.ink}" stroke-width="1"/>')
        return yy

    def bars(self, parts, tb, x, y, w, bottom):
        th = self.th
        cols, rws = tb['cols'], tb['rows'][:9]
        numeric = [j for j in range(1, len(cols)) if rws and all(num(r[j]) is not None for r in rws if j < len(r))]
        h = bottom - y
        if not numeric or h < 110 or len(rws) < 2:
            return
        j = numeric[0]
        vals = [num(r[j]) or 0 for r in rws]
        mx = max(vals) or 1
        n = len(vals)
        gap = 18
        bw = (w - gap * (n - 1)) / n
        base = y + h - 22
        parts.append(self.text(x, y + 2, f'{cols[j]}', 13, th.ink2))
        for i, v in enumerate(vals):
            bh = max(2, (h - 56) * v / mx)
            bx = x + i * (bw + gap)
            parts.append(f'<rect x="{bx:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{th.accent if v == mx else th.line}"/>')
            parts.append(self.text(bx + bw / 2, base - bh - 6, rws[i][j], 12, th.ink, True, 'middle'))
            parts.append(self.text(bx + bw / 2, base + 16, wrap(str(rws[i][0]), bw + gap, 12, 1)[0], 12, th.ink2, False, 'middle'))
        parts.append(f'<line x1="{x}" y1="{base}" x2="{x + w}" y2="{base}" stroke="{th.ink}" stroke-width="1"/>')


def make(bp, template, people, path, job_dir, theme=None):
    """설계도 → PPTX. 돌려주는 값: 장 수. theme: 문서 테마(doc_themes) — 색·서체·표지 바탕만 바뀐다."""
    import doc_themes
    d = Deck(deck_name(template.get('preset')))
    form = template['name']
    secs = bp['sections']
    proj = os.path.join(job_dir, 'ppt')
    out_dir = os.path.join(proj, 'svg_output')
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):
        os.remove(os.path.join(out_dir, f))
    with open(os.path.join(proj, 'spec_lock.md'), 'w', encoding='utf-8') as f:
        f.write('# spec_lock\n\n## pptx_structure\n- mode: flat\n')
    pages, kinds = [d.cover(bp, form, {**people, 'subtitle': template.get('desc', '')})], ['cover']
    if len(secs) >= 3:
        pages.append(d.agenda(secs, len(pages) + 1))
        kinds.append('agenda')
    for i, s in enumerate(secs, 1):
        pages.append(d.body(i, s, form, len(pages) + 1))
        kinds.append('body')
    pages.append(d.closing('감사합니다', f"{people.get('dept', '')} {people.get('담당', '')} · {today_kr()}", len(pages) + 1))
    kinds.append('closing')
    for i, svg in enumerate(pages, 1):
        svg = doc_themes.ppt_apply(svg, theme, kinds[i - 1])        # 문서 테마(색·서체·표지 바탕)
        svg = re.sub(r'\s(data-pptx-[a-z-]+)="[^"]*"', '', svg)      # flat 구조
        with open(os.path.join(out_dir, f'{i:02d}.svg'), 'w', encoding='utf-8') as f:
            f.write(svg)
    pm = corp.path('koscom-doc-pack', '.claude/skills/ppt-master')
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'run_ppt_master.py'), os.path.join(pm, 'scripts', 'svg_to_pptx.py'),
                        proj, '-s', 'output', '-q', '-o', path], capture_output=True, timeout=300)
    if r.returncode != 0 or not os.path.exists(path):
        raise RuntimeError('PPT 변환 실패(ppt-master): ' + (r.stdout + r.stderr).decode('utf-8', 'replace')[-400:])
    return len(pages)


if __name__ == '__main__':           # 자체검사(전사 스킬 없이): 셰브론 06_card_grid 에서 읽은 값 = 예전 고정값
    svg = ('<svg><rect id="master-bg" width="1280" height="720" fill="#ffffff"/><g id="card-1">'
           '<rect x="80" y="256" width="352" height="300" fill="#ffffff" stroke="#dcdce0" stroke-width="1"/>'
           f'<text x="136" y="292" font-family="{FB}" font-size="18" fill="#2b2b2e">{{{{CARD_1_TITLE}}}}</text>'
           f'<text x="108" y="358" font-family="{FM}" font-size="16" fill="#6e6e73">{{{{CARD_1_BODY}}}}</text></g>'
           '<g id="card-3"><rect x="848" y="256" width="352" height="300"/>'
           '<text x="904" y="292" font-size="18">{{CARD_3_TITLE}}</text><text x="876" y="358" font-size="16">{{CARD_3_BODY}}</text></g>'
           '<text x="80" y="674" font-size="14">{{BRAND_MARK}}</text></svg>')
    th = Theme(svg, 'primary_color: "#EE6D1D"')
    assert (th.ink, th.ink2, th.line, th.accent, th.tint, th.fb, th.fm) == (INK, INK2, LINE, ORANGE, '#fad3bb', FB, FM), vars(th)
    assert (th.left, th.right, th.top, th.bottom, th.cards[0]['bx'], th.cards[1]['bx']) == (80, 1200, 256, 640, 108, 876)
    assert type(th.left) is int and int(1120 * .42) == 470
    assert deck_name('deck:warm-doc') == 'warm-doc' and deck_name('deck:없는덱') == deck_name('') == 'koscom-chevron'
    assert wrap('', 100, 16, 1) == [''] and wrap('가 나', 100, 16) == ['가 나']      # 표의 빈 칸 → 경량 렌더러로 넘어가던 IndexError
    assert GUIDE.sub('', '<svg>\n  <g id="photo-guide">\n    <text>replace this plate</text>\n  </g>\n  <g id="title-slot"><text>{{TITLE}}</text></g></svg>') \
        == '<svg>\n  <g id="title-slot"><text>{{TITLE}}</text></g></svg>'
    print('ppt_chevron selftest OK')
