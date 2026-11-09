# 코쇠오피스 설치 — PowerShell에서: .\setup.ps1
$ErrorActionPreference = 'Stop'
Write-Host '1) 파이썬 패키지 설치' -ForegroundColor Cyan
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host '   .env 를 만들었습니다(기본: Claude Code 구독 CLI)' }
Write-Host '2) GitHub 로그인 확인 (스킬 저장소·전사 스킬 접근)' -ForegroundColor Cyan
gh auth status
if ($LASTEXITCODE -ne 0) { gh auth login }
Write-Host '3) 스킬 저장소 · 전사 공용 스킬 받기' -ForegroundColor Cyan
python kosoe.py sync
Write-Host '4) 점검' -ForegroundColor Cyan
python kosoe.py doctor --smoke
Write-Host ''
Write-Host 'Claude 로그인이 안 되어 있으면: python kosoe.py login' -ForegroundColor Yellow
Write-Host '실행: python kosoe.py  →  http://localhost:8810' -ForegroundColor Green
