"""시연 준비(녹화 전): 초기화(개인 스킬 정리) → 예열 → 2:15 장면용 스킬 분석·검증 미리 실행.
python tests/demo_prep.py   (앱이 http://localhost:8810 에서 실행 중이어야 한다)
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_skillgen import call  # noqa: E402

t = time.time()
call('/api/login', {'uid': 'u4'})
call('/api/demo/reset', {'user_skills': True})
print(f'초기화 {time.time() - t:.1f}s')
call('/api/login', {'uid': 'u1'})
t = time.time()
w = call('/api/demo/warm?ai=1', {})
print(f"예열 {time.time() - t:.1f}s", w['sec'], 'AI', w['ai'].get('ms'))
t = time.time()
r = subprocess.run([sys.executable, '-u', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'e2e_skillgen.py'), '--no-submit'])
print(f'스킬 분석·검증 미리 실행 {time.time() - t:.1f}s rc={r.returncode}')
sys.exit(r.returncode)
