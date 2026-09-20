// Print a short-lived App Store Connect API token (ES256 JWT).
//   xcrun swift appstore/asc_token.swift <KEY_ID> <ISSUER_ID> [p8 path]
// Default key path: ~/.appstoreconnect/private_keys/AuthKey_<KEY_ID>.p8
// CryptoKit ships with Xcode, so this needs nothing installed — the Python
// route wanted `cryptography`, which the macOS 27 update took away.
import Foundation
import CryptoKit

func b64url(_ d: Data) -> String {
    d.base64EncodedString()
        .replacingOccurrences(of: "+", with: "-")
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "=", with: "")
}

let a = CommandLine.arguments
guard a.count >= 3 else {
    FileHandle.standardError.write("usage: asc_token.swift <KEY_ID> <ISSUER_ID> [p8]\n".data(using: .utf8)!)
    exit(2)
}
let keyId = a[1], issuer = a[2]
let p8 = a.count > 3 ? a[3]
       : NSHomeDirectory() + "/.appstoreconnect/private_keys/AuthKey_\(keyId).p8"

guard let pem = try? String(contentsOfFile: p8, encoding: .utf8),
      let key = try? P256.Signing.PrivateKey(pemRepresentation: pem) else {
    FileHandle.standardError.write("cannot read or parse \(p8)\n".data(using: .utf8)!)
    exit(1)
}

let now = Int(Date().timeIntervalSince1970)
let header  = #"{"alg":"ES256","kid":"\#(keyId)","typ":"JWT"}"#
let payload = #"{"iss":"\#(issuer)","iat":\#(now),"exp":\#(now + 1200),"aud":"appstoreconnect-v1"}"#
let signing = b64url(Data(header.utf8)) + "." + b64url(Data(payload.utf8))

guard let sig = try? key.signature(for: Data(signing.utf8)) else {
    FileHandle.standardError.write("signing failed\n".data(using: .utf8)!); exit(1)
}
print(signing + "." + b64url(sig.rawRepresentation))
