"""AI 제공자 전환 시험(실행 중인 앱에 HTTP로): 고른 제공자로 추천 → 초안 → 채팅 수정 → 세 형식 생성.
python tests/e2e_provider.py [openrouter|claude_cli] [--model deepseek/deepseek-v4.1-flash] [--keep]
끝나면 원래 제공자로 되돌린다(--keep이면 그대로 둔다).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_skillgen import call, ROOT  # noqa: E402

kind = next((a for a in sys.argv[1:] if not a.startswith('--')), 'openrouter')
model = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else ''
call('/api/login', {'uid': 'u1'})
before = call('/api/ai')['ai']
prev = next(p for p in before['providers'] if p['kind'] == before['kind'])
st = call('/api/ai', {'kind': kind, 'or_model': model})['ai']
print('전환:', before['display'], '→', st['display'], '| 연결', st['connected'])
try:
    p = call('/api/ai/ping', {})['ping']
    print('연결 시험:', p)
    memo = open(os.path.join(ROOT, 'seed', 'out', '시연메모_고객세미나.txt'), encoding='utf-8').read()
    req = '11월 고객 세미나 준비 계획을 팀장님께 올릴 요약보고로 만들어줘. A증권 전환 사례 발표 포함, 예산·인원·일정은 메모 그대로.\n' + memo
    t = time.time()
    r = call('/api/route', {'text': req[:200]})
    print(f'추천 {time.time() - t:.1f}s', r['suggest']['template_id'], '|', r['meta']['mode'], r['meta'].get('error', ''))
    t = time.time()
    c = call('/api/compose', {'template_id': 'planning-pack:summary-report', 'request': req})['compose']
    m = c['llm']
    print(f'초안 {time.time() - t:.1f}s', m['mode'], m.get('label'), '| 가림', m.get('masked'), m.get('error', ''))
    bp = c['blueprint']
    print('  제목:', bp['title'], '| 장:', [s['heading'] for s in bp['sections']])
    text = str(bp)
    print('  예산 120만원 유지:', '120만원' in text, '| A증권 복원:', 'A증권' in text, '| 고정 문구:', '효과 수치는 실측·외부 자료·가정을 구분하여 표기함' in text)
    t = time.time()
    c2 = call(f"/api/compose/{c['id']}/chat", {'message': '향후 계획에 세미나 후 2주 안에 참석사별 PoC 제안 일정을 넣어줘'})['compose']
    last = c2['chat'][-1]
    print(f'수정 {time.time() - t:.1f}s', last['meta']['mode'], '|', last['text'][:80])
    t = time.time()
    d = call(f"/api/compose/{c['id']}/generate", {'fmts': ['hwp', 'ppt', 'web']})
    print(f'생성 {time.time() - t:.1f}s', [(x['fmt'], x['ms']) for x in d['results']])
    for x in d['results']:
        bad = [k['name'] + ': ' + k['detail'] for k in x['checks'] if not k['ok']]
        print('  ', x['fmt'], '검수 미통과:', bad or '없음')
    print('비용:', call('/api/ai')['usage'])
finally:
    if '--keep' not in sys.argv:
        if kind == 'openrouter' and model:      # 고른 OpenRouter 모델도 원래대로
            was = next((p.get('model', '') for p in before['providers'] if p['kind'] == 'openrouter'), '')
            call('/api/ai', {'kind': 'openrouter', 'or_model': was})
        call('/api/ai', {'kind': before['kind'], 'or_model': ''})
        print('되돌림:', call('/api/ai')['ai']['display'])
