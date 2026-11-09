# 코쇠오피스 (Kosoe Office)

회사 양식에 맞춰 **PPT · 웹슬라이드 · 한글** 문서를 만들고, 수정과 검수까지 이어 주는 사내 문서 도우미입니다.
대표 문서 몇 건이면 **전사 공용 스킬을 상속한 우리 부서·나의 스킬**이 만들어지고, 그 스킬은 **Git 저장소에서 버전·승인 관리**됩니다.

- 서버가 없습니다. 이 저장소를 내려받아 **각자 PC에서 실행**합니다(`localhost`).
- AI는 **각자의 Claude Code 구독 CLI**로 부릅니다(API 키 불필요). 로그인이 안 되면 규칙 기반 보조 모드로 계속 동작합니다.
- 사람 사이에 공유되는 것(스킬·승인·전사 스킬 버전)은 **Git**이 맡고, 문서·작업 기록은 각자 PC(`%USERPROFILE%\.kosoe`)에 남습니다.
- 조직·사람·고객·숫자는 모두 **가상**입니다.

## 설치 (Windows)

| # | 할 일 |
|---|---|
| 1 | Python 3.10+, Java 8+, Git, GitHub CLI(`gh`) 설치 |
| 2 | Claude Code 설치 후 본인 계정으로 로그인 (`python kosoe.py login`) |
| 3 | `git clone https://github.com/humanist96/kosoe-office` |
| 4 | `.\setup.ps1` — 패키지 설치 · `gh auth login` · 스킬 저장소와 전사 공용 스킬 받기 · 점검 |
| 5 | `python kosoe.py` → 브라우저에서 http://localhost:8810 |

> 아래 명령의 `python`은 macOS에서는 가상환경을 켠 뒤(`source .venv/bin/activate`) 쓰거나 `python3`로 바꿔 씁니다.

## 설치 (macOS)

| # | 할 일 |
|---|---|
| 1 | `brew install python git gh openjdk` (openjdk는 설치 끝에 나오는 안내대로 `java`가 PATH에 잡히게 연결) |
| 2 | Claude Code 설치(`claude` 명령, 2.x) 후 본인 계정으로 로그인 — `claude auth login` |
| 3 | `git clone https://github.com/humanist96/kosoe-office && cd kosoe-office` |
| 4 | `./setup.sh` — `.venv` 가상환경 · 패키지 설치 · `gh auth login` · 스킬 저장소와 전사 공용 스킬 받기 · 점검 |
| 5 | `source .venv/bin/activate && python kosoe.py` → http://localhost:8810 |

macOS에서 달라지는 점
- PPT 미리보기는 PowerPoint 대신 **장별 SVG**(같은 디자인 원본)로 보여 줍니다. 받은 .pptx는 Keynote·PowerPoint for Mac에서 열립니다(KoPub돋움체 설치 권장).
- 한글(.hwp)은 한컴오피스 Mac 또는 한컴독스(웹)로 엽니다. 앱의 「미리보기」는 파일에서 읽은 문단을 보여 줍니다.
- 데이터 폴더는 `~/.kosoe`, Claude CLI는 PATH의 `claude`(2.x) → `~/.local/bin/claude` → 데스크톱 앱 내장 순으로 찾습니다. 다르면 `.env`의 `KOSOE_CLAUDE_CLI`.

저장소 접근 권한이 곧 사용 권한입니다: 앱 저장소, 스킬 저장소(`humanist96/kosoe-office-skills`), 전사 공용 스킬 4종(그중 `koscom-doc-pack`은 비공개)에 읽기 권한이 있어야 합니다.

```
python kosoe.py doctor --smoke --ping   # 설치 점검(한글·PPT·웹 1건씩 생성, AI 1회 호출)
python kosoe.py sync                    # 스킬 저장소 · 전사 공용 스킬 당겨오기
python kosoe.py seed                    # 시연용 가상 자료(seed/out)
python kosoe.py reset-demo              # 시연 초기화
```

## 구조

```
GitHub
├─ kosoe-office          이 저장소 — 앱(클라이언트) 소스
├─ kosoe-office-skills   스킬 정본: registry/corp.lock.yaml(전사 스킬 SHA·잠금 키) · corp.forms.yaml · skills/org · skills/user
└─ 전사 공용 스킬 4종     koscom-doc-pack(라우터·ppt-master) · koscom_hangul_skill · koscom_webslide · koscom-kosoe-illustrations

PC (python kosoe.py)
├─ app.py          Flask API · 권한 · 승인 흐름 · 감사 로그
├─ corp.py         전사 스킬을 잠금 SHA로 받아 둠(부분 복제) · 템플릿은 매번 git 객체에서 꺼냄
├─ skills.py       스킬 저장소: 상속 해석 · 검사 · 브랜치/PR/병합/태그 · 복구
├─ engines.py      설계도 → 한글(전사 hwp 렌더러) · PPT(ppt_chevron.py → ppt-master) · 웹(webslide.py → koscom-webslide)
├─ checks.py       팩 규칙 검수 · 원본값 대조(수정 누락)
├─ llm.py          AI 어댑터 한 곳(Claude Code CLI · API · 사내 모델 · 규칙 기반) · 마스킹
└─ static/         화면(SPA): 새 문서 · 양식 · 스킬 · ★스킬 만들기 · 검수 · 승인함 · 대시보드
```

## 스킬과 상속

- 스킬 1개 = 폴더 1개 = `kosoe-skill.yaml` 1개. `extends`로 전사 공용 스킬(`corp:`)과 상위 스킬(`skill:`)을 상속합니다.
- 해석 순서: 전사 → 본부 → 팀 → 개인. 고정 문구·용어·검수 규칙은 합치고, 같은 항목은 아래가 덮습니다.
- 전사 잠금 항목(CI 색·글꼴·로고·등급 표기·한글 기본 양식)은 하위 스킬이 바꿀 수 없습니다.
- 등록·변경 = 브랜치 + PR, 승인 = PR 승인 코멘트 + 병합 + 태그 `<id>@v<버전>`. 개인 스킬은 자동 검사 통과 시 바로 병합됩니다.
- 문서마다 만들 때 쓴 전사 스킬 SHA와 스킬 버전을 기록합니다. 승인된 변경은 **다음 문서부터** 반영됩니다.

## 사내 보호 도구(PIA)와 함께 쓰기

사내 보호 도구가 디스크의 `.hwp`·`.pptx`를 암호화할 수 있습니다. 코쇠오피스는 보호 도구를 해제하거나 우회하지 않고,
입력 템플릿을 생성할 때마다 Git 객체에서 새로 꺼내 쓰고, python-pptx 기본 서식은 PyPI 원본을 코드에 넣어 메모리로 공급합니다.
결과 파일이 암호화되는 것은 사내 정상 동작이며 사내 뷰어로 열립니다.
