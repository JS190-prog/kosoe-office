"""검수 확장 — 스킬 규칙 검사와 원본값 대조(수정 누락 찾기).

- skill_checks: 상속 해석된 스킬의 필수 문구·금지어·고정 문구가 결과에 지켜졌는지
- extract_values / crosscheck: 원본(메모·엑셀)과 결과 파일(한글·PPT·웹·사람이 고친 파일)에서
  '항목명 + 숫자 + 단위'를 뽑아 같은 항목의 값이 다르거나 빠진 곳을 찾는다. 읽지 못한 파일은 '판정 불가'.
"""
import html
import re

UNIT = r'(조원|억원|천만원|백만원|만원|원|억|%|건|명|개월|개|시간|분|일|회|배|점)'
NUM_RX = re.compile(r'(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*' + UNIT)
KEY_RX = re.compile(r'([가-힣A-Za-z][가-힣A-Za-z0-9·()\s]{0,14})\s*[:：]?\s*$')
STOP = {'약', '총', '및', '등', '각', '연', '월', '주', '전', '후', '기준', '이내', '이상', '이하', '대비'}


def _norm(v, unit):
    x = float(v.replace(',', ''))
    mul = {'조원': 10**12, '억원': 10**8, '억': 10**8, '천만원': 10**7, '백만원': 10**6, '만원': 10**4, '원': 1}.get(unit)
    return (x * mul, '원') if mul else (x, unit)


def _key(before):
    b = re.split(r'[,.;\n|·•■□○ㅇ\-–(]\s*', before)[-1].strip()
    m = KEY_RX.search(b)
    if not m:
        return ''
    words = [w for w in m.group(1).split() if w not in STOP]
    return ' '.join(words[-2:]).strip()


def extract_values(text):
    """[{key, value, unit, raw, ctx}] — 같은 항목이 여러 번 나오면 모두."""
    out = []
    label = ''
    for line in str(text or '').splitlines():
        s = line.strip()
        if not s:
            continue
        found = False
        for m in NUM_RX.finditer(line):
            v, u = _norm(m.group(1), m.group(2))
            k = _key(line[:m.start()])
            if not k and m.start() <= 2 and label:      # PPT처럼 이름표('예산')와 값이 다른 글상자에 있을 때
                k = label
            out.append({'key': k, 'value': v, 'unit': u, 'raw': m.group(0).strip(), 'ctx': (f'{label} ' if k == label and label else '') + s[:80]})
            found = True
        label = s if (not found and len(s) <= 12 and not re.search(r'\d', s)) else ''
    return out


def crosscheck(source_text, targets):
    """source_text: 원본 자료 글. targets: [{'name','text'|None}]. 돌려주는 값: {'items': [...], 'summary'}"""
    src = [x for x in extract_values(source_text) if x['key']]
    items = []
    for t in targets:
        if t.get('text') is None:
            items.append({'target': t['name'], 'kind': 'unknown', 'detail': '파일을 읽지 못해 판정 불가'})
            continue
        tv = extract_values(t['text'])
        for s in src:
            same_key = [x for x in tv if x['key'] and (x['key'] == s['key'] or s['key'] in x['key'] or x['key'] in s['key']) and x['unit'] == s['unit']]
            if not same_key:
                if not any(abs(x['value'] - s['value']) < 1e-9 and x['unit'] == s['unit'] for x in tv):
                    items.append({'target': t['name'], 'kind': 'missing', 'key': s['key'], 'want': s['raw'], 'got': '',
                                  'detail': f"원본의 '{s['key']} {s['raw']}'이(가) 없음"})
                continue
            if not any(abs(x['value'] - s['value']) < 1e-9 for x in same_key):
                got = same_key[0]
                items.append({'target': t['name'], 'kind': 'mismatch', 'key': s['key'], 'want': s['raw'], 'got': got['raw'],
                              'detail': f"'{s['key']}' 원본 {s['raw']} ≠ {t['name']} {got['raw']}", 'ctx': got['ctx']})
    mism = [i for i in items if i['kind'] == 'mismatch']
    return {'items': items, 'checked': len(src), 'mismatch': len(mism), 'missing': sum(1 for i in items if i['kind'] == 'missing'),
            'unknown': sum(1 for i in items if i['kind'] == 'unknown')}


