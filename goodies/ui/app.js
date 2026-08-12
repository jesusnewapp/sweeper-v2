const state={records:[],scope:"all"};
const query=document.querySelector("#query"),category=document.querySelector("#category");
const results=document.querySelector("#results"),summary=document.querySelector("#summary");
const escapeHtml=value=>String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
function render(){const needle=query.value.trim().toLocaleLowerCase();const chosen=category.value;
 const rows=state.records.filter(row=>(state.scope==="all"||row.scope===state.scope)&&(!chosen||row.category===chosen)&&(!needle||`${row.title} ${row.category} ${row.searchText}`.toLocaleLowerCase().includes(needle))).slice(0,250);
 summary.textContent=`${rows.length} result${rows.length===1?"":"s"}${rows.length===250?" shown (refine your search)":""}`;
 results.innerHTML=rows.map(row=>`<article class="record"><h2>${escapeHtml(row.title)}</h2><div class="meta"><span class="badge">${escapeHtml(row.scope)}</span><span>${escapeHtml(row.category)}</span><span>${escapeHtml(row.id)}</span></div></article>`).join("")||'<p class="record">No matching records.</p>'}
for(const input of [query,category])input.addEventListener("input",render);
document.querySelectorAll("[data-scope]").forEach(button=>button.addEventListener("click",()=>{state.scope=button.dataset.scope;document.querySelectorAll("[data-scope]").forEach(item=>item.setAttribute("aria-pressed",String(item===button)));render()}));
fetch("index.json").then(response=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json()}).then(data=>{state.records=Array.isArray(data.records)?data.records:[];(data.categories||[]).forEach(value=>category.add(new Option(value,value)));render()}).catch(error=>{summary.textContent=`Index unavailable: ${error.message}`;results.innerHTML='<p class="record">Export index.json and serve this folder through a local or hosted web server.</p>'});
