# 수정 레시피 (revision 모드)

모든 수정은 `command.batch` 하나로 묶어 실행 취소 한 번에 되돌릴 수 있게 한다. 수정 전 대상 객체 id와 값을 `job.json`의 `changes`에 적는다.

```python
from vc import cmd
cmd("command.batch", {"label": "요청서 반영", "commands": [
    {"command": "text.setStyle", "params": {"ids": [280, 279], "font": "Noto Serif KR", "style": "Regular", "tracking": -30}},
    {"command": "edit.clear", "params": {"ids": [301]}},
    {"command": "select.set", "params": {"ids": [302, 303, 304, 305, 306, 307, 308]}},
    {"command": "object.group", "params": {}},
    {"command": "object.move", "params": {"dx": -5.018, "dy": 0}},
]})
```

## 대상 찾기

- 문자: `document.find {kind:"Type", text:"제품명"}` → `document.node {id}`로 run별 스타일 확인.
- 영역 안의 객체: `document.find {intersects:[x, y, w, h]}` (아이콘·마크처럼 이름 없는 패스 묶음).
- 판 구분이 있는 문서는 `document.inspect`의 `fill`(스와치 이름 포함)로 어느 판인지 본다.

## 글꼴 변경

1. 새 폰트를 등록한다(`fonts.py --want`). `text.fontList {family}`로 스타일 이름을 확인한다.
2. 크기·색·위치는 그대로 두고 `text.setStyle {font, style}`. 자간은 **원본 설정값**(`pdf_text_dump.py`)으로 맞춘다.
3. 요청이 "글씨체 변경"뿐이면 크기를 바꾸지 않는다. 폭이 크게 달라지면 그 사실을 보고하고, 크기 조정은 사용자에게 묻는다.

## 삭제 후 가운데 정렬

- "후면 가운데"의 기준은 후면 패널의 기하 중심이다. 튜브·용기의 전면/후면 사각형 좌표로 계산하고,
  바코드·아이마크 같은 기존 축과 비교해 함께 보고한다(예: 패널 434.83 pt, 바코드 434.89 pt).
- 여러 패스로 된 마크는 먼저 그룹으로 묶은 뒤 `dx`만 옮긴다(세로 위치 유지).

## 문구 교체

- `text.setText {id, text}`는 첫 run의 스타일을 유지한다. 굵게 등 부분 스타일은 `text.setRangeStyle`(UTF-8 바이트 범위)로 다시 준다.
- 영역 문자는 결과의 `overflow`를 확인한다.

## 저장과 결과물

1. `file.saveAs {path: 04_output/<원본명>_수정_v01.ai}` — 원본은 절대 덮어쓰지 않는다.
2. `document.export {path: …_preview.png, ppi: 150}`
3. `document.exportPdf {path: …_인쇄용_아웃라인.pdf, preset: "High Quality Print", advanced: {outlineText: true}}`
4. `verify_print_pdf.py <pdf> --original 01_source/원본.ai` — 폰트 0, 텍스트 0, 별색이 원본과 같음.
5. `compare.py --original 01_source/원본.ai --other 04_output/…_인쇄용_아웃라인.pdf` — 바뀐 영역이 요청한 곳뿐인지 확인.