def bp_text(bp):
    lines = [bp.get('title', '')]
    for s in bp.get('sections') or []:
        lines.append(s.get('heading', ''))
        for it in s.get('items') or []:
            lines.append(f"{it.get('label', '')} {it.get('text', '')}".strip())
            lines += [c.get('text', '') for c in it.get('children') or []]
        tb = s.get('table')
        if tb and tb.get('rows'):
            cols = tb.get('cols') or []
            for r in tb['rows']:
                lines.append(' '.join(f'{c} {v}' if j and j < len(cols) else str(v) for j, (c, v) in enumerate(zip([''] + cols[1:], r))))
    return '\n'.join(lines)


def html_text(path):
    s = open(path, encoding='utf-8', errors='replace').read()
    s = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', s, flags=re.S)
    s = re.sub(r'<(br|/p|/div|/li|/tr|/h\d)[^>]*>', '\n', s)
    return html.unescape(re.sub(r'<[^>]+>', ' ', s))


def skill_checks(bp, skill):
    """skill = form 행의 skill 정보(checks·glossary·fixed). 돌려주는 값: 검수 항목 목록(engines.check 형식)."""
    if not skill:
        return []
    text = bp_text(bp)
    out = []
    req = (skill.get('checks') or {}).get('required') or []
    miss = [r for r in req if r not in text]
    out.append({'id': 'required', 'name': '팩 필수 문구', 'ok': not miss, 'detail': ' / '.join(miss)[:160], 'fix': bool(miss),
                'from': 'skill'})
    banned = list(dict.fromkeys(((skill.get('checks') or {}).get('banned') or []) + ((skill.get('glossary') or {}).get('banned') or [])))
    hit = [b for b in banned if b and b in text]
    out.append({'id': 'banned', 'name': '팩 금지어', 'ok': not hit, 'detail': ', '.join(hit), 'fix': bool(hit), 'from': 'skill'})
    fixed = skill.get('fixed') or []
    lost = [f['text'] for f in fixed if f.get('text') and f['text'] not in text]
    out.append({'id': 'fixed', 'name': '팩 고정 문구(글자 그대로)', 'ok': not lost, 'detail': ' / '.join(lost)[:160], 'fix': bool(lost),
                'from': 'skill'})
    return out


def fix_skill(bp, skill):
    """필수·고정 문구를 맞는 장에 넣고 금지어를 지운다."""
    import json
    b = json.loads(json.dumps(bp))
    text = bp_text(b)
    secs = b['sections']
    for f in skill.get('fixed') or []:
        if f.get('text') and f['text'] not in text:
            tgt = next((s for s in secs if f.get('heading') and f['heading'] in s['heading']), secs[-1])
            tgt['items'].append({'label': '', 'text': f['text'], 'children': []})
    text = bp_text(b)
    for r in (skill.get('checks') or {}).get('required') or []:
        if r not in text:
            secs[-1]['items'].append({'label': '유의', 'text': r, 'children': []})
    banned = list(dict.fromkeys(((skill.get('checks') or {}).get('banned') or []) + ((skill.get('glossary') or {}).get('banned') or [])))
    for s in secs:
        for it in s['items']:
            for w in banned:
                if w:
                    it['text'] = re.sub(r'\s*' + re.escape(w) + r'\s*', ' ', it['text']).strip()
    return b


def enforce_fixed(bp, fixed):
    """스킬의 고정 문구는 AI가 바꾸거나 빠뜨려도 글자 그대로 들어가게 한다(맞는 장에 넣고, 비슷하게 바꾼 문장은 교체)."""
    import difflib
    import json as _j
    b = _j.loads(_j.dumps(bp))
    secs = b.get('sections') or []
    if not secs:
        return b
    for f in fixed or []:
        t = (f.get('text') or '').strip()
        if not t or t in bp_text(b):
            continue
        best, ratio = None, 0.0
        for s in secs:
            for it in s['items']:
                r = difflib.SequenceMatcher(None, it['text'], t).ratio()
                if r > ratio:
                    best, ratio = it, r
        if best is not None and ratio >= 0.6:
            best['text'] = t
            continue
        h = (f.get('heading') or '').strip()
        tgt = next((s for s in secs if h and (h in s['heading'] or s['heading'] in h)), None) or secs[-1]
        tgt['items'].append({'label': '', 'text': t, 'children': []})
    return b
