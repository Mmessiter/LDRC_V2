// LDRC2SIM — WiFi config portal, help pages, and OTA update
// ------------------------------------------------------------------
// Runs WIFI_AP_STA: a "LDRC2SIM" access point is always available for setup,
// and the device also joins the user's home WiFi in the background once
// credentials are saved. Serves a small web UI (status / WiFi config / help /
// firmware OTA) on port 80, reachable at http://LDRC2SIM.local (mDNS) or the
// AP address http://192.168.4.1. Non-blocking — never stalls the USB-HID loop.

#pragma once
#include "rc_input.h"

namespace WebPortal {
  // rc: optional pointer to the live RC decoder, for the status page (may be null).
  void begin(RcInput* rc);
  void loop();               // service captive-portal DNS + web clients; call often
}
