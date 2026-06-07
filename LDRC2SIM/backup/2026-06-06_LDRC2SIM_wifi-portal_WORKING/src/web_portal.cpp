#include "web_portal.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DNSServer.h>
#include <Update.h>
#include <Preferences.h>

namespace {

const char* AP_SSID  = "LDRC2SIM";       // access-point name
const char* HOSTNAME = "LDRC2SIM";       // -> http://LDRC2SIM.local
const uint16_t DNS_PORT = 53;

WebServer   server(80);
DNSServer   dns;
Preferences prefs;
RcInput*    rc = nullptr;
bool        staConfigured = false;       // we have stored credentials

// ----- persistent WiFi credentials (NVS) -------------------------------
String cfgSsid, cfgPass;

void loadCreds() {
  prefs.begin("ldrc2sim", true);
  cfgSsid = prefs.getString("ssid", "");
  cfgPass = prefs.getString("pass", "");
  prefs.end();
}
void saveCreds(const String& s, const String& p) {
  prefs.begin("ldrc2sim", false);
  prefs.putString("ssid", s);
  prefs.putString("pass", p);
  prefs.end();
}
void clearCreds() {
  prefs.begin("ldrc2sim", false);
  prefs.clear();
  prefs.end();
}

// ----- HTML helpers ----------------------------------------------------
String htmlEscape(const String& in) {
  String o; o.reserve(in.length() + 8);
  for (char c : in) {
    switch (c) {
      case '&': o += "&amp;";  break;
      case '<': o += "&lt;";   break;
      case '>': o += "&gt;";   break;
      case '"': o += "&quot;"; break;
      default:  o += c;
    }
  }
  return o;
}

String page(const String& title, const String& body) {
  String h;
  h.reserve(body.length() + 900);
  h += F("<!doctype html><html><head><meta charset=utf-8>"
         "<meta name=viewport content='width=device-width,initial-scale=1'>"
         "<title>LDRC2SIM</title><style>"
         "body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;"
         "background:#0f1115;color:#e6e6e6}"
         "header{background:#1b2030;padding:14px 18px;font-size:20px;font-weight:600}"
         "nav{background:#161a26;padding:8px 18px}"
         "nav a{color:#7fb2ff;text-decoration:none;margin-right:16px;font-size:15px}"
         "main{padding:18px;max-width:760px}"
         "h2{margin-top:0}"
         ".card{background:#161a26;border:1px solid #262c3d;border-radius:10px;"
         "padding:16px;margin-bottom:16px}"
         "input,button{font-size:16px;padding:9px 10px;border-radius:8px;"
         "border:1px solid #38405a;background:#0f1115;color:#e6e6e6;width:100%;"
         "box-sizing:border-box;margin:6px 0}"
         "button{background:#2a6df4;border:none;font-weight:600;cursor:pointer}"
         "button.warn{background:#7a2230}"
         "table{border-collapse:collapse;width:100%}"
         "td{padding:4px 8px;border-bottom:1px solid #262c3d}"
         "code{background:#0b0d12;padding:2px 5px;border-radius:5px}"
         ".ok{color:#5ad17a}.muted{color:#8a93a6}"
         "</style></head><body>"
         "<header>LDRC2SIM</header>"
         "<nav><a href='/'>Status</a><a href='/wifi'>Wi&#8209;Fi</a>"
         "<a href='/help'>Help</a><a href='/update'>Update</a></nav><main>");
  h += body;
  h += F("</main></body></html>");
  return h;
}

// ----- handlers --------------------------------------------------------
void handleRoot() {
  String staState;
  if (WiFi.status() == WL_CONNECTED)
    staState = "<span class=ok>connected</span> &mdash; " + WiFi.localIP().toString();
  else if (staConfigured)
    staState = "<span class=muted>configured, connecting&hellip;</span>";
  else
    staState = "<span class=muted>not configured</span>";

  String b;
  b += F("<div class=card><h2>Status</h2><table>");
  b += "<tr><td>Access point</td><td><code>" + String(AP_SSID) +
       "</code> @ " + WiFi.softAPIP().toString() + "</td></tr>";
  b += "<tr><td>Home Wi&#8209;Fi</td><td>" + staState + "</td></tr>";
  b += "<tr><td>Address</td><td><code>http://LDRC2SIM.local</code></td></tr>";
  b += F("</table></div>");

  b += F("<div class=card><h2>RC input</h2>"
         "<table>"
         "<tr><td>Protocol</td><td id=proto>&hellip;</td></tr>"
         "<tr><td>Channels 1&#8209;8 (&micro;s)</td><td id=ch>&hellip;</td></tr>"
         "</table>"
         "<p class=muted>Live; first 8 channels in microseconds (~1000&ndash;2000).</p>"
         "</div>"
         "<script>"
         "async function u(){try{let r=await fetch('/status');let d=await r.json();"
         "document.getElementById('proto').textContent="
         "d.link?d.proto:'no RC link \\u2014 sine self\\u2011test';"
         "document.getElementById('ch').textContent=d.ch.join('   ');}catch(e){}}"
         "setInterval(u,1000);u();</script>");
  server.send(200, "text/html", page("Status", b));
}

void handleStatus() {
  String j = "{";
  bool link = rc && rc->linkUp();
  j += "\"link\":"; j += link ? "true" : "false";
  j += ",\"proto\":\""; j += rc ? rc->protocolName() : "n/a"; j += "\"";
  j += ",\"ch\":[";
  for (uint8_t i = 0; i < 8; i++) {
    if (i) j += ",";
    j += String(rc ? rc->channelUs(i) : 1500);
  }
  j += "]}";
  server.send(200, "application/json", j);
}

void handleWifi() {
  String b;
  b += F("<div class=card><h2>Wi&#8209;Fi setup</h2>"
         "<p class=muted>Enter your home network so LDRC2SIM can join it "
         "(for OTA updates and <code>LDRC2SIM.local</code> access).</p>");

  // Scan (brief) and offer a dropdown of found networks.
  int n = WiFi.scanNetworks(false, false);
  b += F("<form method=POST action='/wifi'>");
  if (n > 0) {
    b += F("<label>Detected networks</label>"
           "<select onchange=\"document.getElementById('s').value=this.value\">"
           "<option value=''>&mdash; pick or type below &mdash;</option>");
    for (int i = 0; i < n && i < 20; i++) {
      String s = htmlEscape(WiFi.SSID(i));
      b += "<option value='" + s + "'>" + s + "  (" + String(WiFi.RSSI(i)) + " dBm)</option>";
    }
    b += F("</select>");
  }
  WiFi.scanDelete();
  b += "<label>Network name (SSID)</label>"
       "<input id=s name=ssid value='" + htmlEscape(cfgSsid) + "' autocomplete=off>";
  b += F("<label>Password</label>"
         "<input name=pass type=password autocomplete=off>"
         "<button type=submit>Save &amp; connect</button></form>");
  b += F("</div>");

  b += F("<div class=card><h2>Forget network</h2>"
         "<p class=muted>Clear saved credentials and reboot into AP&#8209;only setup.</p>"
         "<form method=POST action='/forget'>"
         "<button class=warn type=submit>Forget Wi&#8209;Fi</button></form></div>");
  server.send(200, "text/html", page("Wi-Fi", b));
}

void handleWifiSave() {
  String s = server.arg("ssid");
  String p = server.arg("pass");
  if (s.length() == 0) { server.send(400, "text/html", page("Wi-Fi", F("<div class=card>SSID cannot be empty. <a href='/wifi'>Back</a></div>"))); return; }
  saveCreds(s, p);
  String b = "<div class=card><h2>Saved</h2><p>Connecting to <code>" + htmlEscape(s) +
             "</code>&hellip; the device will reboot.</p>"
             "<p class=muted>After a few seconds, reach it at "
             "<code>http://LDRC2SIM.local</code> on your home network "
             "(the <code>LDRC2SIM</code> AP also stays available).</p></div>";
  server.send(200, "text/html", page("Wi-Fi", b));
  delay(800);
  ESP.restart();
}

void handleForget() {
  clearCreds();
  server.send(200, "text/html", page("Wi-Fi", F("<div class=card>Credentials cleared. Rebooting&hellip;</div>")));
  delay(800);
  ESP.restart();
}

void handleHelp() {
  String b = F(
    "<div class=card><h2>How LDRC2SIM works</h2>"
    "<p>Connect your receiver's signal wire to pin <code>D7</code>, GND to "
    "<code>GND</code>, and power the RX from <code>5V</code>. The device "
    "<b>auto-detects the protocol</b> &mdash; no setting to choose. It also "
    "appears on USB as an 8-axis joystick that flight sims (e.g. neXt) read.</p></div>"

    "<div class=card><h2>Supported protocols (auto-detected)</h2><table>"
    "<tr><td><b>CRSF</b></td><td>ExpressLRS / TBS Crossfire. 420 kbaud. "
    "<span class=ok>Recommended</span> &mdash; modern, high resolution, low latency.</td></tr>"
    "<tr><td><b>SBUS</b></td><td>FrSky / Futaba. Inverted, 16 channels. "
    "<span class=ok>Recommended</span> &mdash; universal and robust.</td></tr>"
    "<tr><td><b>IBUS</b></td><td>FlySky. 115200 baud. Works well on FlySky gear.</td></tr>"
    "<tr><td><b>PPM</b></td><td>CPPM pulse train. Universal fallback; lower "
    "resolution and typically &le;8 channels.</td></tr>"
    "</table><p class=muted>On power-up it listens briefly for each in turn until "
    "it sees valid frames, then locks on. If the link drops it re-detects.</p></div>"

    "<div class=card><h2>Wiring &amp; notes</h2>"
    "<ul>"
    "<li>Signal &rarr; <code>D7</code> (GPIO44). CRSF: the RX's <b>TX</b> pad; "
    "SBUS/IBUS/PPM: that named pad.</li>"
    "<li><b>3.3&nbsp;V signals only</b> &mdash; the ESP32-S3 isn't 5&nbsp;V tolerant "
    "(most RX signal pads are 3.3&nbsp;V even on 5&nbsp;V power).</li>"
    "<li>Common <code>GND</code> is required.</li>"
    "<li>The sim reads up to <b>8 proportional channels</b> over USB &mdash; that's "
    "the norm for this kind of adapter.</li>"
    "</ul></div>"

    "<div class=card><h2>Updating firmware</h2>"
    "<p>When on your home Wi&#8209;Fi, use <a href='/update'>Update</a> to upload a "
    "new <code>firmware.bin</code> over the air.</p></div>");
  server.send(200, "text/html", page("Help", b));
}

void handleUpdateForm() {
  String b = F(
    "<div class=card><h2>Firmware update (OTA)</h2>"
    "<p class=muted>Upload a <code>firmware.bin</code> built for this board. "
    "The device verifies and reboots into it; if the upload is bad it keeps "
    "running the current firmware.</p>"
    "<form method=POST action='/update' enctype='multipart/form-data'>"
    "<input type=file name=update accept='.bin'>"
    "<button type=submit>Upload &amp; flash</button></form>"
    "<p class=muted>Find the file at "
    "<code>.pio/build/seeed_xiao_esp32s3/firmware.bin</code> after a build.</p></div>");
  server.send(200, "text/html", page("Update", b));
}

void handleUpdateDone() {
  bool ok = !Update.hasError();
  server.sendHeader("Connection", "close");
  String b = ok
    ? F("<div class=card><h2 class=ok>Update OK</h2><p>Rebooting into the new "
        "firmware&hellip; reconnect in a few seconds.</p></div>")
    : F("<div class=card><h2>Update failed</h2><p>The current firmware is still "
        "running. <a href='/update'>Try again</a>.</p></div>");
  server.send(200, "text/html", page("Update", b));
  if (ok) { delay(800); ESP.restart(); }
}

void handleUpdateUpload() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) {
    Update.begin(UPDATE_SIZE_UNKNOWN);
  } else if (up.status == UPLOAD_FILE_WRITE) {
    Update.write(up.buf, up.currentSize);
  } else if (up.status == UPLOAD_FILE_END) {
    Update.end(true);   // true = set the new image as boot target
  }
}

