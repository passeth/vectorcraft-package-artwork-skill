// Render one page (or a region of it) of a PDF or PDF-compatible .ai with Apple PDFKit, independently of
// VectorCraft. Use it as ground truth for the original and to check what other apps will see in an output.
//
//   swift render_pdf.swift <in.pdf|in.ai> <out.png> [--rect x y w h] [--scale 4] [--page 1]
//
// --rect is in PDF points with the origin at the TOP-LEFT of the media box (y down), the same space
// VectorCraft's document.inspect bounds and document.export rect use for a single artboard at (0, 0).
import Foundation
import PDFKit

var args = Array(CommandLine.arguments.dropFirst())
func take(_ flag: String, _ n: Int) -> [String]? {
    guard let i = args.firstIndex(of: flag), i + n < args.count else { return nil }
    let v = Array(args[(i + 1)...(i + n)])
    args.removeSubrange(i...(i + n))
    return v
}
let rectArg = take("--rect", 4)?.compactMap { Double($0) }
let scale = CGFloat(Double(take("--scale", 1)?.first ?? "4") ?? 4)
let pageNo = Int(take("--page", 1)?.first ?? "1") ?? 1
guard args.count == 2 else {
    FileHandle.standardError.write("usage: render_pdf.swift in.pdf out.png [--rect x y w h] [--scale 4] [--page 1]\n".data(using: .utf8)!)
    exit(2)
}
// A .ai path is read as PDF data whatever its extension.
guard let data = try? Data(contentsOf: URL(fileURLWithPath: args[0])), let doc = PDFDocument(data: data),
      let page = doc.page(at: pageNo - 1) else {
    FileHandle.standardError.write("cannot read page \(pageNo) of \(args[0]) as PDF\n".data(using: .utf8)!)
    exit(1)
}
let box = page.bounds(for: .mediaBox)
var r = CGRect(x: 0, y: 0, width: box.width, height: box.height)
if let a = rectArg, a.count == 4 { r = CGRect(x: a[0], y: a[1], width: a[2], height: a[3]) }
let w = Int((r.width * scale).rounded()), h = Int((r.height * scale).rounded())
guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                          space: CGColorSpaceCreateDeviceRGB(),
                          bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { exit(1) }
ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
ctx.scaleBy(x: scale, y: scale)
// PDF space is y-up from the media box origin; the region is given y-down from its top.
ctx.translateBy(x: -(r.minX + box.minX), y: -(box.maxY - r.minY - r.height))
page.draw(with: .mediaBox, to: ctx)
guard let img = ctx.makeImage(),
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, "public.png" as CFString, 1, nil)
else { exit(1) }
CGImageDestinationAddImage(dest, img, nil)
exit(CGImageDestinationFinalize(dest) ? 0 : 1)
