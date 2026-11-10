"""서식 채우기형 한글 스킬 — form.yaml(칸 정의) ↔ 설계도(blueprint) ↔ values.json.

보고서 스킬은 문단을 조립하지만, 계약서·공문처럼 모양이 정해진 문서는 서식(.hwp)의 칸에 값만 넣는다.
설계도는 그대로 쓴다: 장 = form의 sections, 항목 = 칸(label=칸 이름, text=값), 표 = 반복 행.
그래서 초안·채팅 수정·직접 고치기 화면이 보고서와 똑같이 동작하고, 만들 때만 칸 값으로 바꿔 렌더러에 넘긴다.
"""
import datetime
import re

TODO = '(확인 필요)'


def _default(f):
    """기본값. {year} = 올해, {today:YYYY년 MM월 DD일} = 오늘(YYYY · MM · DD · M · D 자리에 값이 들어간다)."""
    d = datetime.date.today()

    def today(m):
        s = m.group(1) or 'YYYY-MM-DD'
        for k, v in (('YYYY', str(d.year)), ('MM', f'{d.month:02d}'), ('DD', f'{d.day:02d}'), ('M', str(d.month)), ('D', str(d.day))):
            s = s.replace(k, v)
        return s
    return re.sub(r'\{today(?::([^{}]*))?\}', today, str(f.get('default') or '')).replace('{year}', str(d.year))


def fields_of(form):
    return [f for s in form.get('sections') or [] for f in s.get('fields') or []]


def tables_of(form):
    return [(s.get('heading', ''), s['table']) for s in form.get('sections') or [] if s.get('table')]


def prompt_spec(form):
    """AI에게 보여 줄 칸 목록."""
    out = []
    for f in fields_of(form):
        bits = [f"- {f['key']} ({f.get('label', f['key'])})" + (' [필수]' if f.get('required') else '')]
        if f.get('hint'):
            bits.append(f"  설명: {f['hint']}")
        if f.get('example'):
            bits.append(f"  예: {f['example']}")
        if f.get('default'):
            bits.append(f"  자료에 없으면 비워 둔다(기본값 '{_default(f)}'이 들어간다)")
        out.append('\n'.join(bits))
    for h, t in tables_of(form):
        # 칸과 같은 모양(- key (설명))으로 적는다 — '표 이용료'처럼 적으면 AI가 '표 '까지 key로 돌려주는 일이 있었다(DeepSeek: 표가 통째로 빠짐)
        out.append(f"- {t['key']} (표 · {h}): 열 {t['cols']}" + (f" · 단위 {t['unit']}" if t.get('unit') else '')
                   + (f" · 필수 열 {t['required']}" if t.get('required') else '')
                   + f"\n  rows의 key는 \"{t['key']}\". 행마다 열 이름: 값. 합계 행은 넣지 않는다(자동 계산).")
    return '\n'.join(out)


def _table_rows(rows, t, heading, only):
    """AI가 돌려준 rows에서 이 표의 행을 찾는다. key가 조금 달라도('표 이용료' · 장 제목) 받아 준다. only = 양식에 표가 하나뿐인가."""
    rows = rows or {}
    if t['key'] in rows:
        return rows[t['key']] or []
    norm = lambda s: re.sub(r'^표\s*', '', re.sub(r'\s+', '', str(s)))
    for k, v in rows.items():
        if norm(k) in (norm(t['key']), norm(heading)):
            return v or []
    if only and len(rows) == 1:
        return next(iter(rows.values())) or []
    return []


def _clean(v):
    return re.sub(r'\s*\n\s*', ' ', str(v if v is not None else '')).strip()


def _as_date(v, fmt):
    """칸에 date 형식이 적혀 있으면(예: Y.MM.DD) 다른 모양으로 적힌 날짜를 그 형식으로 맞춘다. 날짜가 아니면 그대로."""
    import checks
    m = checks.DATE_RX.fullmatch(v.strip()) if v else None
    return checks.fmt_date(*checks.date_parts(m), fmt) or v if m else v


def to_blueprint(form, fields, rows, title=None, keep_empty=False):
    """칸 값 → 설계도. 값이 없는 필수 칸은 '(확인 필요)'로 둔다.
    keep_empty: 빈 표 행을 남긴다 — 화면에서 [+ 행]으로 막 넣은 행이 저장되며 사라지지 않게(normalize에서 쓴다)."""
    fields = {str(k).strip(): _clean(v) for k, v in (fields or {}).items()}
    secs = []
    vals = {}
    for s in form.get('sections') or []:
        items = []
        for f in s.get('fields') or []:
            v = fields.get(f['key'], '')
            if not v or TODO in v:
                v = _default(f) or (TODO if f.get('required') else '')
            elif f.get('date'):
                v = _as_date(v, f['date'])
            vals[f['key']] = '' if v == TODO else v
            items.append({'label': f.get('label', f['key']), 'text': v, 'children': []})
        tb = None
        t = s.get('table')
        if t:
            data = _table_rows(rows, t, s.get('heading', ''), len(tables_of(form)) == 1)
            grid = []
            for r in data if isinstance(data, list) else []:
                r = r if isinstance(r, dict) else dict(zip(t['cols'], r))
                line = [_clean(r.get(c, '')) for c in t['cols']]
                if (any(line) or keep_empty) and '합계' not in line[0].replace(' ', ''):
                    grid.append(line)
            if not any(any(line) for line in grid):          # 값 있는 행이 하나도 없으면 첫 행의 필수 칸에 '(확인 필요)'
                grid = [[TODO if c in (t.get('required') or []) else '' for c in t['cols']]] + grid[1:]
            tb = {'cols': list(t['cols']), 'rows': grid}
        secs.append({'heading': s.get('heading', ''), 'items': items, 'table': tb})
    if not title:
        title = re.sub(r'\{(\w+)\}', lambda m: vals.get(m.group(1), ''), form.get('title') or form.get('name') or '문서')
        title = re.sub(r'\s*\(\s*\)', '', title).strip()
    return {'title': title, 'sections': secs}


