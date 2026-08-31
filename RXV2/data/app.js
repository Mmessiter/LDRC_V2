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
                    lastErr = new Error(r.status === 409 ? (await r.text())
                                        : 'HTTP ' + r.status + ': ' + (await r.text()));
                    if (r.status === 409) break;   // armed — final, retrying is pointless
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
                '/rotorflight-modes': '/rotorflight',
                '/rotorflight-alacarte': '/rotorflight',
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
                '/rotorflight-calibrate': '/rotorflight-newheli'
            };
            const LABELS = {
                '/': 'front screen', '/blackbox': 'Black box', '/setup': 'Setup',
                '/sim': 'Simulator', '/rotorflight': 'Rotorflight'
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
            // This map is the ONLY source of a page's parent: the pages carry
            // no back buttons of their own any more (Malcolm 2026-08-31 --
            // one mechanism, less complexity two years down the line).
            const parent = PARENTS[location.pathname] || '/';
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
