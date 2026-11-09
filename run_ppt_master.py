"""전사 스킬 ppt-master의 스크립트를 실행하되, python-pptx 기본 템플릿을 메모리에서 공급한다.

사내 보호 도구가 site-packages/pptx/templates/default.pptx 를 암호화(.pia)하면 python-pptx가 빈 발표 파일을
만들지 못한다. PyPI 원본 default.pptx를 base64로 코드에 넣어 두고(디스크에 .pptx를 두지 않음) 그것을 쓴다.
usage: python run_ppt_master.py <script.py> [args...]
"""
import base64
import io
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pptx.api  # noqa: E402
from pptx_default_b64 import DATA  # noqa: E402

_BYTES = base64.b64decode(DATA)
pptx.api._default_pptx_path = lambda: io.BytesIO(_BYTES)


def patch():
    """같은 프로세스 안에서 Presentation()을 쓸 때도 메모리 템플릿을 쓰게 한다."""
    pptx.api._default_pptx_path = lambda: io.BytesIO(_BYTES)


if __name__ == '__main__':
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding='utf-8', errors='replace')
    runpy.run_path(script, run_name='__main__')
