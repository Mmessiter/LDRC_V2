/* RXV2 — demo-mode shim.
 * Intercepts fetch("/api/...") with canned responses captured from a real
 * receiver (Rachel, fw 0.9.219), and synthesises a live channel stream so
 * the View-channels page animates with nobody touching a transmitter.
 * Injected by the apps' demo mode instead of the Bluetooth bridge.
 */
(function () {
  "use strict";
  const _fetch = window.fetch.bind(window);
  const CANNED = {"/api/state.json": {"info": {"fw_version": "RXV2-demo", "build_date": "Jul  9 2026 10:01:30", "name": "Demo RXV2", "name_custom": true, "hostname": "demo", "ip": "0.0.0.0", "mac": "DE:MO:DE:MO:DE:MO", "rssi": -59, "uptime_s": 191, "uptime_str": "0h 3m 11s", "free_heap": 132720, "chip": "ESP32-S3", "chip_rev": 0, "littlefs": true, "ap_ssid": "Rachel", "ap_ip": "192.168.4.1", "partition_running": "app1", "partition_other": "app0", "partition_other_kb": 3264}, "net": {"mode": "WiFi up", "ssid": "(demo)", "ssid_custom": true, "ap_only": false, "ap_auto": false}, "rf": {"packets": 0, "acks_written": 3, "mac_acks_sent": 3, "mac_ack_threshold": 200, "last_pkt_ms": -1, "radios_count": 2, "radios_present": [true, true, false], "loop_hz": 998, "loop_max_us": 1846, "radios_dual": true, "active_radio": 1, "radio_swaps": 0, "fhss_enabled": false, "fhss_idx": 14, "fhss_channel": 82, "telemetry_item": 0, "id_broadcasting": true, "being_flown": false, "sbus_frames_out": 47407, "failsafe_set": false, "gear_ratio": 1.0, "arming_channel": 0, "armed": false, "head_speed": 0, "esc_temp_c": 0.0, "last_channel_ms": -1, "link": {"conn_ms": 0, "packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "hist": [0, 0, 0, 0, 0, 0]}, "board_mac": "E072A1FA5324", "last_payload_len": 0, "last_payload": "", "max_payload_len": 0, "max_payload": "", "self_test": {"verdict": "PASS \u2014 radio responds, registers writable, ready to receive", "begin_ok": true, "chip_connected": true, "channel_ok": true, "data_rate_ok": true, "channel_read": 76, "data_rate_name": "250 kbps"}}, "bind": {"bound": true, "attempts": 0, "pipe": "94 9E 79 E3 E9", "bound_s_ago": 191}, "protocol": {"current": "CRSF", "ppm_inverted": false, "available": [{"id": 1, "name": "CRSF", "desc": "Crossfire/ELRS, 420 kbaud 8N1, ~250 Hz"}, {"id": 0, "name": "SBUS", "desc": "FrSky/Futaba, 100 kbaud 8E2 inverted, ~71 Hz"}, {"id": 2, "name": "IBUS", "desc": "FlySky, 115200 8N1, ~140 Hz"}, {"id": 3, "name": "PPM", "desc": "Single-pin pulse train, 8 ch, ~45 Hz (RMT)"}]}, "sim": false, "fc": {"valid": true, "raw_total": 513, "bytes": 513, "frames": 42, "crc_err": 0, "responses": 0, "last_frame_ms": 813, "v": 0.0, "a": 0.0, "mah": 0, "pct": 0, "rssi": 0, "lq": 0, "snr": 0, "pitch": 0, "roll": 0, "yaw": 0, "flight_mode": "", "raw_dump": "00 0C 08 CB C8 0B 7B EA C8 3F 04 02 52 54 46 4C E7 C8 0A 7B EA C8 30 03 03 04 05 01 59 C8 0A 7B EA C8 31 03 01 00 0C 08 97 C8 0B 7B EA C8 32 04 02 52 54 46 4C 02 C8 0A 7B EA C8 33 03 03 04 05 01 24 C8 0A 7B EA C8 34 03 01 00 0C 08 10 C8 0B 7B EA C8 35 04 02 52 54 46 4C 44 C8 0A 7B EA C8 36 03 03 04 05 01 A3 C8 0A 7B EA C8 37 03 01 00 0C 08 6D C8 0B 7B EA C8 38 04 02 52 54 46 4C A1 "}, "fw": {"manifest_url": ""}, "msp": {"started": true, "active": false, "port": 5760, "bytes_in": 0, "bytes_out": 0, "connections": 0}, "fcinfo": {"detected": true, "variant": "RTFL", "version_known": true, "fw_major": 4, "fw_minor": 6, "fw_patch": 0, "msp_proto": 0, "api_major": 12, "api_minor": 9, "probes_sent": 43, "last_response_ms": 814, "rotorflight_capable": true, "rf_major": 2, "rf_minor": 3}, "channels": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500]}, "/api/events.json": [{"t": 60000, "msg": "Free heap: 137148 B (was 4294967295)"}, {"t": 14774, "msg": "DIAG LOOP-STALL 1117ms"}, {"t": 12344, "msg": "BLE app connected"}, {"t": 4020, "msg": "WiFi up: 192.168.1.204"}, {"t": 1950, "msg": "BLE config on"}, {"t": 1948, "msg": "Trying STA WiFi 'House' (AP also up)"}, {"t": 1941, "msg": "MSP bridge listening :5760"}, {"t": 1905, "msg": "No TX at boot \u2014 WiFi on"}, {"t": 905, "msg": "Boot window: listening for TX..."}, {"t": 856, "msg": "Radios detected: 2 (1:ok 2:ok 3:-)"}, {"t": 706, "msg": "Restored bind 94 9E 79 E3 E9 from NVS"}, {"t": 488, "msg": "NVS: ssid=House pass=yes bind=yes"}, {"t": 467, "msg": "Boot (power-on)"}], "/api/flights.json": [{"i": 0, "count": 0, "dur_ms": 0, "live": true}, {"i": 1, "count": 26, "dur_ms": 24428}], "/api/channels.json": {"ch": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500], "age_ms": -1}, "/api/simmap.json": {"map": [0, 1, 2, 3, 4, 5, 6, 7], "rev": [0, 0, 0, 0, 0, 0, 0, 0]}, "/api/sim/buttons.json": {"btn": [0, 0, 0, 0, 0, 0, 0, 0], "ch": [500, 500, 500, 500, 500, 500, 500, 500]}, "/api/backup/list": {"names": [], "max": 20, "free_bytes": 20480}, "/api/flightlog.json": {"count": 0, "interval_s": 1, "dur_ms": 0, "link": {"packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "conn_ms": 0, "hist": [0, 0, 0, 0, 0, 0]}, "esc": [], "head": [], "v": [], "amps": []}};

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
  };
  // write-code → [read-code, profile-space]  ("rate" | "pid" | null)
  const MSP_SET = { 204: [111, "rate"], 202: [112, "pid"], 95: [94, "pid"],
                    143: [142, null],   149: [148, "pid"] };
  const MSP_READ_SPACE = { 111: "rate", 112: "pid", 94: "pid", 142: null, 148: "pid" };
  const mspStore = (function () {
    try { return JSON.parse(localStorage.getItem("rxv2DemoMsp") || "{}"); }
    catch (e) { return {}; }
  })();
  let rateProfile = 0, pidProfile = 0;
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
    const data = args.get("data") || "";
    if (fn === 210 && data) {               // select rate / PID profile
      const v = parseInt(data.slice(0, 2), 16);
      if (v & 0x80) rateProfile = v & 0x0f; else pidProfile = v & 0x0f;
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

  function J(obj, status) {
    return Promise.resolve(new Response(JSON.stringify(obj), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    }));
  }

  window.fetch = function (input, init) {
    const url = (typeof input === "string") ? input : (input && input.url) || "";
    const q = url.indexOf("?");
    const path = q < 0 ? url : url.slice(0, q);
    const args = new URLSearchParams(q < 0 ? "" : url.slice(q + 1));

    if (!path.startsWith("/api/") && !["/bind", "/fly_arm", "/fly_disarm", "/protocol"].includes(path)) {
      return _fetch(input, init);          // static pages load normally
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
      case "/api/flightlog.json":
        return J(CANNED["/api/flightlog.json"]);
      case "/api/firmware/check":
        // "offline" makes the page skip the update offer quietly.
        return J({ current: "RXV2-demo", offline: true, net_mode: "demo" });
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
    }

    if (path === "/api/state.json") {
      const st = JSON.parse(JSON.stringify(CANNED["/api/state.json"]));
      st.sim = !!demoState.sim;
      st.net.rf_only = !!demoState.rfOnly;
      if (demoState.rfOnly) st.net.mode = "RF only (radios off)";
      if (demoState.name) { st.info.name = demoState.name; st.info.hostname = demoState.name; }
      return J(st);
    }

    if (path in CANNED) return J(CANNED[path]);

    // Every remaining control endpoint is a cheerful no-op in the demo.
    return J({ ok: true, demo: true });
  };
})();
