# VectorCraft 제어 채널 요약

공식 문서: <https://github.com/storytold/vectorcraft> 의 `docs/control-protocol.md`, `docs/mcp.md`(명령·파라미터 전체),
`docs/file-format-parity.md`(.ai/PDF 읽기·쓰기), `docs/production-preflight.md`. 아래는 실제 작업(VectorCraft 0.24.1, macOS)에서
확인한 내용이다. 버전이 바뀌면 `vc.py help <명령>`으로 파라미터를 다시 확인한다.

## 연결

- 앱을 `--control <port>`로 실행해야 열린다(기본 7979, 127.0.0.1 전용, 인증 없음 → 작업할 때만 켠다). Dock·Finder로 연 앱은 포트가 없다.
- macOS에서 이미 실행 중인 앱에는 인자가 전달되지 않는다. `vc_launch.py --start`는 실행 중이면 멈추고(코드 3) 사용자 확인을 요구한다.
  열린 문서가 없거나 모두 저장된 상태면 `vc.py call app.quit`으로 종료한다(수정된 문서가 있으면 `saveChanges` 대화상자가 뜬다).
- `--automation-read-root` / `--automation-write-root`로 읽기·쓰기 경로를 작업 폴더로 제한한다. 루트 밖 경로는 오류.
  VectorCraft 자체 폴더(환경설정, Fonts)는 제한 대상이 아니다.
- 한 줄에 JSON 하나: `{"id", "method", "params"}`. 엔진 명령은 `engine.execute {command, params}`, 목록과 파라미터 설명은 `engine.commands`.
  화면 상태는 `ui.inspect`(열린 문서, 대화상자, 진행 중인 백그라운드 저장).
- 60초 안에 답이 없으면 `timeout`. "will not run"이면 재시도 가능, "still running"이면 문서를 확인한 뒤 판단.
- 헤드리스 대안: 릴리스의 별도 zip `vectorcraft-cli-<ver>-macos-universal.zip`(`vectorcraft-cli run`, `vectorcraft-cli mcp`).
  설치되어 있지 않다면 내려받기 전에 사용자 승인을 받는다.

## 자주 쓰는 명령 (engine.execute)

| 목적 | 명령 | 메모 |
|---|---|---|
| 열기 | `document.open {path, editingData?, textAs?}` | `editingData:false` = PDF 부분만, `"always"` = 편집 데이터 강제 |
| 문서 구조 | `document.inspect {ids?, kind?, depth?}` | bounds는 **em 박스**(문자는 잉크가 아님), 좌표는 아트보드 왼쪽 위 원점, y 아래 방향 |
| 객체 하나 | `document.node {id}` | 문자 run별 font/style/size/tracking/h_scale/fill/xf(기준선 위치) |
| 찾기 | `document.find {kind:"Type", text?, intersects?:[x,y,w,h]}` | |
| 묶어서 실행 | `command.batch {label, commands:[{command, params}]}` | 실행 취소 한 번, 오류 시 전체 롤백 |
| 글자 스타일 | `text.setStyle {ids, font, style, size, tracking, leading, fill, justify, start?, end?}` | start/end는 **UTF-8 바이트** |
| 부분 스타일 | `text.setRangeStyle {id, start, end, style/…}` | 굵게 등 |
| 장평 | `text.setFormat {ids, hScale}` | |
| 새 문자 | `text.create {x, y, text, font, style, size, area?}` | 포인트 문자의 y는 **기준선** |
| 윤곽선 | `type.createOutlines {}` | 선택 대상 |
| 정렬·이동 | `object.align`, `object.move {ids, dx, dy, copy?}`, `object.setBounds {x,y,width,height,reference}` | setBounds는 선택 대상 |
| 칠 | `paint.setFill {ids, swatch|color}`, `paint.setStroke {ids, none|color}`, `stroke.set {ids, weight}` | |
| 별색 | `swatch.new {name, color, spot:true}` | 판 이름이 곧 스와치 이름 |
| 레이어 | `layer.new {name, top}`, `layer.setCurrent {id}`, `layer.setProps {id, template, printable, visible}` | 템플릿 레이어는 인쇄·내보내기에서 빠짐 |
| 이미지 배치 | `file.place {path, link:false, rect:[x,y,w,h]}` | |
| 트레이스 | `imageTrace.makeAndExpand {id, params:{mode:"logo", logoColors:["#000000"], ignoreWhite:true}}` | 평면 로고용 |
| 폰트 | `text.missingFonts`, `text.fonts`, `text.fontList {family?}`, `text.findFontFiles`, `text.addFontFiles` | addFontFiles = 앱 전용 폰트 폴더로 복사 |
| 저장 | `file.saveAs {path}` / `document.save {}` | .ai는 백그라운드 저장: `ui.inspect`로 끝난 것을 확인 |
| 내보내기 | `document.export {path, rect?, ppi?}`, `document.exportPdf {path, preset, advanced:{outlineText:true}}` | PDF 프리셋 `High Quality Print`는 색 변환 없음 → 별색 유지 |
| 닫기 | `file.close {}` | 수정된 문서는 `{"pending":"saveChanges"}` → `ui.dialog.set {field:"discard", value:true}` + `ui.dialog.confirm` |

## 확인된 주의점

- **`.ai` 저장 경고**: 다른 앱(Illustrator)용 편집 데이터에서 문자의 스와치 연결, 커닝, OpenType 기능 등이 빠진다.
  Illustrator에서 열면 별색으로 칠한 문자가 별색 판에서 떨어질 수 있다. **인쇄소에는 아웃라인 PDF를 보낸다.**
- 템플릿 레이어는 "인쇄 안 되는 흐린 레이어"로 저장된다.
- `document.preflight`(프로덕션 프리플라이트)는 0.24.1에 없다. 대신 `text.missingFonts`, `document.find`의 overflow, `verify_print_pdf.py`를 쓴다.
- `paragraph`의 "양끝 정렬, 마지막 줄 왼쪽"이 없다. 줄마다 문단을 나누고 마지막 줄만 왼쪽 정렬한다(`layout_kit.Doc.paragraph`).
- 응답이 수백 KB일 수 있다(`engine.commands` ≈ 760KB, `document.inspect` 전체). 파일로 받는다(`--out`).
- `layer.new {top:true}`는 새 레이어를 매번 맨 위에 쌓는다. 일찍 만든 가이드 레이어는 나중 레이어(바탕 등) 아래에 깔리므로 마지막에 `layer.move`로 올린다(`Doc.raise_layer`).
  `document.inspect`의 `layers`는 위→아래 순서다(첫 항목이 맨 위).
- PNG 내보내기(`document.export`)는 인쇄 안 함(`printable:false`) 레이어도 그린다(템플릿 레이어는 빠짐). PDF 내보내기는 기본으로 뺀다(`includeNonPrinting:true`로 포함).
- 별색 스와치 라이브러리에 PANTONE이 없다(내장: Web Safe, Pastels 등). PANTONE 번호는 사람이 지정한다.
- CMYK 문서에서 CMYK 색역 밖의 별색은 화면 값이 바뀌어 보인다(예: #B9A3E7 → #A692C4). 인쇄는 별색 판으로 나간다.
- 0.24.1에는 `app.toast`(창 위 메시지)가 없다. 시연 캡션은 비인쇄 레이어의 글자로 보여준다.
- 화면 확대: `ui.menu.invoke {command:"view.fitArtboard"}`(엔진 명령이 아니라 UI 명령).
