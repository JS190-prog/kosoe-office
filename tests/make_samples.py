"""새 문서 카드 샘플 그림: 양식마다 가상 표본 설계도(sample.json) → 엔진으로 문서 → 앞쪽 몇 장을 그림(webp)으로.

  KOSOE_HOME=<데이터 폴더> KOSOE_SKILLS_OFFLINE=1 PLAYWRIGHT_CORE=<playwright-core 경로> python tests/make_samples.py [양식 id ...]
  → 스킬 저장소(KOSOE_HOME/skills-repo)의 샘플 폴더에 sample.json · 01.webp … — 전사 양식은 registry/samples/<id>/,
    스킬 양식은 <스킬 폴더>/samples/<양식 id>/ (앱 _sample_dir). 저장소 브랜치에 커밋해 PR로 올린다.
sample.json 이 있으면 그 설계도로 다시 그리기만 하고, 없으면 AI로 만든다(앱의 초안 만들기와 같은 길). 내용을 바꾸려면 sample.json 을 지우고 다시 돌린다.
그림: 한글 = 한컴 한글 → PDF → PNG(앞 3쪽, HWP_PY 파이썬의 pywin32·PyMuPDF) · PPT = PowerPoint 내보내기(앞 4장) · 웹 = check_deck.js(앞 4장)
"""
import concurrent.futures as cf
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image  # noqa: E402

import app  # noqa: E402  — 앱과 같은 양식 행 · 작성 규칙 · 렌더 정보 · 샘플 폴더를 쓴다
import checks  # noqa: E402
import core  # noqa: E402
import corp  # noqa: E402
import engines  # noqa: E402
import llm  # noqa: E402

PEOPLE = {'담당': '홍길동 대리', '팀장': '김철수 팀장', '부서장': '이영희 차장', 'dept': '금융영업1팀', 'hq': '금융영업본부'}
MAX = {'hwp': 3, 'ppt': 4, 'web': 4}
RULE = ("이 문서는 양식 갤러리에 보여 줄 샘플이다. 요청의 주제로 가상의 내용을 그럴듯하게 채운다 — 숫자·날짜·일정·금액·근거 문서 번호를 지어 넣는다. "
        "'(확인 필요)'는 쓰지 않는다. 실존 회사·기관·제품 이름과 실명은 쓰지 않는다(고객사는 A증권·B은행처럼, 사람은 홍길동·김철수·이영희·박지원·최수민). "
        "전화번호·이메일·계좌번호처럼 개인정보로 보이는 값은 쓰지 않는다(연락처는 '내선 2345'처럼). 제목은 22자 이내. "
        "숫자 비교가 어울리는 장 하나 이상에는 표(3~5행)를 넣는다.")
