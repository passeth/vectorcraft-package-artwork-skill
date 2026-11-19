"""Offline checks (no VectorCraft needed): python3 -m unittest discover -s tests -p 'test_*.py'"""
import os
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from layout_kit import break_lines, ean13_check_digit, ean13_pattern  # noqa: E402
from tube_unwrap import ConceptTube, TubeSpec, depth_for, ellipse_arc, unwrap_x  # noqa: E402
from read_request import parse  # noqa: E402
import pdf_text_dump  # noqa: E402
import verify_print_pdf  # noqa: E402


class Ean13(unittest.TestCase):
    def test_pattern(self):
        p = ean13_pattern("4006381333931")
        self.assertEqual(len(p), 95)
        self.assertTrue(p.startswith("101") and p.endswith("101") and p[45:50] == "01010")
        self.assertEqual(ean13_check_digit("400638133393"), 1)

    def test_bad_check_digit(self):
        with self.assertRaises(ValueError):
            ean13_pattern("4006381333932")


class TubeUnwrap(unittest.TestCase):
    def test_spec(self):
        s = TubeSpec(40, 150)
        self.assertAlmostEqual(s.flat_width, 125.6637, places=3)
        self.assertAlmostEqual(s.panel, 62.8319, places=3)

    def test_flat_row_is_linear(self):
        s = TubeSpec(40, 150)
        half = s.panel / 2                       # a flat row: visible width = panel
        self.assertEqual(depth_for(half, s.panel), 0.0)
        self.assertAlmostEqual(unwrap_x(-half, half, s.panel), 0.0, places=6)
        self.assertAlmostEqual(unwrap_x(half / 2, half, s.panel), s.panel * 0.75, places=6)

    def test_round_row_keeps_centre_scale_and_edges(self):
        s = TubeSpec(40, 150)
        self.assertAlmostEqual(depth_for(20.0, s.panel), 20.0, places=2)    # a circle of radius 20
        self.assertAlmostEqual(unwrap_x(20.0, 20.0, s.panel), s.panel, places=2)
        self.assertAlmostEqual(unwrap_x(1.0, 20.0, s.panel) - s.panel / 2, 1.0, places=2)   # true size at centre
        self.assertAlmostEqual(2 * ellipse_arc(20, 20, 3.14159265 / 2), s.panel, places=2)

    def test_box_maps_each_row_on_a_tapering_tube(self):
        s = TubeSpec(40, 150)
        k, cx, height = 4.0, 200, 600                  # 4 px/mm, crimp at y = 0, shoulder at y = 600
        t = ConceptTube.__new__(ConceptTube)           # no image: rows and pixels are set by hand
        t.spec, t.k, t.y_top, t.y_bottom = s, k, 0, height
        t.rows = {}
        for y in range(height + 1):                    # visible half-width 31.4 mm (flat) -> 20 mm (round)
            half_px = (s.panel / 2 + (20.0 - s.panel / 2) * y / height) * k
            t.rows[y] = (cx - half_px, cx + half_px)
        ink = (150, 100, 250, 500)                     # a pixel rectangle x0, y0, x1, y1

        class Pixels:
            def __getitem__(self, xy):
                x, y = xy
                inside = ink[0] <= x <= ink[2] and ink[1] <= y <= ink[3]
                return (0, 0, 0) if inside else (255, 255, 255)

        t.px = Pixels()
        bx, by, bw, bh = t.box((100, 50, 300, 550), test=lambda c: c[0] < 128)
        lefts = [t.to_film(ink[0], y)[0] for y in range(ink[1], ink[3] + 1)]
        rights = [t.to_film(ink[2] + 1, y)[0] for y in range(ink[1], ink[3] + 1)]
        self.assertAlmostEqual(bx, min(lefts), places=6)          # the narrow shoulder rows reach further out
        self.assertAlmostEqual(bx + bw, max(rights), places=6)
        self.assertLess(min(lefts), lefts[0] - 0.3)               # a corner-only box misses them (here ~0.47 mm)
        self.assertAlmostEqual(by, 25.0, places=6)
        self.assertAlmostEqual(bh, 100.25, places=6)


