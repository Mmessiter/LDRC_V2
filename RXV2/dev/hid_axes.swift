import IOKit.hid
import Foundation
let names: [UInt32:String] = [48:"X",49:"Y",50:"Z",51:"Rx",52:"Ry",53:"Rz",54:"Slider",55:"Dial"]
var lo = [UInt32:Int](); var hi = [UInt32:Int](); var n = [UInt32:Int]()
let mgr = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
IOHIDManagerSetDeviceMatching(mgr, [kIOHIDVendorIDKey: 0x1209, kIOHIDProductIDKey: 0x525D] as CFDictionary)
IOHIDManagerRegisterInputValueCallback(mgr, { _,_,_,value in
    let u = IOHIDElementGetUsage(IOHIDValueGetElement(value))
    let v = IOHIDValueGetIntegerValue(value)
    lo[u] = min(lo[u] ?? v, v); hi[u] = max(hi[u] ?? v, v); n[u] = (n[u] ?? 0) + 1
}, nil)
IOHIDManagerScheduleWithRunLoop(mgr, CFRunLoopGetCurrent(), CFRunLoopMode.defaultMode.rawValue)
guard IOHIDManagerOpen(mgr, IOOptionBits(kIOHIDOptionsTypeNone)) == kIOReturnSuccess else { print("cannot open"); exit(1) }
print("listening 12 s - MOVE EVERY STICK NOW")
func pad(_ s: String, _ w: Int) -> String { s.count >= w ? s : s + String(repeating: " ", count: w - s.count) }
DispatchQueue.global().asyncAfter(deadline: .now() + 12) {
    print("axis     reports      min       max    travel")
    for u in lo.keys.sorted() {
        let t = hi[u]! - lo[u]!
        print(pad(names[u] ?? "usage \(u)", 9) + pad("\(n[u]!)", 9) + pad("\(lo[u]!)", 10) + pad("\(hi[u]!)", 10) + pad("\(t)", 9) + (t > 2000 ? " <- MOVING" : ""))
    }
    if lo.isEmpty { print("NOTHING AT ALL arrived") }
    exit(0)
}
CFRunLoopRun()
