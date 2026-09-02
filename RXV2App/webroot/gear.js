// Gear-ratio widget — edits Rotorflight's OWN gear ratios (MSP 131/222).
//
// Malcolm 2026-09-02, the Goblin's "banks 1-3 all the same speed" day: the
// FC had main_rotor_gear_ratio 10:1 (backwards — head = motor × 10) so the
// governor believed the head was doing 72,000 rpm and sat at minimum
// throttle; the receiver's own divisor (10.2) then hid it by dividing the
// number back down. Lesson: ONE ratio, on the flight controller, entered
// as pinion : main-gear teeth, with a live plain-English readout so a
// backwards entry is obvious. The receiver divisor is reset to 1 on save.
//
// Rotorflight (motors.c motorInit): headSpeed = motorRpm × main[0]/main[1];
// non-motorised tail: tailSpeed = headSpeed × tail[1]/tail[0]. Both are
// computed at boot only, so a change needs a flight-controller restart.
// MSP 131 reply = 29 B (has motorCount at [6]); MSP 222 write = 28 B
// (same bytes without it). Ratios sit at reply [21..29) / write [20..28).
(function(){
const rdU16=(b,o)=>b[o]|(b[o+1]<<8);
const hexToBytes=h=>{const o=new Uint8Array(h.length/2);for(let i=0;i<o.length;i++)o[i]=parseInt(h.substr(i*2,2),16);return o;};
const bytesToHex=b=>Array.from(b).map(x=>x.toString(16).padStart(2,'0')).join('');
const fmt=x=>(Math.round(x*100)/100).toString();

// Plain-English verdict for a ratio pair. kind: 'main' | 'tail'.
function verdict(kind,n,d){
    n=parseInt(n)||0; d=parseInt(d)||0;
    if(n<1||d<1) return {bad:true,text:'Enter both numbers (whole teeth counts).'};
    if(kind==='main'){
        if(n===d) return {bad:true,text:'Not set (1 : 1) — Rotorflight will call motor RPM the head speed, about ten times too high.'};
        if(n>d) return {bad:true,text:'⚠️ Backwards — this says the rotor turns '+fmt(n/d)+' times per motor turn. Swap them: pinion : main gear (e.g. 10 : 102).'};
        return {bad:false,text:'= 1 : '+fmt(d/n)+' — the motor turns '+fmt(d/n)+' times per rotor turn ✓'};
    }
    if(n===d) return {bad:false,text:'1 : 1 — tail turns at head speed (only right for a motorised tail).'};
    if(n>d) return {bad:true,text:'⚠️ Backwards — tails spin 4–5 times faster than the head. Swap them (e.g. 1 : 4 or 10 : 47).'};
    return {bad:false,text:'= the tail turns '+fmt(d/n)+' times per rotor turn ✓'};
}

// Live hint under a pair of inputs (used by First-time basics too).
function attachHint(nId,dId,outId,kind){
    const n=document.getElementById(nId), d=document.getElementById(dId), out=document.getElementById(outId);
    if(!n||!d||!out) return;
    const paint=()=>{ const v=verdict(kind,n.value,d.value); out.textContent=v.text; out.style.color=v.bad?'#8a2f2f':'#2f6b3a'; out.style.fontWeight=v.bad?'600':''; };
    n.addEventListener('input',paint); d.addEventListener('input',paint);
    paint(); return paint;
}

const CSS='.gw .gRow{display:flex;align-items:center;flex-wrap:wrap;gap:.35em .5em;margin:.35em 0}'+
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
    el.innerHTML=
      '<div class=gRow><b data-help="Motor pinion (or pulley) teeth : main gear (or pulley) teeth. Rotorflight turns motor RPM into head speed with this &mdash; the governor and the transmitter both depend on it. (Rotorflight: main_rotor_gear_ratio)">Main gear ratio</b>'+
      '<span style="white-space:nowrap"><input type=number id=gwMn min=1 max=50000 step=1 inputmode=numeric> : <input type=number id=gwMd min=1 max=50000 step=1 inputmode=numeric></span> <span class=muted>pinion : main gear</span></div>'+
      '<p class=gHint id=gwMh></p>'+
      (opts.tail===false?'':'<div class=gRow><b data-help="Head : tail &mdash; how many turns the tail rotor makes per one main-rotor turn (belt or shaft drive). Only for the tail-speed readout and tail vibration filters. (Rotorflight: tail_rotor_gear_ratio)">Tail ratio</b>'+
      '<span style="white-space:nowrap"><input type=number id=gwTn min=1 max=50000 step=1 inputmode=numeric> : <input type=number id=gwTd min=1 max=50000 step=1 inputmode=numeric></span> <span class=muted>head : tail</span></div>'+
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
        const mn=parseInt($('gwMn').value)||0, md=parseInt($('gwMd').value)||0;
        const tn=hasTail?(parseInt($('gwTn').value)||0):null, td=hasTail?(parseInt($('gwTd').value)||0):null;
        if(mn<1||md<1||(hasTail&&(tn<1||td<1))){ msg('bad','Enter whole numbers, 1 or more, in every box.'); return; }
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

window.LDRCGear={mount,attachHint,verdict};
})();
