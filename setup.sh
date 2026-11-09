#!/usr/bin/env bash
# 코쇠오피스 설치 — macOS / Linux:  ./setup.sh
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-python3}

echo "1) 필요한 도구 확인"
for t in "$PY" git gh java; do
  if ! command -v "$t" >/dev/null 2>&1; then
    case "$t" in
      gh)   echo "   ✗ gh(GitHub CLI) 없음 → brew install gh" ;;
      java) echo "   ✗ java 없음 → brew install openjdk 후 안내대로 PATH 연결" ;;
      *)    echo "   ✗ $t 없음 → brew install python git" ;;
    esac
  else
    echo "   ✓ $t"
  fi
done

echo "2) 파이썬 패키지 설치 (가상환경 .venv)"
if [ ! -d .venv ]; then "$PY" -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "   .env 를 만들었습니다(기본: Claude Code 구독 CLI)"; }

echo "3) GitHub 로그인 확인 (스킬 저장소 · 전사 공용 스킬 접근)"
gh auth status >/dev/null 2>&1 || gh auth login

echo "4) 스킬 저장소 · 전사 공용 스킬 받기"
python kosoe.py sync

echo "5) 점검"
python kosoe.py doctor --smoke || true

echo
echo "Claude 로그인이 안 되어 있으면: source .venv/bin/activate && python kosoe.py login"
echo "실행: source .venv/bin/activate && python kosoe.py   →  http://localhost:8810"
