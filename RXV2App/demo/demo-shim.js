/* RXV2 — demo-mode shim.
 * Intercepts fetch("/api/...") with canned responses captured from a real
 * receiver (Rachel, fw 0.9.219), and synthesises a live channel stream so
 * the View-channels page animates with nobody touching a transmitter.
 * Injected by the apps' demo mode instead of the Bluetooth bridge.
 */
(function () {
  "use strict";
  const _fetch = window.fetch.bind(window);
  const CANNED = {"/api/state.json": {"info": {"fw_version": "RXV2-demo", "build_date": "Jul  9 2026 10:01:30", "name": "Demo RXV2", "name_custom": true, "hostname": "demo", "ip": "0.0.0.0", "mac": "DE:MO:DE:MO:DE:MO", "rssi": -59, "uptime_s": 191, "uptime_str": "0h 3m 11s", "free_heap": 132720, "chip": "ESP32-S3", "chip_rev": 0, "littlefs": true, "ap_ssid": "Rachel", "ap_ip": "192.168.4.1", "partition_running": "app1", "partition_other": "app0", "partition_other_kb": 3264}, "net": {"mode": "WiFi up", "ssid": "(demo)", "ssid_custom": true, "ap_only": false, "ap_auto": false}, "rf": {"packets": 0, "acks_written": 3, "mac_acks_sent": 3, "mac_ack_threshold": 200, "last_pkt_ms": -1, "radios_count": 2, "radios_present": [true, true, false], "loop_hz": 998, "loop_max_us": 1846, "radios_dual": true, "active_radio": 1, "radio_swaps": 0, "fhss_enabled": false, "fhss_idx": 14, "fhss_channel": 82, "telemetry_item": 0, "id_broadcasting": true, "being_flown": false, "sbus_frames_out": 47407, "failsafe_set": false, "gear_ratio": 1.0, "arming_channel": 0, "armed": false, "head_speed": 0, "esc_temp_c": 0.0, "last_channel_ms": -1, "link": {"conn_ms": 0, "packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "hist": [0, 0, 0, 0, 0, 0]}, "board_mac": "E072A1FA5324", "last_payload_len": 0, "last_payload": "", "max_payload_len": 0, "max_payload": "", "self_test": {"verdict": "PASS \u2014 radio responds, registers writable, ready to receive", "begin_ok": true, "chip_connected": true, "channel_ok": true, "data_rate_ok": true, "channel_read": 76, "data_rate_name": "250 kbps"}}, "bind": {"bound": true, "attempts": 0, "pipe": "94 9E 79 E3 E9", "bound_s_ago": 191}, "protocol": {"current": "CRSF", "ppm_inverted": false, "available": [{"id": 1, "name": "CRSF", "desc": "Crossfire/ELRS, 420 kbaud 8N1, ~250 Hz"}, {"id": 0, "name": "SBUS", "desc": "FrSky/Futaba, 100 kbaud 8E2 inverted, ~71 Hz"}, {"id": 2, "name": "IBUS", "desc": "FlySky, 115200 8N1, ~140 Hz"}, {"id": 3, "name": "PPM", "desc": "Single-pin pulse train, 8 ch, ~45 Hz (RMT)"}]}, "sim": false, "fc": {"valid": true, "raw_total": 513, "bytes": 513, "frames": 42, "crc_err": 0, "responses": 0, "last_frame_ms": 813, "v": 0.0, "a": 0.0, "mah": 0, "pct": 0, "rssi": 0, "lq": 0, "snr": 0, "pitch": 0, "roll": 0, "yaw": 0, "flight_mode": "", "raw_dump": "00 0C 08 CB C8 0B 7B EA C8 3F 04 02 52 54 46 4C E7 C8 0A 7B EA C8 30 03 03 04 05 01 59 C8 0A 7B EA C8 31 03 01 00 0C 08 97 C8 0B 7B EA C8 32 04 02 52 54 46 4C 02 C8 0A 7B EA C8 33 03 03 04 05 01 24 C8 0A 7B EA C8 34 03 01 00 0C 08 10 C8 0B 7B EA C8 35 04 02 52 54 46 4C 44 C8 0A 7B EA C8 36 03 03 04 05 01 A3 C8 0A 7B EA C8 37 03 01 00 0C 08 6D C8 0B 7B EA C8 38 04 02 52 54 46 4C A1 "}, "fw": {"manifest_url": ""}, "msp": {"started": true, "active": false, "port": 5760, "bytes_in": 0, "bytes_out": 0, "connections": 0}, "fcinfo": {"detected": true, "variant": "RTFL", "version_known": true, "fw_major": 4, "fw_minor": 5, "fw_patch": 1, "msp_proto": 0, "api_major": 12, "api_minor": 8, "probes_sent": 43, "last_response_ms": 814, "rotorflight_capable": true, "rf_major": 2, "rf_minor": 2}, "channels": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500]}, "/api/events.json": [{"t": 60000, "msg": "Free heap: 137148 B (was 4294967295)"}, {"t": 14774, "msg": "DIAG LOOP-STALL 1117ms"}, {"t": 12344, "msg": "BLE app connected"}, {"t": 4020, "msg": "WiFi up: 192.168.1.204"}, {"t": 1950, "msg": "BLE config on"}, {"t": 1948, "msg": "Trying STA WiFi 'House' (AP also up)"}, {"t": 1941, "msg": "MSP bridge listening :5760"}, {"t": 1905, "msg": "No TX at boot \u2014 WiFi on"}, {"t": 905, "msg": "Boot window: listening for TX..."}, {"t": 856, "msg": "Radios detected: 2 (1:ok 2:ok 3:-)"}, {"t": 706, "msg": "Restored bind 94 9E 79 E3 E9 from NVS"}, {"t": 488, "msg": "NVS: ssid=House pass=yes bind=yes"}, {"t": 467, "msg": "Boot (power-on)"}], "/api/flights.json": [{"i": 0, "count": 0, "dur_ms": 0, "live": true}, {"i": 1, "count": 26, "dur_ms": 24428}], "/api/channels.json": {"ch": [1500, 1500, 1500, 1500, 1500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500], "age_ms": -1}, "/api/simmap.json": {"map": [0, 1, 2, 3, 4, 5, 6, 7], "rev": [0, 0, 0, 0, 0, 0, 0, 0]}, "/api/sim/buttons.json": {"btn": [0, 0, 0, 0, 0, 0, 0, 0], "ch": [500, 500, 500, 500, 500, 500, 500, 500]}, "/api/backup/list": {"names": [], "max": 20, "free_bytes": 20480}, "/api/flightlog.json": {"count": 0, "interval_s": 1, "dur_ms": 0, "link": {"packets": 0, "max_gap_ms": 0.0, "avg_gap_ms": 0.0, "conn_ms": 0, "hist": [0, 0, 0, 0, 0, 0]}, "esc": [], "head": [], "v": [], "amps": []}};

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

    if (!path.startsWith("/api/") && !["/bind", "/fly_arm", "/protocol"].includes(path)) {
      return _fetch(input, init);          // static pages load normally
    }

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
        if (args.get("name")) CANNED["/api/state.json"].info.name = args.get("name");
        return J({ ok: true, name: CANNED["/api/state.json"].info.name });
    }

    if (path in CANNED) return J(CANNED[path]);

    // Every remaining control endpoint is a cheerful no-op in the demo.
    return J({ ok: true, demo: true });
  };
})();