void handleNotFound() {
  // Captive-portal: send AP clients to the config page.
  server.sendHeader("Location", "http://" + WiFi.softAPIP().toString() + "/", true);
  server.send(302, "text/plain", "");
}

} // namespace

// ======================================================================
namespace WebPortal {

void begin(RcInput* rcIn) {
  rc = rcIn;
  loadCreds();
  staConfigured = cfgSsid.length() > 0;

  WiFi.persistent(false);
  WiFi.setHostname(HOSTNAME);
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID);                      // open AP for setup
  if (staConfigured) {
    WiFi.setAutoReconnect(true);
    WiFi.begin(cfgSsid.c_str(), cfgPass.c_str());   // non-blocking; joins in bg
  }

  dns.start(DNS_PORT, "*", WiFi.softAPIP());  // captive portal on the AP
  MDNS.begin(HOSTNAME);                       // http://LDRC2SIM.local
  MDNS.addService("http", "tcp", 80);

  server.on("/",        HTTP_GET,  handleRoot);
  server.on("/status",  HTTP_GET,  handleStatus);
  server.on("/wifi",    HTTP_GET,  handleWifi);
  server.on("/wifi",    HTTP_POST, handleWifiSave);
  server.on("/forget",  HTTP_POST, handleForget);
  server.on("/help",    HTTP_GET,  handleHelp);
  server.on("/update",  HTTP_GET,  handleUpdateForm);
  server.on("/update",  HTTP_POST, handleUpdateDone, handleUpdateUpload);
  server.onNotFound(handleNotFound);
  server.begin();
}

void loop() {
  dns.processNextRequest();
  server.handleClient();
}

} // namespace WebPortal
