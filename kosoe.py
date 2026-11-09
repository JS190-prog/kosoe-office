"""코쇠오피스 실행 진입점.

python kosoe.py               앱 실행 → http://localhost:8810
python kosoe.py doctor [--smoke] [--ping]   설치 점검
python kosoe.py login         Claude Code 구독 로그인
python kosoe.py sync          스킬 저장소·전사 스킬 당겨오기
python kosoe.py seed          시연용 가상 자료 만들기(seed/out)
python kosoe.py reset-demo    시연 초기화(로컬 DB·결과물, 열린 PR 닫기)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
for s in (sys.stdout, sys.stderr):
    s.reconfigure(encoding='utf-8', errors='replace')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if cmd == 'doctor':
        import doctor
        return doctor.main()
    if cmd == 'login':
        import llm
        exe = llm.cli_path()
        if not exe:
            print('Claude Code CLI를 찾지 못했습니다. 설치 후 .env의 KOSOE_CLAUDE_CLI에 경로를 넣어 주세요.')
            return 1
        print(f'Claude CLI: {exe}\n브라우저가 열리면 본인 Claude 계정으로 로그인하세요.\n')
        subprocess.run([exe, 'auth', 'login'], env=llm._cli_env())
        st = llm.cli_status(force=True)
        print('✅ 로그인 완료' if st['ready'] else f'⚠️ 아직 로그인 안 됨: {st["detail"]}')
        return 0
    if cmd == 'sync':
        import corp
        import skills
        st = skills.ensure(force=True)
        print(f"스킬 저장소 {skills.SLUG}: {st['mode']} {st['head'][:7]} {st['error']}")
        corp.warm()
        return 0
    if cmd == 'seed':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        sys.path.insert(0, os.path.join(ROOT, 'seed'))
        import make_seed
        make_seed.main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'seed', 'out'))
        return 0
    if cmd == 'reset-demo':
        import app
        app.sync_forms(force=True)
        app.reset_demo('--user-skills' in sys.argv)
        print('시연 데이터를 초기화했습니다(로컬 DB·결과물·첨부, 스킬 저장소의 열린 PR).')
        return 0
    if cmd == 'run':
        import app
        app.boot()
        port = int(os.environ.get('PORT') or app.CFG['port'])
        print(f'코쇠오피스 — http://localhost:{port}')
        app.app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
