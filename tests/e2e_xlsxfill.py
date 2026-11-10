"""서식 채우기형 엑셀 스킬(목적별: 견적서 등) 시험 — 실행 중인 앱에 HTTP로.
python tests/e2e_xlsxfill.py [--form pb-addon-quote] [--uid u1] [--base http://localhost:8810]
전사 양식 카드 → 요청(가상 값) → 칸 초안 → 채팅 수정 → 엑셀 생성 → 검수 · 미리보기 · 결과 파일 글 확인.
시험 문서 한 건이 문서함에 남는다. 시연 자료를 건드리지 않으려면 KOSOE_HOME을 다른 폴더로 준 앱에 대고 돌린다
(결과 파일을 직접 읽으므로 이 스크립트도 같은 KOSOE_HOME으로 실행한다).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_skillgen import BASE, call, op, ROOT  # noqa: E402

sys.path.insert(0, ROOT)
FORM = sys.argv[sys.argv.index('--form') + 1] if '--form' in sys.argv else 'pb-addon-quote'
fails = []


def expect(name, cond, detail=''):
    print('  ', '✅' if cond else '❌', name, detail)
    if not cond:
        fails.append(name)


call('/api/login', {'uid': sys.argv[sys.argv.index('--uid') + 1] if '--uid' in sys.argv else 'u1'})
t = next((x for x in call('/api/templates?sync=1')['templates'] if x['id'] == FORM), None)
if not t:
    raise SystemExit(f'양식 {FORM}이 없습니다 — 잠금 파일(registry/corp.lock.yaml)에 kind: xlsx-fill 스킬이 있는지, 또는 .env의 KOSOE_CORP_LOCAL을 확인하세요')
print('① 양식 카드:', t['name'], '|', t['skill'], '| 형식', t['fmt'], '| 범위', t['scope'], '| 등급', t['grade'], '| 쓸 수 있음', t['usable'])
expect('전사 양식 · 서식 채우기형 · 엑셀', t['scope'] == 'corp' and bool(t['skill_info'].get('fill')) and t['fmt'] == 'xlsx')

req = ('가상의 고객사 F자산운용에 보낼 PB 추가업무 견적서를 만들어줘. 추가 업무는 펀드 기준가 검증 자동화야. '
       '이용료는 영업지원 > 펀드 > 펀드 기준가 검증 자동화 회사기본 연 1,200만원(부가세 별도)이고, RM 담당은 금융영업부 홍길동 차장 (02-000-0000)이야.')
t0 = time.time()
c = call('/api/compose', {'template_id': FORM, 'request': req})['compose']
bp = c['blueprint']
print(f"② 초안 {time.time() - t0:.1f}s {c['llm']['mode']} · {c['llm'].get('label')} | 제목: {bp['title']}")
flat = {i['label']: i['text'] for s in bp['sections'] for i in s['items']}
tb = next(s['table'] for s in bp['sections'] if s['table'])
for k, v in flat.items():
    print(f'     {k}: {v}')
print('     표:', tb['rows'])
today = time.strftime('%Y') + '년 ' + time.strftime('%m') + '월 ' + time.strftime('%d') + '일'
if c['llm']['mode'] == 'llm':
    expect('고객사명 · 추가 업무명을 요청에서 찾음', 'F자산운용' in flat['고객사명'] and '펀드 기준가 검증 자동화' in flat['추가 업무명'], flat['고객사명'])
    expect('금액을 표 단위(천원)로 — 1,200만원 → 12,000', any('12,000' in x for r in tb['rows'] for x in r), str(tb['rows']))
    expect('담당자를 요청에서 찾음', '홍길동' in flat['RM 담당'], flat['RM 담당'])
    expect('주지 않은 값(대표이사 · 계약 담당)은 지어내지 않음', not flat['대표이사'] and not flat['계약 담당'], f"{flat['대표이사']!r} {flat['계약 담당']!r}")
expect('말하지 않은 견적 일자는 오늘 · 유효 기간은 기본값', flat['견적 일자'] == today and flat['유효 기간'] == '견적 후 1개월', f"{flat['견적 일자']} / {flat['유효 기간']}")
expect('만들 수 있는 형식은 엑셀만', (c.get('fill') or {}).get('fmts') == ['xlsx'], str(c.get('fill')))

t0 = time.time()
c2 = call(f"/api/compose/{c['id']}/chat", {'message': '대표이사는 김 철 수 로 넣고, 이용료에 영업지원 > 펀드 > 기준가 대사 리포트 회사기본 3,000 행을 하나 더 넣어줘'})['compose']
flat2 = {i['label']: i['text'] for s in c2['blueprint']['sections'] for i in s['items']}
tb2 = next(s['table'] for s in c2['blueprint']['sections'] if s['table'])
print(f"③ 채팅 수정 {time.time() - t0:.1f}s {c2['chat'][-1]['meta']['mode']} | {c2['chat'][-1]['text'][:70]}")
llm2 = c2['chat'][-1]['meta']['mode'] == 'llm'
if llm2:
    expect('칸 값이 바뀜', flat2['대표이사'].replace(' ', '') == '김철수', flat2['대표이사'])
    expect('표에 행이 늘어남', len(tb2['rows']) == len(tb['rows']) + 1, str(tb2['rows']))
expect('칸 이름 · 장 · 표 열은 그대로', list(flat2) == list(flat) and tb2['cols'] == tb['cols'] and [s['heading'] for s in c2['blueprint']['sections']] == [s['heading'] for s in bp['sections']])

# 화면의 [+ 행]: 빈 행을 넣고 저장해도 행이 남아 있어야 그 행에 값을 적을 수 있다(만들 때는 빈 행을 뺀다)
import urllib.request  # noqa: E402
bp3 = json.loads(json.dumps(c2['blueprint']))
tb3 = next(s['table'] for s in bp3['sections'] if s['table'])
tb3['rows'].append([''] * len(tb3['cols']))
put = urllib.request.Request(f"{BASE}/api/compose/{c['id']}", data=json.dumps({'blueprint': bp3}).encode(), headers={'content-type': 'application/json'}, method='PUT')
c3 = json.loads(op.open(put, timeout=60).read().decode())['compose']
tb3s = next(s['table'] for s in c3['blueprint']['sections'] if s['table'])
expect('[+ 행]으로 넣은 빈 행이 저장 뒤에도 남음', len(tb3s['rows']) == len(tb2['rows']) + 1 and not any(tb3s['rows'][-1]), str(tb3s['rows'][-1]))

t0 = time.time()
d = call(f"/api/compose/{c['id']}/generate", {'fmts': ['hwp', 'ppt', 'web', 'xlsx']})
res = d['results']
print(f"④ 생성 {time.time() - t0:.1f}s", [(x['fmt'], x['ms']) for x in res])
expect('한글 · PPT · 웹을 골라도 엑셀만 만들어짐', [x['fmt'] for x in res] == ['xlsx'])
for k in res[0]['checks']:
    print('     ', '✅' if k['ok'] else '❌', k['name'], '|', k['detail'][:90])
doc = d['doc']
f = next(x for x in doc['files'] if x['fmt'] == 'xlsx') if doc.get('files') else {}
print('     엔진:', json.dumps((f or {}).get('resolution') or (f or {}).get('engine') or {}, ensure_ascii=False)[:160])

pv = call(f"/api/docs/{doc['id']}/sheet?ver={doc['ver']}")
expect('미리보기(HTML 표)에 고객사명 · 로고 그림이 있음', 'F자산운용' in pv['html'] and '<img' in pv['html'] and pv['rows'] >= 30, f"{pv['rows']}행 · {len(pv['html'])}자")
raw = op.open(f"{BASE}/api/docs/{doc['id']}/file?fmt=xlsx&ver={doc['ver']}", timeout=60).read()
expect('받기: 엑셀 파일(zip)로 내려옴', raw[:2] == b'PK', f'{len(raw)}바이트')

import engines  # noqa: E402
path = os.path.join(engines.OUT, doc['id'], f"v{doc['ver']}.xlsx")
lines = engines.xlsx_text(path)
text = '\n'.join(lines)
print('⑤ 결과 파일:', path, f'({os.path.getsize(path)}바이트, 글 {len(lines)}줄)')
expect('제목 · 표 머리 · 단위가 서식 그대로 들어 있음', all(k in text for k in ('見   積   書', '귀사에 아래와 같이 견적을 드립니다', '업무구분', '(단위 : 천원/년, 부가세 별도)', '끝.')))
expect('칸이 채워짐(수신처 · 견적명 · 견적 일자)', 'F자산운용 귀중' in text and 'PowerBase추가업무(펀드 기준가 검증 자동화)이용 견적서' in text and f'견적 일자 : {today}' in text)
expect('남은 칸 토큰 없음', '{{' not in text, str([l for l in lines if '{{' in l][:3]))
expect('담당자 줄: 준 것만 들어가고 안 준 줄은 빠짐', 'RM 담당 : 금융영업부 홍길동' in text and '계약 담당' not in text)
if llm2:
    expect('이용료 표 2행 · 합계 15,000', '기준가 대사 리포트' in text and '합계 | 15,000' in text)
from openpyxl import load_workbook  # noqa: E402
ws = load_workbook(path).active
expect('직인은 넣지 않음(그림은 회사 로고 하나)', len(ws._images) == 1, f'그림 {len(ws._images)}개')
n_rows = len(tb2['rows'])
expect('빈 행은 파일에 들어가지 않음(합계가 마지막 이용료 행 바로 아래)', ws.cell(16 + n_rows, 2).value == '합계', f"B{16 + n_rows}={ws.cell(16 + n_rows, 2).value!r}")

print('\n' + ('모두 통과' if not fails else f'실패 {len(fails)}건: ' + ', '.join(fails)))
print('DOC', doc['id'], path)
sys.exit(1 if fails else 0)
