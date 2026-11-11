const tg=window.Telegram?.WebApp; try{tg?.ready();tg?.expand();tg?.disableVerticalSwipes?.()}catch{}
const $=s=>document.querySelector(s), view=$('#view'), ov=$('#ov'), INIT=tg?.initData||'';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let ME=null, tab='home', player=null, plan=null;
async function api(p,o={}){const r=await fetch(p,{method:o.method||'GET',headers:{'X-Init-Data':INIT,'Content-Type':'application/json'},body:o.body?JSON.stringify(o.body):undefined});
 if(!r.ok){const e=new Error(r.status);e.status=r.status;throw e}return r.json()}
const dur=s=>{s=+s||0;const h=s/3600|0,m=s%3600/60|0,x=s%60;return h?`${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}`:`${m}:${String(x).padStart(2,'0')}`};
const kfmt=n=>n>=1e6?(n/1e6).toFixed(1)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':n;
const ago=t=>{const d=(Date.now()/1e3-t);return d<3600?(d/60|0)+'m ago':d<86400?(d/3600|0)+'h ago':(d/86400|0)+'d ago'};
function toast(t){const e=document.createElement('div');e.className='toast';e.textContent=t;document.body.append(e);setTimeout(()=>e.remove(),2400)}
function setTheme(t){document.documentElement.dataset.theme=t;localStorage.theme=t;try{tg?.setHeaderColor(t=='dark'?'#060b1c':'#f1f6ff');tg?.setBackgroundColor(t=='dark'?'#060b1c':'#f1f6ff')}catch{}}
setTheme(localStorage.theme||tg?.colorScheme||'dark');
$('#th').onclick=()=>setTheme(document.documentElement.dataset.theme=='dark'?'light':'dark');
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>go(b.dataset.t));
let st;$('#q').oninput=e=>{clearTimeout(st);st=setTimeout(()=>{tab='home';tabs();home(e.target.value.trim())},350)};
function tabs(){document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.t==tab))}
function go(t){stopPlayer();tab=t;tabs();tg?.BackButton?.hide();({home:()=>home(),plans:()=>upsell(null),me:account}[t])()}
tg?.BackButton?.onClick(()=>go(tab));

/* ---------- boot ---------- */
async function boot(){
 if(!INIT){view.innerHTML='<div class="empty">Open this app from Telegram.</div>';return}
 try{ME=await api('/api/me')}catch(e){view.innerHTML='<div class="empty">Could not load. Reopen the app.</div>';return}
 $('#logo').textContent=ME.app_name;document.title=ME.app_name;
 if(ME.channel.on&&!ME.joined)return joinGate();
 ov.innerHTML='';
 if(!localStorage['w'+ME.user.id])return welcome();
 route();
}
function joinGate(){
 ov.innerHTML=`<div class="ov"><div class="box"><div class="up"><img src="/static/img/welcome.jpg" alt=""><div class="b"><h2>Join our updates channel</h2><p>Join the channel to unlock ${esc(ME.app_name)}. New uploads and announcements land there first.</p>
 <div style="display:grid;gap:10px;margin-top:16px"><button class="btn block" id="jc">Join channel</button><button class="btn ghost block" id="jd">I've joined</button></div></div></div></div></div>`;
 $('#jc').onclick=()=>tg.openTelegramLink?tg.openTelegramLink(ME.channel.url):window.open(ME.channel.url);
 $('#jd').onclick=async()=>{ME=await api('/api/me?fresh=1');ME.joined?boot():toast("You haven't joined yet")};
}
function welcome(){
 ov.innerHTML=`<div class="ov hero2"><div class="wel" style="background-image:url(/static/img/welcome.jpg)"><h1>${esc(ME.app_name)}</h1><p>Adults only (18+). Private, watermarked streaming inside Telegram.</p><button class="btn block" id="go">I am 18+ — Enter</button></div></div>`;
 $('#go').onclick=()=>{localStorage['w'+ME.user.id]=1;ov.innerHTML='';route()};
}
function route(){
 const sp=tg?.initDataUnsafe?.start_param||'', qs=new URLSearchParams(location.search);
 const v=sp.startsWith('v_')?sp.slice(2):qs.get('v');
 if(qs.get('tab')=='plans'){go('plans')}else{go('home')}
 if(v)openVideo(v);
}

