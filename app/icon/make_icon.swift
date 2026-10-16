// The app icon: the P of the P.A.R.O.L.A. logo, the same 3-D ASCII letter, on a black macOS
// rounded square. Usage: swift make_icon.swift <out.png> (1024 x 1024).
import AppKit

let rows = [" ******", "/**////**", "/**   /**", "/*******", "/**////", "/**", "/**", "//"]
let star = NSColor(srgbRed: 0.85, green: 0.27, blue: 0.58, alpha: 1)   // #d84594, the logo's pink
let slash = NSColor(srgbRed: 0.55, green: 0.13, blue: 0.44, alpha: 1)  // #8c2170, its shading
let glow = NSColor(srgbRed: 0.82, green: 0.25, blue: 0.56, alpha: 0.55)

let size = 1024
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)

// macOS icon grid: an 824-point square with rounded corners, centred on the 1024 canvas.
let tile = NSRect(x: 100, y: 100, width: 824, height: 824)
NSColor.black.setFill()
NSBezierPath(roundedRect: tile, xRadius: 185, yRadius: 185).fill()

let font = NSFont(name: "Menlo-Bold", size: 96)!
let advance = ("*" as NSString).size(withAttributes: [.font: font]).width
let lineHeight: CGFloat = 70
let columns = CGFloat(rows.map(\.count).max()!)
let blockWidth = advance * columns, blockHeight = lineHeight * CGFloat(rows.count)
let left = tile.midX - blockWidth / 2 + 24  // optical centre: the stems on the left weigh more
let top = tile.midY + blockHeight / 2 - 8

let shadow = NSShadow()
shadow.shadowColor = glow
shadow.shadowBlurRadius = 18
shadow.shadowOffset = .zero
for (r, row) in rows.enumerated() {
    for (c, ch) in row.enumerated() where ch != " " {
        let attrs: [NSAttributedString.Key: Any] = [
            .font: font, .foregroundColor: ch == "*" ? star : slash, .shadow: shadow,
        ]
        let point = NSPoint(x: left + CGFloat(c) * advance, y: top - CGFloat(r + 1) * lineHeight)
        (String(ch) as NSString).draw(at: point, withAttributes: attrs)
    }
}
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
