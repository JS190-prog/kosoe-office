"""git / gh 실행 도우미. 비공개 저장소도 사용자 본인의 gh 로그인으로 접근한다(전역 설정은 바꾸지 않음)."""
import os
import shutil
import subprocess

CRED = ['-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential']
GIT_ENV = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}


class GitError(RuntimeError):
    pass


def run(args, cwd=None, timeout=120, check=True, binary=False):
    r = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout, env=GIT_ENV)
    if binary:
        if check and r.returncode != 0:
            raise GitError(f"{' '.join(args[:4])}: {r.stderr.decode('utf-8', 'replace')[-300:]}")
        return r.stdout
    out = (r.stdout + r.stderr).decode('utf-8', 'replace').strip()
    if check and r.returncode != 0:
        raise GitError(f"{' '.join(a for a in args[:4] if not a.startswith('credential'))}: {out[-300:]}")
    return out


def git(*a, cwd=None, **k):
    return run(['git', '-c', 'core.quotepath=false', *a], cwd=cwd, **k)


def git_remote(*a, cwd=None, **k):
    """원격과 통신하는 git 명령(fetch·push·clone) — gh 자격 증명 사용."""
    return run(['git', *CRED, *a], cwd=cwd, **k)


def gh(*a, cwd=None, **k):
    return run(['gh', *a], cwd=cwd, **k)


def have_gh():
    if not shutil.which('gh'):
        return False
    return subprocess.run(['gh', 'auth', 'status'], capture_output=True).returncode == 0


_who = {}


def identity():
    """커밋 작성자 = 이 PC에서 gh에 로그인한 사람."""
    if not _who:
        try:
            login = gh('api', 'user', '-q', '.login', timeout=30).strip()
            uid = gh('api', 'user', '-q', '.id', timeout=30).strip()
            _who.update(name=login, email=f'{uid}+{login}@users.noreply.github.com', login=login)
        except Exception:
            _who.update(name='kosoe-office', email='kosoe-office@localhost', login='')
    return _who