/* ---------- home ---------- */
const card=v=>`<div class="card" data-id="${v.id}"><div class="th"><img loading="lazy" src="${v.thumb}" alt=""><div class="sc"></div>${v.premium?'<span class="chip l">💎 Premium</span>':'<span class="chip f">Free</span>'}<span class="chip d">${dur(v.duration)}</span></div><div class="t">${esc(v.title)}</div><div class="m">${kfmt(v.views)} views • ${ago(v.created)}</div></div>`;
async function home(q=''){
 view.innerHTML='<div class="grid">'+'<div class="sk"></div>'.repeat(4)+'</div>';
 let d;try{d=await api('/api/videos'+(q?'?q='+encodeURIComponent(q):''))}catch{view.innerHTML='<div class="empty">Could not load videos.</div>';return}
 if(!d.items.length){view.innerHTML=`<div class="empty">${q?'No videos match your search.':'No videos yet. Check back soon.'}</div>`;return}
 const [h,...rest]=q?[null,...d.items]:d.items;
 view.innerHTML=(h?`<div class="hero card" data-id="${h.id}"><div class="bg" style="background-image:url(${h.thumb})"></div><img src="${h.thumb}" alt=""><div class="sc"></div>${h.premium?'<span class="chip l">💎 Premium</span>':''}<div class="tx"><div class="chip" style="position:static;display:inline-block">Latest</div><h2>${esc(h.title)}</h2><div class="m">${dur(h.duration)} • ${kfmt(h.views)} views</div></div></div>`:'')+
 (rest.length?`<h3 class="sec">${q?'Results':'More videos'}</h3><div class="grid" id="g">${rest.map(card).join('')}</div>`:'')+(d.next?'<div style="text-align:center;margin-top:20px"><button class="btn ghost" id="more">Load more</button></div>':'');
 bind();
 if(d.next)$('#more').onclick=async()=>{const n=await api('/api/videos?before='+d.next+(q?'&q='+encodeURIComponent(q):''));$('#g').insertAdjacentHTML('beforeend',n.items.map(card).join(''));bind();n.next?d.next=n.next:$('#more').remove()};
}
function bind(){document.querySelectorAll('[data-id]').forEach(e=>e.onclick=()=>openVideo(e.dataset.id))}

