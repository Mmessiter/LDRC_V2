// LockDownRadioControl — RXV2App  ::  ModelPhotos.swift
//
// A photograph per receiver (Malcolm 2026-09-05: "when the app is asking
// us whether to connect, it shows us not only the name but also the
// photograph, because some people get muddled by very similar names").
// Stored on the phone under Documents/photos/<receiver name>.jpg, resized
// to ~900 px so a whole fleet costs a few hundred kB. Long-press a receiver
// in the scanner to choose or take one.

import SwiftUI
import PhotosUI
import UIKit

enum ModelPhotos {
    static var dir: URL {
        let d = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("photos", isDirectory: true)
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d
    }
    static func safe(_ name: String) -> String {
        String(name.map { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" ? $0 : "_" })
    }
    static func url(_ name: String) -> URL { dir.appendingPathComponent(safe(name) + ".jpg") }
    static func load(_ name: String) -> UIImage? { UIImage(contentsOfFile: url(name).path) }
    static func has(_ name: String) -> Bool { FileManager.default.fileExists(atPath: url(name).path) }
    static func save(_ name: String, _ image: UIImage) {
        let small = resized(image, maxSide: 900)
        if let d = small.jpegData(compressionQuality: 0.85) { try? d.write(to: url(name), options: .atomic) }
    }
    static func remove(_ name: String) { try? FileManager.default.removeItem(at: url(name)) }
    static func resized(_ img: UIImage, maxSide: CGFloat) -> UIImage {
        let w = img.size.width, h = img.size.height
        let scale = min(1, maxSide / max(w, h))
        if scale >= 1 { return img }
        let size = CGSize(width: w * scale, height: h * scale)
        let fmt = UIGraphicsImageRendererFormat.default(); fmt.scale = 1
        return UIGraphicsImageRenderer(size: size, format: fmt).image { _ in img.draw(in: CGRect(origin: .zero, size: size)) }
    }
}

/// The receiver's photo as a rounded thumbnail, or the antenna glyph.
struct ModelThumb: View {
    let name: String
    var side: CGFloat = 60
    var body: some View {
        if let img = ModelPhotos.load(name) {
            Image(uiImage: img).resizable().scaledToFill()
                .frame(width: side, height: side)
                .clipShape(RoundedRectangle(cornerRadius: side * 0.18, style: .continuous))
        } else {
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.system(size: side * 0.4))
                .foregroundStyle(.tint)
                .frame(width: side, height: side)
        }
    }
}

/// The camera, for "Take photo…" — UIKit's picker in a SwiftUI sheet.
struct CameraPicker: UIViewControllerRepresentable {
    let onImage: (UIImage) -> Void
    @Environment(\.dismiss) private var dismiss
    func makeUIViewController(context: Context) -> UIImagePickerController {
        let p = UIImagePickerController()
        p.sourceType = .camera
        p.delegate = context.coordinator
        return p
    }
    func updateUIViewController(_ vc: UIImagePickerController, context: Context) {}
    func makeCoordinator() -> Coord { Coord(self) }
    final class Coord: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let parent: CameraPicker
        init(_ p: CameraPicker) { parent = p }
        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            if let img = info[.originalImage] as? UIImage { parent.onImage(img) }
            parent.dismiss()
        }
        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { parent.dismiss() }
    }
}
