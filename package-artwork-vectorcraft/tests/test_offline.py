"""Offline checks (no VectorCraft needed): python3 -m unittest discover -s tests -p 'test_*.py'"""
import os
import sys
import tempfile
import unittest
import zipfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from layout_kit import ean13_check_digit, ean13_pattern  # noqa: E402
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
