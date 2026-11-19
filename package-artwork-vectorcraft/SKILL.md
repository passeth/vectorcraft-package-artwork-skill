---
name: "package-artwork-vectorcraft"
description: "VectorCraft 데스크톱 앱을 제어 채널로 자동 조작해 화장품 부자재(튜브·용기·라벨·단상자) 인쇄 데이터를 수정하거나 새로 만든다. 부자재 문안수정 요청서(xlsx)와 원본 .ai로 폰트 교체·객체 삭제·정렬·문구 수정을 반영하고, 디자이너 시안 PNG나 생성 AI 시안 이미지(목업)·전성분 docx·용기 규격으로 별색 인쇄용 필름(튜브는 단면 모델로 펼침, 전성분 근거 특장점·표시사항 포함)을 제작해 수정본 .ai·텍스트 아웃라인 인쇄용 PDF·미리보기·보고서를 작업 폴더 구조에 맞춰 낸다. '아트웍 수정', '부자재 수정요청서 반영', '인쇄 데이터 수정', '라벨/용기인쇄 데이터 제작', 'AI 시안을 필름으로', '튜브 필름 제작', 'VectorCraft로 작업' 요청에 사용한다."
---

# 부자재 인쇄 데이터 수정·제작 (VectorCraft)

## 경계

- **원본은 덮어쓰지 않는다.** 작업 폴더에 복사본을 두고 결과는 `04_output`에 차수(v01…)로 새로 쓴다.
- 실행 중인 VectorCraft를 종료하기 전에 열린 문서와 저장 여부를 확인하고, 수정된 문서가 있으면 사용자에게 묻는다.
- 폰트는 VectorCraft 전용 폰트 폴더에만 등록한다(시스템 설치 아님). 회사가 라이선스를 가진 폰트만 쓴다.
- `vectorcraft-cli` 등 새 프로그램을 내려받아야 하면 먼저 승인을 받는다.
- 결과는 **디자이너·품질 검토용**이다. Adobe Illustrator에서 열어 보지 않았다면 그렇다고 보고한다.
  인쇄소에는 아웃라인 PDF를 보낸다(`.ai`를 다른 앱이 열면 문자의 별색 연결이 빠질 수 있음: references/vectorcraft-control.md).
- 규제 문구(전성분·주의사항·표시사항)는 받은 원문을 그대로 쓰고, 이미지에서 읽은 문구는 원문 대조 전까지 미확정으로 표시한다.

## 준비 (공통)

1. **작업 폴더**: `scripts/new_job.py --request <요청서.xlsx> --source <원본.ai> [--ref …] [--item "요청서 밖에서 받은 수정"]`
   (신규 제작은 `--mode new --name …`). 구조와 이름 규칙: [references/folder-structure.md](references/folder-structure.md).
   요청서 항목은 `scripts/read_request.py`가 읽는다. 채팅으로 받은 추가 요청은 `--item`으로 출처와 함께 남긴다.
2. **앱 실행**: `scripts/vc_launch.py --start --root <작업 폴더>`(읽기·쓰기를 작업 폴더로 제한). 코드 3이면 사용자 확인 후 종료하고 다시 실행.
3. **폰트 먼저**: `scripts/pdf_text_dump.py 01_source/원본.ai`로 원본 폰트와 실제 설정값(크기·자간·장평)을 읽고,
   `scripts/fonts.py --job <작업> --from-pdf 01_source/원본.ai --want "<새 폰트>" --search <팀 폰트 폴더의 하위 폴더>`로 등록한다.
   **문서를 열기 전에** 해야 한다: [references/import-and-fonts.md](references/import-and-fonts.md).

## 수정 (revision 모드)

1. 원본을 편집 데이터와 PDF 부분(`editingData:false`) 두 방식으로 열고, `scripts/compare.py`로 원본 PDF 렌더와 비교해 일치하는 쪽을 고른다.
2. 대상 객체를 `document.find`/`document.node`로 찾고, 원본 값(`pdf_text_dump.py`)과 함께 `job.json`의 `changes`에 적는다.
3. 수정은 `command.batch` 하나로 실행한다. 레시피: [references/revision-recipes.md](references/revision-recipes.md).
4. 출력: `.ai`(saveAs), 미리보기 PNG, 아웃라인 PDF(`High Quality Print` + `outlineText`).
5. 검증: `scripts/verify_print_pdf.py <pdf> --original 01_source/원본.ai`(폰트 0, 텍스트 0, 별색 동일),
   `scripts/compare.py --other <pdf>`(바뀐 영역 = 요청한 곳뿐), `swift scripts/render_pdf.swift`로 다른 엔진 렌더 확인.

## 신규 제작 (new 모드)

시안 이미지·규격·원문으로 인쇄 데이터를 만든다. 필요한 입력, 측정, 레이어·별색 구성, 트레이스, 문자 맞춤, 문단, 바코드, 판 확인은
[references/new-artwork.md](references/new-artwork.md)를 따른다. 작업별 빌드는 `03_work/build_*.py`로 쓰고 `scripts/layout_kit.py`
(`Ref`: 시안 측정·마스크·비교, `Doc`: 잉크 박스 맞춤·문단·트레이스·EAN-13)를 가져다 쓴다. 로고·아이콘 원본과 실제 폰트가 없으면
트레이스·대체 폰트 초안으로 만들고 "교체 필요"로 보고한다.

## 생성 AI 시안 → 필름 (new 모드의 한 갈래)

디자이너 필름 없이 생성 AI 시안(목업 이미지)만 있을 때: 용기 형태를 역산해 시안을 펼친 필름 좌표로 옮기고(`scripts/tube_unwrap.py`),
글자는 실제 서체로 다시 짜고 단순 도형은 수식으로 만들며, 시안에 없는 뒷면·표시사항은 전성분에서 근거를 찾은 특장점과 함께 새로 짠다.
PANTONE 번호·용기 도면·바코드·표시광고는 사람이 정할 항목으로 보고한다. 절차와 주의점: [references/ai-concept-to-film.md](references/ai-concept-to-film.md).

## 보고

`04_output/변경보고서_v01.md`(신규는 `제작보고서_v01.md`)와 `03_work/job.json`에 남긴다:
- 무엇을 어떻게 바꿨는지(객체, 전/후 값, 근거), 고른 열기 방식과 이유
- 대체한 폰트·트레이스한 요소, 바코드 크기·극성 같은 인쇄 위험
- 확인한 것(검증 방법과 결과)과 **확인하지 못한 것**(Illustrator 열기, 실물 규격, 바코드 스캔 등)

제어 채널 명령·주의점: [references/vectorcraft-control.md](references/vectorcraft-control.md). 공식 문서: https://github.com/storytold/vectorcraft (`docs/control-protocol.md`, `docs/mcp.md`).
