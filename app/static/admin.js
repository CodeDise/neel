const tg=window.Telegram?.WebApp;try{tg?.ready();tg?.expand()}catch{}
const $=s=>document.querySelector(s),view=$('#view'),INIT=tg?.initData||'';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(p,m='GET',b){const r=await fetch(p,{method:m,headers:{'X-Init-Data':INIT,'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});if(!r.ok){const e=new Error(r.status);e.status=r.status;throw e}return r.json()}
function setTheme(t){document.documentElement.dataset.theme=t;localStorage.theme=t}setTheme(localStorage.theme||tg?.colorScheme||'dark');
$('#th').onclick=()=>setTheme(document.documentElement.dataset.theme=='dark'?'light':'dark');
const toast=t=>{const e=document.createElement('div');e.className='toast';e.textContent=t;document.body.append(e);setTimeout(()=>e.remove(),2200)};
const date=t=>t?new Date(t*1e3).toLocaleString([], {dateStyle:'medium',timeStyle:'short'}):'—';
const mb=b=>(b/1048576).toFixed(0)+' MB';
function ask(title,fields){return new Promise(res=>{const o=$('#ov');o.innerHTML=`<div class="ov"><div class="box panel"><b style="font-size:17px">${esc(title)}</b><div style="margin-top:12px">${fields.map((f,i)=>`<label style="font-size:12.5px;color:var(--mut)">${esc(f.l)}</label>${f.opts?`<select class="fld" id="f${i}">${f.opts.map(x=>`<option>${esc(x)}</option>`).join('')}</select>`:`<input class="fld" id="f${i}" value="${esc(f.v??'')}" type="${f.t||'text'}">`}`).join('')}</div><div class="row"><button class="btn" id="ok">Save</button><button class="btn ghost" id="no">Cancel</button></div></div></div>`;
 $('#ok').onclick=()=>{const v=fields.map((_,i)=>$('#f'+i).value);o.innerHTML='';res(v)};$('#no').onclick=()=>{o.innerHTML='';res(null)}})}
const sure=m=>confirm(m);
let ME,tab;
const TABS={dashboard:['Dashboard','stats'],videos:['Videos','videos'],users:['Users','users'],payments:['Payments','payments'],admins:['Admins','admins'],shards:['Database','shards'],settings:['Settings','settings']};
async function boot(){
 try{ME=await api('/api/admin/me')}catch{view.innerHTML='<div class="empty" style="text-align:center;color:var(--mut);padding:60px">Not available.</div>';return}
 $('#role').textContent=ME.role;
 const ts=Object.entries(TABS).filter(([k,v])=>ME.perms.includes(v[1]));
 $('#nav').innerHTML=ts.map(([k,v])=>`<button data-t="${k}">${v[0]}</button>`).join('');
 document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>show(b.dataset.t));show(ts[0][0]);
}
function show(t){tab=t;document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('on',b.dataset.t==t));({dashboard,videos,users,payments,admins,shards,settings}[t])()}
async function dashboard(){
 const s=await api('/api/admin/stats');
 view.innerHTML=`<div class="stats">${[['Users',s.users],['Active subs',s.subs],['Videos',s.videos],['Total views',s.views],['Watching now',s.live],['Revenue 30d','$'+s.revenue30],['Revenue total','$'+s.revenue]].map(x=>`<div class="stat"><b>${x[1]}</b><span>${x[0]}</span></div>`).join('')}</div><h3 class="sec">Database shards</h3>${shardCards(s.shards)}`;
}
function shardCards(a,ctl){return a.map(x=>`<div class="panel"><div class="row" style="margin:0"><b>Shard ${x.index}</b>${x.active?'<span class="pill ok">active</span>':''}${x.online?'':'<span class="pill bad">offline</span>'}<span style="flex:1"></span><span style="color:var(--mut)">${x.videos} videos</span></div><div class="bar"><i style="width:${Math.min(100,x.usage_mb/x.limit_mb*100)}%"></i></div><small style="color:var(--mut)">${x.usage_mb} / ${x.limit_mb} MB</small>${ctl&&!x.active?`<div class="row"><button class="btn sm ghost" data-a="${x.index}">Make active</button></div>`:''}</div>`).join('')}
async function videos(q=''){
 view.innerHTML=`<input class="fld" id="vq" placeholder="Search videos" value="${esc(q)}"><div id="vl"></div><p style="color:var(--mut);font-size:13px;margin-top:8px">Uploads happen inside the bot: open the bot, send /admin, tap Upload video.</p>`;
 $('#vq').onchange=e=>videos(e.target.value);
 const d=await api('/api/admin/videos?q='+encodeURIComponent(q));
 $('#vl').innerHTML=d.items.map(v=>`<div class="li"><img src="${v.thumb}" alt=""><div class="g"><b>${esc(v.title)}</b><small>${v.views} views · ${mb(v.size)} · shard ${v.shard}${v.live?` · ${v.live} live`:''}</small><div class="row" style="margin:8px 0 0"><button class="btn sm ghost" data-e="${v.id}">Rename</button><button class="btn sm ghost" data-t="${v.id}" data-p="${v.premium?1:0}">${v.premium?'💎 Premium':'🔓 Free'}</button><button class="btn sm red" data-d="${v.id}">Delete</button></div></div></div>`).join('')||'<div style="color:var(--mut);padding:30px;text-align:center">No videos.</div>';
 const by=a=>d.items.find(v=>v.id==a);
 document.querySelectorAll('[data-e]').forEach(b=>b.onclick=async()=>{const r=await ask('Rename video',[{l:'Title',v:by(b.dataset.e).title}]);if(r){await api('/api/admin/video/'+b.dataset.e,'PATCH',{title:r[0]});videos(q)}});
 document.querySelectorAll('[data-t]').forEach(b=>b.onclick=async()=>{await api('/api/admin/video/'+b.dataset.t,'PATCH',{premium:b.dataset.p!='1'});videos(q)});
 document.querySelectorAll('[data-d]').forEach(b=>b.onclick=async()=>{if(sure('Delete this video permanently?')){await api('/api/admin/video/'+b.dataset.d,'DELETE');videos(q)}});
}
async function users(q=''){
 view.innerHTML=`<input class="fld" id="uq" placeholder="Search by ID, @username or name" value="${esc(q)}"><div id="ul"></div>`;$('#uq').onchange=e=>users(e.target.value.trim());
 const d=await api('/api/admin/users?q='+encodeURIComponent(q));
 $('#ul').innerHTML=d.items.map(u=>`<div class="li"><div class="g"><b>${esc(u.name)||'—'} ${u.username?'@'+esc(u.username):''}</b><small>ID ${u.id} · ${u.sub_until*1e3>Date.now()?'premium until '+date(u.sub_until):'no plan'} ${u.banned?'· banned':''}</small><div class="row" style="margin:8px 0 0"><button class="btn sm ghost" data-g="${u.id}">Grant days</button><button class="btn sm ghost" data-r="${u.id}">Revoke</button><button class="btn sm ${u.banned?'ghost':'red'}" data-b="${u.id}" data-v="${u.banned?0:1}">${u.banned?'Unban':'Ban'}</button></div></div></div>`).join('')||'<div style="color:var(--mut);padding:30px;text-align:center">No users found.</div>';
 document.querySelectorAll('[data-g]').forEach(b=>b.onclick=async()=>{const r=await ask('Grant premium',[{l:'Days',v:30,t:'number'}]);if(r){await api('/api/admin/user/'+b.dataset.g,'POST',{days:+r[0]});toast('Granted');users(q)}});
 document.querySelectorAll('[data-r]').forEach(b=>b.onclick=async()=>{if(sure('Revoke premium?')){await api('/api/admin/user/'+b.dataset.r,'POST',{days:0});users(q)}});
 document.querySelectorAll('[data-b]').forEach(b=>b.onclick=async()=>{await api('/api/admin/user/'+b.dataset.b,'POST',{banned:b.dataset.v=='1'});users(q)});
}
async function payments(){
 const d=await api('/api/admin/payments');
 view.innerHTML=d.items.map(p=>`<div class="li"><div class="g"><b>$${p.amount} · ${esc(p.plan)}</b><small>User ${p.uid} · ${date(p.created)}</small></div><span class="pill ${p.status=='paid'?'ok':p.status=='pending'?'':'bad'}">${p.status}</span></div>`).join('')||'<div style="color:var(--mut);padding:30px;text-align:center">No payments yet.</div>';
}
async function admins(){
 const d=await api('/api/admin/admins');
 view.innerHTML=`<button class="btn" id="aa" style="margin-bottom:14px">Add admin</button>`+d.items.map(a=>`<div class="li"><div class="g"><b>${a.id}</b><small>${a.role}${a.fixed?' · set in environment':''}</small></div>${a.fixed?'':`<button class="btn sm red" data-x="${a.id}">Remove</button>`}</div>`).join('')+`<div class="panel"><b>Roles</b><p style="color:var(--mut);line-height:1.6;margin-top:6px"><b>admin</b> uploads, videos, users, payments, stats, broadcast, settings, database.<br><b>uploader</b> uploads, manages videos, sees stats.<br><b>support</b> users, payments, stats.<br>Only owners (env) manage admins. Admin status is never shown to regular users.</p></div>`;
 $('#aa').onclick=async()=>{const r=await ask('Add admin',[{l:'Telegram user ID',t:'number'},{l:'Role',opts:d.roles}]);if(r&&r[0]){await api('/api/admin/admins','POST',{id:+r[0],role:r[1]});admins()}};
 document.querySelectorAll('[data-x]').forEach(b=>b.onclick=async()=>{if(sure('Remove this admin?')){await api('/api/admin/admins/'+b.dataset.x,'DELETE');admins()}});
}
async function shards(){
 const d=await api('/api/admin/shards');
 view.innerHTML=`<p style="color:var(--mut);margin-bottom:14px;line-height:1.5">Videos are written to the active shard. When it reaches its limit the system switches to the next shard automatically. Add clusters by extending MONGO_URIS.</p>`+shardCards(d.items,true);
 document.querySelectorAll('[data-a]').forEach(b=>b.onclick=async()=>{if(sure('Switch active shard?')){await api('/api/admin/shards/active','POST',{index:+b.dataset.a});shards()}});
}
async function settings(){
 const s=await api('/api/admin/settings');
 view.innerHTML=`<div class="panel"><b>Plans (USDT)</b><div id="pls" style="margin-top:10px"></div><button class="btn sm ghost" id="ap">Add plan</button></div>
 <div class="panel"><b>Watermark</b><label style="display:block;font-size:12.5px;color:var(--mut);margin-top:8px">Template — use {name} {id} {username}</label><input class="fld" id="wt" value="${esc(s.wm_template)}"><label style="font-size:12.5px;color:var(--mut)">Opacity (0.05–0.6)</label><input class="fld" id="wo" type="number" step="0.01" value="${s.wm_opacity}"></div>
 <div class="panel"><b>Bot welcome text</b><textarea class="fld" id="wl" rows="3" style="margin-top:8px">${esc(s.welcome_text)}</textarea><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="nt" ${s.notify?'checked':''}> Push notification on every new upload</label></div>
 <button class="btn block" id="sv">Save settings</button>
 <div class="panel" style="margin-top:16px"><b>Broadcast</b><textarea class="fld" id="bt" rows="3" placeholder="Message to all users (HTML allowed)" style="margin-top:8px"></textarea><button class="btn ghost" id="bc">Send to everyone</button></div>`;
 let plans=s.plans.map(p=>({...p}));
 const draw=()=>{$('#pls').innerHTML=plans.map((p,i)=>`<div class="row" style="margin:0 0 8px"><input class="fld" style="width:70px;margin:0" data-k="id" data-i="${i}" value="${esc(p.id)}"><input class="fld" style="flex:1;min-width:90px;margin:0" data-k="name" data-i="${i}" value="${esc(p.name)}"><input class="fld" style="width:70px;margin:0" type="number" data-k="days" data-i="${i}" value="${p.days}"><input class="fld" style="width:70px;margin:0" type="number" data-k="price" data-i="${i}" value="${p.price}"><button class="btn sm red" data-rm="${i}">✕</button></div>`).join('')+'<small style="color:var(--mut)">id · name · days · price</small>';
  document.querySelectorAll('#pls input').forEach(e=>e.oninput=()=>plans[e.dataset.i][e.dataset.k]=e.value);
  document.querySelectorAll('[data-rm]').forEach(b=>b.onclick=()=>{plans.splice(+b.dataset.rm,1);draw()})};draw();
 $('#ap').onclick=()=>{plans.push({id:'p'+(plans.length+1),name:'New plan',days:30,price:5});draw()};
 $('#sv').onclick=async()=>{await api('/api/admin/settings','POST',{plans,wm_template:$('#wt').value,wm_opacity:+$('#wo').value,welcome_text:$('#wl').value,notify:$('#nt').checked});toast('Saved')};
 $('#bc').onclick=async()=>{const t=$('#bt').value.trim();if(t&&sure('Send to all users?')){await api('/api/admin/broadcast','POST',{text:t});toast('Broadcast started');$('#bt').value=''}};
}
boot();