TOPIC = {   # 처음 만들 때만 쓰는 샘플 주제(없는 양식은 양식 설명) — 만든 뒤에는 sample.json 의 request 에 남는다
    'result-report': '2026년 하반기 사내 생성형 AI 활용 교육 결과(4회 운영, 수료 212명, 만족도 4.6점)',
    'plan-report': '2027년 고객 상담 챗봇 도입 계획(1분기 시범, 2분기 확대)',
    'review-report': '업무용 노트북 600대 교체 방식 검토(구매와 3년 임차 비교)',
    'issue-report': '2026. 11. 3 시세 조회 API 응답 지연 장애(09:12~09:47, 35분)',
    'meeting-report': '차세대 원장 시스템 착수 회의 결과(유관 부서 6곳 참석)',
    'trip-report': '싱가포르 핀테크 행사 출장 결과(2026. 11. 4 ~ 11. 7)',
    'visit-report': 'A증권 IT기획팀 방문 결과(원장 클라우드 전환 협의)',
    'event-plan': '2026 송년 기술 세미나 행사 계획(12. 18, 본사 대강당, 200명)',
    'weekly-report': '금융영업1팀 11월 2주차 주간 업무 보고',
    'education-plan': '신입사원 금융IT 기초 교육 과정 기획(3일, 40명)',
    'deck-proposal': 'B증권 원장 시스템 클라우드 전환 제안',
    'deck-exec': '데이터센터 전력 설비 증설 결정 요청',
    'web-brief': '3분기 금융영업1팀 실적 브리핑(매출 128억원, 전년 대비 12% 증가)',
    'web-edu': '신입 직원 개인정보 보호 기본 교육',
    'invest-plan': '재해복구센터 스토리지 교체 투자계획(총 18.6억원)',
    'gian-body': '본사 회의실 12개실 화상회의 장비 교체(총 3.12억원)',
    'form-trip': '부산 데이터센터 출장(11. 17 ~ 11. 18, 재해복구센터 점검, KTX 왕복 119,600원, 숙박 1박 90,000원, 현장 협의 결과는 복귀 후 별도 보고)',
    'form-leave': '연차 휴가(12. 22 ~ 12. 26, 5일, 가족 여행)',
    'form-edu': '클라우드 아키텍처 전문 과정 참가(외부 교육기관, 3일)',
    'form-purchase': '개발팀 27인치 모니터 10대와 주변기기 구매',
    'deck-warm': '새 전자결재 시스템 사용 안내',
    'deck-midnight': '주문 처리 엔진 성능 개선(처리량 2.4배)',
    'deck-mesh': '2030 디지털 금융 플랫폼 비전과 전략',
    'deck-road': 'AI 상담 서비스 3단계 도입 로드맵',
    'deck-polarity': '온프레미스와 클라우드 운영 방식 비교',
    'deck-signal': '2026 상반기 고객 만족 개선 성과(NPS 32 → 41)',
    'web-motion': '모바일 증권 앱 개편 결과',
    'web-scroll': '사내 클라우드 서비스 도입 연혁과 로드맵',
    'web-3d': '이중화 데이터센터 네트워크 구조',
    'planning-pack:summary-report': '2027년 전사 데이터 거버넌스 체계 구축 추진 계획',
    'sales-pack:proposal': 'A증권 원장 시스템 클라우드 전환 제안',
    'sales-pack:briefing': 'B은행 대상 시세 데이터 API 서비스 브리핑',
    'sales-pack:visit-report': 'C자산운용 운용지원팀 방문 결과(시세 데이터 API 도입 협의)',
    'deck-proposal-u1-287a:main': 'D증권 차세대 트레이딩 시스템 구축 제안',
}


def sample_bp(t):
    """AI로 가상 표본 설계도(앱 compose_new 와 같은 길: 스킬 규칙 → llm.blueprint → 신청서 작성자 칸 → 고정 문구)."""
    tl = app._tpl_for_llm(t)
    tl['rules'] = f"{tl['rules']}\n{RULE}".strip()
    if t['fmt'] == 'hwp' and engines.hwp_kind(t) == 'form':
        tl['form_fields'] = engines.form_fields(t['preset'][5:])
    req = f"{TOPIC.get(t['id'], t['desc'])} — 「{t['name']}」 양식 샘플"
    bp, meta = llm.blueprint(tl, req, [], {'use_llm': True})
    if meta['mode'] != 'llm':
        raise RuntimeError('AI 없이 만들어짐: ' + meta.get('error', 'AI 연결 없음'))
    if tl.get('form_fields'):      # 신청자·출장자 칸은 앱처럼 작성자(가상 조직의 담당)로
        for it in bp['sections'][0]['items']:
            if it['label'] in engines.FORM_ME:
                it['text'] = ''
        bp = engines.form_prefill(bp, PEOPLE)
    bp = checks.enforce_fixed(bp, json.loads(t['fixed'] or '[]'))
    return {'request': req, 'model': meta['model'], 'made': core.today_kr(), 'blueprint': bp}


