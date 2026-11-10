"""서식 채우기형 한글 스킬(목적별: 계약서 등) 시험 — 실행 중인 앱에 HTTP로.
python tests/e2e_fillform.py [--form pb-addon-contract] [--uid u1]
전사 양식 카드 → 요청(가상 값) → 칸 초안 → 채팅 수정 → 한글 생성 → 검수 · 결과 파일 글 확인.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_skillgen import call, ROOT  # noqa: E402

sys.path.insert(0, ROOT)
FORM = sys.argv[sys.argv.index('--form') + 1] if '--form' in sys.argv else 'pb-addon-contract'
fails = []


def expect(name, cond, detail=''):
    print('  ', '✅' if cond else '❌', name, detail)
    if not cond:
        fails.append(name)


call('/api/login', {'uid': sys.argv[sys.argv.index('--uid') + 1] if '--uid' in sys.argv else 'u1'})
t = next((x for x in call('/api/templates?sync=1')['templates'] if x['id'] == FORM), None)
if not t:
    raise SystemExit(f'양식 {FORM}이 없습니다 — 잠금 파일(registry/corp.lock.yaml)에 kind: hwp-fill 스킬이 있는지, 또는 .env의 KOSOE_CORP_LOCAL을 확인하세요')
print('① 양식 카드:', t['name'], '|', t['skill'], '| 범위', t['scope'], '| 등급', t['grade'], '| 쓸 수 있음', t['usable'])
expect('전사 양식 · 서식 채우기형', t['scope'] == 'corp' and bool(t['skill_info'].get('fill')))

req = ('F자산운용 주식회사(가상)와 PB 추가업무 계약서를 만들어줘. 추가 업무는 펀드 기준가 검증 자동화, 기본계약은 2021년 5월 10일에 체결했어. '
       '이용료는 영업지원 > 펀드 > 펀드 기준가 검증 자동화 회사기본 연 1,200만원(부가세 별도)이야.')
t0 = time.time()
c = call('/api/compose', {'template_id': FORM, 'request': req})['compose']
bp = c['blueprint']
print(f"② 초안 {time.time() - t0:.1f}s {c['llm']['mode']} · {c['llm'].get('label')} | 제목: {bp['title']}")
flat = {i['label']: i['text'] for s in bp['sections'] for i in s['items']}
tb = next(s['table'] for s in bp['sections'] if s['table'])
for k, v in flat.items():
    print(f'     {k}: {v}')
print('     표:', tb['rows'])
if c['llm']['mode'] == 'llm':
    expect('고객사명 · 추가 업무명을 요청에서 찾음', 'F자산운용' in flat['고객사명'] and '펀드 기준가 검증 자동화' in flat['추가 업무명'], flat['고객사명'])
    expect('날짜를 서식 형식(YYYY.MM.DD)으로 맞춤', flat['기본계약 체결일'] == '2021.05.10', flat['기본계약 체결일'])
    expect('금액을 표 단위(천원)로 — 1,200만원 → 12,000', any('12,000' in x for r in tb['rows'] for x in r), str(tb['rows']))
    expect('주지 않은 값(대표이사·주소)은 지어내지 않음', not flat['갑 대표이사'] and not flat['갑 주소'], f"{flat['갑 대표이사']!r} {flat['갑 주소']!r}")
expect('조항 문장은 설계도에 없음(서식에 들어 있음)', '체결한다' not in json.dumps(bp, ensure_ascii=False))
expect('만들 수 있는 형식은 한글만', (c.get('fill') or {}).get('fmts') == ['hwp'], str(c.get('fill')))

t0 = time.time()
c2 = call(f"/api/compose/{c['id']}/chat", {'message': '갑 대표이사는 홍 길 동, 주소는 서울특별시 영등포구 가상로 1 이야. 이용료에 영업지원 > 펀드 > 기준가 대사 리포트 회사기본 3,000 행을 하나 더 넣어줘'})['compose']
flat2 = {i['label']: i['text'] for s in c2['blueprint']['sections'] for i in s['items']}
tb2 = next(s['table'] for s in c2['blueprint']['sections'] if s['table'])
print(f"③ 채팅 수정 {time.time() - t0:.1f}s {c2['chat'][-1]['meta']['mode']} | {c2['chat'][-1]['text'][:70]}")
if c2['chat'][-1]['meta']['mode'] == 'llm':
    expect('칸 값이 바뀜', flat2['갑 대표이사'].replace(' ', '') == '홍길동' and '가상로' in flat2['갑 주소'], f"{flat2['갑 대표이사']} / {flat2['갑 주소']}")
    expect('표에 행이 늘어남', len(tb2['rows']) == len(tb['rows']) + 1, str(tb2['rows']))
expect('칸 이름 · 장 · 표 열은 그대로', list(flat2) == list(flat) and tb2['cols'] == tb['cols'] and [s['heading'] for s in c2['blueprint']['sections']] == [s['heading'] for s in bp['sections']])

t0 = time.time()
d = call(f"/api/compose/{c['id']}/generate", {'fmts': ['hwp', 'ppt', 'web']})
res = d['results']
print(f"④ 생성 {time.time() - t0:.1f}s", [(x['fmt'], x['ms']) for x in res])
expect('PPT · 웹을 골라도 한글만 만들어짐', [x['fmt'] for x in res] == ['hwp'])
for k in res[0]['checks']:
    print('     ', '✅' if k['ok'] else '❌', k['name'], '|', k['detail'][:90])
doc = d['doc']
f = next(x for x in doc['files'] if x['fmt'] == 'hwp') if doc.get('files') else {}
print('     엔진:', json.dumps((f or {}).get('resolution') or (f or {}).get('engine') or {}, ensure_ascii=False)[:160])
import skills  # noqa: E402
import engines  # noqa: E402
skills.ensure()
path = os.path.join(engines.OUT, doc['id'], f"v{doc['ver']}.hwp")
lines = engines.hwp_text(path)
text = '\n'.join(lines)
print('⑤ 결과 파일:', path, f'({os.path.getsize(path)}바이트, 글 {len(lines)}줄)')
expect('표지 · 조항 · 서명란이 서식 그대로 들어 있음', all(k in text for k in ('PowerBase 전산서비스 추가 업무 이용 계약서', '제 1 조【목적】', '제 5 조 【기타사항】', '주식회사   코 스 콤')))
expect('칸이 채워짐(고객사명 · 추가 업무명 · 기본계약 체결일)', 'F자산운용' in text and '“펀드 기준가 검증 자동화”로 한다' in text and '2021.05.10일자로' in text)
expect('남은 칸 토큰 없음', '{{' not in text, str([l for l in lines if '{{' in l][:3]))
if c2['chat'][-1]['meta']['mode'] == 'llm':
    expect('이용료 표 2행 · 합계 15,000', '기준가 대사 리포트' in text and '15,000' in text)
print('\n' + ('모두 통과' if not fails else f'실패 {len(fails)}건: ' + ', '.join(fails)))
print('DOC', doc['id'], path)
sys.exit(1 if fails else 0)