class LineBreaks(unittest.TestCase):
    def test_no_line_starts_with_punctuation(self):
        text = "정제수, 글리세린, 미리스틱애씨드, 포타슘하이드록사이드, 라우릭애씨드, 팔미틱애씨드"
        lines = break_lines(text, 11, len)
        self.assertEqual("".join(lines).replace(" ", ""), text.replace(" ", ""))
        for ln in lines[1:]:
            self.assertNotIn(ln[0], ",.)·:;!?")

    def test_breaks_at_space_only_near_the_end(self):
        lines = break_lines("가나다라마 바사아자차카타파하", 9, len)
        self.assertEqual(lines[0], "가나다라마")          # space within 3 chars of the end: break there
        lines = break_lines("가나 다라마바사아자차카타파하", 9, len)
        self.assertEqual(lines[0], "가나 다라마바사아")    # space too early: break mid-word


def xlsx(path, cells):
    strings = sorted({v for v in cells.values()})
    idx = {s: i for i, s in enumerate(strings)}
    rows = {}
    for ref, v in cells.items():
        rows.setdefault(int("".join(c for c in ref if c.isdigit())), []).append((ref, v))
    sheet = "".join(f'<row r="{r}">' + "".join(f'<c r="{ref}" t="s"><v>{idx[v]}</v></c>' for ref, v in sorted(rows[r]))
                    + "</row>" for r in sorted(rows))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", "<sst>" + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet><sheetData>{sheet}</sheetData></worksheet>")


class RequestForm(unittest.TestCase):
    def test_parse(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "req.xlsx")
            xlsx(p, {"B1": "부자재 문안수정 요청서", "H2": "요청서번호", "I2": "260101-1", "A6": "제    품    명",
                     "C6": "테스트 크림 10ml", "H6": "제 품 코 드", "I6": "TEST01", "A8": "적용 대상 부자재", "C8": "튜브",
                     "A10": "No", "B10": "수    정    사    항", "A11": "1", "B11": "전면 제품명 글씨체 변경",
                     "A12": "2", "B12": "후면 아이콘 제거", "A21": "비고"})
            r = parse(p)
            self.assertEqual(r["no"], "260101-1")
            self.assertEqual(r["productCode"], "TEST01")
            self.assertEqual(r["component"], "튜브")
            self.assertEqual(r["items"], ["전면 제품명 글씨체 변경", "후면 아이콘 제거"])


def tiny_pdf(path, content, extra=b""):
    stream = zlib.compress(content)
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Filter/FlateDecode/Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/ABCDEF+Helvetica-Bold>>" + extra]
    body = b"%PDF-1.6\n"
    for i, o in enumerate(objs, 1):
        body += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    open(path, "wb").write(body + b"trailer<</Root 1 0 R>>\n%%EOF\n")


class PdfTools(unittest.TestCase):
    def test_text_dump_reads_tracking(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.pdf")
            tiny_pdf(p, b"BT /F1 1 Tf -0.03 Tc 12 0 0 12 10 50 Tm (SAMPLE TEXT)Tj ET")
            rows = pdf_text_dump.run(p)
            self.assertEqual(rows[0]["font"], "Helvetica-Bold")
            self.assertAlmostEqual(rows[0]["sizePt"], 12)
            self.assertAlmostEqual(rows[0]["tracking"], -30)
            self.assertEqual(rows[0]["text"], "SAMPLE TEXT")

    def test_verify_flags_live_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.pdf")
            tiny_pdf(p, b"BT /F1 1 Tf (A)Tj ET")
            rep = verify_print_pdf.inspect(p)
            self.assertGreater(rep["fontObjects"], 0)
            self.assertGreater(rep["textBlocks"], 0)


if __name__ == "__main__":
    unittest.main()