def pngs(fmt, path, tmp):
    """문서 → 앞쪽 몇 장의 PNG 경로."""
    if fmt == 'hwp':
        py = os.environ.get('HWP_PY') or shutil.which('python')      # 'python'만 쓰면 Windows가 이 .venv 폴더부터 찾는다
        r = subprocess.run([py, corp.path(engines.HWP, 'scripts/hangul.py'), 'pages', path, tmp, '--dpi', '96'],
                           capture_output=True, timeout=300)
        files = sorted(glob.glob(os.path.join(tmp, 'page-*.png')))
    elif fmt == 'ppt':     # 사용자가 PowerPoint를 켜 두었으면 끄지 않는다
        was = b'POWERPNT.EXE' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq POWERPNT.EXE'], capture_output=True).stdout
        ps = (f"$pp = New-Object -ComObject PowerPoint.Application; $p = $pp.Presentations.Open('{path}', $true, $false, $false); "
              f"$i = 1; foreach ($s in $p.Slides) {{ if ($i -gt {MAX['ppt']}) {{ break }}; $s.Export('{tmp}\\s' + $i + '.png', 'PNG', 1280, 720); $i++ }}; "
              f"$p.Close(){'' if was else '; $pp.Quit()'}")
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps], capture_output=True, timeout=300)
        files = sorted(glob.glob(os.path.join(tmp, 's*.png')), key=lambda p: int(os.path.basename(p)[1:-4]))
    else:
        r = subprocess.run(['node', corp.path('koscom-webslide', 'scripts/check_deck.js'), path, '--shots', tmp], capture_output=True, timeout=600)
        files = sorted(glob.glob(os.path.join(tmp, 's[0-9]*.png')))
    if not files:
        raise RuntimeError('그림 없음: ' + (r.stdout + r.stderr).decode('utf-8', 'replace')[-400:])
    return files[:MAX[fmt]]


def save(d, files):
    for old in glob.glob(os.path.join(d, '*.webp')):
        os.remove(old)
    for i, p in enumerate(files, 1):
        im = Image.open(p).convert('RGB')
        if im.width > 1280:
            im = im.resize((1280, round(im.height * 1280 / im.width)), Image.LANCZOS)
        im.save(os.path.join(d, f'{i:02d}.webp'), 'WEBP', quality=80, method=6)
    return len(files)


def main(ids):
    core.init_db()
    app.sync_forms()
    corp.warm()
    ts = [t for t in core.rows(core.db(), 'select * from templates order by path, id') if not ids or t['id'] in ids]
    bad = {}

    def need(t):
        p = os.path.join(app._sample_dir(t), 'sample.json')
        if os.path.exists(p):
            return
        try:
            s = sample_bp(t)
        except Exception as e:
            bad[t['id']] = f'설계도: {e}'
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        left = json.dumps(s['blueprint'], ensure_ascii=False).count('(확인 필요)')
        print(f"설계도 {t['id']}: {s['blueprint']['title']}" + (f' · (확인 필요) {left}곳' if left else ''), flush=True)

    with cf.ThreadPoolExecutor(4) as ex:      # AI 호출만 병렬, 그리기(한글·PowerPoint COM)는 하나씩
        list(ex.map(need, ts))
    for t in ts:
        if t['id'] in bad:
            continue
        d = app._sample_dir(t)
        sp = os.path.join(d, 'sample.json')
        s = json.load(open(sp, encoding='utf-8'))
        info = json.loads(t['skill'] or '{}')
        try:
            tpl = app.template_for_render(t)
            make = lambda: engines.make(t['fmt'], s['blueprint'], tpl, PEOPLE, 'sample-' + t['id'].replace(':', '-'), 1)  # noqa: E731
            path, warns, _, eng = make()
            if any(c['fix'] for c in engines.check(s['blueprint'], warns if t['fmt'] == 'hwp' else ())):     # 검수 [자동 수정](doc_fix) 한 번
                bp, _ = engines.autofix(s['blueprint'], lambda xs: llm.shorten(xs, {'use_llm': True, 'fast': True}), warns)
                s['blueprint'] = checks.fix_skill(bp, {**info, 'fixed': json.loads(t['fixed'] or '[]')}) if info.get('id') else bp
                json.dump(s, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
                path, warns, _, eng = make()
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                n = save(d, pngs(t['fmt'], path, tmp))
            print(f"그림 {t['id']}: {n}장 · {eng['name']}" + (f' · 경고 {warns[:2]}' if warns else ''), flush=True)
        except Exception as e:
            bad[t['id']] = f'그림: {e}'
    for k, v in bad.items():
        print(f'실패 {k}: {v}')
    print(f"완료 {len(ts) - len(bad)}/{len(ts)}")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
