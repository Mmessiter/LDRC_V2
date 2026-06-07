#include "web_portal.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DNSServer.h>
#include <Update.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// User channel map, owned by main.cpp. userMap[out] = 0-based RC input channel
// (0..15) feeding USB Output (out+1); userRev[out] reverses it. The "Map
// channels" page edits these live and persists them to NVS.
extern uint8_t userMap[8];
extern bool    userRev[8];

// Web UI in the LockDownRadioControl house style (RXV2 / ReedMachine): warm
// "flying-field" palette, translucent cards, colour-coded buttons, floating
// "?" help modal, Rotorflight-style channel bars. style.css + app.js are
// served as their own cached routes. Compiled-in (no LittleFS needed).

namespace {

const char* AP_SSID    = "LDRC2SIM";
const char* HOSTNAME   = "LDRC2SIM";
const char* FW_VERSION = "LDRC2SIM-1.0.12";         // parseable: LDRC2SIM-x.y.z
// Update sources consulted by /api/firmware/check. Local = a firmware server on
// the home LAN (dev/firmware_server.py, port 8001 to avoid the RXV2 one on 8000).
// Public = messiter.com, mirrored the same way as the RXV2/ReedsV2 OTA areas
// (public_html/ldrc2sim/release/). Safe to enable now: the fetch has an 8 s
// timeout and only runs on the Firmware "check" action, and the host returns 200.
// Publish releases with dev/stage_website.py then dev/publish_website.sh.
const char* FW_LOCAL_MANIFEST  = "http://m4macmini.local:8001/manifest.json";
const char* FW_PUBLIC_MANIFEST = "https://messiter.com/ldrc2sim/release/manifest.json";
const uint16_t DNS_PORT = 53;

WebServer   server(80);
DNSServer   dns;
Preferences prefs;
RcInput*    rc = nullptr;
bool        staConfigured = false;
String      cfgSsid, cfgPass;

// STA (home Wi-Fi) reconnect watchdog. The ESP32's own auto-reconnect gives up
// after some disconnect reasons / if the AP was briefly missing, and nothing
// else retries — so the device sits in AP-only with valid creds. We re-issue
// WiFi.begin() on a cadence whenever STA is down, and restart mDNS on each
// (re)connect so LDRC2SIM.local resolves on the LAN again.
const uint32_t STA_RETRY_MS = 10000;   // re-issue WiFi.begin() this often while down
uint32_t lastStaAttemptMs = 0;
bool     mdnsOnLan = false;            // mDNS (re)started after a LAN IP arrived

void loadCreds() {
  prefs.begin("ldrc2sim", true);
  cfgSsid = prefs.getString("ssid", "");
  cfgPass = prefs.getString("pass", "");
  prefs.end();
}
void saveCreds(const String& s, const String& p) {
  prefs.begin("ldrc2sim", false);
  prefs.putString("ssid", s); prefs.putString("pass", p);
  prefs.end();
}
void clearCreds() { prefs.begin("ldrc2sim", false); prefs.clear(); prefs.end(); }

// Channel map persistence. Stored as two 8-byte blobs alongside the WiFi creds.
// Defaults (set in main.cpp) stand until the user saves a custom map.
void loadMap() {
  prefs.begin("ldrc2sim", true);
  uint8_t m[8], r[8];
  bool haveM = prefs.getBytes("map", m, sizeof m) == sizeof m;
  bool haveR = prefs.getBytes("rev", r, sizeof r) == sizeof r;
  prefs.end();
  if (haveM) for (uint8_t i = 0; i < 8; i++) if (m[i] < 16) userMap[i] = m[i];
  if (haveR) for (uint8_t i = 0; i < 8; i++) userRev[i] = r[i] ? true : false;
}
void saveMap() {
  uint8_t r[8];
  for (uint8_t i = 0; i < 8; i++) r[i] = userRev[i] ? 1 : 0;
  prefs.begin("ldrc2sim", false);
  prefs.putBytes("map", userMap, 8);
  prefs.putBytes("rev", r, 8);
  prefs.end();
}

String esc(const String& in) {
  String o; o.reserve(in.length() + 8);
  for (char c : in) switch (c) {
    case '&': o += "&amp;";  break; case '<': o += "&lt;"; break;
    case '>': o += "&gt;";   break; case '"': o += "&quot;"; break;
    default:  o += c;
  }
  return o;
}
String jsonEsc(const String& in) {
  String o; o.reserve(in.length() + 8);
  for (char c : in) { if (c == '"' || c == '\\') o += '\\'; if ((uint8_t)c >= 0x20) o += c; }
  return o;
}

// ---- firmware manifest / HTTP-pull OTA --------------------------------
bool isHttps(const String& u) { return u.startsWith("https://"); }

bool httpBeginAny(HTTPClient& http, WiFiClient& plain, WiFiClientSecure& secure, const String& url) {
  if (isHttps(url)) { secure.setInsecure(); return http.begin(secure, url); }
  return http.begin(plain, url);
}

// Fetch a manifest URL and append {"manifest_url":...,"ok":bool, "manifest":<body>|"error":...}.
void fetchManifestInto(String& out, const String& url, uint32_t timeoutMs) {
  out += "{\"manifest_url\":\""; out += url; out += "\"";
  if (url.isEmpty()) { out += ",\"ok\":false,\"error\":\"no url\"}"; return; }
  HTTPClient http; WiFiClient plain; WiFiClientSecure secure;
  http.setConnectTimeout(timeoutMs); http.setTimeout(timeoutMs);
  if (!httpBeginAny(http, plain, secure, url)) { out += ",\"ok\":false,\"error\":\"begin failed\"}"; return; }
  int code = http.GET();
  if (code != HTTP_CODE_OK) {
    out += ",\"ok\":false,\"http_status\":"; out += code; out += ",\"error\":\"fetch failed\"}";
    http.end(); return;
  }
  String body = http.getString(); http.end();
  out += ",\"ok\":true,\"manifest\":"; out += body; out += "}";
}

// ====================================================================
// Shared assets
// ====================================================================
const char STYLE_CSS[] PROGMEM = R"CSS(
*{box-sizing:border-box;touch-action:manipulation;-webkit-tap-highlight-color:transparent}
body{margin:0;min-height:100vh;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
 background:linear-gradient(180deg,#b8d8e8 0%,#f4e4c1 55%,#c8d8a8 100%);color:#2c3e50;
 padding-top:max(1.5em,env(safe-area-inset-top,1.5em));padding-right:max(1em,env(safe-area-inset-right,1em));
 padding-bottom:max(3em,env(safe-area-inset-bottom,3em));padding-left:max(1em,env(safe-area-inset-left,1em))}
.bg-wash{position:fixed;inset:0;z-index:0;pointer-events:none;background:
 radial-gradient(900px 600px at 50% 8%,rgba(255,255,255,.20),transparent 70%),
 radial-gradient(900px 700px at 50% 100%,rgba(46,68,90,.18),transparent 60%)}
.container{max-width:520px;margin:0 auto;position:relative;z-index:1}
h1{text-align:center;color:#2c3e50;font-weight:300;letter-spacing:.08em;font-size:1.9em;
 margin:.3em 0 .15em;text-shadow:0 1px 2px rgba(255,255,255,.5)}
.subtitle{text-align:center;color:#5d7a8c;margin:0 0 1.6em;font-size:.9em}
.btn{display:flex;align-items:center;width:100%;padding:1.1em 1.2em;margin:.7em 0;font-size:1.1em;
 text-decoration:none;color:#fff;border-radius:14px;border:0;box-shadow:0 3px 8px rgba(0,0,0,.12);
 transition:transform .08s,box-shadow .08s;cursor:pointer}
.btn:active{transform:translateY(2px);box-shadow:0 1px 3px rgba(0,0,0,.12)}
.btn .ico{font-size:1.45em;margin-right:.65em;line-height:1}
.btn-fw{background:#7d9eb0}.btn-diag{background:#5fa099}.btn-bb{background:#9aaf7d}
.btn-fly{background:#6cab5e;font-weight:600}.btn-back{background:#7d9eb0;margin-top:1.5em}
.btn-ch{background:#8e6cab}.btn-map{background:#c98a4a}.danger{background:#c97464}
.mapRow{display:grid;grid-template-columns:auto 1fr auto auto;gap:8px 10px;align-items:center;
 padding:.55em 0;border-bottom:1px solid rgba(125,158,176,.18)}
.mapRow:last-child{border-bottom:0}
.mapRow .out{font-weight:600;color:#3a5165;white-space:nowrap}
.mapRow select{padding:.5em;font-size:1em}
.mapRow .rv{display:flex;align-items:center;gap:.3em;font-size:.85em;color:#5d7a8c;font-weight:600}
.mapRow .rv input{width:auto;margin:0}
.mapRow .lv{font-variant-numeric:tabular-nums;color:#3a5165;font-weight:600;min-width:3.4em;text-align:right}
.inGrid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;font-variant-numeric:tabular-nums}
.inCell{background:rgba(255,255,255,.5);border-radius:8px;padding:.45em .3em;text-align:center;
 box-shadow:inset 0 1px 2px rgba(0,0,0,.06)}
.inCell .n{display:block;color:#5d7a8c;font-size:.72em;font-weight:600}
.inCell .v{display:block;color:#3a5165;font-weight:600;font-size:.98em}
.inCell.act{background:rgba(168,210,154,.7)}
.card{background:rgba(255,255,255,.65);border-radius:14px;padding:1.2em 1.4em;margin:.8em 0;
 box-shadow:0 2px 6px rgba(0,0,0,.06)}
.card h2{margin-top:0;font-weight:500;color:#3a5165}
dl{margin:0}dt{font-weight:600;margin-top:.6em;color:#3a5165}dd{margin-left:0;color:#2c3e50}
code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:.92em;color:#5d3a3a}
label{display:block;font-weight:600;color:#3a5165;margin:.9em 0 .2em}
input,select{width:100%;padding:.7em;font-size:1.05em;border-radius:8px;
 border:1.5px solid rgba(125,158,176,.55);background:rgba(255,255,255,.85);color:#2c3e50}
.chk{display:flex;align-items:center;font-weight:400;margin:.5em 0 0;cursor:pointer}
.chk input{width:auto;margin-right:.5em}
.footer{text-align:center;margin-top:2em;color:#5d7a8c;font-size:.85em}
.muted{color:#7a8b95;font-size:.88em}.big{font-size:2.0em;font-weight:300;line-height:1.1;margin:.1em 0}
.status-card{text-align:center;padding:1.3em;border-radius:18px;margin:1em 0;
 box-shadow:0 4px 14px rgba(0,0,0,.08);transition:background .3s;background:rgba(255,255,255,.6)}
.status-card.up{background:rgba(168,210,154,.85)}.status-card.down{background:rgba(220,160,140,.85)}
.helpBtn{position:fixed;top:max(.7em,env(safe-area-inset-top,.7em));
 right:max(.7em,env(safe-area-inset-right,.7em));width:2.4em;height:2.4em;border-radius:50%;
 background:rgba(255,255,255,.85);color:#3a5165;font:700 1.15em/1 -apple-system,sans-serif;
 border:1.5px solid rgba(125,158,176,.5);cursor:pointer;z-index:50;box-shadow:0 2px 6px rgba(0,0,0,.15);padding:0}
.helpBtn:active{transform:scale(.95)}
.helpModal{position:fixed;inset:0;z-index:100;background:rgba(46,68,90,.55);
 -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);display:flex;align-items:center;
 justify-content:center;padding:1em}
.helpPanel{background:rgba(255,255,255,.96);border-radius:14px;padding:1.3em 1.5em;max-width:500px;
 max-height:85vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.25);color:#2c3e50;line-height:1.5}
.helpPanel h2{margin:0 0 .35em;font-weight:500;font-size:1.35em}
.helpPanel h3{margin:1.1em 0 .3em;font-weight:600;color:#3a5165;font-size:1em}
.helpPanel ul{margin:.3em 0 .3em 1.2em;padding:0}.helpPanel li{margin:.25em 0}
.helpClose{margin-top:1.2em;width:100%;padding:.75em;background:#5fa099;color:#fff;border:0;
 border-radius:10px;font-weight:600;font-size:1em;cursor:pointer}
.chTable{display:grid;grid-template-columns:auto 1fr auto;gap:9px 12px;align-items:center;
 font-variant-numeric:tabular-nums}
.chN{color:#5d7a8c;font-weight:600;font-size:.95em;white-space:nowrap}
.chN.act{color:#2a7d44;font-weight:700}
.track{position:relative;height:26px;background:rgba(255,255,255,.5);border-radius:6px;overflow:hidden;
 box-shadow:inset 0 1px 2px rgba(0,0,0,.08)}
.track:before{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(46,68,90,.18)}
.fill{position:absolute;top:0;bottom:0;left:0;width:0;border-radius:6px;transition:opacity .2s}
.us{color:#3a5165;font-weight:600;min-width:3.4em;text-align:right}
.ver{display:flex;justify-content:space-between;align-items:center;gap:.8em;
 background:rgba(255,255,255,.5);border:1px solid rgba(125,158,176,.22);border-radius:14px;
 padding:1em 1.1em;margin:.7em 0;box-shadow:0 2px 6px rgba(0,0,0,.06)}
.ver.cur{outline:2px solid #6cab5e;outline-offset:-2px}
.vn{font-family:ui-monospace,SFMono-Regular,monospace;font-size:1.35em;color:#2c3e50}
.tag{font-size:.62em;letter-spacing:.14em;text-transform:uppercase;padding:.22em .65em;
 border-radius:999px;color:#fff;margin-left:.55em;vertical-align:middle}
.tag.newer{background:#d4944a}.tag.older{background:#7a8b95}.tag.same{background:#6cab5e}
.vbtn{border:0;border-radius:12px;padding:.8em 1.3em;background:#6cab5e;color:#fff;
 font-weight:700;font-size:1em;cursor:pointer;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.12)}
.vbtn:active{transform:translateY(1px)}
.vbtn.older{background:#d4944a}.vbtn.same{background:#5fa099}.vbtn:disabled{opacity:.45;cursor:default}
.pbar{height:16px;border-radius:9px;background:rgba(125,158,176,.28);overflow:hidden;
 box-shadow:inset 0 1px 2px rgba(0,0,0,.12)}
.pfill{height:100%;width:0;border-radius:9px;transition:width .25s ease-out;background-color:#6cab5e;
 background-image:linear-gradient(45deg,rgba(255,255,255,.25) 25%,transparent 25%,transparent 50%,
 rgba(255,255,255,.25) 50%,rgba(255,255,255,.25) 75%,transparent 75%,transparent);
 background-size:1.1em 1.1em;animation:pstripe .7s linear infinite}
@keyframes pstripe{from{background-position:0 0}to{background-position:1.1em 0}}
.pct{text-align:center;color:#3a5165;font-weight:600;font-variant-numeric:tabular-nums;
 font-size:.85em;margin-top:.3em}
#_load{position:fixed;inset:0;display:none;z-index:2000;align-items:center;justify-content:center;
 background:rgba(46,68,90,.4);-webkit-backdrop-filter:blur(2px);backdrop-filter:blur(2px)}
#_load.show{display:flex}
.loadingBox{background:#3a5165;color:#fff;padding:1.1em 1.6em;border-radius:16px;font-size:1.15em;
 font-weight:700;display:flex;align-items:center;gap:.7em;box-shadow:0 10px 30px rgba(0,0,0,.4)}
.spin{width:20px;height:20px;border:3px solid rgba(255,255,255,.35);border-top-color:#fff;
 border-radius:50%;animation:sp 1s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
)CSS";

const char APP_JS[] PROGMEM = R"JS(
window.LDRC={
 showHelp(){const t=document.getElementById('helpContent');
  const h=t?t.innerHTML:'<p>No help on this page yet.</p>';
  const o=document.createElement('div');o.className='helpModal';
  o.innerHTML='<div class=helpPanel>'+h+'<button class=helpClose type=button>Got it</button></div>';
  const c=()=>o.remove();o.addEventListener('click',e=>{if(e.target===o)c();});
  o.querySelector('.helpClose').addEventListener('click',c);document.body.appendChild(o);},
 showLoading(m){let o=document.getElementById('_load');if(!o){o=document.createElement('div');
  o.id='_load';o.innerHTML='<div class=loadingBox><div class=spin></div><span id=_lm></span></div>';
  document.body.appendChild(o);}document.getElementById('_lm').textContent=m||'Please wait…';
  o.classList.add('show');},
 hideLoading(){const o=document.getElementById('_load');if(o)o.classList.remove('show');}
};
LDRC.navigating=false;
document.addEventListener('click',e=>{if(LDRC.navigating){e.preventDefault();return;}
 const a=e.target.closest('a[href]');if(!a||a.target)return;const h=a.getAttribute('href');
 if(!h||h[0]==='#')return;e.preventDefault();LDRC.navigating=true;LDRC.showLoading('Please wait…');
 requestAnimationFrame(()=>requestAnimationFrame(()=>{location.href=a.href;}));},true);
document.addEventListener('submit',()=>{LDRC.navigating=true;LDRC.showLoading('Please wait…');},true);
window.addEventListener('pageshow',()=>{LDRC.navigating=false;LDRC.hideLoading();});
)JS";

String page(const String& title, const String& body, const String& help = "") {
  String h; h.reserve(body.length() + 1100);
  h += F("<!doctype html><html lang=en><head><meta charset=utf-8>"
         "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
         "<meta name=theme-color content='#5fa099'>"
         "<meta name=apple-mobile-web-app-capable content=yes>"
         "<meta name=apple-mobile-web-app-status-bar-style content=black-translucent>"
         "<meta name=apple-mobile-web-app-title content='LDRC2SIM'><title>");
  h += title; h += F(" &middot; LDRC2SIM</title><link rel=stylesheet href='/style.css?v=");
  h += FW_VERSION;
  h += F("'><script src='/app.js?v=");
  h += FW_VERSION;
  h += F("' defer></script></head><body>"
         "<button class=helpBtn aria-label=Help title=Help onclick='LDRC.showHelp()'>?</button>"
         "<div class=bg-wash aria-hidden=true></div><div class=container>");
  h += body;
  h += F("<div class=footer>"); h += FW_VERSION; h += F("</div></div>");
  if (help.length()) { h += F("<template id=helpContent>"); h += help; h += F("</template>"); }
  h += F("</body></html>");
  return h;
}

// Send a page with Connection: close. On the single-client ESP32 WebServer a
// lingering keep-alive socket can stall the *next* navigation for seconds;
// closing after each page keeps tapping between screens snappy.
void sendPage(const String& title, const String& body, const String& help = "") {
  server.sendHeader("Connection", "close");
  server.send(200, "text/html", page(title, body, help));
}

// ====================================================================
// Handlers
// ====================================================================
void handleStyle() {
  server.sendHeader("Cache-Control", "public, max-age=604800, immutable");
  server.send_P(200, "text/css", STYLE_CSS);
}
void handleAppJs() {
  server.sendHeader("Cache-Control", "public, max-age=604800, immutable");
  server.send_P(200, "application/javascript", APP_JS);
}
void handleFavicon() { server.send(204, "image/x-icon", ""); }  // avoid 404 stalls

void handleStatus() {
  server.sendHeader("Cache-Control", "no-store");
  String j = "{";
  bool link = rc && rc->linkUp();
  j += "\"link\":"; j += link ? "true" : "false";
  j += ",\"proto\":\""; j += rc ? rc->protocolName() : "n/a"; j += "\"";
  j += ",\"ch\":[";
  for (uint8_t i = 0; i < 16; i++) { if (i) j += ","; j += String(rc ? rc->channelUs(i) : 1500); }
  j += "]}";
  server.send(200, "application/json", j);
}

// GET /api/scan — async WiFi scan. Returns {"scanning":true} while in progress,
// then {"networks":[...]} (deduped to the strongest per name). Never blocks, so
// the Wi-Fi page loads and exits instantly.
void handleScan() {
  server.sendHeader("Cache-Control", "no-store");
  int r = WiFi.scanComplete();
  if (r == WIFI_SCAN_RUNNING) { server.send(200, "application/json", "{\"scanning\":true}"); return; }
  if (r == WIFI_SCAN_FAILED)  { WiFi.scanNetworks(true); server.send(200, "application/json", "{\"scanning\":true}"); return; }
  String j = "{\"networks\":[";
  int shown = 0;
  for (int i = 0; i < r && shown < 20; i++) {
    String si = WiFi.SSID(i);
    if (si.length() == 0) continue;
    bool dup = false;                          // keep only the strongest AP of a given name
    for (int k = 0; k < r; k++) {
      if (k == i || WiFi.SSID(k) != si) continue;
      if (WiFi.RSSI(k) > WiFi.RSSI(i) || (WiFi.RSSI(k) == WiFi.RSSI(i) && k < i)) { dup = true; break; }
    }
    if (dup) continue;
    if (shown) j += ",";
    j += "\""; j += jsonEsc(si); j += "\"";
    shown++;
  }
  j += "]}";
  WiFi.scanDelete();
  server.send(200, "application/json", j);
}

void handleRoot() {
  String staState;
  if (WiFi.status() == WL_CONNECTED)
    staState = "<span style='color:#2a7d44'>connected</span> &mdash; <code>" + WiFi.localIP().toString() + "</code>";
  else if (staConfigured)
    staState = "<span class=muted>configured, connecting&hellip;</span>";
  else
    staState = "<span class=muted>not set</span>";

  String b;
  b += F("<h1>LDRC2SIM</h1><p class=subtitle>RC receiver &rarr; USB flight-sim adapter</p>"
         "<div class='status-card down' id=stat>"
         "<div id=txline style='font-size:1.3em;font-weight:500'>&hellip;</div></div>"
         "<a class='btn btn-ch'   href='/channels'><span class=ico>&#128202;</span>Channels</a>"
         "<a class='btn btn-map'  href='/map'><span class=ico>&#128279;</span>Remap channels</a>"
         "<a class='btn btn-fw'   href='/wifi'><span class=ico>&#128246;</span>Wi&#8209;Fi settings</a>"
         "<a class='btn btn-diag' href='/help'><span class=ico>&#128225;</span>Protocols</a>"
         "<a class='btn btn-bb'   href='/update'><span class=ico>&#11014;&#65039;</span>Firmware update</a>"
         "<div class=card><h2>Connection</h2><dl>");
  b += "<dt>Access point</dt><dd><code>" + String(AP_SSID) + "</code> @ <code>" + WiFi.softAPIP().toString() + "</code></dd>";
  b += "<dt>Home Wi&#8209;Fi</dt><dd>" + staState + "</dd>";
  b += F("<dt>Address</dt><dd><code>http://LDRC2SIM.local</code></dd></dl></div>"
         "<script>"
         "async function u(){if(LDRC.navigating)return;try{let d=await(await fetch('/status',{cache:'no-store'})).json();"
         "let s=document.getElementById('stat');"
         "document.getElementById('txline').textContent="
         "d.link?(d.proto+' detected from receiver.'):'Receiver not detected.';"
         "s.className='status-card '+(d.link?'up':'down');}catch(e){}}"
         "setInterval(u,2000);u();</script>");

  String help = F("<h2>Home</h2><p>This adapter reads your RC receiver and presents it to "
    "a flight sim over USB as an 8-axis joystick.</p>"
    "<p><b>There is no protocol to select</b> &mdash; CRSF, SBUS, IBUS and PPM are all "
    "detected automatically from the incoming signal.</p>"
    "<h3>RC link</h3><p>Shows the detected protocol (e.g. <i>CRSF detected from "
    "receiver.</i>) when a receiver is sending, or <i>Receiver not detected.</i> when not. "
    "Green = receiving; amber = no link (the axes hold their last known positions / failsafe).</p>"
    "<h3>Buttons</h3><ul><li><b>Channels</b> &mdash; live bars for each channel.</li>"
    "<li><b>Remap channels</b> &mdash; choose which receiver channel feeds each "
    "of the 8 sim outputs (and reverse any of them).</li>"
    "<li><b>Wi-Fi settings</b> &mdash; join your home network.</li>"
    "<li><b>Protocols</b> &mdash; what's supported and recommended, plus wiring.</li>"
    "<li><b>Firmware update</b> &mdash; over-the-air update.</li></ul>");
  sendPage("Home", b, help);
}

void handleChannels() {
  String b = F("<h1>Channels</h1><p class=subtitle>Live receiver channels</p>"
               "<div class='status-card down' id=cstat>&hellip;</div>"
               "<div class=card><div class=chTable id=tbl>");
  for (uint8_t i = 0; i < 8; i++) {
    int hue = i * 45;
    b += "<div class=chN>Ch " + String(i + 1) + "</div>"
         "<div class=track><div class=fill id=f" + String(i) +
         " style='background:hsl(" + String(hue) + ",65%,58%)'></div></div>"
         "<div class=us id=u" + String(i) + ">&middot;</div>";
  }
  b += F("</div></div>"
         "<a class='btn btn-map' href='/map'><span class=ico>&#128279;</span>Remap channels</a>"
         "<a class='btn btn-back' href='/'><span class=ico>&#8617;</span>Back</a>"
         "<script>"
         "const LO=900,HI=2100;"
         "let tgt=Array(8).fill(50),cur=Array(8).fill(50),live=false;"
         "function paint(d){live=d.link;"
         "let c=document.getElementById('cstat');"
         "c.textContent=live?('Live \\u2014 '+d.proto):'No RC signal';"
         "c.className='status-card '+(live?'up':'down');"
         "for(let i=0;i<8;i++){tgt[i]=Math.max(0,Math.min(100,(d.ch[i]-LO)/(HI-LO)*100));"
         "document.getElementById('u'+i).textContent=d.ch[i];}}"
         // 60fps client-side smoothing: ease each bar toward its latest target.
         "function anim(){for(let i=0;i<8;i++){cur[i]+=(tgt[i]-cur[i])*0.3;"
         "let f=document.getElementById('f'+i);f.style.width=cur[i].toFixed(2)+'%';f.style.opacity=live?1:.35;}"
         "requestAnimationFrame(anim);}requestAnimationFrame(anim);"
         "let stop=false;async function tick(){if(stop||LDRC.navigating)return;"  // stop polling the instant a link is tapped
         "try{let r=await fetch('/status',{cache:'no-store'});if(r.ok)paint(await r.json());}catch(e){}"
         // ~60 Hz poll: plenty for the client-side smoothing, and it leaves the
         // device's single loop free for the low-latency RC->USB path.
         "if(!stop&&!LDRC.navigating)setTimeout(tick,16);}"
         "document.addEventListener('DOMContentLoaded',()=>setTimeout(tick,120));"
         "document.addEventListener('visibilitychange',()=>{stop=document.hidden;if(!stop)tick();});"
         "</script>");
  String help = F("<h2>Channels</h2><p>Live bars for the 8 channels coming from your "
    "receiver, in microseconds (~1000&ndash;2000, centre 1500). Move a stick or switch and "
    "the matching bar should respond instantly.</p>"
    "<p>Green header = RC signal live; amber = no link (values are held at their "
    "last positions and the bars dim).</p>");
  sendPage("Channels", b, help);
}

// Map channels: pick which RX input feeds each of the 8 USB outputs, reverse
// any. Rendered server-side with the current map pre-selected; live values
// come from /status (16 channels). Saves to NVS via /api/map (POST).
void handleMap() {
  String b = F("<h1>Remap channels</h1><p class=subtitle>Receiver inputs &rarr; USB outputs</p>"
               "<div class=card><h2>USB outputs (to the sim)</h2>");
  for (uint8_t o = 0; o < 8; o++) {
    b += "<div class=mapRow><span class=out>Out " + String(o + 1) + "</span><select id=m" + String(o) + ">";
    for (uint8_t in = 0; in < 16; in++) {
      b += "<option value=" + String(in);
      if (userMap[o] == in) b += " selected";
      b += ">Ch " + String(in + 1) + "</option>";
    }
    b += "</select><label class=rv><input type=checkbox id=r" + String(o);
    if (userRev[o]) b += " checked";
    b += ">Rev</label><span class=lv id=lv" + String(o) + ">&middot;</span></div>";
  }
  b += F("</div><div class=card><h2>Receiver inputs (live)</h2><div class=chTable id=ing>");
  for (uint8_t in = 0; in < 16; in++) {
    int hue = (int)(in * 22.5);
    b += "<div class=chN id=cn" + String(in) + ">Ch " + String(in + 1) + "</div>"
         "<div class=track><div class=fill id=if" + String(in) +
         " style='background:hsl(" + String(hue) + ",65%,58%)'></div></div>"
         "<div class=us id=iv" + String(in) + ">&middot;</div>";
  }
  b += F("</div></div>"
         "<div id=msg class=muted style='text-align:center;min-height:1.2em;margin:.3em 0'></div>"
         "<button class='btn btn-fly' type=button onclick='save()'><span class=ico>&#9989;</span>Save mapping</button>"
         "<button class='btn btn-bb'  type=button onclick='rst()'><span class=ico>&#8634;</span>Reset to default</button>"
         "<a class='btn btn-back' href='/'><span class=ico>&#8617;</span>Back</a>"
         "<script>"
         "const DEF_M=[0,1,2,3,4,5,6,7],DEF_R=[0,0,0,0,0,0,0,0];"
         // Hidden baseline (logical channel -> physical RX stream slot) so the
         // live numbers track the right stick even though /status is in raw
         // stream order. Matches BASE_MAP in main.cpp.
         "const BASE=[0,1,3,2,4,5,6,7];function phys(L){return L<8?BASE[L]:L;}"
         "const LO=900,HI=2100;let tgt=Array(16).fill(50),cur=Array(16).fill(50),live=false;"
         "function poll(){if(LDRC.navigating)return;"
         "fetch('/status',{cache:'no-store'}).then(r=>r.json()).then(d=>{"
         "if(!d.ch)return;live=d.link;let used={};"
         "for(let o=0;o<8;o++){let s=+document.getElementById('m'+o).value;used[s]=1;"
         "document.getElementById('lv'+o).textContent=d.ch[phys(s)];}"
         "for(let i=0;i<16;i++){let v=d.ch[phys(i)];"
         "tgt[i]=Math.max(0,Math.min(100,(v-LO)/(HI-LO)*100));"
         "document.getElementById('iv'+i).textContent=v;"
         "document.getElementById('cn'+i).className='chN'+(used[i]?' act':'');}"
         "}).catch(e=>{});if(!LDRC.navigating)setTimeout(poll,90);}"
         // 60fps client-side smoothing, matching the Channels view.
         "function anim(){for(let i=0;i<16;i++){cur[i]+=(tgt[i]-cur[i])*0.3;"
         "let f=document.getElementById('if'+i);f.style.width=cur[i].toFixed(2)+'%';"
         "f.style.opacity=live?1:.35;}requestAnimationFrame(anim);}requestAnimationFrame(anim);"
         "document.addEventListener('DOMContentLoaded',()=>setTimeout(poll,120));"
         "document.querySelectorAll('select').forEach(s=>s.addEventListener('change',poll));"
         "function save(){let m=[],r=[];"
         "for(let o=0;o<8;o++){m.push(document.getElementById('m'+o).value);"
         "r.push(document.getElementById('r'+o).checked?1:0);}"
         "document.getElementById('msg').textContent='Saving\\u2026';"
         "fetch('/api/map',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},"
         "body:'map='+m.join(',')+'&rev='+r.join(',')}).then(r=>r.ok?r.text():Promise.reject())"
         ".then(()=>{document.getElementById('msg').textContent='\\u2713 Saved \\u2014 mapping is live.';})"
         ".catch(()=>{document.getElementById('msg').textContent='Save failed \\u2014 try again.';});}"
         "function rst(){for(let o=0;o<8;o++){document.getElementById('m'+o).value=DEF_M[o];"
         "document.getElementById('r'+o).checked=!!DEF_R[o];}poll();"
         "document.getElementById('msg').textContent='Defaults restored \\u2014 tap Save to apply.';}"
         "</script>");
  String help = F("<h2>Remap channels</h2><p>By default the 8 <b>USB outputs</b> the sim sees are a "
    "simple 1:1 of your channels (Out 1 = Ch 1, Out 2 = Ch 2, &hellip;) &mdash; ready to fly, no "
    "setup needed. You only come here if you want to change something.</p>"
    "<p>Each output can be fed by any of the 16 channels from your receiver: pick a channel for an "
    "output, and tick <b>Rev</b> to reverse its direction. The live bars move as you work the "
    "sticks, and a channel whose label is highlighted is currently mapped to an output. Tap "
    "<b>Save mapping</b> to store it &mdash; it takes effect immediately and survives reboots.</p>"
    "<p><b>Reset to default</b> restores the tidy 1:1 mapping; tap Save to apply it.</p>");
  sendPage("Remap channels", b, help);
}

// POST /api/map  body: map=0,1,3,2,4,5,6,7&rev=0,0,1,0,0,0,0,0
void handleMapSave() {
  String m = server.arg("map"), r = server.arg("rev");
  uint8_t nm[8], nr[8];
  uint8_t cm = 0, cr = 0;
  // parse comma-separated lists
  int start = 0;
  for (uint8_t i = 0; i < 8 && start <= m.length(); i++) {
    int comma = m.indexOf(',', start);
    String tok = (comma < 0) ? m.substring(start) : m.substring(start, comma);
    tok.trim();
    if (tok.length()) { int v = tok.toInt(); if (v < 0) v = 0; if (v > 15) v = 15; nm[cm++] = (uint8_t)v; }
    if (comma < 0) break; start = comma + 1;
  }
  start = 0;
  for (uint8_t i = 0; i < 8 && start <= r.length(); i++) {
    int comma = r.indexOf(',', start);
    String tok = (comma < 0) ? r.substring(start) : r.substring(start, comma);
    tok.trim();
    if (tok.length()) { nr[cr++] = (uint8_t)(tok.toInt() != 0); }
    if (comma < 0) break; start = comma + 1;
  }
  if (cm != 8 || cr != 8) { server.send(400, "text/plain", "expected 8 values"); return; }
  for (uint8_t i = 0; i < 8; i++) { userMap[i] = nm[i]; userRev[i] = nr[i] ? true : false; }
  saveMap();
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "text/plain", "ok");
}

void handleWifi() {
  String b = F("<h1>Wi&#8209;Fi setup</h1><p class=subtitle>Join your home network</p>"
               "<div class=card><form method=POST action='/wifi'>");
  // No blocking scan here (that froze the page on entry AND exit). The list is
  // filled in by JS polling /api/scan, which runs an async scan.
  b += F("<label>Detected networks</label>"
         "<select id=nets onchange=\"document.getElementById('s').value=this.value\">"
         "<option value=''>Scanning&hellip;</option></select>");
  b += "<label>Network name (SSID)</label><input id=s name=ssid value='" + esc(cfgSsid) + "' autocomplete=off>";
  b += F("<label>Password</label><input id=pw name=pass type=password autocomplete=off>"
         "<label class=chk><input type=checkbox onchange=\"document.getElementById('pw').type=this.checked?'text':'password'\">Show password</label>"
         "<button class='btn btn-fly' type=submit><span class=ico>&#9989;</span>Save &amp; connect</button>"
         "</form></div>"
         "<div class=card><h2>Forget network</h2>"
         "<p class=muted>Clear saved credentials and reboot into AP&#8209;only setup.</p>"
         "<form method=POST action='/forget'>"
         "<button class='btn danger' type=submit><span class=ico>&#128465;&#65039;</span>Forget Wi&#8209;Fi</button>"
         "</form></div>"
         "<a class='btn btn-back' href='/'><span class=ico>&#8617;</span>Back</a>"
         "<script>"
         "async function scan(){try{let d=await(await fetch('/api/scan',{cache:'no-store'})).json();"
         "if(d.scanning){setTimeout(scan,900);return;}"
         "let sel=document.getElementById('nets'),ns=d.networks||[];"
         "sel.innerHTML='<option value=\"\">'+(ns.length?'\\u2014 pick or type below \\u2014':'(no networks found)')+'</option>';"
         "ns.forEach(n=>{let o=document.createElement('option');o.value=n;o.textContent=n;sel.appendChild(o);});"
         "}catch(e){setTimeout(scan,1500);}}"
         "document.addEventListener('DOMContentLoaded',scan);</script>");
  String help = F("<h2>Wi-Fi setup</h2><p>Pick or type your home network and password so "
    "LDRC2SIM can join it &mdash; that enables over-the-air updates and "
    "<code>http://LDRC2SIM.local</code> access.</p>"
    "<p>The network list fills in after a moment's scan. <b>LDRC2SIM is 2.4&nbsp;GHz only</b>, "
    "so a 5&nbsp;GHz-only network won't appear &mdash; use its 2.4&nbsp;GHz name. Tick "
    "<b>Show password</b> to check what you typed.</p>"
    "<p>The <code>LDRC2SIM</code> access point stays available either way.</p>");
  sendPage("Wi-Fi", b, help);
}

void handleWifiSave() {
  String s = server.arg("ssid"), p = server.arg("pass");
  if (s.length() == 0) {
    server.send(400, "text/html", page("Wi-Fi", F("<h1>Wi&#8209;Fi</h1><div class=card>SSID cannot be empty. <a href='/wifi'>Back</a></div>")));
    return;
  }
  saveCreds(s, p);
  String b = "<h1>Saved</h1><div class='status-card up'><div class=spin style='margin:0 auto .6em'></div>"
             "<p>Connecting to <code>" + esc(s) + "</code> and rebooting&hellip;</p>"
             "<p class=muted>Reach it at <code>http://LDRC2SIM.local</code> on your home network. "
             "Returning to the home screen shortly&hellip;</p></div>"
             "<script>setTimeout(()=>location.href='/',14000)</script>";
  sendPage("Wi-Fi", b);
  delay(800); ESP.restart();
}

void handleForget() {
  clearCreds();
  String b = F("<h1>Cleared</h1><div class=card><p>Credentials cleared &mdash; rebooting into "
               "<code>LDRC2SIM</code> AP setup.</p><p class=muted>Reconnect to the "
               "<code>LDRC2SIM</code> Wi-Fi, then this returns to the home screen&hellip;</p></div>"
               "<script>setTimeout(()=>location.href='/',9000)</script>");
  sendPage("Wi-Fi", b);
  delay(800); ESP.restart();
}

void handleHelp() {
  String b = F(
    "<h1>Protocols &amp; setup</h1><p class=subtitle>Plug in, fly</p>"
    "<div class='status-card up'><div class=big>&#10003; Automatic protocol detection</div>"
    "<p style='margin:.4em 0 0'>There is <b>no protocol to choose</b> anywhere &mdash; "
    "LDRC2SIM detects CRSF, SBUS, IBUS or PPM on its own from the incoming signal. Unlike "
    "adapters where selecting the right protocol is fiddly, error-prone and frustrating, "
    "here you simply plug in and fly.</p></div>"
    "<div class=card><h2>Connecting your receiver</h2>"
    "<p>Plug the <b>3-pin servo lead</b> carrying your receiver's output into the adapter's "
    "input header. Line up the <b>black (GND) wire</b> with the side marked on the case &mdash; "
    "get that right and the other two follow.</p>"
    "<p>The <b>red</b> wire is power: the adapter currently provides <b>5&nbsp;V</b> on it to run "
    "your receiver. (A future option may switch this to 3.3&nbsp;V.) The signal wire carries any "
    "of the four protocols below &mdash; the adapter detects which automatically.</p></div>"
    "<div class=card><h2>Supported protocols (auto-detected)</h2><dl>"
    "<dt>CRSF &mdash; <span style='color:#2a7d44'>recommended</span></dt>"
    "<dd>ExpressLRS / TBS Crossfire. Modern, high resolution, low latency.</dd>"
    "<dt>SBUS &mdash; <span style='color:#2a7d44'>recommended</span></dt>"
    "<dd>FrSky / Futaba. Inverted, 16 channels, universal and robust.</dd>"
    "<dt>IBUS</dt><dd>FlySky. Works well on FlySky gear.</dd>"
    "<dt>PPM</dt><dd>CPPM pulse train. Universal fallback; lower resolution, &le;8 channels.</dd>"
    "</dl><p class=muted>On power-up it listens briefly for each in turn, then locks on; "
    "if the link drops it re-detects. The sim reads up to 8 proportional channels.</p></div>"
    "<a class='btn btn-back' href='/'><span class=ico>&#8617;</span>Back</a>");
  String help = F("<h2>Protocols</h2><p><b>CRSF</b> and <b>SBUS</b> are recommended for best "
    "resolution and reliability. <b>IBUS</b> suits FlySky; <b>PPM</b> is a universal but "
    "lower-resolution fallback. You don't choose &mdash; detection is automatic.</p>"
    "<h3>Plugging in</h3><p>Use the 3-pin servo lead; align the black GND wire with the marked "
    "side of the case. Red supplies 5&nbsp;V to the receiver.</p>");
  sendPage("Protocols", b, help);
}

void handleUpdateForm() {
  String b = F(
    "<h1>Firmware</h1><p class=subtitle>Update / roll back over the air</p>"
    "<div class='status-card up'><div class=muted>Currently installed</div>"
    "<div class=big id=cur>&hellip;</div>"
    "<div id=msg style='margin-top:.3em;font-size:.92em'>Checking for updates&hellip;</div>"
    "<div id=pwrap style='display:none;margin-top:.7em'>"
    "<div class=pbar><div class=pfill id=pfill></div></div>"
    "<div class=pct id=pct>0%</div></div></div>"
    "<div class=card id=slocal style='display:none'><h2>Local server</h2><div id=vlocal></div></div>"
    "<div class=card id=spublic style='display:none'><h2>messiter.com</h2><div id=vpublic></div></div>"
    "<button class='btn btn-fw' type=button onclick='chk()'><span class=ico>&#8635;</span>Check again</button>"
    "<a class='btn btn-back' href='/'><span class=ico>&#8617;</span>Back</a>");
  b += R"JS(<script>
const $=id=>document.getElementById(id);let cur='',trick=null;
function setp(p){p=Math.min(100,p);$('pfill').style.width=p+'%';$('pct').textContent=Math.round(p)+'%';}
function tup(n){const m=String(n).match(/LDRC2SIM-(\d+)\.(\d+)\.(\d+)/);return m?[+m[1],+m[2],+m[3]]:[0,0,0];}
function cmp(a,b){const x=tup(a),y=tup(b);for(let i=0;i<3;i++)if(x[i]!=y[i])return x[i]-y[i];return 0;}
function vr(n){const m=String(n).match(/LDRC2SIM-(.+)/);return m?m[1]:n;}
function ru(u,base){if(/^https?:/i.test(u))return u;try{return new URL(u,base).href;}catch(e){return u;}}
async function inst(url,name){
 if(!confirm('Install '+vr(name)+'? The device downloads, flashes and reboots (~20s).'))return;
 document.querySelectorAll('.vbtn').forEach(b=>b.disabled=true);
 $('msg').textContent='Installing '+vr(name)+'… downloading & flashing';
 // The install is one blocking call on the device, so we can't read true byte
 // progress; trickle the bar toward ~95% for motion, then snap to 100% when the
 // device replies (just before it reboots). The animated stripe keeps it alive.
 let p=4;$('pwrap').style.display='';setp(p);clearInterval(trick);
 trick=setInterval(()=>{p+=Math.max(0.25,(95-p)*0.035);if(p>95)p=95;setp(p);},220);
 try{const r=await fetch('/api/firmware/install?url='+encodeURIComponent(url),{method:'POST'});
  clearInterval(trick);
  if(r.ok){setp(100);$('msg').textContent='✓ Installed '+vr(name)+'. Rebooting — home in 15s…';
   setTimeout(()=>location.href='/',15000);}
  else{$('pwrap').style.display='none';$('msg').textContent='Failed: '+await r.text();
   document.querySelectorAll('.vbtn').forEach(b=>b.disabled=false);}}
 catch(e){clearInterval(trick);$('pwrap').style.display='none';
  $('msg').textContent='Network error: '+e;document.querySelectorAll('.vbtn').forEach(b=>b.disabled=false);}}
function rend(key,src){const sec=$('s'+key),host=$('v'+key);host.innerHTML='';
 if(!src||!src.ok){sec.style.display='none';return;}
 let vs=((src.manifest&&src.manifest.versions)||[]).slice().sort((a,b)=>cmp(b.name,a.name));
 if(!vs.length){sec.style.display='none';return;}sec.style.display='';
 const nw=vs.filter(v=>cmp(v.name,cur)>0),sm=vs.find(v=>cmp(v.name,cur)==0),
  od=vs.filter(v=>cmp(v.name,cur)<0).slice(0,2),show=[];
 if(nw.length)show.push(nw[0]);if(sm)show.push(sm);od.forEach(v=>show.push(v));
 show.forEach(v=>{const c=cmp(v.name,cur),t=c>0?'newer':c<0?'older':'same',
  lab=c>0?'Newer':c<0?'Older':'Current',verb=c>0?'Install':c<0?'Roll back':'Reinstall',u=ru(v.url,src.manifest_url);
  const row=document.createElement('div');row.className='ver'+(c==0?' cur':'');
  row.innerHTML='<span class=vn>'+vr(v.name)+'<span class="tag '+t+'">'+lab+'</span></span>';
  const b=document.createElement('button');b.className='vbtn '+t;b.textContent=verb;b.onclick=()=>inst(u,v.name);
  row.appendChild(b);host.appendChild(row);});}
async function chk(){$('msg').textContent='Checking…';$('pwrap').style.display='none';$('slocal').style.display='none';$('spublic').style.display='none';
 let j;try{j=await(await fetch('/api/firmware/check',{cache:'no-store'})).json();}catch(e){$('msg').textContent='Error contacting the device.';return;}
 cur=j.current||'';$('cur').textContent=vr(cur);
 if(j.offline){$('msg').textContent='On AP mode — join your home WiFi to reach the update server.';return;}
 rend('local',j.local);rend('public',j.public);
 const any=(j.local&&j.local.ok)||(j.public&&j.public.ok);
 $('msg').textContent=any?'':
  'No update server reachable. On your Mac run: python3 dev/firmware_server.py';}
document.addEventListener('DOMContentLoaded',chk);
</script>)JS";
  String help = F("<h2>Firmware</h2><p>Updates over the air from a firmware server on your "
    "home network (and later messiter.com) &mdash; no file names, no USB.</p>"
    "<h3>Buttons</h3><ul><li><b>Install</b> &mdash; a newer version.</li>"
    "<li><b>Reinstall</b> &mdash; the version you're already on.</li>"
    "<li><b>Roll back</b> &mdash; an older version (undo a bad update).</li></ul>"
    "<p>Tap one, confirm, and the device downloads, flashes and reboots itself (~20s), "
    "then this page returns to the home screen.</p>"
    "<h3>Local server</h3><p>On the Mac, run <code>python3 dev/firmware_server.py</code> and "
    "drop <code>LDRC2SIM-x.y.z.bin</code> builds in <code>dev/</code>.</p>");
  sendPage("Firmware", b, help);
}

void handleUpdateDone() {
  bool ok = !Update.hasError();
  server.sendHeader("Connection", "close");
  String b = ok
    ? F("<h1>Update OK</h1><div class='status-card up'><div class=big>&#9989;</div>"
        "<p>Rebooting into the new firmware&hellip; returning to the home screen shortly.</p></div>"
        "<script>setTimeout(()=>location.href='/',14000)</script>")
    : F("<h1>Update failed</h1><div class='status-card down'><p>Current firmware still "
        "running. <a href='/update'>Try again</a>.</p></div>");
  sendPage("Update", b);
  if (ok) { delay(800); ESP.restart(); }
}

void handleUpdateUpload() {  // kept for curl/dev OTA: curl -F update=@firmware.bin .../update
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START)      Update.begin(UPDATE_SIZE_UNKNOWN);
  else if (up.status == UPLOAD_FILE_WRITE) Update.write(up.buf, up.currentSize);
  else if (up.status == UPLOAD_FILE_END)   Update.end(true);
}

// GET /api/firmware/check — fetch local + public manifests, return combined JSON.
void handleFirmwareCheck() {
  server.sendHeader("Cache-Control", "no-store");
  if (WiFi.status() != WL_CONNECTED) {   // AP-only: can't reach servers
    String j = "{\"current\":\""; j += FW_VERSION; j += "\",\"offline\":true}";
    server.send(200, "application/json", j);
    return;
  }
  String out; out.reserve(2048);
  out  = "{\"current\":\""; out += FW_VERSION; out += "\",\"local\":";
  fetchManifestInto(out, String(FW_LOCAL_MANIFEST), 4000);
  out += ",\"public\":";
  fetchManifestInto(out, String(FW_PUBLIC_MANIFEST), 8000);
  out += "}";
  server.send(200, "application/json", out);
}

// POST /api/firmware/install?url=... — download the .bin and flash it, then reboot.
void handleFirmwareInstall() {
  if (!server.hasArg("url")) { server.send(400, "text/plain", "missing url"); return; }
  String url = server.arg("url"); url.trim();
  if (!(url.startsWith("http://") || isHttps(url))) { server.send(400, "text/plain", "bad url"); return; }
  HTTPClient http; WiFiClient plain; WiFiClientSecure secure;
  http.setConnectTimeout(8000); http.setTimeout(15000);
  if (!httpBeginAny(http, plain, secure, url)) { server.send(500, "text/plain", "begin failed"); return; }
  int code = http.GET();
  if (code != HTTP_CODE_OK) { char m[48]; snprintf(m, sizeof m, "HTTP %d from server", code); http.end(); server.send(502, "text/plain", m); return; }
  int len = http.getSize();
  if (len <= 0) { http.end(); server.send(502, "text/plain", "no content-length"); return; }
  if (!Update.begin((size_t)len)) { http.end(); server.send(500, "text/plain", Update.errorString()); return; }
  WiFiClient* stream = http.getStreamPtr();
  size_t written = Update.writeStream(*stream);
  if (written != (size_t)len) { Update.end(); http.end(); server.send(500, "text/plain", "short write"); return; }
  if (!Update.end(true)) { http.end(); server.send(500, "text/plain", Update.errorString()); return; }
  http.end();
  server.send(200, "text/plain", "ok — rebooting");
  delay(800); ESP.restart();
}

// Captive portal ONLY when AP-only (no home WiFi). On STA, unknown paths get a
// plain 404 — redirecting them to the AP IP (unreachable from home WiFi) is what
// made page loads stall on favicon / OS connectivity probes.
void handleNotFound() {
  if (WiFi.status() != WL_CONNECTED) {
    server.sendHeader("Location", "http://" + WiFi.softAPIP().toString() + "/", true);
    server.send(302, "text/plain", "");
  } else {
    server.send(404, "text/plain", "Not found");
  }
}

// WiFi event hook. When the STA side gets a LAN IP (first connect OR a
// reconnect), (re)start the mDNS responder so LDRC2SIM.local resolves on the
// home network. Started fresh each time because the responder bound before the
// STA had an IP only answers on the AP interface.
void onWifiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
    case ARDUINO_EVENT_WIFI_STA_GOT_IP6:
      MDNS.end();
      if (MDNS.begin(HOSTNAME)) MDNS.addService("http", "tcp", 80);
      mdnsOnLan = true;
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      mdnsOnLan = false;             // watchdog in loop() will retry WiFi.begin()
      break;
    default: break;
  }
}

} // namespace

// ====================================================================
namespace WebPortal {

void begin(RcInput* rcIn) {
  rc = rcIn;
  loadCreds();
  loadMap();
  staConfigured = cfgSsid.length() > 0;

  WiFi.persistent(false);
  WiFi.setHostname(HOSTNAME);
  WiFi.onEvent(onWifiEvent);          // mDNS restart on (re)connect
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(AP_SSID);
  WiFi.setSleep(false);   // disable modem power-save: ~90ms latency -> ~few ms.
                          // Hugely smoother channel bars + snappier pages (USB-powered).
  if (staConfigured) {
    WiFi.setAutoReconnect(true);
    WiFi.begin(cfgSsid.c_str(), cfgPass.c_str());
    lastStaAttemptMs = millis();
  }

  dns.start(DNS_PORT, "*", WiFi.softAPIP());
  MDNS.begin(HOSTNAME);               // covers the AP; restarted for the LAN on GOT_IP
  MDNS.addService("http", "tcp", 80);

  server.on("/",            HTTP_GET,  handleRoot);
  server.on("/style.css",   HTTP_GET,  handleStyle);
  server.on("/app.js",      HTTP_GET,  handleAppJs);
  server.on("/favicon.ico", HTTP_GET,  handleFavicon);
  server.on("/status",      HTTP_GET,  handleStatus);
  server.on("/api/scan",    HTTP_GET,  handleScan);
  server.on("/channels",    HTTP_GET,  handleChannels);
  server.on("/map",         HTTP_GET,  handleMap);
  server.on("/api/map",     HTTP_POST, handleMapSave);
  server.on("/wifi",        HTTP_GET,  handleWifi);
  server.on("/wifi",        HTTP_POST, handleWifiSave);
  server.on("/forget",      HTTP_POST, handleForget);
  server.on("/help",        HTTP_GET,  handleHelp);
  server.on("/update",      HTTP_GET,  handleUpdateForm);
  server.on("/update",      HTTP_POST, handleUpdateDone, handleUpdateUpload);
  server.on("/api/firmware/check",   HTTP_GET,  handleFirmwareCheck);
  server.on("/api/firmware/install", HTTP_POST, handleFirmwareInstall);
  server.onNotFound(handleNotFound);
  server.begin();
}

int8_t homeWifi() {
  if (!staConfigured) return -1;
  return (WiFi.status() == WL_CONNECTED) ? 1 : 0;
}

void loop() {
  dns.processNextRequest();
  server.handleClient();

  // STA reconnect watchdog: if creds are set but we're not on the home network,
  // re-issue WiFi.begin() periodically. Non-blocking (connection completes in
  // the background), so it never stalls the RC->USB path. This is what actually
  // recovers from a router blip / out-of-range when auto-reconnect has given up.
  if (staConfigured && WiFi.status() != WL_CONNECTED) {
    uint32_t now = millis();
    if (now - lastStaAttemptMs >= STA_RETRY_MS) {
      lastStaAttemptMs = now;
      WiFi.begin(cfgSsid.c_str(), cfgPass.c_str());
    }
  }
}

} // namespace WebPortal
