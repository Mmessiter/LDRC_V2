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
            // Populated by first state fetch; show a placeholder for now.
            if (!f.textContent.trim()) f.textContent = 'loading...';
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
                + '<li><b>Bluetooth</b> — the RXV2 iPhone app. Nothing to join, no network needed; ideal at the flying field.</li>'
                + '<li><b>WiFi</b> — any browser: join the receiver’s own hotspot (named after your model) and open '
                + '<b>http://192.168.4.1</b> — or, when the receiver is on your home network, simply '
                + '<b>http://&lt;model-name&gt;.local</b>.</li>'
                + '<li><b>Android?</b> The app is Apple-only for now, so the poor unfortunate Android owner '
                + 'must take the WiFi route above. 😉</li>'
                + '</ul></div>';
            const overlay = document.createElement('div');
            overlay.className = 'helpModal';
            overlay.innerHTML =
                '<div class=helpPanel>' + html + linkTip + homeTip +
                '<button class=helpClose type=button>Got it</button>' +
                '</div>';
            const close = () => overlay.remove();
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close();
            });
            overlay.querySelector('.helpClose').addEventListener('click', close);
            document.body.appendChild(overlay);
        },

        // Retry-on-fail wrapper for the /api/msp endpoint. MSP responses
        // occasionally drop on the CRSF wire — pause 200 ms and try again,
        // up to `retries` total attempts. Returns response text or throws.
        async msp(fn, dataHex, retries) {
            retries = retries || 3;
            const url = '/api/msp?fn=' + fn + (dataHex ? '&data=' + dataHex : '');
            let lastErr = null;
            for (let attempt = 0; attempt < retries; attempt++) {
                try {
                    const r = await fetch(url, { cache: 'no-store' });
                    if (r.ok) return (await r.text()).trim();
                    lastErr = new Error('HTTP ' + r.status + ': ' + (await r.text()));
                } catch (e) { lastErr = e; }
                if (attempt < retries - 1) await new Promise(rs => setTimeout(rs, 200));
            }
            throw lastErr;
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
            const tick = async () => {
                await this.fetchState();
                try { fn(this.state); } catch (e) { console.error(e); }
                setTimeout(tick, ms || 500);
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
    }

    // Footer FW version. Defer the fetch by 200 ms so it can't block the
    // first paint, and never await it on DOMContentLoaded (a stalled
    // /api/state.json was queuing nav requests on the chip's single-client
    // WebServer for the iOS keep-alive socket).
    document.addEventListener('DOMContentLoaded', () => {
        // Teach the receiver the time from EVERY page (it has no clock and
        // reboots wipe it). It was only the front + flight pages — sit on the
        // Black box page across a receiver reboot and the clock stayed unset
        // (Malcolm, 2026-08-02). Fire-and-forget; the RX ignores duplicates.
        LDRC.teachTime();
        LDRC.mountFooter();
        // Review mode? Buttons tell the truth: edits go to / come from the
        // PHONE (Malcolm 2026-08-04). Only the Rotorflight tuning pages
        // capture edits in review — other pages' saves genuinely fail
        // offline, so their buttons keep their labels.
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
                '/wifi': '/setup', '/firmware': '/setup',
                '/map': '/sim', '/views': '/sim', '/simctl': '/sim',
                '/rotorflight-rates': '/rotorflight', '/rotorflight-pid': '/rotorflight',
                '/rotorflight-pidplus': '/rotorflight', '/rotorflight-gov-profile': '/rotorflight',
                '/rotorflight-gov-global': '/rotorflight', '/rotorflight-backups': '/rotorflight'
            };
            const LABELS = {
                '/': 'front screen', '/blackbox': 'Black box', '/setup': 'Setup',
                '/sim': 'Simulator', '/rotorflight': 'Rotorflight'
            };
            const parent = PARENTS[location.pathname] || '/';
            const back = document.createElement('a');
            back.href = parent;
            back.className = 'btn';
            back.style.background = '#6f7e8b';
            back.innerHTML = '<span class=ico>&#11013;&#65039;</span>Back to ' + (LABELS[parent] || 'menu');
            const foot = document.querySelector('.footer');
            if (foot && foot.parentNode) foot.parentNode.insertBefore(back, foot);
            else { const c = document.querySelector('.container'); if (c) c.appendChild(back); }
        }
        setTimeout(() => {
            LDRC.fetchState().then(() => {
                if (LDRC.state && LDRC.state.info) {
                    const f = document.querySelector('.footer');
                    if (f) f.textContent = LDRC.state.info.fw_version;
                }
            });
        }, 200);
    });

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
        LDRC.showLoading();
        setTimeout(() => { location.href = a.href; }, 50);
    }, true);
    document.addEventListener('submit', () => LDRC.showLoading(), true);
    // Browser back/refresh/close: the native "Leave site?" dialog is the
    // only way to intercept these. Returning any string triggers it.
    window.addEventListener('beforeunload', e => {
        if (LDRC.dirty && !_navigating) {
            e.preventDefault();
            e.returnValue = 'Un-saved changes will be lost.';
            return e.returnValue;
        }
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
        b.textContent = ble ? '🔵 Bluetooth' : '🛜 WiFi';
        // Above the floating Save/Back bar on the tuning pages.
        const fabLift = document.querySelector('.fabBar') ? ' + 4.6em' : '';
        b.style.cssText =
            'position:fixed;right:12px;bottom:calc(12px + env(safe-area-inset-bottom,0px)' + fabLift + ');'
            + 'z-index:60;padding:.5em 1em;border-radius:999px;font-size:.95em;font-weight:600;'
            + 'letter-spacing:.03em;user-select:none;border:0;font-family:inherit;'
            + (bridge ? 'pointer-events:auto;cursor:pointer;' : 'pointer-events:none;')
            + (ble ? 'background:rgba(74,122,201,.92);color:#eaf3ff;box-shadow:0 3px 10px rgba(30,70,140,.40)'
                   : 'background:rgba(95,160,153,.88);color:#eafff9;box-shadow:0 3px 10px rgba(40,100,90,.35)');
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
