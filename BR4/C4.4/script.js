const PROJECTS_API = "http://localhost:8108/projects";
const DIALOG_API = "http://localhost:8111/api/dialog";
const MESSAGES_API = (id) => `http://localhost:8108/projects/${id}/messages?limit=50`;

let currentProjectId = null;
const projectSelect = document.getElementById("projectSelect");
const newProjectBtn = document.getElementById("newProjectBtn");
const chatDiv = document.getElementById("chat");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const statusDiv = document.getElementById("status");

function showError(msg) { statusDiv.innerHTML = `<span class="error">❌ ${msg}</span>`; setTimeout(() => { if(statusDiv.innerHTML.includes(msg)) statusDiv.innerHTML = "Готов"; }, 5000); }
function updateUI() { if(currentProjectId) { messageInput.disabled=false; sendBtn.disabled=false; statusDiv.innerHTML = `Проект: ${projectSelect.options[projectSelect.selectedIndex]?.text || currentProjectId}`; } else { messageInput.disabled=true; sendBtn.disabled=true; statusDiv.innerHTML = "Выберите проект"; } }

async function loadProjects() {
    try { const resp = await fetch(PROJECTS_API); if(!resp.ok) throw new Error(`HTTP ${resp.status}`); const projects = await resp.json();
        projectSelect.innerHTML = "";
        if(projects.length===0){ const opt = document.createElement("option"); opt.textContent="Нет проектов, создайте первый"; opt.disabled=true; projectSelect.appendChild(opt); currentProjectId=null; chatDiv.innerHTML='<div class="loading">Нет проектов. Нажмите «Новый».</div>'; updateUI(); return; }
        for(const p of projects){ const opt = document.createElement("option"); opt.value=p.id; opt.textContent=`${p.name} (${p.id.slice(0,8)})`; projectSelect.appendChild(opt); }
        if(currentProjectId && projects.some(p=>p.id===currentProjectId)) projectSelect.value=currentProjectId; else { currentProjectId=projects[0].id; projectSelect.value=currentProjectId; }
        await loadMessages(); updateUI();
    } catch(err){ console.error(err); chatDiv.innerHTML='<div class="loading error">Ошибка загрузки проектов.</div>'; showError("Не удалось загрузить проекты"); }
}

async function loadMessages() { if(!currentProjectId) return; chatDiv.innerHTML='<div class="loading">Загрузка истории...</div>'; try{ const resp = await fetch(MESSAGES_API(currentProjectId)); if(!resp.ok) throw new Error(`HTTP ${resp.status}`); const messages = await resp.json(); renderMessages(messages); } catch(err){ console.error(err); chatDiv.innerHTML='<div class="loading error">Ошибка загрузки истории</div>'; showError("Не удалось загрузить историю"); } }
function renderMessages(messages){ if(!messages.length){ chatDiv.innerHTML='<div class="loading">История пуста. Напишите первое сообщение.</div>'; return; } chatDiv.innerHTML=""; const reversed = [...messages].reverse(); for(const msg of reversed){ const div = document.createElement("div"); div.className=`message ${msg.role}`; div.textContent=msg.content; chatDiv.prepend(div); } chatDiv.scrollTop=0; }
function addMessageToChat(role, content){ const div = document.createElement("div"); div.className=`message ${role}`; div.textContent=content; chatDiv.prepend(div); chatDiv.scrollTop=0; }

async function sendMessage(){ const text = messageInput.value.trim(); if(!text) return; if(!currentProjectId){ showError("Сначала выберите проект"); return; } sendBtn.disabled=true; messageInput.disabled=true; const originalText=text; messageInput.value=""; addMessageToChat("user", originalText); try{ const resp = await fetch(DIALOG_API, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ project_id: currentProjectId, message: originalText }) }); const data = await resp.json(); if(!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`); addMessageToChat("assistant", data.reply); await loadMessages(); } catch(err){ console.error(err); addMessageToChat("assistant", `❌ Ошибка: ${err.message}`); showError(err.message); } finally{ sendBtn.disabled=false; messageInput.disabled=false; messageInput.focus(); } }

async function createNewProject(){ const name = prompt("Введите название нового проекта:"); if(!name) return; try{ const resp = await fetch(PROJECTS_API, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ name, description:"Создан через консоль" }) }); if(!resp.ok) throw new Error(await resp.text()); const project = await resp.json(); await loadProjects(); projectSelect.value=project.id; currentProjectId=project.id; await loadMessages(); updateUI(); statusDiv.innerHTML=`Создан проект ${project.name}`; } catch(err){ console.error(err); showError("Не удалось создать проект: "+err.message); } }

projectSelect.addEventListener("change", async()=>{ currentProjectId=projectSelect.value; await loadMessages(); updateUI(); });
newProjectBtn.addEventListener("click", createNewProject);
sendBtn.addEventListener("click", sendMessage);
messageInput.addEventListener("keypress", (e)=>{ if(e.key==="Enter") sendMessage(); });
loadProjects().then(()=>{ if(projectSelect.options.length>0 && !currentProjectId){ currentProjectId=projectSelect.value; loadMessages(); updateUI(); } });