// LockDownRadioControl — RXV2 web UI shared helpers
//
// All pages link this script. It provides:
//   - fetchState()        — hits /api/state.json
//   - fetchEvents()       — hits /api/events.json (Black-box only)
//   - setText(id, value)  — populates an element by id, no-op if absent
//   - setHtml(id, value)  — same but innerHTML (use for trusted markup only)
//   - mountFooter()       — drops the FW version line into <div class=footer>
//   - startPolling(fn,ms) — calls fn() every ms, after the first fetch resolves
//
// Pages call mountFooter() once and (optionally) startPolling() for live data.

(function(){
    'use strict';

    window.LDRC = {
        state: null,
        // Pages that only mean something on a receiver (radio, channel
        // output, flight records). A dongle shows a one-line note instead
        // and Find a setting leaves them out (Malcolm 2026-09-10).
        // Pages that need OUR radio and so make no sense on a dongle.
        // /diagnostics came off this list in 0.9.702: a dongle reads the
        // channels from the flight controller over MSP instead, so View
        // channels works there and shows the whole chain.
        RX_ONLY: ['/bind', '/blackbox', '/flight', '/fly', '/map', '/protocol', '/rxsettings', '/sim', '/simctl', '/views'],
        async dongleGuard() {
            const path = location.pathname.replace(/\.html$/, '').replace(/\/index$/, '/');
            if (!this.RX_ONLY.includes(path)) return false;
            let s = this.state;
            if (!s) { try { s = await Promise.race([this.fetchState(), new Promise(r => setTimeout(() => r(null), 2500))]); } catch (e) { s = null; } }
            if (!s || !s.dongle) return false;
            const keep = new Set(['searchBtn', 'homeBtn', 'backBtn', 'helpBtn']);
            for (const el of Array.from(document.body.children)) {
                if (el.tagName === 'SCRIPT') continue;
                if (Array.from(el.classList).some(c => keep.has(c))) continue;
                el.style.display = 'none';
            }
            const d = document.createElement('div');
            d.innerHTML = '<h1>Not on a dongle</h1><div class=card style="text-align:center"><p>This page belongs to a receiver. A dongle has no radio, so there is nothing here to set.</p>'
                        + '<a class=btn href="/" style="background:#8e6cab;display:inline-block;margin-top:.6em">Home</a></div>';
            document.body.appendChild(d);
            return true;
        },
        events: null,

        // True when this page is served through an app's Bluetooth bridge
        // rather than WiFi/HTTP. iOS uses a custom ble:// scheme; ANDROID
        // masquerades as https://rxv2.local — checking only the scheme left
        // every viaBle branch taking the WiFi path inside the Android app
        // (found 2026-07-29 via the rename white-screen saga).
        viaBle: location.protocol === 'ble:' || location.hostname === 'rxv2.local',

        // True in the app's "Review last session" (receiver off, edits go to
        // the phone). Resolved via LDRC.replayReady (set at the bottom of
        // this file) — pages that need the answer during their FIRST load
        // `await LDRC.replayReady` before wording their messages.
        replay: false,
        replayReady: Promise.resolve(false),

        async fetchState() {
            try {
                const r = await fetch('/api/state.json', { cache: 'no-store' });
                if (!r.ok) return null;
                this.state = await r.json();
                return this.state;
            } catch (e) { return null; }
        },

        async fetchEvents() {
            try {
                const r = await fetch('/api/events.json', { cache: 'no-store' });
                if (!r.ok) return null;
                this.events = await r.json();
                return this.events;
            } catch (e) { return null; }
        },

        setText(id, value) {
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = (value === undefined || value === null) ? '' : String(value);
        },

        setHtml(id, value) {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = (value === undefined || value === null) ? '' : String(value);
        },

        setClass(id, cls, on) {
            const el = document.getElementById(id);
            if (!el) return;
            el.classList.toggle(cls, !!on);
        },

        // Format helpers
        msAgo(ms) {
            if (ms === undefined || ms === null || ms < 0) return 'never';
            return ms + ' ms ago';
        },

        sAgo(s) {
            if (s === undefined || s === null || s < 0) return 'never';
            return s + ' s ago';
        },

        mountFooter() {
            const f = document.querySelector('.footer');
            if (!f) return;
            // Populated by the first state fetch; until then show what the
            // last visit saw (Malcolm 2026-09-10: no 'loading...' flash).
            if (!f.textContent.trim()) { try { f.textContent = localStorage.getItem('ldrc.footer') || ''; } catch (e) { f.textContent = ''; } }
        },

        // Drop-in async replacement for window.confirm — colourful modal.
        // Usage: if (await LDRC.confirm('Write to EEPROM?')) ...
        // Options: { title, message, icon, yes, no, kind: 'go'|'warn'|'danger' }
        confirm(message, opts) {
            opts = opts || {};
            const kind = opts.kind || 'go';    // 'go' (green) | 'warn' (amber) | 'danger' (red)
            return new Promise(resolve => {
                let ov = document.getElementById('_ldrcModal');
                if (!ov) {
                    ov = document.createElement('div');
                    ov.id = '_ldrcModal';
                    ov.className = 'modalOverlay';
                    ov.innerHTML = '<div class=modalBox>'
                        + '<div class=modalAccent id=_mAcc>'
                        +   '<div class=modalIcon id=_mIcon>⚡</div>'
                        +   '<div class=modalTitle id=_mTitle></div>'
                        + '</div>'
                        + '<div class=modalMsg id=_mMsg></div>'
                        + '<div class=modalBtns>'
                        +   '<button class="modalBtn no" id=_mNo>Cancel</button>'
                        +   '<button class="modalBtn yes" id=_mYes>OK</button>'
                        + '</div></div>';
                    document.body.appendChild(ov);
                }
                const acc   = document.getElementById('_mAcc');
                const yesBt = document.getElementById('_mYes');
                const noBt  = document.getElementById('_mNo');
                acc.className = 'modalAccent' + (kind === 'warn' ? ' warn' : kind === 'danger' ? ' danger' : '');
                yesBt.className = 'modalBtn yes' + (kind === 'warn' ? ' warn' : kind === 'danger' ? ' danger' : '');
                document.getElementById('_mIcon').textContent  = opts.icon  || (kind === 'danger' ? '⚠️' : kind === 'warn' ? '✏️' : '💾');
                document.getElementById('_mTitle').textContent = opts.title || (kind === 'danger' ? 'Are you sure?' : 'Confirm');
                document.getElementById('_mMsg').textContent   = message;
                yesBt.textContent = opts.yes || 'Yes, do it';
                noBt.textContent  = opts.no  || 'Cancel';
                noBt.style.display = '';   // restore in case alert() hid it on the shared modal
                const close = (ok) => { ov.classList.remove('show'); yesBt.onclick = null; noBt.onclick = null; resolve(ok); };
                yesBt.onclick = () => close(true);
                noBt.onclick  = () => close(false);
                ov.classList.add('show');
                setTimeout(() => yesBt.focus(), 100);
            });
        },

        // Single-button acknowledgement modal (info / "Saved!"). Reuses the
        // confirm modal with the Cancel button hidden.
        // Usage: await LDRC.alert('Gear ratio = 1.0 saved!', { title:'Saved', icon:'✅' });
        alert(message, opts) {
            opts = opts || {};
            const kind = opts.kind || 'go';
            return new Promise(resolve => {
                let ov = document.getElementById('_ldrcModal');
                if (!ov) {
                    ov = document.createElement('div');
                    ov.id = '_ldrcModal';
                    ov.className = 'modalOverlay';
                    ov.innerHTML = '<div class=modalBox>'
                        + '<div class=modalAccent id=_mAcc>'
                        +   '<div class=modalIcon id=_mIcon>⚡</div>'
                        +   '<div class=modalTitle id=_mTitle></div>'
                        + '</div>'
                        + '<div class=modalMsg id=_mMsg></div>'
                        + '<div class=modalBtns>'
                        +   '<button class="modalBtn no" id=_mNo>Cancel</button>'
                        +   '<button class="modalBtn yes" id=_mYes>OK</button>'
                        + '</div></div>';
                    document.body.appendChild(ov);
                }
                const acc   = document.getElementById('_mAcc');
                const yesBt = document.getElementById('_mYes');
                const noBt  = document.getElementById('_mNo');
                acc.className   = 'modalAccent' + (kind === 'warn' ? ' warn' : kind === 'danger' ? ' danger' : '');
                yesBt.className = 'modalBtn yes' + (kind === 'warn' ? ' warn' : kind === 'danger' ? ' danger' : '');
                document.getElementById('_mIcon').textContent  = opts.icon  || '✅';
                document.getElementById('_mTitle').textContent = opts.title || 'Done';
                document.getElementById('_mMsg').textContent   = message;
                yesBt.textContent  = opts.yes || 'OK';
                noBt.style.display = 'none';
                const close = () => { ov.classList.remove('show'); yesBt.onclick = null; resolve(true); };
                yesBt.onclick = close;
                ov.classList.add('show');
                setTimeout(() => yesBt.focus(), 100);
            });
        },

        // Help modal. Each page provides its own help text in a hidden
        // `<template id=helpContent>` element near the bottom of the
        // body, and a floating `?` button anywhere with onclick
        // "LDRC.showHelp()". The function builds an overlay with the
        // template's content and a "Got it" button. Tap outside the
        // panel or the close button to dismiss.
        showHelp() {
            const tpl = document.getElementById('helpContent');
            const html = tpl ? tpl.innerHTML
                             : '<p>No help text on this page yet.</p>';
            // Remind users that the floating 🏠 button (top-left) is the way back
            // — now that the bottom "Return to menu" button has been removed.
            // Skipped on the home page itself (no 🏠 there).
            const homeTip = (location.pathname === '/' || location.pathname === '/index.html') ? ''
                : '<p class=muted style="margin-top:1em;border-top:1px solid rgba(125,158,176,.25);padding-top:.8em">'
                + '🏠 Tap the <b>home button</b> (top-left) any time to return to the menu.</p>';
            // Shared "ways to connect" section — appears in every page's help,
            // so users always know which pipe they're on and what the options are.
            const linkTip =
                '<div style="margin-top:1em;border-top:1px solid rgba(125,158,176,.25);padding-top:.8em">'
                + '<h3 style="margin:.2em 0 .4em">📡 Ways to connect</h3>'
                + '<p class=muted style="margin:.2em 0 .5em">Right now you are connected over '
                + (this.viaBle ? '<b>Bluetooth</b> (the iPhone app).' : '<b>WiFi</b> (browser).') + '</p>'
                + '<ul style="margin:.2em 0;padding-left:1.2em">'
                + '<li><b>Bluetooth</b> — the RXV2 app (iPhone, iPad, Android). Nothing to join, no network needed; ideal at the flying field.</li>'
                + '<li><b>WiFi</b> — any browser: join the receiver’s own hotspot (named after your model) and open '
                + '<b>http://192.168.4.1</b> — or, when the receiver is on your home network, simply '
                + '<b>http://&lt;model-name&gt;.local</b>.</li>'
                + '<li><b>USB-C cable</b>, receiver or dongle to the flight controller — the configurator’s own channel: '
                + 'every setting, any size, the command line, ports, factory reset and the black box. '
                + 'A transmitter’s own Lua scripts have only the slow CRSF tunnel with its 320-byte replies, so they stop at the everyday pages. '
                + 'With both wires this app can do everything the configurator can, apart from flashing Rotorflight itself. '
                + 'A <b>Chenyang CY-UC-088-0.07M</b> is ideal (70 mm, flat, right-angled at both ends, on Amazon). Any short one will do, so long as it carries <b>data</b> \u2014 many short USB-C leads only charge. Tie it down and leave it in: it costs nothing in the air.</li>'
                + '</ul></div>';
            const overlay = document.createElement('div');
            overlay.className = 'helpModal';
            // A Back button that stays at the top while the help scrolls
            // (Malcolm 2026-09-12: "I sometimes load a help screen by mistake
            // and then need to scroll all the way to the bottom to exit").
            overlay.innerHTML =
                '<button class=helpBack type=button aria-label=Back title=Back>\u2B05\uFE0F</button>'
                + '<div class=helpPanel>'
                + html + linkTip + homeTip
                + '<button class=helpClose type=button>Got it</button>'
                + '</div>';
            const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };
            const onKey = (e) => { if (e.key === 'Escape') close(); };
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close();
            });
            overlay.querySelectorAll('.helpClose, .helpBack').forEach(b => b.addEventListener('click', close));
            document.addEventListener('keydown', onKey);
            document.body.appendChild(overlay);
        },

        // Retry-on-fail wrapper for the /api/msp endpoint. MSP responses
        // occasionally drop on the CRSF wire — pause 200 ms and try again,
        // up to `retries` total attempts. Returns response text or throws.
        async msp(fn, dataHex, retries) {
            retries = retries || 3;
            const url = '/api/msp?fn=' + fn + (dataHex ? '&data=' + dataHex : '');
            let lastErr = null;
            this.busyStart();
            try {
                for (let attempt = 0; attempt < retries; attempt++) {
                    try {
                        const r = await fetch(url, { cache: 'no-store' });
                        if (r.ok) return (await r.text()).trim();
                        lastErr = new Error(r.status === 409 ? (await r.text())
                                            : 'HTTP ' + r.status + ': ' + (await r.text()));
                        if (r.status === 409) break;   // armed — final, retrying is pointless
                    } catch (e) { lastErr = e; }
                    if (attempt < retries - 1) await new Promise(rs => setTimeout(rs, 200));
                }
                throw lastErr;
            } finally { this.busyEnd(); }
        },

        // "Reading from the flight controller…" — one indicator for EVERY page
        // that talks MSP, rather than one bolted onto each (Malcolm 2026-09-14:
        // the command line's Please wait was good, "but reading PIDs and
        // governor settings, etc"). Sitting in LDRC.msp() means the PID page,
        // the governor pages, rates, servos and anything written later all get
        // it for free.
        //
        // Only appears after 900 ms, so the quick reads never flash it, and it
        // counts nested calls — a page load is a dozen MSP reads and should
        // show ONE strip for the whole sequence.
        _busy: 0, _busyT0: 0, _busyTimer: null, _busyShow: null, _busyHide: null,
        busyStart() {
            clearTimeout(this._busyHide); this._busyHide = null;
            if (++this._busy > 1) return;
            if (!document.getElementById('ldrcBusy')) this._busyT0 = Date.now();
            clearTimeout(this._busyShow);
            this._busyShow = setTimeout(() => this._busyPaint(), 900);
        },
        busyEnd() {
            if (--this._busy > 0) return;
            this._busy = 0;
            clearTimeout(this._busyShow); this._busyShow = null;
            // A page load is a SEQUENCE of reads, not concurrent ones, so the
            // counter drops to zero between every pair and the strip flickered
            // on and off. Linger briefly: if another read starts within the
            // grace period the strip simply stays, and one steady strip covers
            // the whole load.
            clearTimeout(this._busyHide);
            this._busyHide = setTimeout(() => {
                if (this._busy > 0) return;
                clearInterval(this._busyTimer); this._busyTimer = null;
                const el = document.getElementById('ldrcBusy');
                if (el) el.remove();
            }, 400);
        },
        _busyPaint() {
            if (this._busy <= 0) return;
            let el = document.getElementById('ldrcBusy');
            if (!el) {
                el = document.createElement('div');
                el.id = 'ldrcBusy';
                el.className = 'ldrcBusy';
                el.innerHTML = '<div class=ldrcBusyRow><b>Reading from the flight controller\u2026</b>' +
                               '<span id=ldrcBusySecs></span></div>' +
                               '<div class=ldrcBusyTrack><div class=ldrcBusyBar></div></div>';
                document.body.appendChild(el);
            }
            const tick = () => {
                const n = Math.round((Date.now() - this._busyT0) / 1000);
                const sec = document.getElementById('ldrcBusySecs');
                if (sec) sec.textContent = n + 's';
            };
            tick();
            clearInterval(this._busyTimer);
            this._busyTimer = setInterval(tick, 500);
        },

        // Rotorflight API version we've actually verified the byte layouts
        // against. Pages that talk MSP for tuning compare the FC's API to
        // this and warn if the FC is newer — byte fields can shift across
        // Rotorflight releases and the page may silently write the wrong
        // bytes. Bump this in sync with the firmware source we re-verified.
        // 1209 == Rotorflight 2.3 (firmware RF-4.6.x).
        RF_API_VERIFIED: 1209,
        rfVersionAlert(api) {
            // Returns a warning string if FC is newer than verified, else null.
            if (!api || api < 100) return null;
            if (api <= this.RF_API_VERIFIED) return null;
            const maj = Math.floor(api / 100), min = api % 100;
            const vMaj = Math.floor(this.RF_API_VERIFIED / 100), vMin = this.RF_API_VERIFIED % 100;
            return 'Rotorflight API ' + maj + '.' + min +
                   ' is newer than the version this LDRC firmware was tested against (' +
                   vMaj + '.' + vMin + '). Field positions may have shifted — please ' +
                   'update LDRC firmware. Edits are still allowed, but Save-and-verify ' +
                   'will show what the flight controller actually accepted.';
        },

        // Governor throttle check (0.9.551 — Goblin 770, 2026-09-03: "stable
        // but far too slow" in bank 1 because the transmitter still sent
        // 50 % throttle from the ESC-governor days). The receiver watches
        // the FC's throttle channel while armed; fcinfo.gov_thr_parked is
        // the % it sat at on the last long armed spell (0 = fine). One patch
        // of text: what to do first, then why. Returns true when shown.
        govThrottleBanner(st, elId) {
            const el = document.getElementById(elId);
            if (!el) return false;
            const fc = (st && st.fcinfo) || {};
            const pct = fc.gov_thr_parked | 0;
            if (!pct) { el.style.display = 'none'; return false; }
            const max = fc.gov_thr_max | 0;
            // Self-styled (solid colours, doctrine) — the hub page has no .banner.warn rule.
            el.style.cssText = 'display:block;background:#ffc88c;color:#5c3a1a;padding:1em;' +
                               'border-radius:10px;margin:0 0 1em;text-align:left;font-size:1.05em';
            el.innerHTML = '<b>Set the transmitter throttle to 100&nbsp;% in every bank.</b><br>' +
                'Last time it sat at ' + pct + '&nbsp;% while armed' +
                (max > pct ? ' and never went above ' + max + '&nbsp;%' : '') +
                '. Rotorflight’s governor only takes over near the bank’s target head speed — ' +
                'below that it simply passes your throttle through, so the head runs stable but slow ' +
                'and bank changes do nothing. Each bank’s head speed is set here in the governor profiles; ' +
                'the throttle switch just needs to be fully up. This notice clears itself after a flight at full throttle.';
            return true;
        },

        // Telemetry setup check (0.9.556 — Goblin 770, 2026-09-03: after a
        // bank copy the transmitter showed no volts and no RPM; the FC's
        // sensor list and link rate were all zero). Cause found 0.9.564:
        // Rotorflight 4.6 answers the adjustments list (MSP 52, 588 B) out
        // of a 320-byte buffer and the overflow wipes its telemetry setup;
        // the receiver never asks for 52 now, so this should stay hidden.
        // Rotorflight sends ONLY the sensors in that list, so the receiver
        // reads it (MSP 73) and fcinfo.telem_cfg_bad flags an empty one.
        // One patch of text: what to do, then why, then the button that
        // does it (POST /api/fc/telemetry/restore — refused with the
        // transmitter on, because the FC restarts). Returns true when shown.
        fcTelemBanner(st, elId) {
            const el = document.getElementById(elId);
            if (!el) return false;
            const fc = (st && st.fcinfo) || {};
            const doneAt = +el.dataset.telemDone || 0;
            if (doneAt && Date.now() - doneAt < 25000) return true;   // let the "restored" note be read
            if (!fc.telem_cfg_bad || this.replay) { el.style.display = 'none'; delete el.dataset.telemShown; return false; }
            if (el.dataset.telemShown === '1') return true;   // keep the button's state while it works
            el.dataset.telemShown = '1';
            el.style.cssText = 'display:block;background:#f2b8a8;color:#5a1e12;padding:1em;' +
                               'border-radius:10px;margin:0 0 1em;text-align:left;font-size:1.05em';
            el.innerHTML = '<b>Restore the flight controller’s telemetry sensors — the transmitter shows no volts or RPM until you do.</b><br>' +
                'Rotorflight’s list of sensors to send is empty (' + (fc.telem_sensors | 0) + ' sensors, link rate ' +
                (fc.telem_rate | 0) + '/' + (fc.telem_ratio | 0) + '), so it sends nothing even though everything else works. ' +
                'Usual cause: a Rotorflight 4.6 bug — its adjustments list (from the configurator or a radio script) is too big for its ' +
                'receiver-link buffer and the overflow wipes this setup; the receiver itself never asks for that list. ' +
                'Restoring puts back flight mode, battery, RPM, temperature, attitude and altitude, then restarts the flight controller. ' +
                'Transmitter OFF, blades off.<br>' +
                '<button class="btn" style="background:#b8432b;color:#fff;margin:.7em 0 0;width:100%" id=telemRestoreBtn>' +
                '<span class=ico>🔧</span>Restore telemetry sensors</button>';
            const btn = document.getElementById('telemRestoreBtn');
            btn.onclick = async () => {
                btn.disabled = true; btn.textContent = 'Restoring…';
                let r = null, msg = '';
                try {
                    const resp = await fetch('/api/fc/telemetry/restore', {method: 'POST', cache: 'no-store'});
                    const rep = await LDRC.readReply(resp);
                    r = rep.data; msg = LDRC.replyMessage(rep);
                } catch (e) { msg = 'no answer from the receiver'; }
                if (r && r.ok) {
                    el.dataset.telemDone = Date.now(); delete el.dataset.telemShown;
                    el.innerHTML = '<b>✓ Telemetry sensors restored — the flight controller is restarting.</b><br>' +
                        'Give it 10 seconds, then turn the transmitter on and check volts and RPM show on the screen before any spool-up.';
                } else {
                    btn.disabled = false;
                    btn.innerHTML = '<span class=ico>🔧</span>Restore telemetry sensors';
                    await this.alert(msg, {title: 'Not restored', icon: '⚠️', kind: 'danger'});
                }
            };
            return true;
        },

        // Telemetry speed card (0.9.563). Rotorflight paces everything it
        // sends on the CRSF wire — sensors AND its answers to the phone and
        // the transmitter — by the telemetry link rate. Its default (250/8)
        // answers a settings read in ~0.5 s per chunk; fast (1000/1) is
        // 6-17× quicker and the volts/RPM readings update sooner. The
        // receiver remembers the choice (fcinfo.telem_speed_pref) and shows
        // what the FC actually runs (telem_speed_live). Applying restarts
        // the FC, so it is refused with the transmitter on.
        fcTelemSpeedCard(st, elId) {
            const el = document.getElementById(elId);
            if (!el) return false;
            // Never on a dongle: the telemetry link speed belongs to whatever
            // receiver flies the model (Malcolm 2026-09-10: a dongle offered
            // "Apply fast telemetry" from the 3 s refresh and the write failed).
            if (st && st.dongle) { el.style.display = 'none'; return false; }
            const fc = (st && st.fcinfo) || {};
            if (this.replay || !fc.detected || !fc.rotorflight_capable) { el.style.display = 'none'; delete el.dataset.speedShown; return false; }
            const doneAt = +el.dataset.speedDone || 0;
            if (doneAt && Date.now() - doneAt < 25000) return true;   // let the "saved" note be read
            const pref = fc.telem_speed_pref || 'fast';
            const live = fc.telem_speed_live || 'unknown';
            const key  = pref + '/' + live;
            if (el.dataset.speedShown === key) return true;             // keep the buttons' state while they work
            el.dataset.speedShown = key;
            const matches = (live === pref);
            // One quiet line, the explanations under the finger (Malcolm
            // 2026-09-05: "simply say telemetry: fast, underlined, to keep
            // the screen a little more simple"). data-help = press-and-hold
            // bubble; the link-rate numbers live in there too.
            const rate = (fc.telem_rate | 0) + '/' + (fc.telem_ratio | 0);
            const esc = t => t.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
            const helpTelem = 'Rotorflight paces everything it sends on the receiver wire — its sensors and its answers to this phone and the transmitter — by one telemetry link rate. The receiver remembers your choice and shows what the flight controller actually runs.';
            const helpOf = mode => mode === 'fast'
                ? 'Fast = link rate 1000/1. The flight controller answers the phone and the transmitter about six times quicker than Rotorflight’s standard rate, and volts and RPM update sooner.'
                : 'Standard = Rotorflight’s own default link rate, 250/8. Fast answers settings reads, backups and restores about six times quicker.';
            const liveHelp = live === 'fast' || live === 'standard' ? helpOf(live) + ' The flight controller runs link rate ' + rate + ' now.'
                           : live === 'unknown' ? 'The receiver has not read the flight controller’s telemetry setup yet.'
                           : live === 'none' ? 'The flight controller’s telemetry sensor list is empty — no volts or RPM. See the telemetry banner above.'
                           : 'The flight controller runs a custom link rate, ' + rate + ' — neither fast (1000/1) nor standard (250/8).';
            const liveWord = live === 'fast' || live === 'standard' ? live
                           : live === 'unknown' ? 'not read yet'
                           : live === 'none' ? 'none — sensors empty'
                           : 'custom ' + rate;
            const term = (word, help) => '<span data-help="' + esc(help) + '">' + word + '</span>';
            el.style.cssText = 'display:block;background:' + (matches ? '#d6e9d6' : '#dbe6f2') + ';color:' +
                               (matches ? '#1f4d24' : '#1d3a56') + ';padding:1em;border-radius:10px;margin:0 0 1em;text-align:left;font-size:1.05em';
            let html = '';
            if (matches) {
                html += '<b>' + term('Telemetry', helpTelem) + ': ' + term(pref, liveHelp) + '</b>';
            } else {
                html += '<b>' + term('Telemetry', helpTelem) + ': ' + term(liveWord, liveHelp) + ' — ' +
                        term(pref, helpOf(pref)) + ' is chosen but not applied yet.</b><br>' +
                        'Applying restarts the flight controller: transmitter off, blades off.';
            }
            const other = pref === 'fast' ? 'standard' : 'fast';
            html += '<div style="display:flex;gap:.6em;margin:.7em 0 0;flex-wrap:wrap">';
            if (!matches) html += '<button class="btn" style="background:#2f6fb0;color:#fff;margin:0;flex:2 1 12em" id=telemSpeedApply><span class=ico>⚡</span>Apply ' + pref + ' telemetry</button>';
            html += '<button class="btn" style="background:' + (matches ? '#5b7a63' : '#6b7c8c') + ';color:#fff;margin:0;flex:1 1 9em" id=telemSpeedOther>Use ' + other + (other === 'fast' ? ' (recommended)' : '') + '</button>';
            html += '</div>';
            el.innerHTML = html;
            const post = async (btn, mode) => {
                const was = btn.innerHTML;
                btn.disabled = true;
                // Malcolm 2026-09-14: "long pauses might cause panic". This one
                // writes settings, saves EEPROM and restarts the flight
                // controller, so it can be 10-20 s. Count it out loud.
                const t0 = Date.now();
                const tick = () => { btn.textContent = 'Working… ' + Math.round((Date.now() - t0) / 1000) + 's'; };
                tick();
                const timer = setInterval(tick, 500);
                let r = null, msg = '', status = 0;
                try {
                    const resp = await fetch('/api/fc/telemetry/speed?mode=' + mode, {method: 'POST', cache: 'no-store'});
                    status = resp.status;
                    const rep = await LDRC.readReply(resp);
                    r = rep.data; msg = LDRC.replyMessage(rep);
                } catch (e) { msg = 'no answer from the receiver'; }
                clearInterval(timer);
                if (r && r.ok && r.applied) {
                    el.dataset.speedDone = Date.now(); delete el.dataset.speedShown;
                    el.innerHTML = '<b>✓ ' + (mode === 'fast' ? 'Fast' : 'Standard') + ' telemetry saved — the flight controller is restarting.</b><br>' +
                        'Give it 10 seconds, then turn the transmitter on and check volts and RPM show on the screen before any spool-up.';
                } else if (r && r.ok) {
                    el.dataset.speedDone = Date.now(); delete el.dataset.speedShown;
                    el.innerHTML = '<b>✓ ' + msg.charAt(0).toUpperCase() + msg.slice(1) + '.</b>';
                } else {
                    btn.disabled = false; btn.innerHTML = was;
                    delete el.dataset.speedShown;     // the preference may have been saved — redraw next tick
                    await this.alert(msg, {title: status === 409 ? 'Saved, not applied yet' : 'Not applied', icon: '⚠️', kind: 'danger'});
                }
            };
            const a = document.getElementById('telemSpeedApply');
            if (a) a.onclick = () => post(a, pref);
            const o = document.getElementById('telemSpeedOther');
            if (o) o.onclick = () => post(o, other);
            return true;
        },

        // Read a reply that SHOULD be JSON, without ever showing the pilot a
        // browser exception. Malcolm 2026-09-14 got "The string did not match
        // the expected pattern" when applying fast telemetry — that is WebKit's
        // message for resp.json() on a body that is not JSON (an empty reply,
        // or a plain-text error from the receiver), and the raw exception text
        // was being handed straight to the alert. Useless to read and it hides
        // what actually went wrong.
        //
        // Returns { data, text, status, ok } and never throws.
        async readReply(resp) {
            let text = '';
            try { text = await resp.text(); } catch (e) { text = ''; }
            let data = null;
            const t = text.trim();
            if (t && (t[0] === '{' || t[0] === '[')) { try { data = JSON.parse(t); } catch (e) { data = null; } }
            return { data, text: t, status: resp.status, ok: resp.ok };
        },
        // Turn any reply into one sentence worth reading.
        replyMessage(rep) {
            if (rep.data && (rep.data.message || rep.data.err)) return rep.data.message || rep.data.err;
            if (rep.text) return rep.text.slice(0, 200);
            if (rep.status === 0) return 'no answer from the receiver';
            return 'the receiver answered nothing (HTTP ' + rep.status + ')';
        },

        // ---- "A newer Rotorflight is out" -------------------------------
        // Malcolm 2026-09-15: "although we cannot implement the update, can we
        // detect if there is an update on offer? ... we could at least suggest
        // to the user it's time to connect briefly to the configurator."
        //
        // Yes — but the default is SILENCE. This speaks only when it has
        // something worth acting on, because a notice you learn to ignore is
        // worse than no notice.
        //
        // The recommendation rides in the manifest the app already fetches
        // (dev/rotorflight_latest.json -> stage_website.py). It is curated by
        // hand: dev/check_rotorflight_release.py asks GitHub and SUGGESTS, a
        // human decides. Rotorflight's release workflow does not mark release
        // candidates as prereleases, so an automatic "latest" would cheerfully
        // recommend an RC.
        //
        // THE TRAP THIS AVOIDS: we must never steer someone onto a Rotorflight
        // newer than the byte layouts our own tuning pages were checked against
        // (RF_API_VERIFIED). If the newest release is ahead of us, the honest
        // advice is the opposite — stay put — and that is what it says.
        async rotorflightUpdateCard(st, elId) {
            const el = document.getElementById(elId);
            if (!el) return false;
            const hide = () => { el.style.display = 'none'; return false; };
            const fc = (st && st.fcinfo) || {};
            if (this.replay) return hide();                       // a recording, or the demo
            if (!fc.detected || !fc.version_known) return hide();
            if (fc.variant !== 'RTFL' || fc.api_major !== 12) return hide();
            if (st && st.rf && st.rf.armed) return hide();        // never mid-session
            const feed = await this.rfLatest();
            if (!feed || !feed.api || !feed.firmware) return hide();   // cannot check: say nothing

            const fcApi = fc.api_major * 100 + fc.api_minor;
            let head, body, kind;
            if (feed.api > this.RF_API_VERIFIED) {
                // The release is ahead of us. Protect the pilot AND ourselves.
                if (fcApi >= feed.api) return hide();             // already there: rfVersionAlert has it
                head = 'Stay on Rotorflight ' + (fc.rf_major || 2) + '.' + (fc.rf_minor || 3) + ' for now';
                body = 'Rotorflight ' + feed.suite + ' (firmware ' + feed.firmware + ') is out, but these ' +
                       'pages have not been checked against it yet. Nothing here is broken \u2014 there is ' +
                       'simply no hurry.';
                kind = 'hold';
            } else if (fcApi < feed.api) {
                head = 'A newer Rotorflight is available';
                body = 'Your flight controller runs ' + fc.fw_major + '.' + fc.fw_minor + '.' + (fc.fw_patch | 0) +
                       '. Rotorflight ' + feed.suite + ' (firmware ' + feed.firmware + ') came out on ' +
                       (feed.released || 'a later date') + '. ' +
                       '<b>Back up first, on the Backup &amp; restore page \u2014 flashing erases everything.</b> ' +
                       'Then connect the flight controller to a computer running the Rotorflight Configurator; ' +
                       'that is the one job these pages cannot do for you. Afterwards, restore your backup here.';
                kind = 'go';
            } else {
                return hide();                                    // up to date: nothing to say
            }

            const seen = 'rfUpd.' + (st && st.info && st.info.name || '') + '.' + feed.firmware + '.' + kind;
            try { if (localStorage.getItem(seen)) return hide(); } catch (e) {}

            el.style.display = 'block';
            el.style.cssText = 'display:block;background:' + (kind === 'go' ? '#dbe6f2' : '#e8e4d6') +
                ';color:' + (kind === 'go' ? '#1d3a56' : '#4a4327') +
                ';padding:1em;border-radius:10px;margin:0 0 1em;text-align:left;font-size:1.02em';
            el.innerHTML = '<b>' + head + '</b><br>' + body +
                (feed.notes_url ? '<br><a href="' + feed.notes_url + '" target="_blank" rel="noopener">What changed</a>' : '') +
                '<div style="margin:.7em 0 0"><button class="btn" id=rfUpdSeen style="background:#6b7c8c;color:#fff;margin:0">Got it \u2014 don\u2019t mention again</button></div>';
            const b = document.getElementById('rfUpdSeen');
            if (b) b.onclick = () => { try { localStorage.setItem(seen, '1'); } catch (e) {} el.style.display = 'none'; };
            return true;
        },

        // The curated recommendation, once a CALENDAR DAY (Malcolm 2026-09-15:
        // "it should check only once in a day, just after the first boot up
        // that day"). A rolling 24-hour timer drifts; a date does not.
        //
        // It also never makes the card wait for the network. Any cached copy is
        // returned straight away and the refresh happens quietly behind it, so
        // a new release shows up the following day. Given Rotorflight puts out
        // a release roughly twice a year, that is no delay worth having, and it
        // keeps the check off the Bluetooth link at exactly the moment the
        // pilot is opening pages.
        //
        // A failed check does NOT claim the day — it simply waits an hour, so a
        // phone with no signal at the field tries again once it is home.
        async rfLatest() {
            const KEY = 'rfLatest.v2';
            const today = new Date().toISOString().slice(0, 10);   // YYYY-MM-DD, local boot day
            let c = null;
            try { c = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) {}

            const due = !c || c.day !== today;
            const retryOk = !c || !c.failedAt || (Date.now() - c.failedAt) > 3600000;

            if (due && retryOk) {
                const refresh = async () => {
                    const tryUrl = async (u) => {
                        try {
                            const r = await fetch(u, { cache: 'no-store' });
                            if (!r.ok) return null;
                            const j = await r.json();
                            return (j && j.rotorflight) || null;
                        } catch (e) { return null; }
                    };
                    // The phone's own internet first (it works at the field);
                    // then the receiver's, if it has any.
                    const rf = await tryUrl('/app/manifest') || await tryUrl('/api/firmware/check');
                    try {
                        if (rf) localStorage.setItem(KEY, JSON.stringify({ day: today, rf }));
                        else    localStorage.setItem(KEY, JSON.stringify({ ...(c || {}), failedAt: Date.now() }));
                    } catch (e) {}
                    return rf;
                };
                // Nothing cached at all: this is the first run, so wait for it
                // once. Otherwise let it happen in the background.
                if (!c || !c.rf) return await refresh();
                refresh();
            }
            return (c && c.rf) || null;
        },

        // Dirty-tracking: tuning pages call markDirty() on any user input
        // (via a delegated 'input' listener) and clearDirty() after a
        // successful load() or save(). confirmLoseChanges() shows a
        // dramatic warning before profile-switches that would discard
        // un-saved edits — most often the user has just nudged a value
        // and the new bank's load() would silently overwrite it.
        dirty: false,
        markDirty()  { this.dirty = true;  },
        clearDirty() { this.dirty = false; },

        // Tell the receiver the wall-clock time (it has no clock of its own).
        // Rate-limited so status pages can call it from their poll loops when
        // they notice the clock is unset (receiver rebooted underneath them).
        _teachTimeAt: 0,
        teachTime() {
            const now = Date.now();
            if (now - this._teachTimeAt < 10000) return;
            this._teachTimeAt = now;
            fetch('/api/time', { method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: 'epoch_ms=' + now + '&tz_min=' + (-new Date().getTimezoneOffset()) }).catch(() => {});
        },
        // Coming BACK to a long list lands where you left it, not at the top
        // (Malcolm 2026-09-11). The position is kept per page when you leave
        // it, and put back only when you arrive by the back arrow or a back
        // gesture - a fresh visit still starts at the top. Layout settles late
        // on pages that fill themselves in, so the restore is repeated briefly,
        // but never once you have started scrolling yourself.
        saveScroll() { try { sessionStorage.setItem('ldrc.scroll:' + location.pathname, String(Math.round(window.scrollY))); } catch (e) {} },
        restoreScroll(cameBack) {
            let nav = null; try { nav = performance.getEntriesByType('navigation')[0]; } catch (e) {}
            if (!cameBack && !(nav && nav.type === 'back_forward')) return;
            let y = 0; try { y = parseInt(sessionStorage.getItem('ldrc.scroll:' + location.pathname) || '0', 10); } catch (e) {}
            if (!(y > 0)) return;
            let set = -1;
            const go = () => {
                if (set >= 0 && Math.abs(window.scrollY - set) > 8) return;      // you moved: leave it
                const max = document.documentElement.scrollHeight - window.innerHeight;
                if (max <= 0) return;
                set = Math.min(y, max); window.scrollTo(0, set);
            };
            go(); [150, 400, 800].forEach(ms => setTimeout(go, ms));
        },
        // One step of the back-arrow trail. `trail` = pages visited before
        // this one (oldest first, at most 6). Arriving by the arrow, or at
        // a page that is already on top of the trail (a swipe back, or a
        // link that loops), pops back to it; any other arrival pushes the
        // page we came from. Returns the new trail and the page the arrow
        // should go to (null = use the hub/map fallback).
        trailStep(trail, here, from, cameBack) {
            let t = Array.isArray(trail) ? trail.filter(x => typeof x === 'string') : [];
            const i = t.lastIndexOf(here);
            if (cameBack || (t.length && t[t.length - 1] === here)) {
                if (i >= 0) t = t.slice(0, i);
            } else if (from && from !== here) {
                if (i >= 0) t = t.slice(0, i);          // a loop back to an earlier page: shorten the trail to it
                t.push(from);
                if (t.length > 6) t = t.slice(-6);
            }
            const prev = t.length && t[t.length - 1] !== here ? t[t.length - 1] : null;
            return { trail: t, prev };
        },
        async confirmLoseChanges(action) {
            if (!this.dirty) return true;
            const msg = action
                ? 'You have un-saved changes. They will be lost when ' + action + ' — they CANNOT be recovered. Save first, or continue and discard them.'
                : 'You have un-saved changes. They will be lost. Save first, or continue and discard them.';
            const ok = await this.confirm(msg,
                {title:'Un-saved changes!', icon:'⚠️', yes:'Discard & continue', no:'Stay & save', kind:'danger'});
            if (ok) this.dirty = false;
            return ok;
        },

        async startPolling(fn, ms) {
            // MEASURED 2026-09-14: /api/state.json is 4,414 bytes and Bluetooth
            // carries about 24 kB/s, so each poll is ~190 ms of the link. The
            // 500 ms default means a page can spend 40 % of the whole link on
            // polling alone, and everything else — a stick movement, a Save,
            // a settings read — waits behind it. That was most of "much too
            // slow".
            //
            // On WiFi nothing changes: it is fast and free there. On Bluetooth
            // the floor is 1.5 s, which is still well inside the cadence any of
            // these panels actually needs (they show link status, battery and
            // armed state, none of which moves faster than that).
            const floor = this.viaBle ? 1500 : 0;
            const every = Math.max(floor, ms || 500);
            const tick = async () => {
                await this.fetchState();
                try { fn(this.state); } catch (e) { console.error(e); }
                setTimeout(tick, every);
            };
            tick();
        }
    };

    // Ask the app whether we're in "Review last session" (the stub answers
    // locally, no radio). Kicked off at script time — deferred scripts run
    // BEFORE DOMContentLoaded, so pages that `await LDRC.replayReady` in
    // their first load() always get the true answer.
    if (LDRC.viaBle) {
        LDRC.replayReady = fetch('/app/snapshot/progress', { cache: 'no-store' })
            .then(r => r.json())
            .then(p => { LDRC.replay = (p.phase === 'replay'); return LDRC.replay; })
            .catch(() => false);
        // A recording looks exactly like the live model - so every replayed page says
        // so at the top (Malcolm 2026-09-11: opened "Review: Goblin770" with the model
        // switched off and took it for a live connection).
        LDRC.replayReady.then(rep => {
            if (!rep) return;
            const put = () => {
                const c = document.querySelector('.container'); if (!c || document.getElementById('replayBanner')) return;
                const b = document.createElement('div'); b.id = 'replayBanner';
                b.style.cssText = 'background:#ffd278;color:#5c3a00;border-radius:12px;padding:.8em 1em;margin:0 0 1em;font-weight:600;text-align:center';
                const name = (LDRC.state && LDRC.state.info && LDRC.state.info.name) || '';
                b.textContent = 'Recording' + (name ? ' of ' + name : '') + ' \u2014 nothing here is live. To connect, use Load another model on the front page.';
                c.insertBefore(b, c.firstChild);
                if (!name) LDRC.fetchState().then(() => { const n = LDRC.state && LDRC.state.info && LDRC.state.info.name; if (n) b.textContent = 'Recording of ' + n + ' \u2014 nothing here is live. To connect, use Load another model on the front page.'; });
            };
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', put); else put();
        });
    }

    // Footer FW version. Defer the fetch by 200 ms so it can't block the
    // first paint, and never await it on DOMContentLoaded (a stalled
    // /api/state.json was queuing nav requests on the chip's single-client
    // WebServer for the iOS keep-alive socket).
    // Slider baselines (Malcolm 2026-09-07): a slider's CENTRE means "the
    // numbers at your last backup". Models vary hugely, so an absolute
    // scale soon parks a slider at the end of its travel; a backup says
    // "these are good now" and every slider re-centres on them while the
    // numbers themselves stay put. Baselines live on the phone per
    // receiver (its name) and per bank; a page stores today's numbers as
    // the baseline the first time it sees a slider with none.
    LDRC.baseRx  = () => (LDRC.state && LDRC.state.info && LDRC.state.info.name) || 'rx';
    LDRC.baseKey = (slider, bank) => 'ldrc.base.' + LDRC.baseRx() + '.' + slider + (bank === undefined || bank === null ? '' : '.' + bank);
    LDRC.baseGet = (slider, bank) => { try { const v = localStorage.getItem(LDRC.baseKey(slider, bank)); return v ? JSON.parse(v) : null; } catch (e) { return null; } };
    LDRC.baseSet = (slider, bank, obj) => { try { localStorage.setItem(LDRC.baseKey(slider, bank), JSON.stringify(obj)); } catch (e) {} };
    LDRC.baseFresh = false;      // a slider was (re-)centred on this page load - say so, or the pilot wonders where it went (Malcolm 2026-09-07)
    LDRC.baseFor = (slider, bank, current) => { let b = LDRC.baseGet(slider, bank); if (!b) { LDRC.baseSet(slider, bank, current); b = current; LDRC.baseFresh = true; } return b; };
    LDRC.baseNotice = () => LDRC.baseFresh ? 'Slider centred on today\u2019s numbers (a backup, restore or bank copy resets the centre). The numbers themselves are unchanged.' : '';
    LDRC.baseClear = () => {
        const pre = 'ldrc.base.' + LDRC.baseRx() + '.';
        try {
            const ks = [];
            for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k && k.startsWith(pre)) ks.push(k); }
            ks.forEach(k => localStorage.removeItem(k));
            return ks.length;
        } catch (e) { return 0; }
    };
    // Relative slider maths: 50 = the baseline; the ends are half and double.
    LDRC.relScale = (base, v) => base * Math.pow(2, (v - 50) / 50);
    LDRC.relPos   = (base, val) => (base > 0 && val > 0) ? Math.max(0, Math.min(100, Math.round((50 + 50 * Math.log2(val / base)) / 5) * 5)) : 50;
    LDRC.clamp5   = x => Math.max(0, Math.min(100, Math.round(x / 5) * 5));
    LDRC.endHint  = (v, lo, hi) => (v <= lo || v >= hi) ? ' At the end of its travel: back up to the phone and every slider re-centres on today\u2019s numbers.' : '';

    // "Find a setting" (Malcolm 2026-09-07): a result link carries
    // ?fid=<input id>&find=<label text>. Light that row up on arrival so a
    // newcomer sees WHERE the setting is. Pages that draw their rows in
    // JavaScript get a few retries. Nothing is focused - no keyboard pops.
    LDRC.findOnArrival = function () {
        let sp;
        try { sp = new URLSearchParams(location.search); } catch (e) { return; }
        const fid = sp.get('fid'), find = (sp.get('find') || '').trim().toLowerCase();
        if (!fid && !find) return;
        const norm = t => (t || '').replace(/\s+/g, ' ').trim().toLowerCase();
        const locate = () => {
            let el = fid ? document.getElementById(fid) : null;
            if (!el && find) {
                const cands = document.querySelectorAll('label,b[data-help],h2,h3,th,legend,.lab,a.btn,button.btn');
                for (const c of cands) { if (norm(c.textContent).startsWith(find)) { el = c; break; } }
                if (!el) for (const c of cands) { if (norm(c.textContent).includes(find)) { el = c; break; } }
            }
            return el;
        };
        const tries = [0, 300, 900, 1800, 3200];
        const attempt = i => {
            const el = locate();
            if (!el) { if (i + 1 < tries.length) setTimeout(() => attempt(i + 1), tries[i + 1] - tries[i]); return; }
            const row = el.closest('.fldRow,.fRow,tr,label,h2,h3,.card,a.btn,button.btn') || el;
            try { row.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) { row.scrollIntoView(); }
            row.classList.add('ldrc-found');
            setTimeout(() => row.classList.remove('ldrc-found'), 6000);
        };
        attempt(0);
    };

    document.addEventListener('DOMContentLoaded', () => {
        // Teach the receiver the time from EVERY page (it has no clock and
        // reboots wipe it). It was only the front + flight pages — sit on the
        // Black box page across a receiver reboot and the clock stayed unset
        // (Malcolm, 2026-08-02). Fire-and-forget; the RX ignores duplicates.
        LDRC.teachTime();
        LDRC.mountFooter();
        LDRC.dongleGuard();
        LDRC.findOnArrival();
        // Review mode? Buttons tell the truth: edits go to / come from the
        // PHONE (Malcolm 2026-08-04). Only the Rotorflight tuning pages
        // capture edits in review — other pages' saves genuinely fail
        // offline, so their buttons keep their labels.
        // Keyboard vs floating bar (Malcolm 2026-08-06: "the floating
        // buttons sink behind it!"): the on-screen keyboard shrinks the
        // VISUAL viewport but position:fixed still anchors to the layout
        // viewport underneath it. Ride the visual viewport instead — the
        // bar translates up to sit just above the keyboard while editing.
        const fab = document.querySelector('.fabBar');
        if (fab && window.visualViewport) {
            const vv = window.visualViewport;
            const place = () => {
                const lift = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
                fab.style.transition = 'transform .15s';
                fab.style.transform = lift ? 'translateY(-' + lift + 'px)' : '';
            };
            vv.addEventListener('resize', place);
            vv.addEventListener('scroll', place);
            place();
        }

        LDRC.replayReady.then(isReplay => {
            if (!isReplay) return;
            const captured = ['/rotorflight-pid', '/rotorflight-pidplus',
                              '/rotorflight-rates', '/rotorflight-gov-global',
                              '/rotorflight-gov-profile'];
            if (!captured.includes(location.pathname)) return;
            const b = document.getElementById('saveBtn');
            if (b) b.innerHTML = '<span class=ico>&#128190;</span>Save to phone';
            const r = document.getElementById('reloadBtn');
            if (r) r.innerHTML = '<span class=ico>&#8635;</span>Reload from phone';
        });
        // Fixed "front screen" button, top-left on every page EXCEPT the home
        // page itself — so returning to the menu is one tap, no scrolling to the
        // bottom. It's a normal <a href="/">, so the click interceptor below
        // gives it the same instant-nav + unsaved-edit guard as any link.
        // 🔍 Find a setting, beside "?" on EVERY page but its own (Malcolm
        // 2026-09-07: "search becomes available everywhere"). A plain link,
        // so the click interceptor gives it instant nav + the unsaved guard.
        if (!/^\/search(\.html)?$/.test(location.pathname) && document.querySelector('.helpBtn')) {
            const find = document.createElement('a');
            find.href = '/search';
            find.className = 'searchBtn';
            find.setAttribute('aria-label', 'Find a setting');
            find.title = 'Find a setting';
            find.textContent = '🔍';
            document.body.appendChild(find);
            document.body.classList.add('hasSearch');
        }
        if (location.pathname !== '/' && location.pathname !== '/index.html') {
            const home = document.createElement('a');
            home.href = '/';
            home.className = 'homeBtn';
            home.setAttribute('aria-label', 'Front screen');
            home.title = 'Front screen';
            home.textContent = '🏠';
            document.body.appendChild(home);

            // Bottom "Back to <the menu that called this page>" button. Without
            // it, sub-menus dead-end: the only way onward was 🏠 to the front
            // and drilling back down. One shared parent map here means every
            // page gets the right button with no per-page markup; unknown pages
            // fall back to the front screen. (Pages that swap their container
            // for a "rebooting…" card lose the button with it — intended.)
            const PARENTS = {
                '/flight': '/blackbox', '/events': '/blackbox',
                '/bind': '/setup', '/protocol': '/setup', '/diagnostics': '/setup',
                '/wifi': '/setup', '/firmware': '/setup', '/rxsettings': '/setup',
                '/map': '/sim', '/views': '/sim', '/simctl': '/sim',
                '/rotorflight-wizards': '/rotorflight',
                '/rotorflight-newheli': '/rotorflight-wizards',
                '/rotorflight-tuning': '/rotorflight-wizards',
                '/rotorflight-computer': '/rotorflight-newheli',
                '/rotorflight-wiring': '/rotorflight-newheli',
                '/rotorflight-txchannels': '/rotorflight-newheli',
                '/rotorflight-firsttime': '/rotorflight-newheli',
                '/rotorflight-esc': '/rotorflight-newheli',
                '/rotorflight-filtercheck': '/rotorflight-blackbox',
                '/rotorflight-modes': '/rotorflight',
                '/rotorflight-alacarte': '/rotorflight',
                '/rotorflight-easy': '/rotorflight-alacarte',
                '/search': '/',
                '/rotorflight-backup': '/rotorflight',
                '/rotorflight-servos': '/rotorflight',
                '/rotorflight-rescue': '/rotorflight',
                '/rotorflight-travel': '/rotorflight',
                '/rotorflight-rates': '/rotorflight',
                '/rotorflight-pid': '/rotorflight',
                '/rotorflight-pidplus': '/rotorflight',
                '/rotorflight-gov-global': '/rotorflight',
                '/rotorflight-gov-profile': '/rotorflight',
                '/rotorflight-gear': '/rotorflight',
                '/rotorflight-calibrate': '/rotorflight-newheli',
                '/rotorflight-escprog': '/rotorflight'
            };
            const LABELS = {
                '/': 'front screen', '/blackbox': 'Receiver log', '/setup': 'Setup',
                '/sim': 'Simulator', '/rotorflight': 'Rotorflight',
                '/rotorflight-alacarte': 'À la carte', '/rotorflight-wizards': 'Wizards',
                '/rotorflight-newheli': 'New helicopter', '/rotorflight-tuning': 'Tuning'
            };
            // Floating ⬅️ beside 🏠 (Malcolm 2026-08-31: the bottom back button
            // "often needs a long scroll to find" — now it's always in reach).
            // Parent: the page's own bottom back link if it has one (the
            // Rotorflight pages carry .btn-bb with the right target), else the
            // PARENTS map; when the parent IS the front screen, 🏠 already
            // covers it. The old bottom buttons are hidden by style.css.
            // btn-bb is ALSO used for ordinary menu buttons (the front
            // screen's Rotorflight/Black box — hiding the whole class
            // vaporised them, Malcolm 2026-08-31), so identify a true back
            // button by its "Back to …" wording and hide only that one.
            // This map is the ONLY static source of a page's parent: the
            // pages carry no back buttons of their own any more (Malcolm
            // 2026-08-31 -- one mechanism). If we arrived FROM one of the
            // menu hubs, that hub wins (a page can be reached from both the
            // wizard and A la carte); the map is the fallback for reloads
            // and deep links.
            const HUBS = new Set(['/', '/rotorflight', '/rotorflight-alacarte',
                '/rotorflight-wizards', '/rotorflight-newheli', '/rotorflight-tuning',
                '/setup', '/sim', '/blackbox']);
            let from = null;
            try{ from = sessionStorage.getItem('ldrc.from'); }catch(_){}
            // The trail (Malcolm 2026-09-06: "the back button doesn't always
            // go back to the page I would have expected"): the last few
            // pages actually visited, so the arrow walks back through what
            // you were doing. The hub-from and the PARENTS map are the
            // fallback when the trail is empty (reloads, deep links).
            let trail = [];
            try { trail = JSON.parse(sessionStorage.getItem('ldrc.trail') || '[]'); } catch(_) {}
            let cameBack = false;
            try { cameBack = sessionStorage.getItem('ldrc.back') === '1'; sessionStorage.removeItem('ldrc.back'); } catch(_) {}
            LDRC.restoreScroll(cameBack);
            const step = LDRC.trailStep(trail, location.pathname, from, cameBack);
            try { sessionStorage.setItem('ldrc.trail', JSON.stringify(step.trail)); } catch(_) {}
            const parent = step.prev
                || (HUBS.has(from) && from !== location.pathname ? from : null)
                || PARENTS[location.pathname] || '/';
            if (parent !== '/') {
                document.body.classList.add('hasBack');
                const back = document.createElement('a');
                back.href = parent;
                back.className = 'backBtn';
                back.setAttribute('aria-label', 'Back to ' + (LABELS[parent] || 'previous page'));
                back.title = 'Back';
                back.textContent = '⬅️';
                document.body.appendChild(back);
            }
        }
        setTimeout(() => {
            LDRC.fetchState().then(() => {
                if (LDRC.state && LDRC.state.info) {
                    const f = document.querySelector('.footer');
                    if (f) f.textContent = LDRC.state.info.fw_version;
                    try { localStorage.setItem('ldrc.footer', LDRC.state.info.fw_version || ''); } catch (e) {}
                }
            });
        }, 200);
    });

    // Press-and-hold help bubbles (Malcolm 2026-09-01: "he puts his finger
    // on those words and a bubble appears"). Elements carry their text in
    // data-help; the bubble lives while the pointer is down and never
    // steals presses aimed at a control inside the label.
    let _hb = null;
    const _hbHide = () => { if (_hb) { _hb.remove(); _hb = null; } };
    document.addEventListener('pointerdown', e => {
        const t = e.target.closest('[data-help]');
        if (!t || e.target.closest('input,select,button,a,textarea')) return;
        e.preventDefault();
        _hbHide();
        const b = document.createElement('div');
        b.className = 'helpBubble';
        b.textContent = t.getAttribute('data-help');
        document.body.appendChild(b);
        const r = t.getBoundingClientRect();
        b.style.left = Math.max(8, Math.min(window.innerWidth - 8 - b.offsetWidth, r.left)) + 'px';
        // ALWAYS above the finger, never below — the finger approaches from
        // below and hides anything under it (Malcolm 2026-09-01). Near the
        // top of the screen the bubble pins to the top edge instead.
        b.style.top = Math.max(8, r.top - b.offsetHeight - 46) + 'px';
        _hb = b;
    }, { passive: false });
    // Kill iOS's long-press extras on help labels (drag ghost, loupe, text
    // selection): pointerdown's preventDefault is not enough — the touch
    // event's default must go too (Malcolm 2026-09-01, screenshot of a
    // floating card ghost).
    document.addEventListener('touchstart', e => {
        const t = e.target.closest('[data-help]');
        if (t && !e.target.closest('input,select,button,a,textarea')) e.preventDefault();
    }, { passive: false });
    for (const ev of ['pointerup', 'pointercancel']) document.addEventListener(ev, _hbHide);
    window.addEventListener('scroll', _hbHide, true);

    // Click interceptor — ported from the Reed remaking-machine project,
    // where this pattern gives near-instant nav on iOS Safari:
    //   - e.preventDefault() then JS-initiated location.href = a.href
    //     bypasses iOS's 300 ms double-tap-zoom delay
    //   - the `navigating` flag swallows re-taps so they can't queue
    //     additional requests on the single-client WebServer
    //   - 50 ms setTimeout gives Safari one paint tick to show the overlay
    let _navigating = false;
    document.addEventListener('click', async e => {
        if (_navigating) { e.preventDefault(); return; }
        const a = e.target.closest('a[href]');
        if (!a || a.target) return;
        const href = a.getAttribute('href');
        if (!href || href === '#' || href[0] === '#') return;
        if (href.startsWith('blob:') || href.startsWith('data:')) return;
        if (/^https?:|^mailto:|^tel:/i.test(href) && a.origin && a.origin !== location.origin) return;
        if (a.hasAttribute('download')) return;
        e.preventDefault();
        // If the current page has un-saved edits, ask before navigating
        // away — the new page would silently discard them.
        if (LDRC.dirty) {
            if (!(await LDRC.confirmLoseChanges('leaving this page'))) return;
        }
        _navigating = true;
        // Breadcrumb for the floating back arrow: pages reachable from BOTH
        // the wizard and A la carte need to go back to the menu actually
        // used (Malcolm 2026-08-31). The arrow itself marks the hop as a
        // step BACK so the trail pops instead of growing.
        try{
            sessionStorage.setItem('ldrc.from', location.pathname);
            if (a.classList.contains('backBtn')) sessionStorage.setItem('ldrc.back', '1');
        }catch(_){}
        LDRC.saveScroll();
        LDRC.showLoading();
        setTimeout(() => { location.href = a.href; }, 50);
    }, true);
    document.addEventListener('submit', () => LDRC.showLoading(), true);
    window.addEventListener('pagehide', () => LDRC.saveScroll());
    // Browser back/refresh/close: the native "Leave site?" dialog is the
    // only way to intercept these. Returning any string triggers it.
    window.addEventListener('beforeunload', e => {
        if (LDRC.dirty && !_navigating) {
            e.preventDefault();
            e.returnValue = 'Un-saved changes will be lost.';
            return e.returnValue;
        }
    });
    // Whatever way a page is left (a script's location.href, a swipe back,
    // the arrow), record it as the page we came from.
    window.addEventListener('pagehide', () => {
        try{ sessionStorage.setItem('ldrc.from', location.pathname); }catch(_){}
    });
    // bfcache: iOS may restore the page with the overlay still up.
    window.addEventListener('pageshow', () => {
        _navigating = false;
        LDRC.hideLoading();
    });

    LDRC.showLoading = function(msg) {
        let ov = document.getElementById('_ldrcLoad');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = '_ldrcLoad';
            ov.innerHTML = '<div class=loadingBox><div class=loadingSpin></div><div id=_ldrcLoadMsg>Please wait&hellip;</div></div>';
            document.body.appendChild(ov);
        }
        const m = document.getElementById('_ldrcLoadMsg');
        if (m) m.innerHTML = msg || 'Please wait&hellip;';
        ov.classList.add('show');
    };
    LDRC.hideLoading = function() {
        const ov = document.getElementById('_ldrcLoad');
        if (ov) ov.classList.remove('show');
    };

    // Stale-values overlay — used by Rotorflight value-display pages
    // while a fresh fetch is in flight. Toggles a <body> class that
    // CSS (style.css) turns into "fade values to grey". Call markStale
    // at the start of a load, clearStale after the last .value = ...
    // assignment. Failed loads should leave the page stale (values
    // remain suspect until something actually arrives).
    LDRC.markStale  = function() { document.body.classList.add('stale-values'); };
    LDRC.clearStale = function() { document.body.classList.remove('stale-values'); };

    // Always-visible link badge: says at a glance whether this screen is
    // riding Bluetooth (iPhone app) or WiFi (browser). Scripts load with
    // `defer`, so the DOM is ready — safe to append immediately.
    //
    // Inside the app (ble:) the web UI runs full-screen with no native
    // chrome, so the badge doubles as the Disconnect button: tap →
    // confirm → post 'disconnect' over the rxv2 JS→Swift bridge.
    (function () {
        const ble    = LDRC.viaBle;
        const bridge = ble && window.webkit && window.webkit.messageHandlers
                           && window.webkit.messageHandlers.rxv2;
        const b = document.createElement(bridge ? 'button' : 'div');
        // Radios off (fly mode): the Bluetooth badge would be a fib — the
        // receiver is only whispering down one kept link. Hide it until
        // the radios come back (checked once; the flow reloads pages).
        if (ble) {
            fetch('/api/state.json', { cache: 'no-store' })
                .then(r => r.json())
                .then(st => { if (st && st.net && st.net.rf_only) b.style.display = 'none'; })
                .catch(() => {});
        }
        b.id = 'linkBadge';
        b.type = bridge ? 'button' : undefined;
        // Malcolm's own Genmoji blue tooth (2026-08-15) — a glossy blue
        // molar with signal waves on the enamel, drawn on his iPhone and
        // carved out of the pasted AdaptiveImageGlyph. Still the Disconnect
        // button in the app: tap → confirm. WiFi keeps its dot.
        if (ble) {
            b.innerHTML = '<img alt="Bluetooth" style="width:2em;height:2em;display:block;'
                + 'filter:drop-shadow(0 2px 5px rgba(30,70,140,.5))" '
                + 'src="data:image/png;base64,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">';
        } else {
            b.textContent = '🛜';
        }
        b.title = ble ? 'Bluetooth — tap to disconnect' : 'WiFi';
        // Above the floating Save/Back bar on the tuning pages.
        const fabLift = document.querySelector('.fabBar') ? ' + 4.6em' : '';
        b.style.cssText =
            'position:fixed;right:10px;bottom:calc(10px + env(safe-area-inset-bottom,0px)' + fabLift + ');'
            + 'z-index:60;width:2.1em;height:2.1em;padding:0;border-radius:50%;font-size:1em;'
            + 'display:flex;align-items:center;justify-content:center;'
            + 'user-select:none;border:0;font-family:inherit;'
            + (bridge ? 'pointer-events:auto;cursor:pointer;' : 'pointer-events:none;')
            + (ble ? 'background:transparent'
                   : 'background:rgba(95,160,153,.88);box-shadow:0 2px 7px rgba(40,100,90,.35)');
        if (bridge) {
            b.onclick = async () => {
                const ok = await LDRC.confirm(
                    'Disconnect Bluetooth and return to the receiver list?',
                    { icon: '🔵', title: 'Disconnect?', yes: 'Disconnect', no: 'Stay', kind: 'warn' });
                if (ok) window.webkit.messageHandlers.rxv2.postMessage('disconnect');
            };
        }
        document.body.appendChild(b);
    })();
})();

