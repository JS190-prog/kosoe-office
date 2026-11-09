"""엔진 연기 시험: 스킬 저장소 동기화 → 전사 스킬 받기 → 상속 해석 → 한글·PPT·웹 생성.
python tests/smoke_engines.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')

import corp  # noqa: E402
import engines  # noqa: E402
import skills  # noqa: E402

t = time.time()
st = skills.ensure(force=True)
print('skills repo:', st['mode'], st['head'][:7], st['error'] or '', f'{time.time() - t:.1f}s')
t = time.time()
corp.warm()
print(f'corp warm {time.time() - t:.1f}s')
r = skills.resolve('sales-pack')
print('chain:', [l['id'] for l in r['levels']], 'corp:', r['resolution']['corp'])
print('blocks:', list(r['blocks']))
for s in skills.all_skills().values():
    print('validate', s['id'], skills.validate(s, skills.all_skills()) or 'OK')
rows = skills.form_rows()
print('forms:', len(rows), [x['id'] for x in rows if x['scope'] != 'corp'])

bp = {'title': 'A증권 원장 클라우드 전환 제안', 'sections': [
    {'heading': '회사 소개', 'items': [{'label': '', 'text': '코쇠금융IT는 자본시장 인프라를 함께 만들어 온 금융 IT 전문 기업임(가상)', 'children': []},
                                     {'label': '설립', 'text': '1977년 설립, 자본시장 IT 48년', 'children': []}], 'table': None},
    {'heading': '고객 과제', 'items': [{'label': '비용', 'text': '레거시 원장 유지비가 매년 증가함', 'children': [{'text': '하드웨어 교체 주기 도래'}]},
                                     {'label': '속도', 'text': '신규 상품 출시까지 평균 6개월 소요', 'children': []},
                                     {'label': '인력', 'text': '운영 인력의 절반이 야간 배치에 묶여 있음', 'children': []}], 'table': None},
    {'heading': '서비스 제안', 'items': [{'label': '핵심', 'text': '코쇠 원장 클라우드는 원장·시세·주문 시스템을 하나의 클라우드로 운영하는 서비스임(가상)', 'children': []},
                                       {'label': '이전', 'text': '무중단 단계 이전(3단계), 데이터 대조 자동화', 'children': []},
                                       {'label': '운영', 'text': '24시간 관제와 장애 대응 30분 이내', 'children': []},
                                       {'label': '보안', 'text': '금융보안원 클라우드 가이드 준수', 'children': []}], 'table': None},
    {'heading': '일정·비용', 'items': [{'label': '기간', 'text': '2027. 1. 5 ~ 2027. 6. 30 (6개월)', 'children': []},
                                     {'label': '유의', 'text': '본 자료의 수치와 일정은 협의 결과에 따라 달라질 수 있음', 'children': []}],
     'table': {'cols': ['단계', '기간', '비용(백만원)'], 'rows': [['분석', '1개월', '120'], ['이전', '3개월', '480'], ['안정화', '2개월', '160']]}},
]}
tpl = {'name': '영업1팀 고객 제안서', 'desc': '영업1팀 표준 제안서', 'preset': ''}
people = {'담당': '홍길동 대리', '팀장': '김철수 팀장', '부서장': '이영희 차장', 'dept': '금융영업1팀'}
for fmt in ('hwp', 'ppt', 'web'):
    t = time.time()
    path, warns, ms, eng = engines.make(fmt, bp, tpl, people, 'smoke', 1)
    print(fmt, os.path.getsize(path), 'bytes', f'{ms}ms', eng, warns[:2])
print('out:', os.path.join(engines.OUT, 'smoke'))
