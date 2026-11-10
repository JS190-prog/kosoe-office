"""문서 테마 9가지의 시안과 미리보기 그림을 만든다(가상 자료, 서버 없이 엔진을 직접 부른다).

    python tests/doc_theme_previews.py <출력 폴더> [--only=a,b] [--no-web] [--gallery-only]

- <출력 폴더>/PPT_<id>_<이름>.pptx, 웹_<id>_<이름>.html : 같은 설계도를 테마별로 만든 결과물
- <출력 폴더>/미리보기/<id>/ppt_NN.png · web_01.png : 장별 그림
- <출력 폴더>/시안_한눈에.html : 테마 9가지를 한 화면에서 비교(그림을 안에 넣은 한 파일)
- static/doc_themes/thumb/<id>_ppt.webp · <id>_web.webp : 앱의 테마 고르기 화면에 쓰는 그림
그림은 설치된 Edge로 찍는다(playwright-core 필요: 환경 변수 PLAYWRIGHT_CORE 로 경로 지정).
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in (sys.stdout, sys.stderr):
    _s.reconfigure(encoding='utf-8', errors='replace')

import doc_themes  # noqa: E402
import ppt_chevron  # noqa: E402
import webslide  # noqa: E402
from core import ROOT  # noqa: E402

# 전사 스킬 잠금 파일만 읽는다(스킬 저장소를 당겨 오거나 바꾸지 않는다)
import corp  # noqa: E402
import skills  # noqa: E402
import yaml  # noqa: E402

corp.set_lock(yaml.safe_load(open(os.path.join(skills.REPO, 'registry', 'corp.lock.yaml'), encoding='utf-8')), 'preview')

args = [a for a in sys.argv[1:] if not a.startswith('--')]
OUT = os.path.abspath(args[0]) if args else os.path.join(ROOT, 'out_doc_themes')
only = next((a.split('=', 1)[1].split(',') for a in sys.argv if a.startswith('--only=')), None)
NO_WEB = '--no-web' in sys.argv
os.makedirs(OUT, exist_ok=True)

# 가상 자료 — 실제 고객·금액이 아니다
BP = {'title': '원장 클라우드 전환 고객 세미나 계획', 'sections': [
    {'heading': '행사 개요', 'items': [
        {'label': '일시', 'text': '2026. 12. 3 14:00~16:30, 반나절 일정으로 진행'},
        {'label': '장소', 'text': '본사 15층 강당, 온라인 중계 병행'},
        {'label': '대상', 'text': '가상 고객사 12곳의 IT 기획·운영 담당 45명'}]},
    {'heading': '세부 일정', 'items': [
        {'label': '진행', 'text': '발표 3건과 질의응답으로 구성', 'children': [{'text': '발표마다 20분, 질의응답 10분'}]},
        {'label': '자료', 'text': '발표 자료는 행사 3일 전 확정'}],
     'table': {'cols': ['시간', '내용', '담당'], 'rows': [['14:00', '개회 · 전환 배경', '영업 팩'], ['14:20', '전환 절차와 일정', '기획 팩'],
                                                    ['15:00', '운영 사례 (가상)', '운영 팩'], ['15:40', '질의응답 · 상담', '전원']]}},
    {'heading': '소요 예산', 'items': [{'label': '합계', 'text': '총 120만원, 부가세 별도 (가상 금액)'}],
     'table': {'cols': ['항목', '금액(만원)'], 'rows': [['장소·장비', '40'], ['다과', '25'], ['자료 제작', '35'], ['기념품', '20']]}},
    {'heading': '준비 일정', 'items': [
        {'label': '11. 17', 'text': '초청 대상 확정과 안내문 발송'},
        {'label': '11. 24', 'text': '발표 자료 초안 검토', 'children': [{'text': '수치와 고객사명은 검수로 대조'}]},
        {'label': '11. 30', 'text': '발표 자료 확정, 장소 점검'},
        {'label': '12. 3', 'text': '행사 진행과 상담 접수'},
        {'label': '12. 10', 'text': '결과 보고와 후속 조치 정리'}]},
]}
TPL = {'name': '행사 계획 보고', 'desc': '고객 세미나 준비 계획 (가상 자료)', 'chain_names': ['전사 koscom-doc-pack', '영업 팩']}
PEOPLE = {'dept': '금융영업1팀', '담당': '홍길동'}

SHOT = r'''
const path = require('path'), fs = require('fs');
const pw = require(process.env.PLAYWRIGHT_CORE || 'playwright-core');
const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
(async () => {
  const b = await pw.chromium.launch({channel: 'msedge', headless: true});
  for (const j of jobs) {
    const p = await b.newPage({viewport: {width: j.w, height: j.h}});
    await p.goto('file:///' + path.resolve(j.src).split(path.sep).join('/'), {waitUntil: 'load'});
    await p.waitForTimeout(j.wait || 300);
    await p.screenshot({path: j.out});
    await p.close();
  }
  await b.close();
})();
'''

jobs, made = [], []
for t in doc_themes.THEMES:
    tid, name = t['id'], t['name'].replace(' ', '')
    if '--gallery-only' in sys.argv or (only and tid not in only):
        continue
    jd = os.path.join(OUT, '_job', tid)
    os.makedirs(jd, exist_ok=True)
    pptx = os.path.join(OUT, f'PPT_{tid}_{name}.pptx')
    n = ppt_chevron.make(BP, TPL, PEOPLE, pptx, jd, tid)
    shots = os.path.join(OUT, '미리보기', tid)
    os.makedirs(shots, exist_ok=True)
    for i in range(1, n + 1):
        jobs.append({'src': os.path.join(jd, 'ppt', 'svg_output', f'{i:02d}.svg'), 'out': os.path.join(shots, f'ppt_{i:02d}.png'), 'w': 1280, 'h': 720})
    row = {'id': tid, 'name': t['name'], 'pptx': os.path.basename(pptx), 'pages': n, 'pptx_kb': os.path.getsize(pptx) // 1024}
    if not NO_WEB:
        html = os.path.join(OUT, f'웹_{tid}_{name}.html')
        webslide.make(BP, TPL, PEOPLE, html, jd, TPL['chain_names'], tid)
        jobs.append({'src': html, 'out': os.path.join(shots, 'web_01.png'), 'w': 1440, 'h': 810, 'wait': 2500})
        row.update(web=os.path.basename(html), web_mb=round(os.path.getsize(html) / 1e6, 2))
    made.append(row)
    print(row, flush=True)

jf = os.path.join(OUT, '_job', 'shots.json')
json.dump(jobs, open(jf, 'w', encoding='utf-8'))
js = os.path.join(OUT, '_job', 'shot.js')
open(js, 'w', encoding='utf-8').write(SHOT)
r = subprocess.run(['node', js, jf], capture_output=True, text=True, encoding='utf-8')
print('그림', len(jobs), '장', (r.stderr or '')[-300:])

# 앱의 테마 고르기 화면용 작은 그림
from PIL import Image  # noqa: E402

th = os.path.join(ROOT, 'static', 'doc_themes', 'thumb')
os.makedirs(th, exist_ok=True)
for m in made:
    for kind, src in (('ppt', 'ppt_01.png'), ('web', 'web_01.png')):
        p = os.path.join(OUT, '미리보기', m['id'], src)
        if os.path.exists(p):
            Image.open(p).convert('RGB').resize((480, 270), Image.LANCZOS).save(os.path.join(th, f"{m['id']}_{kind}.webp"), 'WEBP', quality=80)
json.dump(made, open(os.path.join(OUT, '_job', 'made.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


# 한눈에 보기 — 폴더에 있는 결과물과 그림으로 만든다
import base64  # noqa: E402
import io  # noqa: E402


def _uri(p):
    b = io.BytesIO()
    Image.open(p).convert('RGB').resize((480, 270), Image.LANCZOS).save(b, 'JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(b.getvalue()).decode()


cards = []
for t in doc_themes.THEMES:
    tid, name = t['id'], t['name'].replace(' ', '')
    pptx, web = f'PPT_{tid}_{name}.pptx', f'웹_{tid}_{name}.html'
    if not os.path.exists(os.path.join(OUT, pptx)):
        continue
    shots = sorted(f for f in os.listdir(os.path.join(OUT, '미리보기', tid)) if f.startswith('ppt_'))
    pick = [shots[i] for i in (0, 1, 2, 4, 5, len(shots) - 1) if i < len(shots)]
    th = ''.join(f'<img src="{_uri(os.path.join(OUT, "미리보기", tid, n))}" alt="">' for n in dict.fromkeys(pick))
    links = f'<a href="{pptx}">PPT 파일 ({os.path.getsize(os.path.join(OUT, pptx)) // 1024}KB, {len(shots)}장)</a>'
    if os.path.exists(os.path.join(OUT, web)):
        links += f' · <a href="{web}">같은 테마의 웹슬라이드 ({os.path.getsize(os.path.join(OUT, web)) / 1e6:.1f}MB)</a>'
    cards.append(f'<section><h2>{tid.upper()} · {t["name"]}</h2><p>{t["desc"]}</p><div class="t">{th}</div><p class="f">{links}</p></section>')
page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>코쇠오피스 PPT 디자인 시안 9가지</title>'
        '<style>body{margin:0;padding:32px 40px 60px;font:500 15px/1.6 "KoPub돋움체 Medium","Malgun Gothic",sans-serif;background:#f1f1f3;color:#2b2b2e}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:0}'
        'p{margin:2px 0 10px;color:#6e6e73}section{background:#fff;border:1px solid #dcdce0;padding:16px 18px;margin-top:18px}.t{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}'
        '.t img{width:100%;display:block;border:1px solid #e6e6ea}.f{margin:10px 0 0}a{color:#00338d}</style>'
        '<h1>코쇠오피스 PPT 디자인 시안 9가지</h1><p>같은 설계도(가상 자료)를 테마만 바꿔 만든 결과입니다. 그림은 표지·목차·카드·표와 그래프·목록·맺음 순서입니다. PPT는 도형과 글자를 그대로 고칠 수 있습니다.</p>'
        + ''.join(cards) + '</html>')
open(os.path.join(OUT, '시안_한눈에.html'), 'w', encoding='utf-8').write(page)
print('한눈에 보기:', len(cards), '테마')
