// Gear-ratio widget — edits Rotorflight's OWN gear ratios (MSP 131/222).
//
// Malcolm 2026-09-02, the Goblin's "banks 1-3 all the same speed" day: the
// FC had main_rotor_gear_ratio 10:1 (backwards — head = motor × 10) so the
// governor believed the head was doing 72,000 rpm and sat at minimum
// throttle; the receiver's own divisor (10.2) then hid it by dividing the
// number back down. Lesson: ONE ratio, on the flight controller, with a
// live plain-English readout so a backwards entry is obvious. The receiver
// divisor is reset to 1 on save. Malcolm, the same evening: label the boxes
// themselves "rotor : motor" (and "rotor : tail") so the direction is
// self-evident, and cut the text. Decimals are accepted (1 : 10.2) and
// scaled to the whole-number pair Rotorflight stores (10 : 102).
//
// Rotorflight (motors.c motorInit): headSpeed = motorRpm × main[0]/main[1];
// non-motorised tail: tailSpeed = headSpeed × tail[1]/tail[0]. So main[0]
// = rotor turns, main[1] = motor turns; tail[0] = rotor, tail[1] = tail.
// Both are computed at boot only, so a change needs a flight-controller
// restart. MSP 131 reply = 29 B (has motorCount at [6]); MSP 222 write =
// 28 B (same bytes without it). Ratios sit at reply [21..29) / write [20..28).
(function(){
const rdU16=(b,o)=>b[o]|(b[o+1]<<8);
const hexToBytes=h=>{const o=new Uint8Array(h.length/2);for(let i=0;i<o.length;i++)o[i]=parseInt(h.substr(i*2,2),16);return o;};
const bytesToHex=b=>Array.from(b).map(x=>x.toString(16).padStart(2,'0')).join('');
const fmt=x=>(Math.round(x*100)/100).toString();
const isInt=x=>Math.abs(x-Math.round(x))<1e-6;

// Two box values → the whole-number pair the FC stores, or null if unusable.
// "1 : 10.2" → [10,102]; "399 : 4080" → [399,4080]; blanks/zeros → null.
function pair(a,b){
    let n=parseFloat(a), d=parseFloat(b);
    if(!(n>0)||!(d>0)) return null;
    for(let k=0;k<4&&!(isInt(n)&&isInt(d));k++){ n*=10; d*=10; }
    n=Math.round(n); d=Math.round(d);
    if(n<1||d<1||n>65535||d>65535) return null;
    return [n,d];
}

// Plain-English verdict for a ratio pair. kind: 'main' | 'tail'.
function verdict(kind,n,d){
    n=parseFloat(n)||0; d=parseFloat(d)||0;
    if(!(n>0&&d>0)) return {bad:true,text:'Enter both numbers.'};
    const same=Math.abs(n-d)<1e-9;
    if(kind==='main'){
        if(same) return {bad:true,text:'Not set (1 : 1) — head speed would read as motor RPM, about ten times too high.'};
        if(n>d) return {bad:true,text:'⚠️ Backwards — this says the rotor turns '+fmt(n/d)+' times per motor turn. Swap the two numbers.'};
        return {bad:false,text:'= 1 : '+fmt(d/n)+' — the motor turns '+fmt(d/n)+' times per rotor turn ✓'};
    }
    if(same) return {bad:false,text:'1 : 1 — the tail turns at head speed (only right for a motorised tail).'};
    if(n>d) return {bad:true,text:'⚠️ Backwards — the tail spins 4–5 times faster than the rotor. Swap the two numbers.'};
    return {bad:false,text:'= the tail turns '+fmt(d/n)+' times per rotor turn ✓'};
}

// Live hint under a pair of inputs (used by First-time basics too).
function attachHint(nId,dId,outId,kind){
    addCss();
    const n=document.getElementById(nId), d=document.getElementById(dId), out=document.getElementById(outId);
    if(!n||!d||!out) return;
    const paint=()=>{ const v=verdict(kind,n.value,d.value); out.textContent=v.text; out.style.color=v.bad?'#8a2f2f':'#2f6b3a'; out.style.fontWeight=v.bad?'600':''; };
    n.addEventListener('input',paint); d.addEventListener('input',paint);
    paint(); return paint;
}

// .gPair = two boxes with a caption over each ("rotor" : "motor") — shared
// with First-time basics, so it is not scoped to .gw.
const CSS='.gPair{display:inline-flex;align-items:flex-end;gap:.3em;white-space:nowrap}'+
'.gPair .gCell{display:inline-flex;flex-direction:column;align-items:center;gap:.12em}'+
'.gPair .gCap{font-size:.74em;font-weight:600;color:#4a5b66;line-height:1.1;letter-spacing:.02em}'+
'.gPair .gColon{font-weight:700;padding-bottom:.45em}'+
'.gw .gRow{display:flex;align-items:center;flex-wrap:wrap;gap:.35em .5em;margin:.35em 0}'+
'.gw .gRow b{min-width:8.5em}.gw input[type=number]{width:4.6em;padding:.4em;font-size:1em;border-radius:8px;border:1px solid #b8c7d0}'+
'.gw .gHint{font-size:.86em;margin:0 0 .5em;min-height:1.2em;line-height:1.35}'+
'.gw .gMsg{font-size:.9em;margin:.4em 0;padding:.55em .7em;border-radius:8px;display:none;line-height:1.4}'+
'.gw .gMsg.good{display:block;background:#dcefd9;color:#1f4a24}.gw .gMsg.bad{display:block;background:#f3d7d2;color:#6d1f14}.gw .gMsg.info{display:block;background:#dfe9f2;color:#22415a}'+
'.gw .gRestart{display:none;margin:.5em 0 0;padding:.6em .7em;border-radius:8px;background:#f3e4bd;color:#5c4a1a;font-size:.9em;line-height:1.4}'+
'.gw .gRestart .btn{margin:.5em 0 0}.gw .gLive{font-size:.85em;color:#55676f;margin:.4em 0 0}';
function addCss(){ if(document.getElementById('gwCss'))return; const s=document.createElement('style'); s.id='gwCss'; s.textContent=CSS; document.head.appendChild(s); }

// Renders the editor inside `host` (an element or id). opts.tail=false hides the tail pair.
function mount(host,opts){
    opts=opts||{}; addCss();
    const el=typeof host==='string'?document.getElementById(host):host;
    if(!el) return null;
    el.classList.add('gw');
    const boxes=(a,b,ca,cb)=>'<span class=gPair><span class=gCell><span class=gCap>'+ca+'</span><input type=number id='+a+' min=0 max=65535 step=any inputmode=decimal></span>'+
      '<span class=gColon>:</span><span class=gCell><span class=gCap>'+cb+'</span><input type=number id='+b+' min=0 max=65535 step=any inputmode=decimal></span></span>';
    el.innerHTML=
      '<div class=gRow><b data-help="Rotor : motor &mdash; how many turns each makes, e.g. 1 : 10.2, or the teeth counts (pinion : main gear, 10 : 102). Rotorflight turns motor RPM into head speed with this; the governor and the transmitter both depend on it. Two-stage belt + gear drive (SAB Goblin, RAW, Black Thunder): multiply the stages &mdash; motor pulley &times; drive pinion : big pulley &times; main gear, e.g. Goblin 770 = 21&times;19 : 60&times;68 = 399 : 4080. (Rotorflight: main_rotor_gear_ratio)">Main gear ratio</b>'+
      boxes('gwMn','gwMd','rotor','motor')+'</div>'+
      '<p class=gHint id=gwMh></p>'+
      (opts.tail===false?'':'<div class=gRow><b data-help="Rotor : tail &mdash; how many turns each makes, usually 1 : 4 to 1 : 5.5. Only the tail-speed readout and tail vibration filters use it. Two-stage (SAB): tail pulley &times; drive pinion : front tail pulley &times; main gear, e.g. Goblin 770 = 25&times;19 : 37&times;68 = 475 : 2516. (Rotorflight: tail_rotor_gear_ratio)">Tail ratio</b>'+
      boxes('gwTn','gwTd','rotor','tail')+'</div>'+
      '<p class=gHint id=gwTh></p>')+
      '<button class="btn btn-fw" id=gwSave style="background:#5f8fab;margin:.2em 0 0"><span class=ico>&#128190;</span>Save to flight controller</button>'+
      '<div class=gMsg id=gwMsg></div>'+
      '<div class=gRestart id=gwRb><b>Restart the flight controller to apply.</b> Rotorflight only reads the gear ratio at power-up. Motor stopped, blades clear.'+
      '<button class="btn btn-fw" id=gwRbBtn style="background:#b3703c"><span class=ico>&#128260;</span>Restart flight controller</button></div>'+
      '<p class=gLive id=gwLive></p>';
    const $=id=>document.getElementById(id);
    const hasTail=opts.tail!==false;
    let raw=null, dirty=false;
    const paintM=attachHint('gwMn','gwMd','gwMh','main');
    const paintT=hasTail?attachHint('gwTn','gwTd','gwTh','tail'):null;
    const msg=(k,t)=>{ const m=$('gwMsg'); m.className='gMsg'+(k?' '+k:''); m.textContent=t||''; };
    el.addEventListener('input',()=>{dirty=true;});

    async function load(){
        try{
            const b=hexToBytes(await LDRC.msp(131));
            if(b.length<29) throw new Error('motor config short ('+b.length+' B)');
            raw=b.slice(0,29);
            if(!dirty){
                $('gwMn').value=rdU16(b,21); $('gwMd').value=rdU16(b,23);
                if(hasTail){ $('gwTn').value=rdU16(b,25); $('gwTd').value=rdU16(b,27); }
                paintM(); if(paintT)paintT();
            }
            $('gwSave').disabled=false;
            return true;
        }catch(e){
            raw=null; $('gwSave').disabled=true;
            msg('bad','No flight controller answering — power the model (blades off) and reload. '+(e&&e.message?e.message:''));
            return false;
        }
    }

    async function save(){
        let st=null; try{ st=await LDRC.fetchState(); }catch(e){}
        if(st&&st.rf&&st.rf.armed){ msg('bad','Refused — the model is ARMED. Disarm first.'); return; }
        const pm=pair($('gwMn').value,$('gwMd').value), pt=hasTail?pair($('gwTn').value,$('gwTd').value):null;
        if(!pm||(hasTail&&!pt)){ msg('bad','Enter a number above zero in every box (up to 65535, one decimal place is fine).'); return; }
        const mn=pm[0], md=pm[1], tn=hasTail?pt[0]:null, td=hasTail?pt[1]:null;
        const vm=verdict('main',mn,md);
        if(vm.bad && !(await LDRC.confirm(vm.text+'\n\nSave it anyway?',{title:'Gear ratio looks wrong',icon:'⚠️',yes:'Save anyway',kind:'warn'}))) return;
        if(hasTail){ const vt=verdict('tail',tn,td);
            if(vt.bad && !(await LDRC.confirm(vt.text+'\n\nSave it anyway?',{title:'Tail ratio looks wrong',icon:'⚠️',yes:'Save anyway',kind:'warn'}))) return; }
        $('gwSave').disabled=true; msg('info','Saving…');
        try{
            // Read-modify-write: fresh 131 so nothing else in the motor config is disturbed.
            const b=hexToBytes(await LDRC.msp(131));
            if(b.length<29) throw new Error('motor config short');
            const w=new Uint8Array(28);
            w.set(b.slice(0,6),0); w.set(b.slice(7,21),6);          // everything but motorCount + ratios
            const r=[mn,md, hasTail?tn:rdU16(b,25), hasTail?td:rdU16(b,27)];
            for(let i=0;i<4;i++){ w[20+2*i]=r[i]&0xff; w[21+2*i]=(r[i]>>8)&0xff; }
            await LDRC.msp(222,bytesToHex(w));
            await LDRC.msp(250);
            const c=hexToBytes(await LDRC.msp(131));
            const ok=c.length>=29 && rdU16(c,21)===r[0] && rdU16(c,23)===r[1] && rdU16(c,25)===r[2] && rdU16(c,27)===r[3];
            if(!ok) throw new Error('the flight controller kept different values — reload and check');
            dirty=false; raw=c.slice(0,29);
            // Show what the FC now holds (a decimal entry was scaled to whole numbers).
            $('gwMn').value=r[0]; $('gwMd').value=r[1];
            if(hasTail){ $('gwTn').value=r[2]; $('gwTd').value=r[3]; }
            paintM(); if(paintT)paintT();
            let extra='';
            // The receiver's old divisor would divide the (now correct) head speed again.
            if(st&&st.rf&&st.rf.gear_ratio!=null&&Math.abs(st.rf.gear_ratio-1)>0.001){
                try{ await fetch('/api/gear?ratio=1',{method:'POST'}); extra=' Receiver divisor reset from '+st.rf.gear_ratio+' to 1 (the flight controller now sends true head speed).'; }
                catch(e){ extra=' Could not reset the receiver divisor ('+st.rf.gear_ratio+') — set it to 1 on the receiver page.'; }
            }
            msg('good','✓ Saved and read back from the flight controller.'+extra);
            $('gwRb').style.display='block';
            if(opts.onSaved) opts.onSaved();
        }catch(e){ msg('bad','Save failed: '+(e&&e.message?e.message:e)); }
        $('gwSave').disabled=false;
    }

    async function restart(){
        let st=null; try{ st=await LDRC.fetchState(); }catch(e){}
        if(st&&st.rf&&(st.rf.armed||(st.rf.head_speed|0)>0)){ msg('bad','Not now — the model is armed or the rotor is turning. Stop the motor first.'); return; }
        if(!(await LDRC.confirm('Restart the flight controller now? The link returns in a few seconds.',{title:'Restart flight controller',icon:'🔄',yes:'Restart',kind:'warn'}))) return;
        $('gwRb').style.display='none';
        try{ await LDRC.msp(68,'',1); }catch(e){}   // it reboots before answering; a retry would reboot it twice
        msg('info','Flight controller restarting — back in a few seconds…');
        setTimeout(async()=>{ if(await load()) msg('good','✓ Restarted — the new gear ratio is live. Spool up (blades off) and check the transmitter’s head speed.'); },8000);
    }

    async function live(){
        try{ const s=await LDRC.fetchState();
            if(s&&s.rf){
                const hs=s.rf.head_speed|0, gr=s.rf.gear_ratio;
                let t=hs>0?'Head speed on the transmitter now: '+hs+' rpm.':'';
                if(gr!=null&&Math.abs(gr-1)>0.001) t+=' Receiver divisor is '+gr+' (should be 1 — fixed on next Save).';
                $('gwLive').textContent=t;
            } }catch(e){}
        setTimeout(live,2000);
    }

    $('gwSave').addEventListener('click',save);
    $('gwRbBtn').addEventListener('click',restart);
    load(); live();
    return {load,save,verdict};
}

window.LDRCGear={mount,attachHint,verdict,pair};
})();
