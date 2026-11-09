"""검수 시연 시험: 원본 메모 ↔ 사람이 고친 PPT(예산 100만원) → 불일치 1, 수정본 → 재검사 통과."""
import os, sys
sys.argv += ['--uid', 'u1']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_skillgen import call, ROOT  # noqa: E402  (로그인 · 업로드 도우미 재사용)

OUT = os.path.join(ROOT, 'seed', 'out')
call('/api/login', {'uid': 'u1'})
memo = open(os.path.join(OUT, '시연메모_고객세미나.txt'), encoding='utf-8').read()
for name in ('검수시연_사람이고친PPT_예산오류.pptx', '검수시연_사람이고친PPT_수정본.pptx'):
    up = call('/api/upload', files=[('file', os.path.join(OUT, name))])['upload']
    r = call('/api/inspect', {'source_text': memo, 'target_ids': [up['id']]})
    res = r['result']
    print(name, '→ 대조', res['checked'], '불일치', res['mismatch'], '빠짐', res['missing'], '판정 불가', res['unknown'])
    for i in res['items']:
        if i['kind'] == 'mismatch':
            print('   ', i['detail'])