/* ---------- player ---------- */
async function openVideo(id){
 let d;try{d=await api('/api/video/'+id)}catch{return toast('Video not found')}
 if(d.locked)return upsell(d);
 let p;try{p=await api(`/api/video/${id}/play`,{method:'POST'})}catch(e){return e.status==402?upsell(d):e.status==403?joinGate():toast('Cannot play this video')}
 stopPlayer();tg?.BackButton?.show();
 view.innerHTML=`<div class="player" id="pl"><video id="v" playsinline webkit-playsinline preload="metadata" poster="${d.thumb}" controlsList="nodownload noremoteplayback" disablePictureInPicture disableRemotePlayback></video>
 <div class="bigplay" id="bp"><span>▶</span></div><div class="ctl"><button id="pp">▶</button><span id="ct">0:00</span><input type="range" id="sk" min="0" max="1000" value="0"><span id="dt">${dur(d.duration)}</span><button id="sp">1x</button><button id="fs">⛶</button></div>
 <div class="shield" id="sh"><div><div style="font-size:34px">🔒</div><b>Playback paused</b><p style="opacity:.8;margin-top:6px">Protected content. Return to this screen to continue.</p></div></div></div>
 <div class="vt">${esc(d.title)}</div><div class="row"><span class="live"><i></i><span id="lv">${p.live} watching</span></span><span class="live" id="vw">${kfmt(p.views)} views</span><span style="flex:1"></span><button class="btn sm" id="sh2">Share</button></div>`;
 $('#sh2').onclick=()=>{const u='https://t.me/share/url?url='+encodeURIComponent(d.link)+'&text='+encodeURIComponent(d.title);tg?.openTelegramLink?tg.openTelegramLink(u):window.open(u)};
 const v=$('#v'),pl=$('#pl');v.src=p.url;
 const tgl=()=>v.paused?v.play():v.pause();
 $('#bp').onclick=tgl;v.onclick=tgl;$('#pp').onclick=tgl;
 v.onplay=()=>{$('#pp').textContent='❚❚';$('#bp').style.display='none'};v.onpause=()=>{$('#pp').textContent='▶';$('#bp').style.display=''};
 v.ontimeupdate=()=>{if(v.duration){$('#sk').value=v.currentTime/v.duration*1000;$('#ct').textContent=dur(v.currentTime)}};
 v.onloadedmetadata=()=>$('#dt').textContent=dur(v.duration);
 $('#sk').oninput=e=>{if(v.duration)v.currentTime=e.target.value/1000*v.duration};
 const sp=[1,1.25,1.5,2,.75];let si=0;$('#sp').onclick=()=>{si=(si+1)%sp.length;v.playbackRate=sp[si];$('#sp').textContent=sp[si]+'x'};
 $('#fs').onclick=()=>{const f=document.fullscreenElement||document.webkitFullscreenElement;if(f){(document.exitFullscreen||document.webkitExitFullscreen).call(document)}else if(pl.requestFullscreen)pl.requestFullscreen().catch(()=>pl.classList.toggle('fs'));else pl.classList.toggle('fs')};
 player={id,v,pl,token:p.token,timers:[]};guard(player,p);
 player.timers.push(setInterval(async()=>{try{const r=await api(`/api/video/${id}/ping`,{method:'POST',body:{t:p.token}});$('#lv').textContent=r.live+' watching';$('#vw').textContent=kfmt(r.views)+' views'}catch(e){if(e.status==403){v.pause();toast('Session ended on another device')}}},15000));
}
function stopPlayer(){if(!player)return;player.timers.forEach(clearInterval);player.obs?.disconnect();player.off?.();try{player.v.pause();player.v.removeAttribute('src');player.v.load()}catch{}player=null}

/* watermark + anti-recording */
function guard(P,p){
 const {pl,v}=P,mk=()=>{const w=document.createElement('div');w.className='wm';w.style.opacity=p.opacity;pl.append(w);return w};
 let wms=[mk(),mk()],strikes=0;
 const stamp=()=>{const t=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});wms.forEach(w=>{w.textContent=p.wm+' • '+t;w.style.left=(2+Math.random()*58)+'%';w.style.top=(8+Math.random()*68)+'%'})};
 stamp();P.timers.push(setInterval(stamp,6000));
 const check=()=>{const bad=wms.some(w=>!w.isConnected||getComputedStyle(w).display=='none'||+getComputedStyle(w).opacity<.05||getComputedStyle(w).visibility=='hidden');
  if(bad){strikes++;wms.forEach(w=>w.remove());wms=[mk(),mk()];stamp();if(strikes>=3){v.pause();lock(true)}}};
 P.obs=new MutationObserver(check);P.obs.observe(pl,{childList:true,attributes:true,subtree:true,attributeFilter:['style','class']});
 P.timers.push(setInterval(check,2000));
 const sh=$('#sh');const lock=on=>{sh.style.display=on?'grid':'none'};
 const hide=()=>{if(document.hidden||!document.hasFocus()){v.pause();lock(true)}};
 const show=()=>{if(strikes<3&&!document.hidden)lock(false)};
 const keys=e=>{const k=e.key?.toLowerCase();if(k=='printscreen'){navigator.clipboard?.writeText('');v.pause();lock(true);e.preventDefault()}
  if(k=='f12'||(e.ctrlKey||e.metaKey)&&['s','p','u'].includes(k)||(e.ctrlKey&&e.shiftKey&&['i','j','c'].includes(k)))e.preventDefault()};
 const ctx=e=>e.preventDefault(),dev=()=>{if(innerWidth>700&&(outerWidth-innerWidth>170||outerHeight-innerHeight>200)){v.pause();lock(true)}};
 document.addEventListener('visibilitychange',hide);addEventListener('blur',hide);addEventListener('focus',show);
 document.addEventListener('keydown',keys);document.addEventListener('contextmenu',ctx);addEventListener('resize',dev);
 try{navigator.mediaDevices.getDisplayMedia=()=>Promise.reject(new DOMException('Blocked','NotAllowedError'))}catch{}
 P.off=()=>{document.removeEventListener('visibilitychange',hide);removeEventListener('blur',hide);removeEventListener('focus',show);document.removeEventListener('keydown',keys);document.removeEventListener('contextmenu',ctx);removeEventListener('resize',dev)};
}

