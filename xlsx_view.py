"""엑셀(.xlsx) 미리보기 — 인쇄 영역을 HTML 표로 옮긴다(글꼴 크기 · 굵게 · 밑줄 · 맞춤 · 테두리 · 채우기 · 병합 · 숫자 표시 · 그림).

화면으로 모양을 보는 용도다. 엑셀이 그리는 것과 똑같지는 않다(글꼴은 화면의 글꼴, 줄 바꿈 위치는 다를 수 있다) —
정확한 모양은 「Excel로 열기」로 본다. 파일은 이 PC 밖으로 나가지 않는다.
"""
import base64
import html
import re

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, range_boundaries

EMU_PX = 9525
LINE = {'thin': '1px solid', 'medium': '2px solid', 'thick': '3px solid', 'double': '3px double', 'hair': '1px dotted', 'dotted': '1px dotted',
        'dashed': '1px dashed', 'mediumDashed': '2px dashed', 'dashDot': '1px dashed', 'mediumDashDot': '2px dashed', 'dashDotDot': '1px dotted',
        'mediumDashDotDot': '2px dotted', 'slantDashDot': '2px dashed'}


def _rgb(color, default=None):
    v = getattr(color, 'rgb', None)
    return '#' + v[-6:] if isinstance(v, str) and re.fullmatch(r'[0-9A-Fa-f]{6,8}', v) else default


def _text(c):
    v = c.value
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        f = c.number_format or 'General'
        if v == 0 and '"-"' in f:
            return '-'
        if '#,##0' in f:
            dec = len(f.split(';')[0].split('.')[1].rstrip('_) ').replace('_', '')) if '.' in f.split(';')[0] else 0
            return f'{v:,.{dec}f}'
        return str(int(v)) if v == int(v) else str(v)
    return str(v)


def _side(s):
    return f"{LINE.get(s.style, '1px solid')} {_rgb(s.color, '#000')}" if s is not None and s.style else None


def to_html(path, max_rows=200):
    """→ {'html': 표, 'width': px, 'sheet': 시트 이름, 'rows': 행 수}. 첫 시트의 인쇄 영역(없으면 쓰인 범위)만 그린다."""
    wb = load_workbook(path)
    ws = wb.worksheets[0]
    area = ws.print_area
    area = (area if isinstance(area, str) else (area[0] if area else '')) or ws.dimensions
    c0, r0, c1, r1 = range_boundaries(area.split('!')[-1].replace('$', ''))
    r1 = min(r1, r0 + max_rows - 1)
    col_w = {c: int((ws.column_dimensions[get_column_letter(c)].width or 8.43) * 8 + 5) for c in range(c0, c1 + 1)}
    row_h = {r: round((ws.row_dimensions[r].height or ws.sheet_format.defaultRowHeight or 15) * 96 / 72) for r in range(r0, r1 + 1)}
    spans, covered = {}, set()
    for mr in ws.merged_cells.ranges:
        spans[(mr.min_row, mr.min_col)] = (mr.max_row - mr.min_row + 1, mr.max_col - mr.min_col + 1)
        covered |= {(r, c) for r in range(mr.min_row, mr.max_row + 1) for c in range(mr.min_col, mr.max_col + 1)} - {(mr.min_row, mr.min_col)}
    out = [f'<table class="xlv-t" style="border-collapse:collapse;table-layout:fixed;width:{sum(col_w.values())}px;background:#fff;color:#000">',
           '<colgroup>' + ''.join(f'<col style="width:{w}px">' for w in col_w.values()) + '</colgroup>']
    for r in range(r0, r1 + 1):
        out.append(f'<tr style="height:{row_h[r]}px">')
        for c in range(c0, c1 + 1):
            if (r, c) in covered:
                continue
            cell = ws.cell(row=r, column=c)
            rs, cs = spans.get((r, c), (1, 1))
            f, a, b = cell.font, cell.alignment, cell.border
            st = [f'font-size:{f.sz or 11}pt', 'padding:0 3px', 'overflow:visible', f"vertical-align:{ {'center': 'middle', 'top': 'top'}.get(a.vertical, 'bottom')}"]
            if f.b:
                st.append('font-weight:700')
            if f.u:
                st.append('text-decoration:underline')
            col = _rgb(f.color)
            if col and col.lower() != '#000000':
                st.append(f'color:{col}')
            num = isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool)
            st.append(f"text-align:{a.horizontal if a.horizontal in ('left', 'center', 'right') else ('right' if num else 'left')}")
            st.append('white-space:pre-wrap;word-break:break-all' if a.wrap_text else 'white-space:pre')
            if cell.fill is not None and cell.fill.fill_type == 'solid':
                bg = _rgb(cell.fill.fgColor)
                if bg and bg.lower() != '#ffffff':
                    st.append(f'background:{bg}')
            for name in ('top', 'right', 'bottom', 'left'):
                s = _side(getattr(b, name))
                if s:
                    st.append(f'border-{name}:{s}')
            span = (f' rowspan="{rs}"' if rs > 1 else '') + (f' colspan="{cs}"' if cs > 1 else '')
            text = html.escape(_text(cell))
            if text and not a.wrap_text and 'text-align:right' in st:
                # 엑셀은 오른쪽 맞춤 글이 칸보다 길면 왼쪽 빈 칸으로 넘친다 — 글 방향을 뒤집어 왼쪽으로 넘치게 한다
                span += ' dir="rtl"'
                text = f'<span dir="ltr" style="unicode-bidi:isolate">{text}</span>'
            out.append(f'<td{span} style="{";".join(st)}">{text}</td>')
        out.append('</tr>')
    out.append('</table>')
    # 그림(로고 등): 놓인 칸의 왼쪽 위를 기준으로 표 위에 겹쳐 놓는다
    imgs = []
    for img in ws._images:
        try:
            m = img.anchor._from
            if not (r0 <= m.row + 1 <= r1 and c0 <= m.col + 1 <= c1):
                continue
            x = sum(col_w[c] for c in range(c0, m.col + 1)) + round(m.colOff / EMU_PX)
            y = sum(row_h[r] for r in range(r0, m.row + 1)) + round(m.rowOff / EMU_PX)
            ext, to = getattr(img.anchor, 'ext', None), getattr(img.anchor, 'to', None)
            if ext is not None:                              # 시트에 놓인 크기(그림 파일의 원래 크기가 아니다)
                w, h = round(ext.width / EMU_PX), round(ext.height / EMU_PX)
            elif to is not None:
                w = sum(col_w.get(c, 69) for c in range(c0, to.col + 1)) + round(to.colOff / EMU_PX) - x
                h = sum(row_h.get(r, 20) for r in range(r0, to.row + 1)) + round(to.rowOff / EMU_PX) - y
            else:
                w, h = int(img.width), int(img.height)
            data = img._data()
            mime = 'image/png' if data[:4] == b'\x89PNG' else 'image/jpeg'
            imgs.append(f'<img alt="" src="data:{mime};base64,{base64.b64encode(data).decode()}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px">')
        except Exception:
            continue
    width = sum(col_w.values())
    return {'html': f'<div class="xlv-page" style="position:relative;width:{width}px;margin:auto">{"".join(out)}{"".join(imgs)}</div>',
            'width': width, 'sheet': ws.title, 'rows': r1 - r0 + 1}
