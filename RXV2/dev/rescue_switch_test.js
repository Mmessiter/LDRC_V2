// The Rescue page names the rescue switch's channel as the Switches page does (0.9.900). Malcolm, 19 Oct 2026: "I have set up
// rescue on channel 10 ... On the rescue option in the app, it lists it as on channel 9, which is incorrect." The Modes
// table carries Rotorflight's AUX index: AUX 1 is channel 6 (roll, pitch, yaw, collective, throttle come first), so AUX 5
// is channel 10. The page added 5; everything else (the Switches page, the adjustments, the transmitter) adds 6.
const path = require('path');
process.argv[2] = 'data/rotorflight-rescue.html';
const H = require(path.join(__dirname, 'page_test.js'));
const S = H.sandbox, ok = H.ok, run = H.run, els = H.els;
const slot = (perm, aux, lo, hi) => [perm, aux, (lo - 1500) / 5 & 255, (hi - 1500) / 5 & 255].map(b => b.toString(16).padStart(2, '0')).join('');
(async () => {
    S.LDRC.msp = async fn => fn === 34 ? slot(53, 4, 1500, 2125) + slot(0, 0, 1500, 2125) + '00000000'.repeat(18) : '';   // RESCUE (53) on AUX 5, then ARM on AUX 1
    await run('loadRescueSwitch()');
    const h = els.swInfo.innerHTML;
    ok(/Channel 10<\/b> \(AUX 5\)/.test(h), 'rescue on AUX 5 is channel 10 (' + h.replace(/<[^>]+>/g, '').slice(0, 60) + ')');
    ok(!/Channel 9\b/.test(h) && /watch channel 10 on/.test(h), 'and the check line says channel 10 too');
    S.LDRC.msp = async fn => fn === 34 ? slot(53, 0, 1500, 2125) + '00000000'.repeat(19) : '';
    await run('loadRescueSwitch()');
    ok(/Channel 6<\/b> \(AUX 1\)/.test(els.swInfo.innerHTML), 'AUX 1 is channel 6');
    S.LDRC.msp = async fn => fn === 34 ? '00000000'.repeat(20) : '';
    await run('loadRescueSwitch()');
    ok(/NO SWITCH ASSIGNED/.test(els.swInfo.innerHTML), 'no rescue slot: the warning');
    console.log('rescue_switch_test: ' + (H.fails() ? 'FAILED' : 'all pass'));
    process.exit(H.fails() ? 1 : 0);
})();
