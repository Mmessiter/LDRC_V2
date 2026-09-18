/* RXV2 — demo-mode shim.
 * Intercepts fetch("/api/...") with canned responses captured from a real
 * receiver (fw 0.9.219), and synthesises a live channel stream so
 * the View-channels page animates with nobody touching a transmitter.
 * Injected by the apps' demo mode instead of the Bluetooth bridge.
 */
(function () {
  "use strict";
  const _fetch = window.fetch.bind(window);
  const CANNED = {"/api/state.json": {"dongle": false, "dongle_link": "uart", "usb_fc": false, "usb_fc_mode": 1, "fc_link": "crsf", "usb": {"host": false, "device": false, "cli": false}, "info": {"fw_version": "RXV2-demo", "build_date": "Jul  9 2026 10:01:30", "name": "Demo RXV2", "name_custom": true, "hostname": "demo", "ip": "0.0.0.0", "mac": "DE:MO:DE:MO:DE:MO", "rssi": -59, "uptime_s": 191, "uptime_str": "0h 3m 11s", "free_heap": 132720, "chip": "ESP32-S3", "chip_rev": 0, "littlefs": true, "ap_ssid": "LDRC_RX", "ap_ip": "192.168.4.1", "partition_running": "app1", "partition_other": "app0", "partition_other_kb": 3264}, "net": {"mode": "WiFi up", "ssid": "(demo)", "ssid_custom": true, "ap_only": false, "ap_auto": false}, "rf": {"packets": 0, "acks_written": 3, "mac_acks_sent": 3, "mac_ack_threshold": 200, "last_pkt_ms": -1, "radios_count": 2, "radios_present": [true, true, false], "loop_hz": 998, "loop_max_us": 1846, "radios_dual": true, "active_radio": 1, "radio_swaps": 0, "fhss_enabled": false, "fhss_idx": 14, "fhss_channel": 82, "telemetry_item": 0, "id_broadcasting": true, "being_flown": false, "sbus_frames_out": 47407, "failsafe_set": false, "gear_ratio": 1.0, "arming_channel": 0, "armed": false, "head_speed": 1852, "esc_temp_c": 43.5, "last_channel_ms": -1, "link": {"conn_ms": 0, "packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "hist": [0, 0, 0, 0, 0, 0]}, "board_mac": "E072A1FA5324", "last_payload_len": 0, "last_payload": "", "max_payload_len": 0, "max_payload": "", "self_test": {"verdict": "PASS \u2014 radio responds, registers writable, ready to receive", "begin_ok": true, "chip_connected": true, "channel_ok": true, "data_rate_ok": true, "channel_read": 76, "data_rate_name": "250 kbps"}}, "bind": {"bound": true, "attempts": 0, "pipe": "94 9E 79 E3 E9", "bound_s_ago": 191}, "protocol": {"current": "CRSF", "ppm_inverted": false, "available": [{"id": 1, "name": "CRSF", "desc": "Crossfire/ELRS, 420 kbaud 8N1, ~250 Hz"}, {"id": 0, "name": "SBUS", "desc": "FrSky/Futaba, 100 kbaud 8E2 inverted, ~71 Hz"}, {"id": 2, "name": "IBUS", "desc": "FlySky, 115200 8N1, ~140 Hz"}, {"id": 3, "name": "PPM", "desc": "Single-pin pulse train, 8 ch, ~45 Hz (RMT)"}]}, "sim": false, "fc": {"valid": true, "raw_total": 513, "bytes": 513, "frames": 42, "crc_err": 0, "responses": 0, "last_frame_ms": 813, "v": 25.21, "a": 14.2, "mah": 862, "pct": 62, "rssi": -58, "lq": 100, "snr": 9, "pitch": -2, "roll": 1, "yaw": 118, "flight_mode": "NORMAL", "raw_dump": "00 0C 08 CB C8 0B 7B EA C8 3F 04 02 52 54 46 4C E7 C8 0A 7B EA C8 30 03 03 04 05 01 59 C8 0A 7B EA C8 31 03 01 00 0C 08 97 C8 0B 7B EA C8 32 04 02 52 54 46 4C 02 C8 0A 7B EA C8 33 03 03 04 05 01 24 C8 0A 7B EA C8 34 03 01 00 0C 08 10 C8 0B 7B EA C8 35 04 02 52 54 46 4C 44 C8 0A 7B EA C8 36 03 03 04 05 01 A3 C8 0A 7B EA C8 37 03 01 00 0C 08 6D C8 0B 7B EA C8 38 04 02 52 54 46 4C A1 "}, "fw": {"manifest_url": ""}, "msp": {"started": true, "active": false, "port": 5760, "bytes_in": 0, "bytes_out": 0, "connections": 0}, "fcinfo": {"detected": true, "variant": "RTFL", "version_known": true, "fw_major": 4, "fw_minor": 6, "fw_patch": 0, "msp_proto": 0, "api_major": 12, "api_minor": 9, "probes_sent": 43, "last_response_ms": 814, "rotorflight_capable": true, "rf_major": 2, "rf_minor": 3, "throttle_ch": 5, "gov_mode": 3, "gov_thr_parked": 0, "gov_thr_max": 0, "telem_cfg_known": true, "telem_cfg_bad": false, "telem_sensors": 7, "telem_mode": 0, "telem_rate": 1000, "telem_ratio": 1, "telem_speed_pref": "fast", "telem_speed_live": "fast", "telem_good_cached": true, "telem_repairs": 0, "telem_checked_ago": 3, "pid_banks": 6, "rate_banks": 6, "banks_shown": 0}, "channels": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500]}, "/api/events.json": [{"t": 60000, "msg": "Free heap: 137148 B (was 4294967295)"}, {"t": 14774, "msg": "DIAG LOOP-STALL 1117ms"}, {"t": 12344, "msg": "BLE app connected"}, {"t": 4020, "msg": "WiFi up: 192.168.1.50"}, {"t": 1950, "msg": "BLE config on"}, {"t": 1948, "msg": "Trying STA WiFi 'Home network' (AP also up)"}, {"t": 1941, "msg": "MSP bridge listening :5760"}, {"t": 1905, "msg": "No TX at boot \u2014 WiFi on"}, {"t": 905, "msg": "Boot window: listening for TX..."}, {"t": 856, "msg": "Radios detected: 2 (1:ok 2:ok 3:-)"}, {"t": 706, "msg": "Restored bind 94 9E 79 E3 E9 from NVS"}, {"t": 488, "msg": "NVS: ssid=Home network pass=yes bind=yes"}, {"t": 467, "msg": "Boot (power-on)"}], "/api/flights.json": [{"i": 0, "count": 0, "dur_ms": 0, "live": true}, {"i": 1, "count": 820, "dur_ms": 820000}, {"i": 2, "count": 475, "dur_ms": 475000}], "/api/channels.json": {"ch": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500], "age_ms": -1}, "/api/simmap.json": {"map": [0, 1, 2, 3, 4, 5, 6, 7], "rev": [0, 0, 0, 0, 0, 0, 0, 0]}, "/api/sim/buttons.json": {"btn": [0, 0, 0, 0, 0, 0, 0, 0], "ch": [500, 500, 500, 500, 500, 500, 500, 500]}, "/api/backup/list": {"names": [], "max": 20, "free_bytes": 20480}, "/api/flightlog.json": {"count": 0, "interval_s": 1, "dur_ms": 0, "link": {"packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "conn_ms": 0, "hist": [0, 0, 0, 0, 0, 0]}, "esc": [], "head": [], "v": [], "amps": []}};

  // ── Synthesised live channels: gentle stick exercise ────────────
  const t0 = Date.now();
  function channels() {
    const t = (Date.now() - t0) / 1000;
    const ch = CANNED["/api/channels.json"].ch.slice();
    ch[0] = Math.round(1500 + 380 * Math.sin(t * 0.9));          // aileron
    ch[1] = Math.round(1500 + 380 * Math.sin(t * 0.7 + 1.3));    // elevator
    ch[2] = Math.round(1500 + 460 * Math.sin(t * 0.23 + 2.1));   // collective
    ch[3] = Math.round(1500 + 300 * Math.sin(t * 1.4 + 0.4));    // rudder
    ch[7] = (Math.floor(t / 6) % 2) ? 2000 : 1000;               // a switch flips
    return ch;
  }
  let streamTimer = null;
  function armStream(ms) {
    if (streamTimer) clearInterval(streamTimer);
    streamTimer = setInterval(() => {
      if (typeof window.__rxStream === "function") {
        window.__rxStream("S|" + channels().join(",") + "|12|0");
      }
    }, Math.max(20, Math.min(200, ms || 50)));
  }


  // ── Simulated Rotorflight flight controller ──────────────────────
  // The Rotorflight pages read/write raw MSP frames via /api/msp. The
  // demo keeps a little FC in localStorage: reads return stored bytes
  // (or authentic-looking defaults), writes persist — so edited PIDs,
  // rates and governor values survive and read back, even across app
  // restarts. Byte layouts match the pages' own decoders (RF 2.3).
  const MSP_DEFAULTS = {
    // MSP_RC_TUNING (111): type 6 ROTORFLIGHT; per axis [rate,expo,shape,-,accel16]
    // Roll 240°/s, Pitch 240°/s, Yaw 300°/s, Collective 12.5; boost tail + yaw dyn.
    111: [6, 48,20,60,0,0,0, 48,20,60,0,0,0, 60,12,40,0,0,0, 100,0,50,0,0,0,
          0,15, 0,15, 0,15, 0,15, 30,25,60],
    // MSP_PID (112): 17 u16 LE — R/P/Y × (P,I,D,F) + boost R/P/Y + h R/P
    112: (function () {
      const w = [50,100,20,100, 50,100,40,100, 80,120,40,0, 0,0,0, 25,25];
      const b = [];
      for (const v of w) { b.push(v & 0xff, (v >> 8) & 0xff); }
      return b;
    })(),
    // MSP_PID_ADVANCED (94): 43 bytes, sparse fields per the page's table
    94: (function () {
      const b = new Array(43).fill(0);
      b[1] = 25;                      // ground error decay
      b[6] = 1;                       // piro compensation on
      b[7] = 45; b[8] = 45; b[9] = 45;      // error limits
      b[10] = 50; b[11] = 50; b[12] = 100;  // bandwidths
      b[13] = 15; b[14] = 15; b[15] = 20;   // D cutoffs
      b[17] = 25; b[18] = 25; b[19] = 0;    // cross coupling
      b[20] = 30; b[21] = 30;               // CW / CCW stop gain
      b[22] = 5;                             // yaw precomp cutoff
      b[23] = 10; b[24] = 0;                 // cyclic / collective FF
      b[36] = 40; b[37] = 40;                // horizon gains
      b[38] = 0; b[39] = 0; b[40] = 0;       // boost gains
      b[41] = 10; b[42] = 20;                // inertia precomp gain / cutoff
      return b;
    })(),
    // MSP_GOVERNOR_CONFIG (142): 42 bytes
    142: (function () {
      const b = new Array(42).fill(0);
      const u16 = (o, v) => { b[o] = v & 0xff; b[o+1] = (v >> 8) & 0xff; };
      b[0] = 2;            // mode: STANDARD
      u16(1, 200);         // startup time 20.0 s
      u16(3, 100);         // spoolup time 10.0 s
      u16(5, 20);          // tracking time 2.0 s
      u16(7, 50);          // recovery time 5.0 s
      u16(9, 50);          // AR hold time
      u16(13, 50);         // auto timeout
      b[19] = 15;          // handover throttle %
      b[20] = 20; b[21] = 20; b[22] = 20; b[23] = 10;   // filters
      b[25] = 0;
      u16(26, 100);        // spooldown
      b[28] = 1;           // throttle type
      return b;
    })(),
    // MSP_GOVERNOR_PROFILE (148): 17 bytes — headspeed 2100 etc.
    148: [2100 & 0xff, (2100 >> 8) & 0xff, 40, 40, 50, 10, 15, 20, 20, 30, 10, 100, 100, 0,0,0,0],
    // MSP_MIXER_CONFIG (42): 21 bytes — 120° swash, total limit 21°
    // (raw 1750 = 21×1000/12), up/down balance +20.0 (raw s8 100). The
    // Travel extents page reads this + per-input frames below.
    42: [0, 0, 0, 0,0, 2, 0, 0,0, 0xD6,0x06, 0,0, 0,0, 0,0, 0, 100, 0, 0],
  };
  // MSP_GET_MIXER_INPUT (174) per-index defaults: rate,min,max as s16 LE.
  // Index 1/2 cyclic (gain 86 %, ±14° = ±1167), 3 yaw (100 %, ±40° = ±1667),
  // 4 collective (gain 230 %, ±14°) — Black Thunder II's real numbers.
  const MIXER_IN_DEFAULTS = (function () {
    const s16 = (v) => { if (v < 0) v += 65536; return [v & 0xff, (v >> 8) & 0xff]; };
    const mk = (rate, min, max) => [].concat(s16(rate), s16(min), s16(max));
    return { 1: mk(860, -1167, 1167), 2: mk(860, -1167, 1167),
             3: mk(1000, -1667, 1667), 4: mk(2300, -1167, 1167) };
  })();
  // write-code → [read-code, profile-space]  ("rate" | "pid" | null)
  const MSP_SET = { 204: [111, "rate"], 202: [112, "pid"], 95: [94, "pid"],
                    143: [142, null],   149: [148, "pid"], 43: [42, null],
                    147: [146, "pid"],  216: [123, null],  222: [131, null],
                    33:  [32, null],    65:  [64, null],   39:  [38, null],
                    37:  [36, null],    81:  [80, null] };
  const MSP_READ_SPACE = { 111: "rate", 112: "pid", 94: "pid", 142: null, 148: "pid", 42: null,
                           146: "pid", 123: null, 131: null, 32: null, 64: null, 38: null, 36: null,
                           34: null, 105: null, 108: null, 120: null, 80: null, 70: null, 101: null };
  // Canned answers for the wizard-era pages (servos, rescue, switches,
  // first-time basics) so the demo shows realistic data instead of
  // "undefined servos" (Malcolm's screenshot, 2026-08-25).
  const u16 = v => { v = ((v % 65536) + 65536) % 65536; return [v & 0xff, (v >> 8) & 0xff]; };
  const SERVO_DEF = [].concat(u16(1500), u16(-700), u16(700), u16(500), u16(500), u16(333), u16(0), u16(0));
  MSP_DEFAULTS[120] = [4].concat(SERVO_DEF, SERVO_DEF, SERVO_DEF, SERVO_DEF);
  MSP_DEFAULTS[146] = [1,1,120,80, 10,25,25,10].concat(u16(650), u16(450), u16(350), u16(500),
                       u16(200), u16(50), u16(20), u16(480), u16(250), u16(2000));
  MSP_DEFAULTS[34]  = [0,1,0x14,0x78, 53,5,0x14,0x78].concat(new Array(18*4).fill(0));
  MSP_DEFAULTS[36]  = [0x08,0x04,0x00,0x0c];
  MSP_DEFAULTS[131] = [].concat(u16(1000), u16(2000), u16(1000), [1,28,1,0], u16(480), [0],
                       [28,28,0,0], [4,4,4,4], u16(11), u16(110), u16(20), u16(90));
  MSP_DEFAULTS[123] = [4,0].concat(u16(400), u16(0), [0,0,0,0], [0,0,0,0]);
  MSP_DEFAULTS[32]  = [].concat(u16(4500), [6,2,2], u16(330), u16(430), u16(420), u16(350), [50,35]);
  MSP_DEFAULTS[64]  = [0,1,2,3,4,5,6,7];
  MSP_DEFAULTS[38]  = [0,0,0,0,0,0];
  MSP_DEFAULTS[108] = [0,0,0,0,0,0];
  MSP_DEFAULTS[105] = [].concat(u16(1500),u16(1500),u16(1500),u16(1500),u16(1500),u16(1700),u16(1500),u16(1500));
  // Flight recorder page (Rotorflight Blackbox): MSP 80 config — supported,
  // device FLASH, mode NORMAL, denom 8, RF's default field set 0x7EE7F,
  // initial-erase 0, rolling 0, grace 5 s. MSP 70 flash summary — flags
  // supported+ready, 256 sectors, 16 MB total, 2.1 MB used. MSP 101 status —
  // PID loop 1000 µs (→ 125 samples/s at 1-in-8), profile bytes patched live.
  MSP_DEFAULTS[80]  = [1, 1, 1].concat(u16(8), [0x7f, 0xee, 0x07, 0x00], u16(0), [0, 5]);
  const FLASH_TOTAL = 16 * 1024 * 1024, FLASH_USED = 2228224;
  const u32 = v => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
  MSP_DEFAULTS[70]  = [3].concat(u32(256), u32(FLASH_TOTAL), u32(FLASH_USED));
  MSP_DEFAULTS[101] = [].concat(u16(1000), u16(125), u16(0x21), [0,0,0,0], [0], u16(300), u16(180), [0],
                       [26], [0,0,0,0], [0, 2], [0, 6, 0, 6], [1, 4, 1]);
  const mspStore = (function () {
    try { return JSON.parse(localStorage.getItem("rxv2DemoMsp") || "{}"); }
    catch (e) { return {}; }
  })();
  let rateProfile = 0, pidProfile = 0;
  let demoBanksShown = 0;            // 0 = all of them (0.9.742)
  function mspKey(fn, space) {
    return fn + "/" + (space === "rate" ? rateProfile : space === "pid" ? pidProfile : 0);
  }
  function toHex(bytes) {
    return bytes.map(v => (v & 0xff).toString(16).padStart(2, "0")).join("");
  }
  function T(text) {
    return Promise.resolve(new Response(text, {
      status: 200, headers: { "Content-Type": "text/plain" },
    }));
  }
  function mspHandle(args) {
    const fn = parseInt(args.get("fn") || "0", 10);
    let data = args.get("data") || "";
    if (fn === 210 && data) {               // select rate / PID profile
      const v = parseInt(data.slice(0, 2), 16);
      if (v & 0x80) rateProfile = v & 0x0f; else pidProfile = v & 0x0f;
      return T("");
    }
    if (fn === 174 && data) {               // read one mixer input by index
      const idx = parseInt(data.slice(0, 2), 16);
      const stored = mspStore["174/" + idx];
      return T(stored || toHex(MIXER_IN_DEFAULTS[idx] || [0,0,0,0,0,0]));
    }
    if (fn === 171 && data) {               // write one mixer input: idx + 6 bytes
      const idx = parseInt(data.slice(0, 2), 16);
      mspStore["174/" + idx] = data.slice(2).toLowerCase();
      try { localStorage.setItem("rxv2DemoMsp", JSON.stringify(mspStore)); } catch (e) {}
      return T("");
    }
    if (fn === 212 && data) {               // write one servo: idx + 16 bytes
      const idx = parseInt(data.slice(0, 2), 16);
      mspStore["120s/" + idx] = data.slice(2).toLowerCase();
      try { localStorage.setItem("rxv2DemoMsp", JSON.stringify(mspStore)); } catch (e) {}
      return T("");
    }
    if (fn === 120) {                       // assemble servo config from stored edits
      let out = "04";
      for (let i = 0; i < 4; i++) out += mspStore["120s/" + i] || toHex(SERVO_DEF);
      return T(out);
    }
    if (fn === 222 && data) {               // motor config: the 28-B write lacks the motorCount byte the 29-B read has at [6]
      data = data.slice(0, 12) + "01" + data.slice(12);
    }
    if (fn === 81 && data) {                // blackbox config: the 12-B write lacks the "supported" byte the 13-B read leads with
      data = "01" + data;
    }
    if (fn === 72) {                        // erase the (pretend) dataflash: used bytes → 0
      mspStore["70/0"] = toHex([3].concat(u32(256), u32(FLASH_TOTAL), u32(0)));
      try { localStorage.setItem("rxv2DemoMsp", JSON.stringify(mspStore)); } catch (e) {}
      return T("");
    }
    if (fn === 101) {                       // status: current PID / rate profile indexes
      const b = MSP_DEFAULTS[101].slice(); b[23] = pidProfile; b[25] = rateProfile;
      return T(toHex(b));
    }
    if (fn === 183 && data.length >= 6) {   // MSP_COPY_PROFILE [type, dst, src] (Copy-a-bank page)
      const type = parseInt(data.slice(0, 2), 16), dst = parseInt(data.slice(2, 4), 16) & 0x0f,
            src  = parseInt(data.slice(4, 6), 16) & 0x0f;
      const fns = type === 0 ? [112, 94, 148, 146] : [111];   // PID profile carries the governor + rescue
      for (const f of fns) {
        const v = mspStore[f + "/" + src];
        if (v) mspStore[f + "/" + dst] = v; else delete mspStore[f + "/" + dst];
      }
      try { localStorage.setItem("rxv2DemoMsp", JSON.stringify(mspStore)); } catch (e) {}
      return T("");
    }
    if (fn in MSP_SET && data) {            // write: persist for the paired read
      const [readFn, space] = MSP_SET[fn];
      mspStore[mspKey(readFn, space)] = data.toLowerCase();
      try { localStorage.setItem("rxv2DemoMsp", JSON.stringify(mspStore)); } catch (e) {}
      return T("");
    }
    if (fn in MSP_READ_SPACE) {             // read: stored beats defaults
      const stored = mspStore[mspKey(fn, MSP_READ_SPACE[fn])];
      return T(stored || toHex(MSP_DEFAULTS[fn]));
    }
    return T("");                            // EEPROM write, reboot, etc.
  }

  // ── Persistent demo state (sim mode, receiver name) ─────────────
  // Every page navigation loads a fresh copy of this shim, so anything
  // the user changes has to live in localStorage to survive.
  const demoState = (function () {
    try { return JSON.parse(localStorage.getItem("rxv2DemoState") || "{}"); }
    catch (e) { return {}; }
  })();
  function saveDemoState() {
    try { localStorage.setItem("rxv2DemoState", JSON.stringify(demoState)); }
    catch (e) {}
  }
  // Which demo: the app says so on every page it serves (window.__demoDongle).
  if (typeof window.__demoDongle === "boolean") { demoState.dongle = window.__demoDongle; saveDemoState(); }

  function J(obj, status) {
    return Promise.resolve(new Response(JSON.stringify(obj), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    }));
  }

  // ── Synthesised saved flights ─────────────────────────────────────
  // The Flight-analysis page was blank in demo (Malcolm 2026-08-14:
  // "newer demo screens lack imaginary data"). Deterministic per index so
  // the graphs look the same on every visit: flight 1 is a 13½-minute
  // hover with occasional climbs; flight 2 a shorter tuning session whose
  // param_ops > 0 shows the friendly "screens were viewed" note.
  function synthFlight(f) {
    const n = f === 2 ? 475 : 820;                   // samples at 1 s
    const esc = [], head = [], v = [], amps = [];
    let temp = 24, volts = 25.2;
    for (let i = 0; i < n; i++) {
      const spool = Math.min(1, i / 18);             // 18 s spool-up
      const land  = i > n - 25 ? (n - i) / 25 : 1;   // spool-down at the end
      const wob   = Math.sin(i / 7) * 12 + Math.sin(i / 23) * 18;
      const climb = (Math.sin(i / 41) > 0.82) ? 1 : 0;
      const rpm   = Math.round((1850 + wob - climb * 45) * spool * land);
      const a     = +(0.3 + spool * land * (7.5 + climb * 11 + Math.sin(i / 13) * 1.4)).toFixed(1);
      volts -= a * 0.00012;                          // pack drains with load
      temp  += (spool * land * (30 + climb * 10) + 24 - temp) * 0.01;
      esc.push(Math.round(temp));
      head.push(Math.max(0, rpm));
      v.push(+(volts - a * 0.008).toFixed(2));       // droop under current
      amps.push(a);
    }
    const durMs = n * 1000;
    return {
      count: n, interval_s: 1, dur_ms: durMs,
      saved_at: Math.floor(Date.now() / 1000) - (f === 2 ? 86400 : 3600),
      link: { packets: durMs / 2, max_gap_ms: f === 2 ? 61.2 : 26.4,
              max_gap_at_ms: Math.round(durMs * 0.37), avg_gap_ms: 0.92,
              conn_ms: durMs,
              hist: f === 2 ? [214, 41, 2, 6, 1, 0] : [92, 18, 0, 2, 0, 0],
              swaps: f === 2 ? 9 : 3,
              radio_ms: [Math.round(durMs * 0.6), Math.round(durMs * 0.4), 0],
              param_ops: f === 2 ? 4 : 0 },
      esc, head, v, amps,
    };
  }

  window.fetch = function (input, init) {
    const url = (typeof input === "string") ? input : (input && input.url) || "";
    const q = url.indexOf("?");
    const path = q < 0 ? url : url.slice(0, q);
    const args = new URLSearchParams(q < 0 ? "" : url.slice(q + 1));

    if (!path.startsWith("/api/") && !["/bind", "/fly_arm", "/fly_disarm", "/protocol"].includes(path)) {
      return _fetch(input, init);          // static pages load normally
    }

    // Banks (0.9.742): the demo FC reports six of each (see the MSP 101
    // canned reply below), and the demo remembers a "how many banks" choice
    // for as long as the page is open.
    if (path === "/api/banks.json")
      return J({ pid: 6, rate: 6, shown: demoBanksShown, fc: true });
    if (path === "/api/fc/banks") {
      const n = parseInt(args.get("show") || "0", 10);
      if (!(n >= 0 && n <= 6)) return J({ ok: false, err: "show must be 0 (all) to 6" }, 400);
      demoBanksShown = n;
      return J({ ok: true, banks_shown: n, pid_banks: 6, rate_banks: 6 });
    }

    if (path === "/api/msp") return mspHandle(args);

    switch (path) {
      case "/api/channels.json": {
        const c = CANNED["/api/channels.json"];
        return J({ ch: channels(), age_ms: 12, arm: c.arm });
      }
      case "/api/channels.stream":
        armStream(parseInt(args.get("ms") || "50", 10));
        return J({ ok: true });
      case "/api/flightlog.json": {
        const f = parseInt(args.get("f") || "0", 10);
        if (f > 0) return J(synthFlight(f));
        return J(CANNED["/api/flightlog.json"]);   // live flight: none in demo
      }
      case "/api/firmware/check":
        // "offline" makes the page skip the RECEIVER update offer quietly.
        // The Rotorflight block still has to be here: the demo's flight
        // controller is a real 4.6.0, so "Check for a Rotorflight update"
        // should answer "up to date" exactly as a real receiver would,
        // rather than "could not check" on a phone that plainly has internet.
        return J({ current: "RXV2-demo", offline: true, net_mode: "demo",
                   rotorflight: { firmware: "4.6.0", api: 1209, suite: "2.3",
                                  released: "2026-06-30",
                                  notes_url: "https://github.com/rotorflight/rotorflight-firmware/releases" } });
      case "/api/gear": {                    // receiver head-speed divisor (gear.js resets it to 1)
        const r = parseFloat(args.get("ratio") || "1");
        demoState.gear = (r > 0.1 && r <= 100) ? r : 1;
        saveDemoState();
        return J({ ok: true, gear_ratio: demoState.gear });
      }
      case "/api/name":
        if (args.get("name")) { demoState.name = args.get("name"); saveDemoState(); }
        return J({ ok: true, name: demoState.name ||
                   CANNED["/api/state.json"].info.name });
      case "/fly_arm":
        demoState.rfOnly = true; saveDemoState();
        return J({ ok: true });
      case "/fly_disarm":
        // the "reboot" — radios return
        demoState.rfOnly = false; saveDemoState();
        return J({ ok: true });
      case "/api/dongle":
      case "/api/usbfc":
        // Not switchable inside the demo any more: the front list offers both demos.
        return Promise.resolve(new Response('<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><body style="font-family:-apple-system,Helvetica,sans-serif;padding:2em;background:#f4f7fa;color:#2c3e50"><h2>Demo</h2><p>The demo cannot switch between receiver and dongle here. Close the demo and choose <b>Try the receiver demo</b> or <b>Try the dongle demo</b> on the app\'s front list.</p><p><a href="/">Back</a></p></body>', { status: 200, headers: { "Content-Type": "text/html" } }));
      case "/api/sim": {
        // The page confirms first, shows its "rebooting" card, THEN posts
        // here — flip the persistent flag so the "rebooted" receiver
        // really is in (or out of) simulator mode when the page returns.
        const body = (init && init.body) ? String(init.body) : "";
        const on = new URLSearchParams(body).get("on") === "1";
        demoState.sim = on;
        saveDemoState();
        return J({ ok: true, sim: on });
      }
      case "/api/fc/telemetry/speed":
        // 0.9.563: the demo FC already runs fast telemetry (1000/1).
        return J({ ok: true, applied: false, message: "the flight controller already runs fast telemetry (link rate 1000/1)" });
      case "/api/fc/telemetry/restore":
        return J({ ok: true, message: "Rotorflight telemetry setup restored (7 sensors, fast speed) - FC restarting" });
    }

    if (path === "/api/state.json") {
      const st = JSON.parse(JSON.stringify(CANNED["/api/state.json"]));
      st.sim = !!demoState.sim;
      if (demoState.dongle) {                        // the dongle demo: the app on a Rotorflight dongle, flight controller on USB
        st.dongle = true; st.dongle_auto = true; st.dongle_mode = 0; st.dongle_link = "usb"; st.fc_link = "usb"; st.usb_fc = false;
        st.usb = { host: true, device: true, vid: "0483", pid: "5740", cli: false };
        if (!demoState.name) { st.info.name = "Demo dongle"; st.info.hostname = "demo-dongle"; }
        if (st.fcinfo) st.fcinfo.detected = true;
        if (st.rf) { st.rf.last_pkt_ms = -1; st.rf.packets = 0; }
        if (st.bind) st.bind.bound = false;
      }
      st.net.rf_only = !!demoState.rfOnly;
      if (demoState.rfOnly) st.net.mode = "RF only (radios off)";
      if (demoState.name) { st.info.name = demoState.name; st.info.hostname = demoState.name; }
      if (demoState.gear != null) st.rf.gear_ratio = demoState.gear;
      return J(st);
    }

    if (path in CANNED) return J(CANNED[path]);

    // Every remaining control endpoint is a cheerful no-op in the demo.
    return J({ ok: true, demo: true });
  };
})();
