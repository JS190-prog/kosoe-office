"""문서 기준 문체 · 검증 미통과 강제 등록 시험.
python tests/e2e_style.py            # 단위 시험(앱 없이): 문체 재기 · 문체별 검수 · 자동 수정
python tests/e2e_style.py --app      # + 실행 중인 앱으로: 계약서 예시 → 분석 → 검증(문체 기준이 문서 기준으로 바뀌는지)
python tests/e2e_style.py --app --force   # + 사람 확인을 건너뛴 채 강제 등록(사유 없음 거절 → 사유 있으면 등록, 실제 PR이 만들어진다)
"""
import json
import os
import sys
import time
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'seed'))
for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')

import checks  # noqa: E402
import engines  # noqa: E402
import llm  # noqa: E402

fails = []


def expect(name, cond, detail=''):
    print('  ', '✅' if cond else '❌', name, detail)
    if not cond:
        fails.append(name)


def unit():
    from make_seed import CONTRACT
    print('① 문체 재기')
    st = checks.measure_style([CONTRACT])
    print('   계약서:', checks.style_label(st), '|', st['basis'])
    expect('계약서 → 서술형(~한다)', st['ending'] == 'plain', st['ending'])
    expect('계약서 → 날짜 2019.03.15 형식', st['date'] == 'Y.MM.DD', st['date'])
    expect('계약서 → 90자 제한 풀림', st['max_len'] == 0 or st['max_len'] > 90, str(st['max_len']))
    report = '\n'.join(['□ 추진 배경', 'ㅇ 원장 시스템 노후화로 장애가 반복되어 전환이 필요함', 'ㅇ 2026. 11. 20 고객 세미나에서 전환 사례를 발표할 예정임',
                        'ㅇ 예산 120만원 범위에서 다과와 기념품을 준비함', 'ㅇ 참석 인원 45명 기준으로 좌석을 배치함'])
    sr = checks.measure_style([report])
    print('   보고서:', checks.style_label(sr), '|', sr['basis'])
    expect('보고서 → 전사 보고 문법 그대로', checks.is_default_style(sr))
    polite = '\n'.join(['귀사의 무궁한 발전을 기원합니다.', '아래와 같이 서비스 점검 일정을 안내드립니다.', '점검은 2026년 11월 20일 새벽에 진행합니다.', '문의 사항은 담당 부서로 연락해 주시기 바랍니다.'])
    sp = checks.measure_style([polite])
    expect('공문 → 존댓말(~합니다) · 2026년 10월 28일', sp['ending'] == 'polite' and sp['date'] == 'Y년 M월 D일', checks.style_label(sp))

    print('② 문체별 검수')
    bp = {'title': '계약서', 'sections': [{'heading': '제 1 조【목적】', 'table': None, 'items': [
        {'label': '', 'text': '"갑"과 "을"은 2019.03.15 체결한 기본계약의 부속 계약으로서 추가 업무 이용에 필요한 사항을 정하기 위하여 이 계약을 체결한다. ' * 2, 'children': []}]}]}
    d = {c['id']: c for c in engines.check(bp)}
    expect('보고 문법으로 보면 날짜·길이·종결 모두 미통과', not d['date']['ok'] and not d['long']['ok'] and not d['end']['ok'])
    d = {c['id']: c for c in engines.check(bp, (), st)}
    expect('계약서 문체로 보면 통과', all(c['ok'] for k, c in d.items() if k in ('date', 'long', 'end')), ', '.join(c['name'] for c in d.values()))
    bad = {'title': 't', 'sections': [{'heading': 'h', 'table': None, 'items': [{'label': '', 'text': '계약기간은 2026. 7. 6부터 1년으로 함', 'children': []}]}]}
    d = {c['id']: c for c in engines.check(bad, (), st)}
    expect('계약서 문체에서 개조식(~함)·다른 날짜 형식은 미통과', not d['end']['ok'] and not d['date']['ok'], d['date']['detail'])
    fixed, _ = engines.autofix(bad, lambda xs: (xs, None), (), st)
    t = fixed['sections'][0]['items'][0]['text']
    expect('자동 수정 → 서술형 · 문서의 날짜 형식', t == '계약기간은 2026.07.06부터 1년으로 한다.', t)
    d = {c['id']: c for c in engines.check(bp, (), None, [bp['sections'][0]['items'][0]['text']])}
    expect('고정 문구(글자 그대로 넣는 글)는 문체 검사에서 제외', all(d[k]['ok'] for k in ('date', 'long', 'end')))
    old = '2026-10-28, 2026.10.28, 2026년 10월 28일, 2026. 10. 28'
    b2 = {'title': 't', 'sections': [{'heading': 'h', 'table': None, 'items': [{'label': '', 'text': old, 'children': []}]}]}
    d = {c['id']: c for c in engines.check(b2)}
    expect('기본 문법의 날짜 검사는 그대로(3건 지적)', d['date']['detail'].count('2026') == 3, d['date']['detail'])

    print('③ 고정 문구 안의 칸([칸 이름])')
    fx = '[고객사명](이하 "갑"이라 한다)와 코쇠금융IT(이하 "을"이라 한다)는 "갑"과 "을"이 [기본계약 체결일] 체결한 기본계약의 부속 계약으로서 이 계약을 체결한다.'
    filled = fx.replace('[고객사명]', 'F자산운용 주식회사').replace('[기본계약 체결일]', '2021.05.10')
    broken = 'F자산운용(이하 "갑")과 코쇠금융IT(이하 "을")는 2021.05.10 체결한 기본계약의 부속 계약으로 이 계약을 체결함'
    one = lambda t: {'title': 't', 'sections': [{'heading': '제1조', 'table': None, 'items': [{'label': '', 'text': t, 'children': []}]}]}
    expect('칸을 채운 문장은 고정 문구를 지킨 것', checks.fixed_present(fx, filled) and not checks.fixed_present(fx, broken))
    expect('가림 토큰 [고객사명1]은 칸이 아님', checks.slots_of([fx, '[고객사명1] 귀중']) == ['[고객사명]', '[기본계약 체결일]'])
    expect('채운 문장은 그대로 둠', checks.enforce_fixed(one(filled), [{'heading': '제1조', 'text': fx}])['sections'][0]['items'][0]['text'] == filled)
    b3 = checks.enforce_fixed(one(broken), [{'heading': '제1조', 'text': fx}])
    expect('틀을 바꾼 문장은 고정 문구로 되돌림', b3['sections'][0]['items'][0]['text'] == fx)
    d = {c['id']: c for c in engines.check(b3, (), None, [fx])}
    expect('안 채운 칸은 「확인 필요」로 잡힘', not d['todo']['ok'], d['todo']['detail'])

    print('④ 작성 규칙')
    expect('문체 없으면 코스콤 보고 문법', llm.writing_rules(None) == llm.WRITING_RULES)
    r = llm.writing_rules(st)
    expect('계약서 문체 규칙에 서술형 · 2026.10.28', '서술형 평서문' in r and "'2026.10.28'" in r and '명사형 종결' not in r)
    expect('style 값 검사', checks.validate_style({'ending': 'x'}) and not checks.validate_style({'ending': 'plain', 'date': 'Y.MM.DD', 'max_len': 0}))


