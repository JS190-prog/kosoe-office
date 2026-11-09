"""시연용 가상 자료 만들기 — python seed/make_seed.py [출력 폴더]

- 대표문서/: 스킬 빌더 시연용 '영업 제안서' 3건(PPT 2 · 한글 1). 목차·고정 문구가 같고 고객·숫자만 다르다.
- 시연메모_고객세미나.txt: 0:00·1:50 장면용 메모(예산 120만원)
모든 회사·사람·숫자는 가상이다.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')

import engines  # noqa: E402
import skills  # noqa: E402

INTRO = '코쇠금융IT는 자본시장 인프라를 함께 만들어 온 금융 IT 전문 기업임(가상)'
VALID = '제안 유효기간은 제출일로부터 30일임'
NOTE = '본 자료의 수치와 일정은 협의 결과에 따라 달라질 수 있음'
CLIENTS = [
    ('B증권', 'MTS 주문 지연', '주문 처리 시간 0.8초 → 0.3초 목표', 3, '2027. 2. 1', [('분석', '1개월', '90'), ('구축', '3개월', '420'), ('안정화', '1개월', '70')], 'ppt'),
    ('C자산운용', '펀드 기준가 산출 야간 배치 지연', '배치 시간 4시간 → 1시간 목표', 4, '2027. 3. 2', [('분석', '1개월', '60'), ('구축', '2개월', '260'), ('안정화', '1개월', '50')], 'ppt'),
    ('D저축은행', '원장 시스템 노후화', '장애 건수 연 12건 → 4건 목표', 5, '2027. 4. 1', [('분석', '1개월', '80'), ('이전', '3개월', '390'), ('안정화', '2개월', '110')], 'hwp'),
]


def bp_of(c):
    name, pain, goal, months, start, cost, _ = c
    return {'title': f'{name} 제안서', 'sections': [
        {'heading': '회사 소개', 'items': [{'label': '', 'text': INTRO, 'children': []}, {'label': '실적', 'text': '증권·자산운용·저축은행 고객 40여 곳 운영(가상)', 'children': []}], 'table': None},
        {'heading': '고객 과제', 'items': [{'label': '현황', 'text': f'{pain}이(가) 반복됨', 'children': []}, {'label': '목표', 'text': goal, 'children': []}], 'table': None},
        {'heading': '서비스 제안', 'items': [{'label': '서비스', 'text': '코쇠 원장 클라우드 도입', 'children': []}, {'label': '방식', 'text': '단계별 무중단 전환, 데이터 대조 자동화', 'children': []}], 'table': None},
        {'heading': '레퍼런스', 'items': [{'label': '사례', 'text': 'A증권 원장 클라우드 전환 완료(가상)', 'children': []}], 'table': None},
        {'heading': '일정·비용', 'items': [{'label': '기간', 'text': f'{start} 착수, {months}개월', 'children': []}, {'label': '유의', 'text': NOTE, 'children': []},
                                         {'label': '유효', 'text': VALID, 'children': []}],
         'table': {'cols': ['단계', '기간', '비용(백만원)'], 'rows': [list(r) for r in cost]}},
    ]}


def main(out):
    skills.ensure(force=True)
    d = os.path.join(out, '대표문서')
    os.makedirs(d, exist_ok=True)
    people = {'담당': '홍길동 대리', '팀장': '김철수 팀장', '부서장': '이영희 차장', 'dept': '금융영업1팀'}
    tpl = {'name': '영업 제안서', 'desc': '금융영업 고객 제안', 'preset': ''}
    for i, c in enumerate(CLIENTS, 1):
        path, warns, ms, eng = engines.make(c[6], bp_of(c), tpl, people, 'seed', i)
        dst = os.path.join(d, f'영업제안_{c[0]}.' + ('pptx' if c[6] == 'ppt' else 'hwp'))
        shutil.copy(path, dst)
        print('대표 문서', dst, f'{ms}ms', eng['name'])
    memo = ('2026 고객 세미나 준비 메모 (가상)\n'
            '- 행사명: 원장 클라우드 고객 세미나\n- 일시: 2026. 11. 20 14:00, 장소: 본사 대회의실\n'
            '- 대상: 증권·자산운용 고객 IT 담당자, 참석 인원 45명\n- 예산: 120만원 (다과 40만원, 기념품 80만원)\n'
            '- 진행: 서비스 소개 20분, A증권 전환 사례 20분, 질의응답 20분\n- 후속: 참석사 대상 개별 PoC 제안\n')
    mp = os.path.join(out, '시연메모_고객세미나.txt')
    open(mp, 'w', encoding='utf-8').write(memo)
    print('시연 메모', mp)
    # 검수 시연: 사람이 고치다 예산을 잘못 바꾼 PPT(100만원)와 바로잡은 PPT(120만원)
    ev = lambda budget: {'title': '원장 클라우드 고객 세미나 계획', 'sections': [
        {'heading': '행사 개요', 'items': [{'label': '일시', 'text': '2026. 11. 20 14:00, 본사 대회의실', 'children': []},
                                         {'label': '대상', 'text': '증권·자산운용 고객 IT 담당자, 참석 인원 45명', 'children': []}], 'table': None},
        {'heading': '소요 예산', 'items': [{'label': '예산', 'text': f'{budget}만원 (다과 40만원, 기념품 80만원)', 'children': []}], 'table': None},
        {'heading': '진행 순서', 'items': [{'label': '1부', 'text': '서비스 소개 20분', 'children': []}, {'label': '2부', 'text': 'A증권 전환 사례 20분', 'children': []},
                                         {'label': '3부', 'text': '질의응답 20분', 'children': []}], 'table': None}]}
    for name, budget in (('검수시연_사람이고친PPT_예산오류.pptx', 100), ('검수시연_사람이고친PPT_수정본.pptx', 120)):
        path, *_ = engines.make('ppt', ev(budget), {'name': '행사 계획', 'desc': '고객 세미나'}, people, 'seed-ev', budget)
        shutil.copy(path, os.path.join(out, name))
        print('검수 시연', name)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'seed', 'out'))