// ── Keyboard-aware action bar (Malcolm 2026-08-15: "the keyboard hides
// Save to Flight Controller"). On iOS the on-screen keyboard overlays a
// position:fixed bottom bar; the visualViewport API tells us how much of
// the layout viewport it covers, and the bar rides up by exactly that.
(function () {
    const vv = window.visualViewport;
    if (!vv) return;
    function adjust() {
        const bar = document.querySelector('.fabBar');
        if (!bar) return;
        const covered = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
        if (covered > 40) {
            bar.style.transform = 'translateY(-' + covered + 'px)';
            // The keyboard swallows the home-indicator safe area, but the
            // bar's bottom padding still reserved it — reclaim it while
            // raised or the buttons sit half-under the keyboard's accessory
            // strip (Malcolm 2026-08-15: "Nearly!").
            bar.style.paddingBottom = '.55em';
        } else {
            bar.style.transform = '';
            bar.style.paddingBottom = '';
        }
    }
    vv.addEventListener('resize', adjust);
    vv.addEventListener('scroll', adjust);
    addEventListener('focusin',  () => setTimeout(adjust, 60));
    addEventListener('focusout', () => setTimeout(adjust, 250));
})();

// ARMED banner (Malcolm 2026-08-24, after the crash: "make this clear to the
// user — even the naive user will notice!"). Every page watches the armed
// state; the moment arming comes on with auto fly mode active, a full-screen
// banner explains what is about to happen — so the radios going silent three
// seconds later reads as the safety feature it is, never as a fault. The
// banner deliberately survives the disconnection (the page is dead by then
// anyway) and disappears only when the link returns disarmed.
(function () {
    let overlay = null;
    function showArmedBanner() {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#c0392b;color:#fff;' +
            'display:flex;flex-direction:column;align-items:center;justify-content:center;' +
            'text-align:center;padding:2em;gap:.7em';
        overlay.innerHTML =
            '<div style="font-size:3.2em">⚠️</div>' +
            '<div style="font-size:1.7em;font-weight:800;letter-spacing:.02em">ARMED!</div>' +
            '<div style="font-size:1.15em;font-weight:600;line-height:1.55">WiFi &amp; Bluetooth are switching OFF for flying.<br>The app disconnects in 3 seconds.</div>' +
            '<div style="font-size:.95em;opacity:.92">Disarm the model to get it back.</div>';
        document.body.appendChild(overlay);
    }
    function hideArmedBanner() {
        if (!overlay) return;
        overlay.remove();
        overlay = null;
    }
    async function tick() {
        if (document.hidden) return;
        if (window.LDRC && LDRC.replay) return;          // recordings can't arm anything
        try {
            const s = await (await fetch('/api/state.json', { cache: 'no-store' })).json();
            if (s && s.rf && s.rf.armed && s.rf.autofly) showArmedBanner();
            else if (overlay && s && s.rf && !s.rf.armed) hideArmedBanner();
        } catch (e) { /* link gone — keep the banner up, it explains why */ }
    }
    if (document.readyState === 'loading')
        document.addEventListener('DOMContentLoaded', () => setInterval(tick, 1200));
    else setInterval(tick, 1200);
})();
