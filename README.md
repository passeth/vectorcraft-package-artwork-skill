# package-artwork-vectorcraft

화장품 부자재(튜브·용기·라벨·단상자) **인쇄 데이터를 AI 에이전트가 수정하거나 새로 만드는 스킬**입니다.
에이전트(Claude Code 등)가 오픈소스 벡터 편집기 [VectorCraft](https://github.com/storytold/vectorcraft)를 로컬 제어 채널로 직접 조작합니다.
사람이 메뉴를 누르는 대신 명령을 보내고, 단계마다 결과를 렌더링해 원본과 비교하며 진행합니다.

> English summary at the bottom.

## 할 수 있는 것

| 모드 | 입력 | 결과 |
|---|---|---|
| **수정** | 부자재 문안수정 요청서(xlsx) + 원본 `.ai` | 폰트 교체, 객체 삭제·정렬, 문구 수정 → 수정본 `.ai`, 텍스트 아웃라인 인쇄용 PDF, 미리보기 PNG, 변경 보고서 |
| **신규 제작** | 디자이너 시안 이미지(PNG) + 전성분 원문(docx) + 인쇄 규격 | 별색 인쇄용 벡터 파일(로고·아이콘 트레이스, 시안에 맞춘 문자, 원문과 대조한 전성분, EAN-13 생성) + 같은 결과물 세트 |
| **생성 AI 시안 → 필름** | AI가 만든 목업 이미지 + 전성분 원문 + 용기 규격(예: 120ml Ø40 튜브) | 용기 형태를 역산해 시안을 펼친 필름으로 옮기고, 글자는 실제 서체로 다시 짜고, 시안에 없는 뒷면·표시사항은 전성분 근거 특장점과 함께 새로 짠 별색 필름 초안 |

검증 장치가 함께 들어 있습니다.
- 원본 PDF와 결과를 같은 방식으로 렌더링해 **바뀐 영역만 빨갛게 표시**
- 인쇄용 PDF에 **폰트·라이브 텍스트가 0인지, 별색 판이 원본과 같은지** 확인
- 판 레이어의 모든 객체가 해당 별색으로만 칠해졌는지 개수 확인
- Apple PDFKit으로 VectorCraft와 별개의 렌더링 확인

## 요구 사항

- macOS (Apple Silicon에서 검증)
- [VectorCraft](https://github.com/storytold/vectorcraft/releases) 데스크톱 앱 (0.24.1에서 검증)
- Python 3, [Pillow](https://pypi.org/project/pillow/) (비교·신규 제작용)
- Xcode Command Line Tools (`swift`, PDFKit 렌더러용)
- 스킬을 읽는 에이전트: [Claude Code](https://claude.com/claude-code) 등

## 설치 (Claude Code)

```bash
git clone https://github.com/passeth/vectorcraft-package-artwork-skill.git
```

```bash
cp -R vectorcraft-package-artwork-skill/package-artwork-vectorcraft ~/.claude/skills/
```

다른 에이전트는 그 에이전트의 스킬 폴더에 `package-artwork-vectorcraft` 폴더를 넣으세요.

## 사용 예

에이전트에게 이렇게 요청합니다.

- "이 요청서대로 아트웍 수정해줘" + `요청서.xlsx`, `원본.ai`
- "전면 국문 제품명 폰트를 ○○로 바꾸고, 후면 아이콘 하나 빼고 마크를 가운데로 맞춰줘"
- "이 시안 PNG와 전성분 docx로 230×120mm 2도 용기인쇄 데이터 만들어줘"
- "인쇄용으로 텍스트 아웃라인 처리한 PDF도 만들어줘"

에이전트는 작업 폴더를 만들고, VectorCraft를 제어 포트와 함께 실행하고(작업 폴더 밖은 읽고 쓰지 못하게 제한), 폰트를 등록한 뒤 작업합니다.

## 작업 폴더

```
<작업 루트>/<요청서번호>_<제품코드>_<제품명>_<부자재>/
  00_request/  요청서, 요청 메모, 참고 이미지
  01_source/   원본 (덮어쓰지 않음)
  02_fonts/    이 작업에 쓴 폰트 사본
  03_work/     job.json(진행 기록), 비교 이미지, 빌드 스크립트
  04_output/   _수정_v01.ai, _인쇄용_아웃라인.pdf, _preview.png, 보고서
```

자세한 규칙은 [folder-structure.md](package-artwork-vectorcraft/references/folder-structure.md)에 있습니다.

## 들어 있는 것

| 파일 | 역할 |
|---|---|
| `SKILL.md` | 에이전트가 읽는 절차와 경계 |
| `references/` | 제어 채널 요약, 폴더 구조, 열기·폰트, 수정 레시피, 신규 제작 절차 |
| `scripts/vc.py` | VectorCraft 제어 채널 클라이언트 (`vc.py cmd document.inspect '{}'`) |
| `scripts/vc_launch.py` | 제어 포트와 읽기·쓰기 제한을 걸어 앱 실행 (실행 중인 앱은 임의로 끄지 않음) |
| `scripts/new_job.py`, `read_request.py` | 작업 폴더 생성, 요청서 xlsx 읽기 |
| `scripts/fonts.py` | 필요한 폰트를 찾아 작업 폴더에 복사하고 VectorCraft 전용 폰트 폴더에 등록 (시스템 설치 아님) |
| `scripts/pdf_text_dump.py` | 원본 PDF의 실제 문자 설정값(폰트·크기·자간·장평·위치) 읽기 |
| `scripts/compare.py`, `render_pdf.swift` | 원본과 결과 비교 이미지, PDFKit 렌더 |
| `scripts/verify_print_pdf.py` | 인쇄용 PDF 검사 (폰트·텍스트·별색·이미지·박스) |
| `scripts/layout_kit.py` | 신규 제작용 도구: 시안 측정, 잉크 박스 맞춤 문자, 줄바꿈 유지·자동 줄바꿈(금칙) 문단, 대형 압축 글자, 물결 배지, 가이드·자리 표시, 로고 트레이스, EAN-13 |
| `scripts/tube_unwrap.py` | 튜브 목업 이미지를 펼친 필름 좌표로 변환 (크림프 납작 → 어깨 원형 단면 모델), 형태 점검 |
| `tests/` | VectorCraft 없이 도는 테스트 (`python3 -m unittest discover -s tests`) |

## 꼭 알아둘 점

- **결과는 디자이너·품질 검토용 초안입니다.** 인쇄 전에 담당 디자이너가 확인하세요.
- **인쇄소에는 아웃라인 PDF를 보내세요.** VectorCraft가 `.ai`를 저장할 때 다른 앱(Illustrator)용 편집 데이터에서 문자의 스와치 연결 등이 빠진다고 경고합니다. Illustrator에서 열면 별색으로 칠한 문자가 별색 판에서 떨어질 수 있습니다.
- **폰트는 라이선스가 있는 것만** 쓰세요. 스킬은 폰트를 내려받지 않고, 사용자가 가진 파일을 앱 전용 폴더에 등록만 합니다.
- **바코드**는 크기(GS1 최소 80%)와 극성(어두운 막대·밝은 바탕)을 확인하세요. 스킬은 기준에 못 미치면 위험으로 보고합니다.
- 전성분·주의사항 같은 **표시 문구는 받은 원문을 그대로** 씁니다. 이미지에서 읽은 문구는 원문 대조 전까지 미확정으로 표시합니다.
- VectorCraft 제어 포트(127.0.0.1)는 **인증이 없습니다.** 작업할 때만 켜세요.
- 이 프로젝트는 VectorCraft 팀과 관련이 없습니다. VectorCraft는 storytold/ArtCraft 팀의 MIT OR Apache-2.0 프로젝트입니다.

## English summary

An agent skill (Claude Code and others) for **revising or building print-ready packaging artwork** for cosmetics tubes, bottles and labels. The agent drives the open-source [VectorCraft](https://github.com/storytold/vectorcraft) desktop app through its local JSON control channel.

- **Revision mode** applies a change request (xlsx) to an original `.ai`, such as a font swap, object removal, alignment or copy change.
- **New mode** builds spot-colour vector artwork from a designer's PNG sheet, the official ingredient text and the print spec.
- **AI concept → film** turns a generative-AI mockup into a flat spot-colour film draft: it unwraps the tube from its crimp-to-shoulder shape, re-sets the type in real fonts, and builds the missing back panel with claims grounded in the ingredient list.
- Both modes produce a revised `.ai`, an outlined print PDF, a preview and a report.
- Built-in checks compare renders against the original and confirm that the print PDF has no live fonts and keeps the original spot plates.

Requires macOS, VectorCraft (tested with 0.24.1), Python 3 + Pillow and Xcode Command Line Tools. Outputs are drafts for designer review. Send printers the outlined PDF, because VectorCraft warns that the `.ai` editing data for other apps drops swatch links on type. The documentation is in Korean.

## License

[MIT](LICENSE)
