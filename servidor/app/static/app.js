"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const names = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  const TZ = "Etc/GMT+3";
  const defaults = {interval:60, refresh:15, low:4, high:38, humidity:90, aliases:{}};
  const storage = (kind, operation, key, value) => {
    try { return window[kind][operation](key, value); } catch { return null; }
  };
  let saved = {};
  try { saved = JSON.parse(storage("localStorage", "getItem", "agroweather.preferences") || "{}"); } catch { /* preferences reset */ }
  const prefs = {...defaults, ...saved};
  let alertMemory = {};
  try { alertMemory = JSON.parse(storage("localStorage","getItem","agroweather.alerts") || "{}"); } catch { /* reset invalid history */ }
  if (!alertMemory || typeof alertMemory !== "object" || Array.isArray(alertMemory)) alertMemory = {};
  prefs.aliases = prefs.aliases && typeof prefs.aliases === "object" ? prefs.aliases : {};
  if (![30,60].includes(Number(prefs.interval))) prefs.interval = 60;
  if (![15,30,60].includes(Number(prefs.refresh))) prefs.refresh = 15;
  if (![prefs.low,prefs.high,prefs.humidity].every(Number.isFinite) || prefs.low < -40 || prefs.high > 85 || prefs.low >= prefs.high || prefs.humidity < 1 || prefs.humidity > 100) Object.assign(prefs,{low:4,high:38,humidity:90});
  const localNow = new Date(Date.now() - 10800000);
  const state = {view:"home", station:storage("localStorage","getItem","agroweather.station") || "", stations:[],
    payload:null, mode:"recent", days:1, shift:"todos", year:localNow.getUTCFullYear(),
    months:[localNow.getUTCMonth()+1], season:"summer", date:localNow.toISOString().slice(0,10),
    token:storage("sessionStorage","getItem","agroweather.token") || "", request:0, query:null,
    clock:null, clockAt:0, ageAt:0, timer:null, online:false, loadedAt:0, showDiagnostics:false};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = (v, digits=1) => typeof v === "number" && Number.isFinite(v) ? v.toLocaleString("pt-BR",{minimumFractionDigits:digits,maximumFractionDigits:digits}) : "—";
  const count = n => Number(n || 0).toLocaleString("pt-BR");
  const date = (v, full=true) => v ? new Intl.DateTimeFormat("pt-BR",{timeZone:TZ,day:"2-digit",month:"2-digit",...(full?{year:"numeric"}:{}),hour:"2-digit",minute:"2-digit",...(full?{second:"2-digit"}:{}),hourCycle:"h23"}).format(new Date(v)) : "—";
  const clock = () => state.clock === null ? Date.now() : state.clock + performance.now() - state.clockAt;
  const elapsed = seconds => seconds < 60 ? `${Math.max(0,Math.floor(seconds))} s` : seconds < 3600 ? `${Math.floor(seconds/60)} min` : seconds < 86400 ? `${Math.floor(seconds/3600)} h` : `${Math.floor(seconds/86400)} dias`;
  const diagnostic = id => /^(teste|diagnostico)/i.test(id);
  const visibleStations = () => state.stations.filter(item=>state.showDiagnostics || !diagnostic(item.dispositivo));
  const stationName = id => prefs.aliases[id] || (diagnostic(id) ? `Diagnóstico · ${id}` : `Estação de campo · ${id.slice(-6).toUpperCase()}`);
  const icon = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const pressureInvalid = value => typeof value === "number" && (value < 300 || value > 1100);

  async function api(path, token=state.token) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(path,{headers:token?{Authorization:`Bearer ${token}`}:{},signal:controller.signal,cache:"no-store"});
      if (!response.ok) {
        let message = `Servidor respondeu HTTP ${response.status}.`;
        try { message = (await response.json()).erro || message; } catch { /* non-json error */ }
        const error = new Error(message); error.status = response.status; throw error;
      }
      return response;
    } finally { clearTimeout(timeout); }
  }

  function banner(text, access=false) {
    const node = $("error-banner"); node.replaceChildren(); node.hidden = !text;
    if (!text) return;
    node.append(document.createTextNode(text));
    if (access) { const button = document.createElement("button"); button.textContent="Informar token"; button.addEventListener("click",openAccess); node.append(button); }
  }

  function range() {
    const fixed = (year,month,day=1) => new Date(Date.UTC(year,month,day,3));
    let start, end, months="";
    if (state.mode === "recent") { end=new Date(clock()); start=new Date(end.getTime()-state.days*86400000); }
    else if (state.mode === "day") {
      const [y,m,d]=state.date.split("-").map(Number); start=fixed(y,m-1,d); end=fixed(y,m-1,d+1);
    } else if (state.mode === "months") { start=fixed(state.year,0); end=fixed(state.year+1,0); months=state.months.join(","); }
    else {
      const month={summer:-1,autumn:2,winter:5,spring:8}[state.season];
      start=fixed(state.year,month); end=fixed(state.year,month+3);
    }
    const query=new URLSearchParams({dispositivo:state.station,inicio:start.toISOString(),fim:end.toISOString(),turno:state.shift});
    if(months) query.set("meses",months);
    return query;
  }

  function describePeriod() {
    const shift={todos:"todos os horários",dia:"dia · 06h às 18h",noite:"noite · 18h às 06h"}[state.shift];
    let title;
    if(state.mode==="recent") title=state.days===1?"Últimas 24 horas":`Últimos ${state.days} dias`;
    else if(state.mode==="day") title=`Dia ${state.date.split("-").reverse().join("/")}`;
    else if(state.mode==="months") title=`${[...state.months].sort((a,b)=>a-b).map(m=>names[m-1]).join(", ")} de ${state.year}`;
    else title=({summer:`Verão ${state.year} · dez/${state.year-1} a fev/${state.year}`,autumn:`Outono ${state.year} · mar a mai`,winter:`Inverno ${state.year} · jun a ago`,spring:`Primavera ${state.year} · set a nov`})[state.season];
    $("period-description").textContent=`${title} · ${shift}`;
  }

  function renderPicker() {
    const picker=$("station"); picker.replaceChildren();
    if(!visibleStations().length) { const option=new Option("Aguardando primeira estação…",""); picker.add(option); picker.disabled=true; return; }
    picker.disabled=false;
    for(const item of visibleStations()) picker.add(new Option(stationName(item.dispositivo),item.dispositivo));
    picker.value=state.station;
  }

  function conditions() {
    const last=state.payload?.atual;
    if(!last) return [{level:"neutral",title:"Aguardando medições",text:"Os avisos serão avaliados quando a estação enviar sua primeira leitura.",icon:"chip"}];
    const age=state.payload.idade_segundos+(performance.now()-state.ageAt)/1000;
    const items=[];
    if(age>prefs.interval*3) items.push({level:"warning",title:"Sem leituras recentes",text:`A última leitura foi recebida há ${elapsed(age)}. Intervalo esperado: ${prefs.interval} segundos.`,icon:"chip"});
    if(last.temp_aht<=prefs.low) items.push({level:"warning",title:"Temperatura abaixo do limite",text:`${fmt(last.temp_aht)} °C na última leitura; limite configurado: ${fmt(prefs.low)} °C.`,icon:"temp"});
    if(last.temp_aht>=prefs.high) items.push({level:"warning",title:"Temperatura acima do limite",text:`${fmt(last.temp_aht)} °C na última leitura; limite configurado: ${fmt(prefs.high)} °C.`,icon:"temp"});
    if(last.umidade>=prefs.humidity) items.push({level:"warning",title:"Umidade elevada",text:`Umidade relativa de ${fmt(last.umidade)}%, acima ou igual ao limite de ${fmt(prefs.humidity,0)}%.`,icon:"drop"});
    if(pressureInvalid(last.pressao)) items.push({level:"warning",title:"Verificar leitura do BMP280",text:`Pressão recebida: ${fmt(last.pressao)} hPa. Está fora da faixa de medição de 300–1100 hPa. O valor original foi preservado no histórico.`,icon:"gauge"});
    else if(last.pressao===null) items.push({level:"warning",title:"Pressão indisponível",text:"A última leitura não contém uma medição válida de pressão do BMP280.",icon:"gauge"});
    if(!items.length) items.push({level:"good",title:"Nenhum limite ultrapassado",text:"A última leitura está dentro dos limites de temperatura e umidade configurados no painel.",icon:"cloud"});
    return items;
  }

  function renderLive() {
    const payload=state.payload, last=payload?.atual;
    $("current-temp").textContent=fmt(last?.temp_aht); $("current-humidity").textContent=fmt(last?.umidade);
    $("current-pressure").textContent=fmt(last?.pressao); $("bmp-temp").textContent=last?.temp_bmp===null||!last?"—":`${fmt(last.temp_bmp)} °C`;
    $("dewpoint").textContent=payload?.ponto_orvalho===null||!last?"—":`${fmt(payload.ponto_orvalho)} °C`;
    $("dewpoint").title="Estimativa pela aproximação de Magnus, com temperatura e umidade da última leitura.";
    $("sample-interval").textContent=`${prefs.interval} s`;
    $("sequence").textContent=last?count(last.sequencia):"—";
    $("station-description").textContent=state.station?stationName(state.station):"As condições da sua estação de campo.";
    const quality=$("pressure-quality"); quality.className="small muted";
    quality.textContent=!last||last.pressao===null?"Sem leitura":pressureInvalid(last.pressao)?"Verificar sensor":"Na faixa do sensor";
    if(last&&pressureInvalid(last.pressao)) quality.classList.add("warning-text");
    const age=last?payload.idade_segundos+(performance.now()-state.ageAt)/1000:null;
    const recent=last&&age<=prefs.interval*3;
    $("last-update").textContent=last?`Última leitura: ${date(last.recebido_em)}`:"Aguardando primeira leitura";
    $("next-update").textContent=last?`Recebida há ${elapsed(age)} · painel a cada ${prefs.refresh} s`:`Atualização automática a cada ${prefs.refresh} s`;
    const connection=$("connection"); connection.className=`status ${!state.online?"warning":!last?"neutral":recent?"":"warning"}`;
    connection.innerHTML=`<i></i>${!state.online?"Sem conexão":!last?"Aguardando dados":recent?"Recebendo dados":"Leitura antiga"}`;
    const status=$("station-state"); status.textContent=!last?"Aguardando":recent?"Em dia":"Sem leitura recente"; status.className=recent?"good-text":last?"warning-text":"neutral-text";
    const list=conditions(), warnings=list.filter(x=>x.level==="warning");
    $("alert-number").textContent=last?String(warnings.length):"—";
    $("alert-summary").textContent=!last?"Aguardando medições":warnings.length===0?"Dentro dos limites":warnings.length===1?"Condição identificada":"Condições identificadas";
    $("alert-preview").textContent=list[0].text;
    // A condition is unread once per episode, not once per sensor reading.
    const active=warnings.map(item=>item.title);
    const previous=alertMemory[state.station];
    const seen=Array.isArray(previous?.seen)?previous.seen.filter(key=>active.includes(key)):[];
    if(state.view==="alerts") for(const key of active) if(!seen.includes(key)) seen.push(key);
    const unread=active.filter(key=>!seen.includes(key)).length;
    if(last && state.station){
      const next={active,seen};
      if(JSON.stringify(previous)!==JSON.stringify(next)){
        alertMemory[state.station]=next;
        storage("localStorage","setItem","agroweather.alerts",JSON.stringify(alertMemory));
      }
    }
    $("nav-alert-count").textContent=String(unread); $("nav-alert-count").hidden=!unread;
    $("alerts-list").innerHTML=list.map(item=>`<article class="card condition ${item.level}">${icon(item.icon)}<div><h2>${esc(item.title)}</h2><p>${esc(item.text)}</p>${last?`<small>${item.level==="warning"?"Condição ativa · visualizada neste navegador · ":""}Base: última leitura de ${esc(date(last.recebido_em))}</small>`:""}</div></article>`).join("");
  }

  function renderDevices() {
    $("devices-body").innerHTML=visibleStations().length?visibleStations().map(item=>{
      const age=Math.max(0,(clock()-Date.parse(item.ultima_leitura))/1000), recent=age<=prefs.interval*3;
      return `<tr><td>${esc(stationName(item.dispositivo))}</td><td class="mono">${esc(item.dispositivo)}</td><td>${count(item.total)}</td><td>${esc(date(item.primeira_leitura))}</td><td>${esc(date(item.ultima_leitura))}</td><td><span class="pill ${recent?"":"warning"}">${recent?"Dados recentes":"Leitura antiga"}</span></td><td><button class="button secondary" data-open-station="${esc(item.dispositivo)}">Abrir</button></td></tr>`;
    }).join(""):'<tr><td colspan="7" class="empty-cell">Nenhuma estação de campo enviou dados ainda. Para consultar testes, habilite os dispositivos de diagnóstico.</td></tr>';
  }

  function chart(hostId, specs) {
    const host=$(hostId), rows=state.payload?.serie||[];
    host.replaceChildren();
    if(!rows.length||!specs.some(s=>rows.some(row=>typeof row[s.key]==="number"))) {
      host.innerHTML=`<div class="chart-empty">${icon("cloud")}<span>Sem medições neste período</span><small>Escolha outro período ou aguarde uma nova leitura da estação.</small></div>`; return;
    }
    const width=Math.max(250,host.clientWidth), height=host.clientHeight||280;
    const left=45, right=specs.length>1?37:18, top=14, bottom=35, innerW=width-left-right, innerH=height-top-bottom;
    const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
    svg.setAttribute("viewBox",`0 0 ${width} ${height}`); svg.setAttribute("role","img"); svg.setAttribute("aria-label",host.getAttribute("aria-label"));
    const add=(tag,attrs,text)=>{const el=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;svg.append(el);return el;};
    const times=rows.map(r=>Date.parse(r.recebido_em)); let start=times[0],end=times.at(-1);
    if(start===end){start-=30000;end+=30000;}
    const x=t=>left+(t-start)/(end-start)*innerW;
    specs=specs.map(spec=>{
      const values=rows.map(r=>r[spec.key]).filter(v=>typeof v==="number"&&Number.isFinite(v));
      let min=spec.key==="umidade"?0:values.length?Math.min(...values):0;
      let max=spec.key==="umidade"?100:values.length?Math.max(...values):1;
      if(spec.key!=="umidade"){const padding=Math.max((max-min)*.2,spec.key==="pressao"?1:.3);min-=padding;max+=padding;}
      return {...spec,min,max,y:value=>top+(max-value)/(max-min)*innerH};
    });
    for(let i=0;i<=4;i++){
      const y=top+i*innerH/4; add("line",{x1:left,x2:width-right,y1:y,y2:y,stroke:"#373940","stroke-width":.7,"stroke-dasharray":"3 4"});
      specs.forEach((spec,index)=>{const value=spec.max-i*(spec.max-spec.min)/4;add("text",{x:index?width-right+8:left-9,y:y+3,fill:index?"#78aeca":"#8e94a0","font-size":9,"text-anchor":index?"start":"end"},fmt(value,spec.key==="umidade"?0:1));});
    }
    for(let i=0;i<5;i++){
      const t=start+(end-start)*i/4;
      const label=new Intl.DateTimeFormat("pt-BR",{timeZone:TZ,...(end-start>129600000?{day:"2-digit",month:"2-digit"}:{hour:"2-digit",minute:"2-digit",hourCycle:"h23"})}).format(t);
      add("text",{x:left+i*innerW/4,y:height-10,fill:"#8e94a0","font-size":9,"text-anchor":i===0?"start":i===4?"end":"middle"},label);
    }
    const maxGap=Math.max(prefs.interval*3,(state.payload?.agrupamento_segundos||0)*2)*1000;
    specs.forEach(spec=>{
      let points=[];
      const flush=()=>{if(points.length>1)add("polyline",{points:points.join(" "),fill:"none",stroke:spec.color,"stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"});points=[];};
      rows.forEach((row,index)=>{
        const value=row[spec.key];
        if(value===null||!Number.isFinite(value)){flush();return;}
        if(index>0&&times[index]-times[index-1]>maxGap)flush();
        points.push(`${x(times[index])},${spec.y(value)}`);
        if(rows.length<35)add("circle",{cx:x(times[index]),cy:spec.y(value),r:2.6,fill:spec.color});
      });flush();
    });
    const marker=add("line",{x1:left,x2:left,y1:top,y2:height-bottom,stroke:"#8d939f","stroke-width":1,"stroke-dasharray":"3 4",visibility:"hidden"});
    const overlay=add("rect",{x:left,y:top,width:innerW,height:innerH,fill:"transparent"});
    const tooltip=document.createElement("div");tooltip.className="chart-tooltip";tooltip.hidden=true;
    const pointer=event=>{
      const box=svg.getBoundingClientRect();const target=start+Math.max(0,Math.min(1,((event.clientX-box.left)*width/box.width-left)/innerW))*(end-start);
      let nearest=0;for(let i=1;i<times.length;i++)if(Math.abs(times[i]-target)<Math.abs(times[nearest]-target))nearest=i;
      const row=rows[nearest];marker.setAttribute("x1",x(times[nearest]));marker.setAttribute("x2",x(times[nearest]));marker.setAttribute("visibility","visible");
      tooltip.innerHTML=`<strong>${esc(date(row.recebido_em))}${row.amostras>1?` · média de ${count(row.amostras)} leituras`:""}</strong>`+specs.map(s=>`${esc(s.label)}: ${fmt(row[s.key])} ${esc(s.unit)}`).join("<br>");tooltip.hidden=false;
    };
    overlay.addEventListener("pointermove",pointer);overlay.addEventListener("pointerdown",pointer);
    svg.addEventListener("pointerleave",()=>{tooltip.hidden=true;marker.setAttribute("visibility","hidden");});
    host.append(svg,tooltip);
  }

  function renderCharts() {
    if(state.view!=="home")return;
    chart("climate-chart",[{key:"temp_aht",label:"Temperatura",unit:"°C",color:"#f89b45"},{key:"umidade",label:"Umidade",unit:"%",color:"#4ea8de"}]);
    chart("pressure-chart",[{key:"pressao",label:"Pressão",unit:"hPa",color:"#b3a0e5"}]);
  }

  function renderHistory() {
    const data=state.payload, summary=data?.resumo||{}, rows=data?.registros||[];
    $("period-stats").innerHTML=`<span><b>${count(summary.total)}</b> leituras no período</span><span>Temperatura mín. <b>${fmt(summary.temperatura_min)} °C</b> / máx. <b>${fmt(summary.temperatura_max)} °C</b></span><span>Umidade média <b>${fmt(summary.umidade_media)}%</b></span>`;
    $("chart-summary").textContent=data?.agrupamento_segundos?`Médias por intervalos de ${Math.round(data.agrupamento_segundos/60)} min · ${count(summary.total)} leituras`:`${count(summary.total)} leituras · valores recebidos`;
    $("history-description").textContent=`${Math.min(100,summary.total||0)} últimas leituras do período · CSV inclui todos os registros filtrados`;
    $("history-body").innerHTML=rows.length?rows.map(row=>`<tr><td>${esc(date(row.recebido_em))}</td><td class="orange">${fmt(row.temp_aht,2)} °C</td><td class="blue">${fmt(row.umidade,2)}%</td><td class="${pressureInvalid(row.pressao)?"warning-text":""}">${fmt(row.pressao,2)}${row.pressao===null?"":" hPa"}${pressureInvalid(row.pressao)?" ⚠":""}</td><td>${fmt(row.temp_bmp,2)}${row.temp_bmp===null?"":" °C"}</td><td class="mono">${count(row.sequencia)}</td></tr>`).join(""):'<tr><td colspan="6" class="empty-cell">Nenhuma medição neste período. Experimente outro filtro.</td></tr>';
    $("export").disabled=!summary.total;
  }

  async function refresh() {
    const request=++state.request;
    $("refresh").classList.add("loading");$("export").disabled=true;
    try {
      const list=await (await api("/api/estacoes")).json();if(request!==state.request)return;
      state.clock=Date.parse(list.servidor_em);state.clockAt=performance.now();state.stations=list.estacoes;
      if(!visibleStations().some(item=>item.dispositivo===state.station)) state.station=visibleStations()[0]?.dispositivo||"";
      renderPicker();
      let payload=null;
      if(state.station){const query=range().toString();payload=await(await api(`/api/painel?${query}`)).json();if(request!==state.request)return;state.query=query;storage("localStorage","setItem","agroweather.station",state.station);}
      state.payload=payload;state.ageAt=performance.now();state.online=true;state.loadedAt=performance.now();
      if(payload){state.clock=Date.parse(payload.servidor_em);state.clockAt=performance.now();}
      banner("");describePeriod();renderLive();renderDevices();renderHistory();renderCharts();
    }catch(error){
      if(request!==state.request)return;
      state.online=false;
      banner(error.status===401?"O servidor exige um token válido para consultar o histórico.":`Não foi possível atualizar os dados. ${error.name==="AbortError"?"Tempo de resposta esgotado.":error.message}`,error.status===401);
      renderLive();
    }finally{if(request===state.request)$("refresh").classList.remove("loading");}
  }

  function fillSettings() {
    $("setting-name").value=state.station?stationName(state.station):"";
    $("setting-interval").value=String(prefs.interval);$("setting-refresh").value=String(prefs.refresh);
    $("setting-low").value=prefs.low;$("setting-high").value=prefs.high;$("setting-humidity").value=prefs.humidity;
    $("settings-feedback").textContent="";
  }
  function navigate(view) {
    if(!["home","devices","alerts","settings"].includes(view))view="home";
    state.view=view;
    for(const name of ["home","devices","alerts","settings"])$("view-"+name).hidden=name!==view;
    document.querySelectorAll(".nav-btn").forEach(button=>{const active=button.dataset.view===view;button.classList.toggle("active",active);if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current");});
    if(view==="settings")fillSettings();
    renderLive();
    if(view==="home")renderCharts();
  }
  function selectStation(id) {state.station=id;refresh();if(state.view==="settings")fillSettings();}
  function setMode() {
    state.mode=$("view-mode").value;
    $("recent-panel").hidden=state.mode!=="recent";$("day-panel").hidden=state.mode!=="day";
    $("year-panel").hidden=!["months","seasons"].includes(state.mode);
    $("months-panel").hidden=state.mode!=="months";$("seasons-panel").hidden=state.mode!=="seasons";
    describePeriod();refresh();
  }
  function restartTimer(){clearInterval(state.timer);state.timer=setInterval(refresh,prefs.refresh*1000);}
  function openAccess() {$("access-token").value=state.token;$("access-feedback").textContent="";$("access-dialog").showModal();$("access-token").focus();}

  document.addEventListener("click",event=>{
    const nav=event.target.closest("[data-view]");if(nav){location.hash=nav.dataset.view;navigate(nav.dataset.view);}
    const open=event.target.closest("[data-open-station]");if(open){selectStation(open.dataset.openStation);location.hash="home";navigate("home");}
    const recent=event.target.closest("[data-days]");if(recent){state.days=Number(recent.dataset.days);document.querySelectorAll("[data-days]").forEach(b=>b.classList.toggle("active",b===recent));refresh();}
    const shift=event.target.closest("[data-shift]");if(shift){state.shift=shift.dataset.shift;document.querySelectorAll("[data-shift]").forEach(b=>b.classList.toggle("active",b===shift));refresh();}
    const season=event.target.closest("[data-season]");if(season){state.season=season.dataset.season;document.querySelectorAll("[data-season]").forEach(b=>b.classList.toggle("active",b===season));refresh();}
  });
  $("station").addEventListener("change",event=>selectStation(event.target.value));
  $("show-diagnostics").addEventListener("change",event=>{state.showDiagnostics=event.target.checked;refresh();});
  $("view-mode").addEventListener("change",setMode);
  $("specific-date").value=state.date;$("specific-date").addEventListener("change",event=>{if(event.target.value){state.date=event.target.value;refresh();}});
  $("filter-year").value=state.year;$("filter-year").addEventListener("change",event=>{if(event.target.checkValidity()){state.year=Number(event.target.value);refresh();}else event.target.reportValidity();});
  names.forEach((name,index)=>{const button=document.createElement("button");button.type="button";button.textContent=name;button.classList.toggle("active",state.months.includes(index+1));button.setAttribute("aria-pressed",String(state.months.includes(index+1)));button.addEventListener("click",()=>{const m=index+1;if(state.months.includes(m)){if(state.months.length===1)return;state.months=state.months.filter(x=>x!==m);}else state.months.push(m);button.classList.toggle("active",state.months.includes(m));button.setAttribute("aria-pressed",String(state.months.includes(m)));refresh();});$("months-panel").append(button);});
  $("refresh").addEventListener("click",refresh);
  $("settings-form").addEventListener("submit",event=>{
    event.preventDefault();const low=Number($("setting-low").value),high=Number($("setting-high").value);
    if(low>=high){$("settings-feedback").textContent="O limite baixo precisa ser menor que o limite alto.";return;}
    Object.assign(prefs,{low,high,humidity:Number($("setting-humidity").value),interval:Number($("setting-interval").value),refresh:Number($("setting-refresh").value)});
    if(state.station)prefs.aliases[state.station]=$("setting-name").value.trim().slice(0,60)||`Estação · ${state.station.slice(-6)}`;
    storage("localStorage","setItem","agroweather.preferences",JSON.stringify(prefs));
    $("settings-feedback").textContent="Preferências salvas neste navegador.";restartTimer();renderPicker();renderDevices();renderLive();
  });
  $("access-button").addEventListener("click",openAccess);$("access-cancel").addEventListener("click",()=>$("access-dialog").close());
  $("access-form").addEventListener("submit",async event=>{
    event.preventDefault();const candidate=$("access-token").value.trim();
    try{await api("/api/estacoes",candidate);state.token=candidate;storage("sessionStorage","setItem","agroweather.token",candidate);$("access-dialog").close();refresh();}
    catch(error){$("access-feedback").textContent=error.message;}
  });
  $("export").addEventListener("click",async()=>{
    if(!state.query)return;$("export").disabled=true;
    try{const blob=await(await api(`/api/exportar.csv?${state.query}`)).blob();const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`agroweather-${state.station}-${new Date(clock()).toISOString().slice(0,10)}.csv`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
    catch(error){banner(`Não foi possível exportar. ${error.message}`,error.status===401);}
    finally{$("export").disabled=!state.payload?.resumo.total;}
  });
  window.addEventListener("hashchange",()=>navigate(location.hash.slice(1)));
  let resizeTimer;window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(renderCharts,120);});
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  setInterval(()=>{renderLive();if(state.view==="devices")renderDevices();},1000);
  navigate(location.hash.slice(1)||"home");describePeriod();renderLive();renderDevices();renderHistory();renderCharts();refresh();restartTimer();
})();
