// Flatten a PNG onto white and rewrite it with no alpha channel.
// The App Store rejects screenshots that carry alpha; sips cannot strip it and
// Pillow is not always installed, so this uses CoreGraphics, which always is.
//   xcrun swift appstore/flatten_png.swift <file.png> [...]
import CoreGraphics
import ImageIO
import Foundation
import UniformTypeIdentifiers

for path in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        FileHandle.standardError.write("cannot read \(path)\n".data(using: .utf8)!); exit(1)
    }
    let w = img.width, h = img.height
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8,
                              bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else {
        FileHandle.standardError.write("no context for \(path)\n".data(using: .utf8)!); exit(1)
    }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
    guard let out = ctx.makeImage(),
          let dst = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        FileHandle.standardError.write("cannot write \(path)\n".data(using: .utf8)!); exit(1)
    }
    CGImageDestinationAddImage(dst, out, nil)
    if !CGImageDestinationFinalize(dst) {
        FileHandle.standardError.write("finalize failed \(path)\n".data(using: .utf8)!); exit(1)
    }
}