def _num(s):
    s = str(s).replace(',', '').strip()
    return float(s) if re.fullmatch(r'-?\d+(\.\d+)?', s) else None


def _fmt(x):
    return f'{int(x):,}' if x == int(x) else f'{x:,.2f}'.rstrip('0').rstrip('.')


def to_values(bp, form, keep_empty=False):
    """설계도 → 렌더러에 넘길 values.json. '(확인 필요)'는 인쇄하지 않고 비운다. 기본값·빈 칸 표시·합계를 채운다.
    값이 없는 표 행(빈 칸 표시만 든 행 포함)은 뺀다. keep_empty면 빈 행으로 남긴다(화면 편집 중)."""
    secs = bp.get('sections') or []
    fields, rows = {}, {}
    for i, s in enumerate(form.get('sections') or []):
        b = next((x for x in secs if x.get('heading') == s.get('heading')), secs[i] if i < len(secs) else {'items': [], 'table': None})
        items = b.get('items') or []
        for j, f in enumerate(s.get('fields') or []):
            lab = f.get('label', f['key'])
            it = next((x for x in items if (x.get('label') or '').strip() in (lab, f['key'])), items[j] if j < len(items) and not (items[j].get('label') or '').strip() else None)
            v = _clean((it or {}).get('text', ''))
            fields[f['key']] = '' if TODO in v else (v or _default(f))
        t = s.get('table')
        if t:
            tb = b.get('table') or {}
            cols = tb.get('cols') or t['cols']
            out = []
            for r in tb.get('rows') or []:
                d = {}
                for k, c in enumerate(t['cols']):
                    idx = cols.index(c) if c in cols else k
                    v = _clean(r[idx]) if idx < len(r) else ''
                    d[c] = '' if TODO in v else v
                blank = t.get('blank') or {}
                if '합계' in d[t['cols'][0]].replace(' ', ''):
                    continue
                if not any(v and v != blank.get(c) for c, v in d.items()):
                    if keep_empty:
                        out.append({c: '' for c in t['cols']})
                    continue
                for c, mark in blank.items():
                    if not d.get(c):
                        d[c] = mark
                out.append(d)
            rows[t['key']] = out
            sm = t.get('sum')
            if sm:
                nums = [_num(d.get(sm['col'], '')) for d in out if any(d.values())]
                fields[sm['into']] = _fmt(sum(nums)) if nums and all(n is not None for n in nums) else ''
    return {'fields': fields, 'rows': rows}


def normalize(bp, form):
    """채팅·직접 수정 뒤에도 장·칸 이름·표 열이 서식과 같게 되돌린다(값만 유지)."""
    v = to_values(bp, form, keep_empty=True)      # [+ 행]으로 넣은 빈 행은 남긴다(만들 때 to_values가 뺀다)
    made = to_blueprint(form, v['fields'], v['rows'], keep_empty=True)
    return made


def check(bp, form):
    """서식 채우기 문서의 검수: 필수 칸 · 칸 형식 · 표."""
    v = to_values(bp, form)
    miss = [f.get('label', f['key']) for f in fields_of(form) if f.get('required') and not v['fields'].get(f['key'])]
    bad = []
    for f in fields_of(form):
        val = v['fields'].get(f['key'])
        if val and f.get('pattern') and not re.fullmatch(f['pattern'], val):
            bad.append(f"{f.get('label', f['key'])} '{val}'" + (f" ({f['hint']})" if f.get('hint') else ''))
    out = [{'id': 'fill_required', 'name': '필수 칸 채움', 'ok': not miss, 'detail': ', '.join(miss) + (' — 값을 넣어 주세요' if miss else ''), 'fix': False},
           {'id': 'fill_format', 'name': '칸 형식', 'ok': not bad, 'detail': '; '.join(bad), 'fix': False}]
    for h, t in tables_of(form):
        data = v['rows'].get(t['key']) or []
        holes = [f"{i + 1}행 {c}" for i, d in enumerate(data) for c in (t.get('required') or []) if not d.get(c)]
        sm = t.get('sum')
        nosum = bool(sm) and bool(data) and not v['fields'].get(sm['into'])
        detail = '행이 없음' if not data else ', '.join(holes) + (' 값 없음' if holes else '') + (f" {sm['col']}에 숫자가 아닌 값이 있어 합계를 내지 못함" if nosum else '')
        out.append({'id': 'fill_table', 'name': f'{h} 표', 'ok': bool(data) and not holes and not nosum, 'detail': detail.strip(), 'fix': False})
    return out
