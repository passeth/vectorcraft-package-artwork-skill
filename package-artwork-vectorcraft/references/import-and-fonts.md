# 원본 열기와 폰트

## 순서가 중요하다: 폰트 먼저, 열기는 나중

`.ai`의 편집 데이터는 **열 때** 폰트를 PostScript 이름으로 찾아 붙인다. 폰트가 없는 채로 열면 대체 폰트 기준으로
영역 문자 프레임을 늘리고 줄바꿈을 다시 잡아서, 나중에 폰트를 넣어도 그 결과가 남는다.

1. `pdf_text_dump.py 01_source/원본.ai` — 원본이 쓰는 폰트(PostScript 이름)와 실제 설정값을 본다.
2. `fonts.py --job <작업> --from-pdf 01_source/원본.ai --want "<새 폰트 패밀리>" --search <팀 폰트 폴더>` —
   02_fonts로 복사하고 VectorCraft 전용 폰트 폴더에 등록한다(시스템 설치 아님).
   - 클라우드 동기화 폴더(Synology Drive, Dropbox 등) 전체를 `--search`로 주지 않는다. 파일을 하나씩 읽으며 내려받기가 일어나 매우 느리다.
     폰트가 있는 하위 폴더(예: `…/폰트/영문`)만 준다.
   - 회사가 라이선스를 가진 폰트만 등록한다.
3. 그다음에 문서를 연다. 열기 결과의 `warnings`에 "fonts that aren't available"이 남아 있으면 해결한 뒤 다시 연다.

## 편집 데이터 vs PDF 부분: 둘 다 열어 원본 PDF와 비교한다

| 열기 | 장점 | 확인된 문제 |
|---|---|---|
| 기본(편집 데이터) | 레이어·그룹·문단 박스 구조 유지 | 영역 문자 줄바꿈이 원본과 다를 수 있음(예: 주소 줄), 같은 문자가 중복 객체로 생길 수 있음, "frames got taller" 경고 |
| `editingData:false`(PDF 부분) | 인쇄되는 모양과 같은 줄·위치 | 문자가 줄마다 포인트 문자로 나뉨, 레이어 구조 단순, **자간은 글리프 위치에서 추정한 값**(원본 설정값 아님) |

판단 방법:
```
compare.py --original 01_source/원본.ai --out-dir 03_work/compare --label editdata --doc-index 0
compare.py --original 01_source/원본.ai --out-dir 03_work/compare --label pdfpart  --doc-index 1
```
`regions`가 비어 있는(또는 렌더러 차이 수준인) 쪽을 고른다. 고른 이유를 `job.json`의 `importMode`에 적는다.
쓰지 않는 문서는 `file.close`로 닫는다.

## 원본 설정값 읽기

PDF 부분으로 연 문서의 자간은 추정값이다(예: 실제 −50 → −59). 글꼴을 바꾸거나 스타일을 맞출 때는
`pdf_text_dump.py`가 보여주는 원본 값(크기, `Tc`=자간, 장평)을 쓴다. 예: `-0.03 Tc` → 자간 −30.

## 결과 파일의 폰트

- 저장한 `.ai`의 PDF 부분과 내보낸 PDF에는 폰트가 서브셋으로 들어간다.
- 인쇄용 PDF는 `advanced.outlineText:true`로 내보내 폰트 의존을 없앤다. `verify_print_pdf.py`로 폰트 0, 텍스트 0을 확인한다.