def app(force):
    from e2e_skillgen import call, BASE, op
    import urllib.request

    def try_call(path, body):
        req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={'content-type': 'application/json'})
        try:
            return json.loads(op.open(req, timeout=900).read().decode())
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode())

    doc = os.path.join(ROOT, 'seed', 'out', '계약서예시', '전산서비스_추가업무_이용계약서_E증권(가상).txt')
    if not os.path.exists(doc):
        raise SystemExit('먼저 python kosoe.py seed')
    call('/api/login', {'uid': 'u1'})
    print('⑤ 앱: 계약서 예시로 스킬 만들기 — AI', call('/api/ai')['ai']['display'])
    uid = call('/api/upload', files=[('file', doc)])['upload']['id']
    t = time.time()
    j = call('/api/skillgen/analyze', {'upload_ids': [uid], 'request': '전산서비스 추가업무 계약서 스킬 만들어줘', 'scope': 'me'})['job']
    a, f = j['analysis'], j['draft']['forms'][0]
    print(f"   분석 {time.time() - t:.1f}s {a['meta']['mode']} | 문체 {a['style']['label']} | 구성 {f['outline']}")
    expect('분석: 문서 기준 문체가 스킬 양식에 적힘', f.get('style', {}).get('ending') == 'plain', json.dumps(f.get('style'), ensure_ascii=False))
    t = time.time()
    r = call(f"/api/skillgen/{j['id']}/evaluate", {'draft': j['draft']})['report']
    print(f"   검증 {time.time() - t:.1f}s 사용 {r['with_score']}/{r['full']} 미사용 {r['without_score']}/{r['full']} auto_pass={r['auto_pass']}")
    for c in r['criteria']:
        print('     ', '✅' if c['pass'] else '❌', c['name'], '|', str(c.get('detail', ''))[:120])
    g = next(c for c in r['criteria'] if c['id'] == 'grammar')
    expect('검증: 문체 기준 이름이 문서 기준', g['name'].startswith('문체 — 대표 문서 기준'), g['name'])
    expect('검증: 문체 기준 통과', g['pass'], g.get('detail', ''))
    if not force:
        return
    print('⑥ 강제 등록(사람 확인 0건인 채로)')
    x = try_call(f"/api/skillgen/{j['id']}/submit", {'thumbs': 0})
    expect('강제 표시 없으면 거절', not x.get('ok'), x.get('error', ''))
    x = try_call(f"/api/skillgen/{j['id']}/submit", {'thumbs': 0, 'force': True, 'reason': ''})
    expect('사유 없으면 거절', not x.get('ok'), x.get('error', ''))
    t = time.time()
    x = try_call(f"/api/skillgen/{j['id']}/submit", {'thumbs': 0, 'force': True, 'reason': '시험: 사람 확인을 건너뛰고 등록되는지 확인'})
    expect('사유 있으면 등록', x.get('ok'), x.get('error', ''))
    if x.get('ok'):
        q = x['request']
        print(f"   {time.time() - t:.1f}s stage={q['stage']} pr={q['pr_url']}", [h['act'] for h in q['history']])
        expect('요청 기록에 강제 등록 표시', '강제 등록' in q['history'][0]['act'] and q['note']['report']['forced']['failed'])
        call('/api/skills?sync=1')
        s = call('/api/skills/' + j['draft']['id'])['skill'] if q['stage'] == 'done' else None
        if s:
            expect('스킬 파일에 verification: forced', (s.get('verification') or {}).get('status') == 'forced', json.dumps(s.get('verification'), ensure_ascii=False)[:160])
            expect('SKILL.md에 강제 등록 기록', '강제 등록됨' in (s.get('skill_md') or ''))


if __name__ == '__main__':
    unit()
    if '--app' in sys.argv:
        app('--force' in sys.argv)
    print('\n' + ('모두 통과' if not fails else f'실패 {len(fails)}건: ' + ', '.join(fails)))
    sys.exit(1 if fails else 0)