/* ---------- premium / account ---------- */
function upsell(d){
 stopPlayer();if(d)tg?.BackButton?.show();
 const s=ME.sub;
 if(s.active&&!d){view.innerHTML=`<div class="up"><img src="/static/img/upsell.jpg" alt=""><div class="b"><h2>Premium is active</h2><p>${s.days_left} days left · renews manually when you buy again.</p></div></div><h3 class="sec" style="margin-top:22px">Extend your plan</h3><div id="pp"></div>`;return plansUI($('#pp'))}
 view.innerHTML=`<div class="up"><img src="/static/img/upsell.jpg" alt=""><div class="b"><h2>${d?'This video is premium':'Go premium'}</h2><p>${d?esc(d.title)+' — subscribe to watch it and every premium upload.':'Unlock every premium video, new drops first, in full quality.'}</p><div id="pp"></div></div></div>`;
 plansUI($('#pp'));
}
function plansUI(el){
 plan=ME.plans[0]?.id;
 const draw=()=>{el.innerHTML=`<div class="plans">${ME.plans.map(p=>`<button class="plan ${p.id==plan?'on':''}" data-p="${p.id}"><span><b>${esc(p.name)}</b><small>${p.days} days access</small></span><span class="p">$${p.price}</span></button>`).join('')}</div>
 <button class="btn block" id="pay">Pay with USDT</button><button class="btn ghost block" id="chk" style="margin-top:10px">I've paid — refresh</button>`;
 el.querySelectorAll('.plan').forEach(b=>b.onclick=()=>{plan=b.dataset.p;draw()});
 $('#pay').onclick=async()=>{$('#pay').disabled=true;try{const r=await api('/api/pay',{method:'POST',body:{plan}});tg?.openLink?tg.openLink(r.url):window.open(r.url)}catch{toast('Payments unavailable right now')}$('#pay').disabled=false};
 $('#chk').onclick=async()=>{ME=await api('/api/me?fresh=1');ME.sub.active?(toast('Premium active 🎉'),go('home')):toast('Payment not confirmed yet')}};
 draw();
}
function account(){
 const u=ME.user,s=ME.sub;
 view.innerHTML=`<div class="panel"><b style="font-size:18px">${esc(u.name)}</b><div style="color:var(--mut);margin-top:4px">${u.username?'@'+esc(u.username)+' · ':''}ID ${u.id}</div></div>
 <div class="panel"><b>Subscription</b><p style="color:var(--mut);margin:6px 0 12px">${s.active?`Active · ${s.days_left} days left`:'No active plan'}</p><button class="btn" id="gp">${s.active?'Extend':'Get premium'}</button></div>
 <div class="panel"><b>Updates channel</b><p style="color:var(--mut);margin:6px 0 12px">New uploads are announced here first.</p>${ME.channel.on?'<button class="btn ghost" id="ch">Open channel</button>':''}</div>`;
 $('#gp').onclick=()=>go('plans');if($('#ch'))$('#ch').onclick=()=>tg?.openTelegramLink(ME.channel.url);
}
boot();
