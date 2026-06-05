
let PAGE = 'dashboard';
let allData = {};
let selectedModel = null;  // For model detail view
const $ = id => document.getElementById(id);

function toast(msg, color='#34d399') {
  const t = $('toast');
  t.textContent = msg; t.style.color = color;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function switchPage(p) {
  PAGE = p; selectedModel = null;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const nav = document.querySelector(`.nav-item[data-page="${p}"]`);
  if(nav) nav.classList.add('active');
  document.querySelectorAll('.page').forEach(pg => pg.classList.remove('active'));
  const pg = $(`page-${p}`);
  if(pg) pg.classList.add('active');
  loadPage(p);
}

function closeModal(id) { $(id).style.display = 'none'; }

async function fetchAPI(path, timeoutMs=5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(path, {signal: controller.signal});
    clearTimeout(timer);
    return await r.json();
  } catch(e) {
    clearTimeout(timer);
    return {};
  }
}
async function postAPI(path, data, timeoutMs=8000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data), signal: controller.signal});
    clearTimeout(timer);
    return await r.json();
  } catch(e) {
    clearTimeout(timer);
    return {};
  }
}

async function load() { loadPage(PAGE); }
async function loadPage(page) {
  const [analytics, models, accounts, revenue, captions, gallery, pipeline, hub, dashboard, loras, batches, library, settings, dataset, vault, social, datasets] = await Promise.all([
    fetchAPI('/api/analytics'),
    fetchAPI('/api/models'),
    fetchAPI('/api/accounts'),
    fetchAPI('/api/revenue'),
    fetchAPI('/api/captions'),
    fetchAPI('/api/gallery'),
    fetchAPI('/api/pipeline'),
    fetchAPI('/api/hub'),
    fetchAPI('/api/dashboard'),
    fetchAPI('/api/lora/versions'),
    fetchAPI('/api/content/batches'),
    fetchAPI('/api/content/library'),
    fetchAPI('/api/settings'),
    fetchAPI('/api/dataset/images'),
    fetchAPI('/api/accounts/vault'),
    fetchAPI('/api/accounts/social'),
    fetchAPI('/api/dataset/list'),
  ]);
  allData = { analytics, models, accounts, revenue, captions, gallery, pipeline, hub, dashboard, loras, batches, library, settings, dataset, vault, social, datasets };
  if(page==='dashboard') renderDashboard();
  else if(page==='models') renderModels();
  else if(page==='pipeline') renderPipeline();
  else if(page==='content') renderContentLib();
  else if(page==='dataset') renderDataset();
  else if(page==='textgen') renderTextGen();
  else if(page==='lora') renderLora();
  else if(page==='revenue') renderRevenue();
  else if(page==='accounts') renderAccounts();
  else if(page==='settings') renderSettings();
}

// ══════════════════ DASHBOARD ══════════════════
function renderDashboard() {
  const d = allData.dashboard || {};
  const a = allData.analytics || {};
  const s = a.summary || {};
  $('dashStats').innerHTML = `
    <div class="card stat"><div class="stat-val">$${d.total_revenue||0}</div><div class="stat-label">Total revenue</div><div class="stat-sub">$${d.month_revenue||0} this month</div></div>
    <div class="card stat"><div class="stat-val">${d.total_subs||0}</div><div class="stat-label">Subscribers</div></div>
    <div class="card stat"><div class="stat-val">${d.total_fans||0}</div><div class="stat-label">Total fans</div></div>
    <div class="card stat"><div class="stat-val">${d.pending_validation||0}</div><div class="stat-label">Pending validation</div><div class="stat-sub">${d.validated_count||0} validated</div></div>`;

  $('dashPendingBadge').textContent = d.pending_validation||0;
  if((d.pending_validation||0) > 0) {
    $('dashPendingAlert').innerHTML = `<div class="alert-box alert-warning">⚠ ${d.pending_validation} images need validation — <a href="#" onclick="switchPage('pipeline');return false" style="color:#a855f7">Go to Pipeline →</a></div>`;
  } else {
    $('dashPendingAlert').innerHTML = '<div class="alert-box alert-info">✓ All images validated</div>';
  }

  const revByModel = d.revenue_by_model || {};
  const modelNames = Object.keys(revByModel);
  const maxRev = Math.max(...Object.values(revByModel), 1);
  $('dashRevByModel').innerHTML = modelNames.length === 0
    ? '<div style="font-size:12px;color:#6b6b80;padding:10px">No revenue data</div>'
    : modelNames.map(m => {
        const amt = revByModel[m] || 0;
        const pct = (amt / maxRev * 100);
        return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px">
          <span style="width:60px;color:#d4d4d8">${m}</span>
          <div class="bar" style="flex:1;height:6px"><div class="bar-fill" style="width:${pct}%;height:6px"></div></div>
          <span style="color:#34d399;width:50px;text-align:right">$${amt}</span>
        </div>`;
      }).join('');

  const sync = d.account_sync || {};
  $('dashSyncStatus').textContent = sync.status || 'idle';
  $('dashSyncInfo').innerHTML = `
    <div style="font-size:12px;color:#a1a1aa">
      <div>Last sync: ${sync.last_sync||'N/A'}</div>
      <div>Next: ${sync.next_sync||'auto 2h'}</div>
    </div>`;

  $('dashActions').innerHTML = `
    <div style="display:flex;flex-wrap:wrap;gap:6px">
      <button class="btn btn-sm btn-ghost" onclick="switchPage('models')">+ New Model</button>
      <button class="btn btn-sm btn-ghost" onclick="showGenModal()">+ Generate</button>
      <button class="btn btn-sm btn-ghost" onclick="switchPage('revenue')">+ Revenue</button>
      <button class="btn btn-sm btn-ghost" onclick="switchPage('content')">View Library</button>
    </div>`;

  const prios = a.priorities || [];
  $('dashPriorities').innerHTML = prios.length === 0
    ? '<div style="padding:16px;color:#6b6b80;font-size:12px;text-align:center">All good! Nothing urgent.</div>'
    : prios.map(p => `<div class="prio-item ${p.priority}">
      <div><div style="font-size:13px;font-weight:500;color:#d4d4d8">${p.action} — ${p.model}</div>
      <div style="font-size:11px;color:#6b6b80;margin-top:2px">${p.detail}</div></div>
      <span class="pill ${p.priority==='high'?'pill-red':p.priority==='medium'?'pill-yellow':'pill-gray'}">${p.priority}</span>
    </div>`).join('');
}

// ══════════════════ MODELS ══════════════════
function renderModels() {
  if(selectedModel) { renderModelDetail(selectedModel); return; }
  const models = allData.models || [];
  $('modelsGrid').innerHTML = models.map(m => {
    const initials = (m.name||'?').slice(0,2).toUpperCase();
    return `<div class="model-card" onclick="selectModel('${m.name}')">
          <button class="mc-del" onclick="event.stopPropagation();deleteModel('${m.name}')">×</button>
          <div class="avatar">${initials}</div>
          <div class="mc-name">${m.name}</div>
      <div class="mc-bio">${m.age||''} · ${m.ethnicity||''} · ${m.location||''}</div>
      <div class="mc-stat">
              <span>💰 $${m.revenue||0}</span>
              <span>👥 ${m.fans||0} fans</span>
              <span>🖼 ${m.images||0}</span>
            </div>
            <div class="mc-tags">
              ${(m.platforms||[]).map(p => `<span class="tag">${p}</span>`).join('')}
              <span class="tag ${(m.lora_count||0) > 0 ? 'tag-green' : 'tag-yellow'}">${m.lora_count||0} LoRAs</span>
            </div>
          </div>`;
  }).join('');
  $('addModelForm').style.display = 'none';
}

function selectModel(name) {
  selectedModel = name;
  renderModelDetail(name);
}

function backToModels() { selectedModel = null; renderModels(); }

async function deleteModel(name) {
  if(!confirm(`Delete model "${name}" and all its data?`)) return;
  await postAPI('/api/models/delete', {name});
  toast(`Deleted ${name}`);
  selectedModel = null;
  load();
}

async function uploadPFP(name) {
  const input = document.getElementById('pfpInput');
  if(!input.files || !input.files[0]) return;
  const formData = new FormData();
  formData.append('file', input.files[0]);
  try {
    const r = await fetch(`/api/models/${name}/pfp`, {method:'POST', body: formData});
    const data = await r.json();
    if(data.ok) {
      const img = document.getElementById('pfpImg');
      const init = document.getElementById('pfpInitial');
      if(img && init) { img.src = data.path; img.style.display = 'block'; init.style.display = 'none'; }
      toast('Photo uploaded');
    }
  } catch(e) { toast('Upload failed','#f87171'); }
  input.value = '';
}

function renderModelDetail(name) {
  const models = allData.models || [];
  const m = models.find(x => x.name === name) || {};
  const loras = (allData.loras || []).filter(l => l.model_id === name);
  const sfwLoras = loras.filter(l => l.type === 'SFW');
  const nsfwLoras = loras.filter(l => l.type === 'NSFW');
  const batches = (allData.batches || []).filter(b => b.model === name).slice(0,5);

  $('modelsGrid').innerHTML = '';
  $('addModelForm').style.display = 'none';

  // Populate generate modal model dropdown
  const gmModel = $('gmModel');
  if(gmModel) gmModel.innerHTML = models.map(x => `<option ${x.name===name?'selected':''}>${x.name}</option>`).join('');
  updateGmLoras(name);

  $('modelDetail').style.display = 'block';
  $('modelDetail').innerHTML = `
    <div class="card">
      <div style="display:flex;gap:14px;align-items:start;flex-wrap:wrap">
        <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#a855f7,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:22px;color:#fff;font-weight:600;flex-shrink:0;cursor:pointer;overflow:hidden;position:relative" onclick="document.getElementById('pfpInput').click()" title="Click to upload photo">
          <span id="pfpInitial">${(name||'?').slice(0,2).toUpperCase()}</span>
          <img id="pfpImg" style="display:none;width:100%;height:100%;object-fit:cover">
          <input type="file" id="pfpInput" accept="image/*" style="display:none" onchange="uploadPFP('${name}')">
        </div>
        <div style="flex:1;min-width:200px">
          <div style="font-size:17px;font-weight:600;color:#fff">${m.name||name}</div>
          <div style="font-size:11px;color:#6b6b80">${m.age||''} · ${m.ethnicity||''} · ${m.location||''}</div>
          <div style="font-size:11px;color:#a1a1aa;margin-top:4px">${m.persona||''}${m.kinks ? ' · Kinks: '+m.kinks : ''}</div>
          <div style="margin-top:8px;display:flex;gap:12px;font-size:12px;flex-wrap:wrap">
            <span style="color:#34d399">$${m.revenue||0}/mo</span>
            <span style="color:#a1a1aa">${m.fans||0} fans</span>
            <span style="color:#a1a1aa">${m.images||0} images</span>
            <span style="color:#a1a1aa">${m.followers||0} followers</span>
          </div>
          <div style="margin-top:8px;display:flex;gap:4px;flex-wrap:wrap">
            <span class="tag ${(m.style||'').includes('NSFW')?'tag-red':'tag-green'}">${m.style||'SFW'}</span>
            <span class="tag tag-purple">${m.nsfw_level||'none'}</span>
            ${(m.platforms||[]).map(p => `<span class="tag">${p}</span>`).join('')}
          </div>
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-primary btn-sm" onclick="showGenModal('${name}')">Generate</button>
          <button class="btn btn-ghost btn-sm" onclick="backToModels()">← Back</button>
          <button class="btn btn-ghost btn-sm" style="color:#f87171;border-color:rgba(239,68,68,.3)" onclick="deleteModel('${name}')">× Delete</button>
        </div>
      </div>
    </div>

    <!-- SFW LoRAs -->
    <div class="card">
      <div class="card-title"><span>SFW LoRAs</span><button class="btn btn-xs btn-ghost" onclick="showTrainLora('${name}','SFW')">+ Train</button></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${sfwLoras.length === 0 ? '<div style="font-size:12px;color:#6b6b80;padding:8px 0">No SFW LoRAs trained</div>' :
          sfwLoras.map(l => `<div class="lora-card">
            <div class="lora-version">v${l.version} SFW</div>
            <div class="lora-meta">${l.images_trained||0} images · Loss: ${l.loss||'?'}</div>
            <div class="lora-meta">Trigger: ${l.trigger_word||'—'}</div>
            <div style="margin-top:6px;display:flex;gap:4px">
              <button class="btn btn-xs btn-ghost" onclick="toast('Test gen in Pipeline')">Test</button>
              <button class="btn btn-xs btn-ghost" onclick="toast('Edit LoRA')">Edit</button>
            </div>
          </div>`).join('')}
      </div>
    </div>

    <!-- NSFW LoRAs -->
    <div class="card">
      <div class="card-title"><span>NSFW LoRAs</span><button class="btn btn-xs btn-ghost" onclick="showTrainLora('${name}','NSFW')">+ Train</button></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${nsfwLoras.length === 0 ? '<div style="font-size:12px;color:#6b6b80;padding:8px 0">No NSFW LoRAs trained</div>' :
          nsfwLoras.map(l => `<div class="lora-card">
            <div class="lora-version">v${l.version} NSFW</div>
            <div class="lora-meta">${l.images_trained||0} images · Loss: ${l.loss||'?'}</div>
            <div class="lora-meta">Trigger: ${l.trigger_word||'—'}</div>
            <div style="margin-top:6px;display:flex;gap:4px">
              <button class="btn btn-xs btn-ghost" onclick="toast('Test gen in Pipeline')">Test</button>
              <button class="btn btn-xs btn-ghost" onclick="toast('Edit LoRA')">Edit</button>
            </div>
          </div>`).join('')}
      </div>
    </div>

    <!-- Generate section -->
    <div class="card">
      <div class="card-title">Generate content</div>
      <div class="f-row" style="margin-bottom:8px">
        <div class="f-group"><label>LoRA</label><select class="f-control f-control-sm" id="mdLora"><option value="">Select...</option>${loras.map(l => `<option value="${l.id}">v${l.version} ${l.type} - ${l.trigger_word||''}</option>`).join('')}</select></div>
        <div class="f-group"><label>NSFW level</label><select class="f-control f-control-sm" id="mdNsfw"><option>SFW</option><option>Mild</option><option>Explicit</option></select></div>
        <div class="f-group"><label>Count</label><select class="f-control f-control-sm" id="mdCount"><option>4</option><option>8</option><option>12</option></select></div>
      </div>
      <div class="f-group" style="margin-bottom:8px"><label>Prompt</label><input class="f-control f-control-sm" id="mdPrompt" placeholder="Describe the image..." style="width:100%"></div>
      <button class="btn btn-primary btn-sm" onclick="quickGenerate('${name}')">Generate 4 Images</button>
    </div>

    <!-- Recent batches -->
    <div class="card">
      <div class="card-title">Recent batches</div>
      ${batches.length === 0 ? '<div style="font-size:12px;color:#6b6b80;padding:8px">No recent generations</div>' :
        batches.map(b => `<div style="padding:8px 0;border-bottom:1px solid #0f0f1a;font-size:12px;display:flex;justify-content:space-between;align-items:center">
          <div><span style="color:#d4d4d8">${b.lora_id||b.prompt||'Batch'}</span><span style="color:#6b6b80;margin-left:6px">${b.prompt ? b.prompt.slice(0,40) : ''}</span></div>
          <div style="display:flex;align-items:center;gap:8px">
            <div class="bar bar-green" style="width:80px;height:4px;display:inline-block;vertical-align:middle">
              <div class="bar-fill" style="width:${b.pending_count === 0 ? 100 : ((b.validated_count||0)/Math.max((b.pending_count||0)+(b.validated_count||0),1)*100)}%"></div>
            </div>
            <span class="pill ${b.status==='completed'?'pill-green':'pill-yellow'}">${b.status||'pending'}</span>
          </div>
        </div>`).join('')}
    </div>

    <!-- LoRA training history -->
    <div class="card">
      <div class="card-title">LoRA training history</div>
      <div class="table-wrap">
        <table>
          <tr><th>Version</th><th>Type</th><th>Images</th><th>Loss</th><th>Source</th><th>Date</th><th></th></tr>
          ${loras.length === 0 ? '<tr><td colspan="7" style="color:#6b6b80;text-align:center;padding:16px">No training history</td></tr>' :
            loras.map(l => `<tr>
              <td style="font-weight:500">v${l.version}</td>
              <td><span class="tag ${l.type==='NSFW'?'tag-red':'tag-green'}">${l.type}</span></td>
              <td>${l.images_trained||0}</td>
              <td>${l.loss||'—'}</td>
              <td>${l.source||'uploaded'}</td>
              <td>${(l.trained_at||'').slice(0,10)}</td>
              <td><button class="btn btn-xs btn-ghost" onclick="deleteLora('${l.id}')">×</button></td>
            </tr>`).join('')}
        </table>
      </div>
    </div>`;
}

function updateGmLoras(modelName) {
  const loras = (allData.loras || []).filter(l => l.model_id === modelName);
  const sel = $('gmLora');
  if(sel) sel.innerHTML = '<option value="">Select LoRA</option>' +
    loras.map(l => `<option value="${l.id}">v${l.version} ${l.type} — ${l.trigger_word||'no trigger'}</option>`).join('');
}

async function quickGenerate(model) {
  const loraId = $(`mdLora`).value;
  const nsfw = $(`mdNsfw`).value;
  const count = parseInt($(`mdCount`).value) || 4;
  const prompt = $(`mdPrompt`).value;
  if(!prompt) return toast('Enter a prompt','#f87171');
  const r = await postAPI('/api/content/batches/create', {
    model, lora_id: loraId, prompt, nsfw_level: nsfw.toLowerCase(), count,
    steps: 30, cfg: 7.0, seed: -1
  });
  if(r.ok) toast(`Batch created: ${count} images in Pipeline`);
  load();
}

function showAddModel() { $('addModelForm').style.display = 'block'; }
function hideAddModel() { $('addModelForm').style.display = 'none'; }

async function saveNewModel() {
  const name = $('nm_name').value.trim();
  if(!name) return toast('Enter a name','#f87171');
  await postAPI('/api/models/update', {
    name, age:$('nm_age').value, ethnicity:$('nm_eth').value,
    location:$('nm_loc').value,
    persona:$('nm_pers').value,
    platforms:$('nm_plat').value.split(',').map(s=>s.trim())
  });
  $('addModelForm').style.display = 'none';
  toast('Model added');
  load();
}

// ══════════════════ PIPELINE ══════════════════
function renderPipeline() {
  const batches = allData.batches || [];
  const models = allData.models || [];
  const mf = $('pipeModelFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option value="${m.name}">${m.name}</option>`).join('');
  const filter = mf ? mf.value : 'all';
  const filtered = filter === 'all' ? batches : batches.filter(b => b.model === filter);

  $('batchList').innerHTML = filtered.length === 0
    ? '<div class="card" style="text-align:center;padding:30px;color:#6b6b80;font-size:13px">No batches yet. Generate from Models →</div>'
    : filtered.map((b, bi) => {
        const total = (b.images||[]).length || b.count || 0;
        const approved = b.images ? b.images.filter(i => i.human_status==='approved').length : b.validated_count||0;
        const rejected = b.images ? b.images.filter(i => i.human_status==='rejected').length : 0;
        const pending = total - approved - rejected;
        const pct = total > 0 ? ((approved+rejected)/total*100) : 0;
        const batchIndex = allData.batches.indexOf(b);

        return `<div class="card">
          <div class="card-title"><span>${b.model||'Model'} — ${b.lora_id||'No LoRA'} — ${(b.created_at||'').slice(0,16)||'just now'}</span>
            <span class="pill ${b.status==='completed'?'pill-green':'pill-yellow'}">${pending} pending</span>
          </div>
          <div style="margin-bottom:8px;font-size:11px;color:#6b6b80">Prompt: ${b.prompt||'—'}</div>
          <div class="bar bar-${pending>0?'yellow':'green'}" style="margin-bottom:8px">
            <div class="bar-fill" style="width:${pct}%"></div>
          </div>
          <div style="font-size:11px;color:#6b6b80;margin-bottom:8px">${approved} approved · ${rejected} rejected · ${pending} pending</div>
          ${b.images && pending > 0 ? `<div class="grid-4">
            ${b.images.filter(i => i.human_status === null).slice(0,8).map((img, ii) => `
              <div class="img-thumb">
                <div class="score" style="color:${img.auto_score>=70?'#34d399':'#fbbf24'}">${img.auto_score}</div>
                <div style="font-size:9px;color:#6b6b80">${(img.flags||[]).join(', ')}</div>
                ${(img.flags||[]).length > 0 ? `<span class="badge tag tag-yellow">⚠ flagged</span>` : ''}
                <div class="img-actions">
                  <button class="btn btn-xs btn-green" onclick="validateImg(${batchIndex},'${img.id}','approved')">✓</button>
                  <button class="btn btn-xs btn-red" onclick="validateImg(${batchIndex},'${img.id}','rejected')">✗</button>
                </div>
              </div>
            `).join('')}
          </div>
          <div style="margin-top:8px;display:flex;gap:6px">
            <button class="btn btn-sm btn-primary" onclick="validateAll(${batchIndex},'approved')">✓ Validate All</button>
            <button class="btn btn-sm btn-ghost" onclick="validateAll(${batchIndex},'rejected')">✗ Reject All</button>
          </div>` : (b.status==='completed' ? `<div class="alert-box alert-info">✓ Batch completed — ${approved} approved</div>` : '')}
        </div>`;
      }).join('');
}

async function validateImg(batchIdx, imgId, status) {
  const batches = allData.batches;
  if(batchIdx < 0 || batchIdx >= batches.length) return;
  const batch = batches[batchIdx];
  await postAPI(`/api/content/batch/${batch.id}/validate`, {image_id: imgId, status});
  toast(`Image ${status}`);
  load();
}

async function validateAll(batchIdx, status) {
  const batches = allData.batches;
  if(batchIdx < 0 || batchIdx >= batches.length) return;
  const batch = batches[batchIdx];
  await postAPI(`/api/content/batch/${batch.id}/validate_all`, {status});
  toast(`All marked as ${status}`);
  load();
}

// ══════════════════ CONTENT LIBRARY ══════════════════
function renderContentLib() {
  const library = allData.library || [];
  const models = allData.models || [];
  const mf = $('clModelFilter'), sf = $('clStatusFilter'), nf = $('clNsfwFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  let filtered = library;
  if(mf && mf.value !== 'all') filtered = filtered.filter(c => c.model === mf.value);
  if(sf && sf.value !== 'all') filtered = filtered.filter(c => c.status === sf.value);
  if(nf && nf.value !== 'all') filtered = filtered.filter(c => (c.nsfw_level||'').toLowerCase() === nf.value.toLowerCase());

  $('contentGrid').innerHTML = filtered.length === 0
    ? '<div class="card" style="text-align:center;padding:30px;color:#6b6b80;font-size:13px">Library empty. Validate images in Pipeline →</div>'
    : `<div class="grid-4">${filtered.slice(0,40).map(c => `
      <div class="img-thumb" onclick="showContentDetail('${c.id||c.batch_id}')" style="cursor:pointer">
        <div style="font-size:24px;font-weight:300;color:#a855f7;margin-bottom:4px">🖼</div>
        <div style="font-size:11px;color:#d4d4d8">${c.model||'?'}</div>
        <span class="tag ${c.nsfw_level==='explicit'?'tag-red':c.nsfw_level==='mild'?'tag-yellow':'tag-green'}">${c.nsfw_level||'sfw'}</span>
        <span class="tag ${c.status==='posted'?'tag-green':c.status==='approved'?'tag-purple':'tag-yellow'}">${c.status||'draft'}</span>
        <div style="font-size:9px;color:#3a3a50;margin-top:4px">${(c.added_at||'').slice(0,10)}</div>
      </div>`).join('')}</div>
    <div style="font-size:10px;color:#3a3a50;text-align:center;margin-top:10px">${filtered.length} items · Click for details</div>`;
}

function showContentDetail(id) {
  const c = (allData.library||[]).find(x => x.id === id || x.batch_id === id);
  if(!c) return toast('Not found','#f87171');
  const caps = c.captions || [];
  toast(`${c.model||'?'} — ${c.nsfw_level||'sfw'}`);
}

// ══════════════════ TEXT GEN ══════════════════
function renderTextGen() {
  const models = allData.models || [];
  const sel = $('tgModel');
  if(sel) sel.innerHTML = models.map(m => `<option>${m.name}</option>`).join('');
}

async function generateText() {
  const model = $('tgModel').value;
  const types = [...document.querySelectorAll('#tgTypes input:checked')].map(el => el.value);
  const nsfw = $('tgNsfw').value.toLowerCase();
  const vars = parseInt($('tgVars').value) || 3;
  const context = $('tgContext').value;
  if(types.length === 0) return toast('Select at least one type','#f87171');
  const r = await postAPI('/api/textgen/generate', {model,content_types:types,nsfw_level:nsfw,context,variations:vars});
  $('tgResults').innerHTML = Array.isArray(r) && r.length > 0
    ? r.map(t => `<div style="padding:10px 12px;background:#0a0a12;border:1px solid #1f1f2e;border-radius:8px;margin-bottom:6px">
      <div style="font-size:10px;color:#a855f7;text-transform:uppercase;font-weight:600">${t.type}</div>
      <div style="font-size:12px;color:#d4d4d8;margin:4px 0">${t.text}</div>
      <div style="display:flex;gap:4px">
        <button class="btn btn-xs btn-ghost" onclick="copyText(this.previousElementSibling.textContent)">Copy</button>
        <button class="btn btn-xs btn-ghost" onclick="toast('Edit in text editor')">Edit</button>
      </div>
    </div>`).join('')
    : '<div style="color:#f87171;font-size:12px;padding:12px">Generation failed</div>';
}

function copyText(text) {
  navigator.clipboard.writeText(text.trim()).then(() => toast('Copied!'));
}

// ══════════════════ LORA MANAGEMENT ══════════════════
function renderLora() {
  const loras = allData.loras || [];
  const models = allData.models || [];
  const mf = $('loraModelFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  const filter = mf ? mf.value : 'all';
  const filtered = filter === 'all' ? loras : loras.filter(l => l.model_id === filter);

  // Summary
  const best = filtered.length > 0 ? filtered.reduce((a,b) => (a.images_trained||0) > (b.images_trained||0) ? a : b) : null;
  $('loraSummary').style.display = filtered.length > 0 ? 'block' : 'none';
  $('loraSummary').innerHTML = filtered.length > 0 ? `
    <div style="display:flex;gap:16px;flex-wrap:wrap;font-size:12px">
      <span>Total: <strong style="color:#fff">${filtered.length}</strong> LoRAs</span>
      <span>Models: <strong style="color:#fff">${new Set(filtered.map(l=>l.model_id)).size}</strong></span>
      ${best ? `<span>Best: <strong style="color:#34d399">${best.model_id} v${best.version}</strong> (${best.images_trained||0} img, loss ${best.loss||'?'})</span>` : ''}
    </div>` : '';

  $('loraTableWrap').innerHTML = filtered.length === 0
    ? '<div class="card"><div style="text-align:center;padding:20px;color:#6b6b80;font-size:13px">No LoRAs trained yet.</div></div>'
    : `<div class="card"><div class="table-wrap">
    <table>
      <tr><th>LoRA</th><th>Model</th><th>Type</th><th>Images</th><th>Loss</th><th>Trigger</th><th>Source</th><th>Trained</th><th></th></tr>
      ${filtered.map(l => `<tr>
        <td style="font-weight:500">v${l.version}</td>
        <td>${l.model_id}</td>
        <td><span class="tag ${l.type==='NSFW'?'tag-red':'tag-green'}">${l.type||'SFW'}</span></td>
        <td>${l.images_trained||0}</td>
        <td>${l.loss||'—'}</td>
        <td style="font-size:11px;color:#818cf8">${l.trigger_word||'—'}</td>
        <td>${l.source||'uploaded'}</td>
        <td>${(l.trained_at||'').slice(0,10)}</td>
        <td><button class="btn btn-xs btn-ghost" onclick="deleteLora('${l.id}')">×</button></td>
      </tr>`).join('')}
    </table></div></div>`;
}

async function deleteLora(id) {
  if(!confirm('Delete this LoRA version?')) return;
  await postAPI('/api/lora/versions/delete', {id});
  toast('Deleted');
  load();
}

function showTrainLora(model, type) {
  const models = allData.models || [];
  $('tlModel').innerHTML = models.map(m => `<option ${m.name===model?'selected':''}>${m.name}</option>`).join('');
  if(type) $('tlType').value = type;
  
  // Populate dataset selector
  const images = allData.dataset || [];
  const dsSel = $('tlDatasetSelect');
  if(dsSel) {
    const byModel = {};
    images.forEach(i => {
      if(i.status === 'new' || i.status === 'used') {
        const key = `${i.model} - ${i.type.toUpperCase()} (${i.status})`;
        if(!byModel[key]) byModel[key] = [];
        byModel[key].push(i.id);
      }
    });
    dsSel.innerHTML = '<option value="">— Select saved dataset —</option>' +
      Object.entries(byModel).map(([key, ids]) =>
        `<option value="${ids.join(',')}">${key} — ${ids.length} images</option>`
      ).join('');
  }
  
  $('trainLoraModal').style.display = 'flex';
}

function loadDatasetForTraining() {
  const sel = $('tlDatasetSelect');
  if(sel && sel.value) {
    const ids = sel.value.split(',');
    selectedDsImages = ids;
    $('tlImagesInfo').textContent = `${ids.length} images selected`;
  } else {
    selectedDsImages = [];
    $('tlImagesInfo').textContent = '0 selected';
  }
}

async function saveTrainLora() {
  const model = $('tlModel').value;
  const type = $('tlType').value;
  const source = $('tlSource').value;
  const images = parseInt($('tlImages').value) || 120;
  const loss = parseFloat($('tlLoss').value) || 0.08;
  const trigger = $('tlTrigger').value;
  const steps = parseInt($('tlSteps').value) || 1500;
  const lr = parseFloat($('tlLr').value) || 0.0001;

  // Find current version
  const existing = (allData.loras||[]).filter(l => l.model_id === model && l.type === type);
  const version = existing.length > 0 ? Math.max(...existing.map(l => l.version||0)) + 1 : 1;

  const r = await postAPI('/api/lora/versions/add', {
    model_id: model, version, type, source, images_trained: images,
    loss, trigger_word: trigger, steps, lr, base_model: 'sd_xl_base_1.0'
  });
  closeModal('trainLoraModal');
  toast(`LoRA v${version} saved`);
  // Also mark model lora as trained
  await postAPI('/api/models/update', {name: model, lora: 'trained'});
  load();
}

// ══════════════════ REVENUE ══════════════════
function renderRevenue() {
  const r = allData.revenue || {};
  const entries = r.entries || [];
  const byModel = r.by_model || {};
  const models = allData.models || [];
  const mf = $('revModelFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  const filter = mf ? mf.value : 'all';
  const filtered = filter === 'all' ? entries : entries.filter(e => e.model === filter);

  $('revStats').innerHTML = `
    <div class="card stat"><div class="stat-val">$${r.total||0}</div><div class="stat-label">Total revenue</div></div>
    <div class="card stat"><div class="stat-val">${entries.length}</div><div class="stat-label">Transactions</div></div>
    <div class="card stat"><div class="stat-val">$${entries.filter(e => (e.date||'').startsWith(new Date().toISOString().slice(0,7))).reduce((s,e) => s+e.amount, 0)}</div><div class="stat-label">This month</div></div>`;

  const modelNames = Object.keys(byModel);
  $('revByModel').innerHTML = modelNames.length === 0
    ? '<div style="font-size:12px;color:#6b6b80;padding:8px">No data</div>'
    : modelNames.map(m => `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #0f0f1a;font-size:12px">
      <span style="color:#d4d4d8">${m}</span>
      <span style="color:#34d399">$${byModel[m]||0}</span>
    </div>`).join('');

  $('revHistory').innerHTML = filtered.length === 0
    ? '<div style="font-size:12px;color:#6b6b80;padding:8px">No payments logged</div>'
    : `<div class="table-wrap"><table>
      <tr><th>Date</th><th>Model</th><th>Platform</th><th>Amount</th><th>Net</th><th></th></tr>
      ${filtered.slice(-50).reverse().map((e,i) => {
        const realIdx = r.entries.indexOf(e);
        return `<tr>
          <td>${e.date||''}</td>
          <td>${e.model||'?'}</td>
          <td style="color:#6b6b80">${e.source||''}</td>
          <td style="color:#34d399;font-weight:500">+$${e.amount||0}</td>
          <td style="color:#6b6b80">$${e.net||Math.round((e.amount||0)*0.85)}</td>
          <td><button class="btn btn-xs btn-ghost" onclick="deleteRev(${realIdx})">×</button></td>
        </tr>`;
      }).join('')}
    </table></div>`;
}

function showAddRevenue() {
  const models = allData.models || [];
  $('arModel').innerHTML = models.map(m => `<option>${m.name}</option>`).join('');
  $('addRevModal').style.display = 'flex';
}

async function saveRevenue() {
  const amount = parseInt($('arAmount').value) || 0;
  if(amount <= 0) return toast('Enter amount','#f87171');
  await postAPI('/api/revenue/add', {amount, model:$('arModel').value, source:$('arPlat').value});
  closeModal('addRevModal');
  toast(`+$${amount}`);
  load();
}

async function deleteRev(idx) {
  await postAPI('/api/revenue/delete', {index: idx});
  load();
}

// ══════════════════ ACCOUNTS ══════════════════
function renderAccounts() {
  const models = allData.models || [];
  const accts = allData.accounts || [];
  const mf = $('acctModelFilter'), pf = $('acctPlatFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  const mfVal = mf ? mf.value : 'all';
  const pfVal = pf ? pf.value : 'all';

  $('accountsList').innerHTML = models.filter(m => mfVal === 'all' || m.name === mfVal).map(m => {
    const modelAccts = accts.filter(a => a.model === m.name).filter(a => pfVal === 'all' || a.platform === pfVal);
    const platforms = [...new Set(modelAccts.map(a => a.platform))];
    return `<div class="card">
      <div class="card-title"><span>${m.name} — ${m.followers||0} followers</span></div>
      ${platforms.length === 0 ? '<div style="font-size:12px;color:#6b6b80;padding:6px 0">No accounts for this filter</div>' :
        platforms.map(p => {
          const acct = modelAccts.find(a => a.platform === p) || {};
          return `<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #0f0f1a;flex-wrap:wrap;gap:6px">
            <div style="display:flex;align-items:center;gap:6px">
              <span style="font-size:13px;color:#d4d4d8">${p}</span>
              <span class="tag ${acct.status==='active'?'tag-green':acct.status==='warmup'?'tag-yellow':'tag-red'}">${acct.status||'uncreated'}</span>
              <span style="font-size:11px;color:#6b6b80">${acct.username||''} · ${acct.followers||0} flwrs</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px">
              <div class="bar" style="width:60px;height:4px;display:inline-block">
                <div class="bar-fill" style="width:${acct.warmup||0}%"></div>
              </div>
              <span style="font-size:10px;color:#6b6b80">${acct.warmup||0}%</span>
              <button class="btn btn-xs btn-ghost" onclick="editAcct('${m.name}','${p}')">Edit</button>
              <button class="btn btn-xs btn-ghost" onclick="toast('Sync triggered')">Sync</button>
            </div>
          </div>`;
        }).join('')}
    </div>`;
  }).join('');

  $('acctCronInfo').innerHTML = `
    <div style="font-size:12px;color:#a1a1aa;display:flex;gap:16px;flex-wrap:wrap">
      <span>Schedule: every 2h</span>
      <span>Last run: ${allData.dashboard?.account_sync?.last_sync||'N/A'}</span>
      <span>Status: ${allData.dashboard?.account_sync?.status||'idle'}</span>
    </div>`;
}

function editAcct(model, platform) {
  const a = (allData.accounts||[]).find(x => x.model === model && x.platform === platform) || {};
  const status = prompt('Status:', a.status || 'uncreated'); if(!status) return;
  const warmup = parseInt(prompt('Warmup %:', a.warmup || 0)) || 0;
  const followers = parseInt(prompt('Followers:', a.followers || 0)) || 0;
  const username = prompt('Username:', a.username || '') || '';
  postAPI('/api/accounts/update', {model, platform, status, warmup, followers, username});
  toast('Account updated');
  load();
}

// ══════════════════ SETTINGS ══════════════════
let currentSettingsTab = 'general';

function switchSettingsTab(tab) {
  currentSettingsTab = tab;
  document.querySelectorAll('#settingsTabs .tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  renderSettingsTab(tab);
}

function renderSettings() {
  switchSettingsTab(currentSettingsTab);
}

function renderSettingsTab(tab) {
  const s = allData.settings || {};
  const gen = s.general || {};
  const train = s.training || {};
  const accts = s.accounts || {};

  const content = {
    general: `<div class="card">
      <div class="card-title">General</div>
      <div class="f-row" style="margin-bottom:8px">
        <div class="f-group"><label>Currency</label><select class="f-control f-control-sm" id="stgCurrency"><option ${gen.currency==='USD'?'selected':''}>USD</option><option ${gen.currency==='EUR'?'selected':''}>EUR</option></select></div>
        <div class="f-group"><label>Timezone</label><select class="f-control f-control-sm" id="stgTimezone"><option ${(gen.timezone||'UTC+0')==='UTC+0'?'selected':''}>UTC+0</option><option>UTC-5</option></select></div>
        <div class="f-group"><label>Default NSFW</label><select class="f-control f-control-sm" id="stgDefaultNsfw"><option ${(gen.default_nsfw||'SFW')==='SFW'?'selected':''}>SFW</option><option>Mild</option></select></div>
      </div>
      <div class="f-row" style="margin-bottom:8px">
        <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${gen.auto_approve_sfw?'checked':''} id="stgAutoApprove"> Auto-approve SFW</label>
        <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${gen.manual_review_nsfw?'checked':''} id="stgManualNsfw"> Manual review NSFW</label>
      </div>
      <button class="btn btn-primary btn-sm" onclick="saveSettingsGeneral()">Save</button>
    </div>
    <div style="font-size:10px;color:#3a3a50;margin-top:8px">Drive: ${s._drive_status||'memory_only'}</div>`,

    training: `<div class="card">
      <div class="card-title">Training defaults</div>
      <div class="f-row" style="margin-bottom:8px">
        <div class="f-group"><label>Base model</label><input class="f-control f-control-sm" id="stgBaseModel" value="${train.base_model||'sd_xl_base_1.0'}" style="width:160px"></div>
        <div class="f-group"><label>Steps</label><input class="f-control f-control-sm" id="stgSteps" type="number" value="${train.default_steps||1500}" style="width:60px"></div>
        <div class="f-group"><label>LR</label><input class="f-control f-control-sm" id="stgLr" value="${train.default_lr||0.0001}" style="width:70px"></div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="saveSettingsTraining()">Save</button>
    </div>`,

    accounts: `<div class="card">
      <div class="card-title">Account sync</div>
      <div class="f-group" style="margin-bottom:8px"><label>Cron schedule</label><select class="f-control f-control-sm" id="stgCron"><option ${(accts.cron_schedule||'every 2h')==='every 2h'?'selected':''}>every 2h</option><option>every 4h</option><option>every 6h</option></select></div>
      <div class="f-group" style="margin-bottom:8px"><label>Platforms to sync</label><div style="display:flex;flex-wrap:wrap;gap:8px">
        ${(accts.platforms||['X','Telegram','Reddit','IG']).map(p => `<span class="tag tag-purple">${p}</span>`).join('')}
      </div></div>
      <button class="btn btn-primary btn-sm" onclick="toast('Settings saved')">Save</button>
    </div>`,

    keys: `<div class="card">
      <div class="card-title">API keys</div>
      <div class="f-group" style="margin-bottom:8px"><label>Fal.ai</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="••••••••" style="flex:1" disabled><button class="btn btn-xs btn-ghost">Test</button></div></div>
      <div class="f-group" style="margin-bottom:8px"><label>Replicate</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="••••••••" style="flex:1" disabled><button class="btn btn-xs btn-ghost">Test</button></div></div>
      <div class="f-group"><label>S3 / Cloud storage</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="Not configured" style="flex:1" disabled></div></div>
      <div style="font-size:10px;color:#3a3a50;margin-top:10px">Keys stored in Railway env vars</div>
    </div>`,

    data: `<div class="card">
      <div class="card-title">Data management</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">
        <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Models</button>
        <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Revenue</button>
        <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Content</button>
        <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export All</button>
      </div>
      <div style="padding:12px;background:#0f0f1a;border:1px solid #1f1f2e;border-radius:8px;margin-top:8px">
        <div style="font-size:12px;color:#f87171;font-weight:500">⚠ Danger zone</div>
        <div style="font-size:11px;color:#6b6b80;margin:6px 0">These actions cannot be undone.</div>
        <button class="btn btn-sm btn-red" onclick="if(confirm('Delete ALL data?')) toast('Data cleared')">Delete All Data</button>
      </div>
    </div>`
  };

  $('settingsContent').innerHTML = content[tab] || '<div>Unknown tab</div>';
}

async function saveSettingsGeneral() {
  const data = {
    currency: $('stgCurrency').value,
    timezone: $('stgTimezone').value,
    default_nsfw: $('stgDefaultNsfw').value,
    auto_approve_sfw: $('stgAutoApprove').checked,
    manual_review_nsfw: $('stgManualNsfw').checked,
  };
  await postAPI('/api/settings/update', {general: data});
  toast('Settings saved');
}

async function saveSettingsTraining() {
  await postAPI('/api/settings/update', {training: {
    base_model: $('stgBaseModel').value,
    default_steps: parseInt($('stgSteps').value) || 1500,
    default_lr: parseFloat($('stgLr').value) || 0.0001,
  }});
  toast('Training defaults saved');
}

// ══════════════════ GENERATE MODAL ══════════════════
function showGenModal(model) {
  const models = allData.models || [];
  $('gmModel').innerHTML = models.map(m => `<option ${m.name===model?'selected':''}>${m.name}</option>`).join('');
  if(model) updateGmLoras(model);
  $('genModal').style.display = 'flex';
}

$('gmModel').addEventListener('change', function() {
  updateGmLoras(this.value);
});

async function saveGenerateBatch() {
  const model = $('gmModel').value;
  const loraId = $('gmLora').value;
  const nsfw = $('gmNsfw').value.toLowerCase();
  const count = parseInt($('gmCount').value) || 4;
  const prompt = $('gmPrompt').value.trim();
  const source = $('gmSource').value;
  if(!prompt) return toast('Enter a prompt','#f87171');

  if(source === 'export') {
    const r = await postAPI('/api/generate/export', {
      model, lora_name: loraId, prompt, neg_prompt: $('gmNegPrompt').value,
      count, steps: parseInt($('gmSteps').value) || 30,
      cfg: parseFloat($('gmCfg').value) || 7.0, seed: parseInt($('gmSeed').value) || -1,
      use_adetailer: $('gmADetailer').checked, use_upscale: $('gmUpscale').checked,
      varied_prompts: $('gmVaried').checked, base_model: 'RealVisXL_v5.0'
    });
    if(r.ok && r.zip_file) {
      toast('Gen workflow exported! Downloading...');
      window.location.href = `/api/exports/download/${r.zip_file}`;
    } else {
      toast('Export failed','#f87171');
    }
    closeModal('genModal');
    return;
  }

  if(source === 'runpod') {
    toast('Sending to RunPod...');
    const r = await postAPI('/api/runpod/generate', {
      model, lora_id: loraId, prompt, neg_prompt: $('gmNegPrompt').value,
      count, steps: parseInt($('gmSteps').value) || 30,
      cfg: parseFloat($('gmCfg').value) || 7.0, seed: parseInt($('gmSeed').value) || -1
    });
    if(r.ok) { toast(`RunPod gen started: ${r.runpod_job_id}`); }
    else { toast(r.error||'RunPod failed','#f87171'); }
    closeModal('genModal');
    return;
  }

  // Default: create batch (management mode)
  const r = await postAPI('/api/content/batches/create', {
    model, lora_id: loraId, prompt, nsfw_level: nsfw, count,
    steps: parseInt($('gmSteps').value) || 30,
    cfg: parseFloat($('gmCfg').value) || 7.0,
    seed: parseInt($('gmSeed').value) || -1,
  });
  closeModal('genModal');
  if(r.ok) toast(`Batch created: ${r.images||count} images → Pipeline`);
  load();
}

// ══════════════════ DATASET ══════════════════
let selectedDsImages = [];

function renderDataset() {
  const images = allData.dataset || [];
  const models = allData.models || [];
  const datasets = allData.datasets || [];
  const mf = $('dsModelFilter'), tf = $('dsTypeFilter'), sf = $('dsStatusFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  // Populate upload model picker
  const upModel = $('dsUploadModel');
  if(upModel) upModel.innerHTML = '<option value="">— Select —</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  // Populate dataset selector
  const upDs = $('dsUploadDataset');
  if(upDs) upDs.innerHTML = '<option value="">None (direct)</option>' + datasets.map(d => `<option value="${d.id}">${d.name} (${d.model} ${d.type})</option>`).join('');
  
  let filtered = images;
  if(mf && mf.value !== 'all') filtered = filtered.filter(i => i.model === mf.value);
  if(tf && tf.value !== 'all') filtered = filtered.filter(i => i.type.toUpperCase() === tf.value.toUpperCase());
  if(sf && sf.value !== 'all') filtered = filtered.filter(i => i.status === sf.value);

  const total = images.length;
  const used = images.filter(i => i.status === 'used').length;
  const rejected = images.filter(i => i.status === 'rejected').length;
  const newImgs = images.filter(i => i.status === 'new').length;

  $('dsStats').style.display = total > 0 ? 'block' : 'none';
  $('dsStats').innerHTML = `<div style="display:flex;gap:16px;font-size:12px;flex-wrap:wrap">
    <span>Total: <strong style="color:#fff">${total}</strong></span>
    <span>New: <strong style="color:#fbbf24">${newImgs}</strong></span>
    <span>Used: <strong style="color:#34d399">${used}</strong></span>
    <span>Rejected: <strong style="color:#f87171">${rejected}</strong></span>
  </div>`;

  // Show named datasets
  $('dsDatasets').style.display = datasets.length > 0 ? 'block' : 'none';
  $('dsDatasets').innerHTML = `<div class="card-title">Saved Datasets</div>
    ${datasets.map(d => {
      const dsImages = images.filter(i => i.dataset_id === d.id);
      return `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid #0f0f1a;font-size:12px">
        <span><strong style="color:#d4d4d8">${d.name}</strong> <span style="color:#6b6b80">— ${d.model} ${d.type}</span></span>
        <span style="color:#a1a1aa">${dsImages.length} images</span>
      </div>`;
    }).join('')}`;

  if(filtered.length === 0) {
    $('dsGrid').innerHTML = '<div style="color:#6b6b80;font-size:13px;text-align:center;padding:40px">No images. Upload to get started.</div>';
    $('dsActions').style.display = 'none';
    return;
  }

  $('dsGrid').innerHTML = `<div class="grid-4">${filtered.map(i => {
      const checked = selectedDsImages.includes(i.id) ? 'checked' : '';
      const imgUrl = `/api/dataset/file/${i.model}/${i.type}/${i.filename}`;
      return `<div class="img-thumb" style="cursor:default;padding:0;overflow:hidden;position:relative">
        <img src="${imgUrl}" style="width:100%;height:100px;object-fit:cover;display:block" onerror="this.style.display='none';this.parentNode.innerHTML+='<div style=padding:30px;font-size:24px;color:#a855f7;text-align:center>🖼</div>'">
        <div style="padding:6px 8px">
          <div style="font-size:10px;color:#6b6b80">${i.filename||'?'}</div>
          <span class="tag ${i.status==='used'?'tag-green':i.status==='rejected'?'tag-red':'tag-yellow'}">${i.status||'new'}</span>
          <div style="margin-top:4px;display:flex;align-items:center;gap:4px;font-size:10px">
            <input type="checkbox" ${checked} onchange="toggleDsImage('${i.id}')" style="accent-color:#a855f7">
            <span style="color:#6b6b80">Select</span>
          </div>
          ${i.caption ? `<div style="font-size:9px;color:#3a3a50;margin-top:4px">${i.caption.slice(0,40)}</div>` : ''}
        </div>
      </div>`;
    }).join('')}</div>`;

  const hasSelection = selectedDsImages.length > 0;
  $('dsTrainBtn').style.display = hasSelection ? 'inline-flex' : 'none';
  $('dsTagUsedBtn').style.display = hasSelection ? 'inline-flex' : 'none';
  $('dsTagRejectBtn').style.display = hasSelection ? 'inline-flex' : 'none';
  $('dsActions').style.display = 'block';
}

function toggleDsImage(id) {
  const idx = selectedDsImages.indexOf(id);
  if(idx > -1) selectedDsImages.splice(idx, 1);
  else selectedDsImages.push(id);
  renderDataset();
}

async function uploadDatasetImages() {
  const input = $('dsFileInput');
  if(!input.files || input.files.length === 0) return toast('Select files','#f87171');
  const model = $('dsUploadModel').value;
  const type = $('dsUploadType').value;
  if(!model) return toast('Select a model in the upload section','#f87171');

  $('dsUploadStatus').textContent = 'Uploading...';
  const formData = new FormData();
  for(let f of input.files) formData.append('files', f);
  formData.append('model', model);
  formData.append('type', type.toLowerCase());
  try {
    const r = await fetch('/api/dataset/upload/files', {method:'POST', body: formData});
    const data = await r.json();
    if(data.ok) { toast(`${data.saved} images uploaded`); $('dsUploadStatus').textContent = ''; load(); }
    else { toast(data.error||'Upload failed','#f87171'); }
  } catch(e) { toast('Upload error','#f87171'); }
  input.value = '';
}

async function autoCaptionSelected() {
  if(selectedDsImages.length === 0) return toast('Select images first','#f87171');
  const r = await postAPI('/api/dataset/images/auto_caption', {ids: selectedDsImages});
  if(r.ok) toast(`${r.count} captions generated`);
  load();
}

async function exportTrainingPackage() {
  if(selectedDsImages.length === 0) return toast('Select images first','#f87171');
  const model = $('dsModelFilter').value;
  if(model === 'all') return toast('Select a specific model filter','#f87171');
  const r = await postAPI('/api/dataset/export/training', {
    ids: selectedDsImages, model, lora_name: `${model.toLowerCase()}_training`,
    base_model: 'RealVisXL_v5.0', repeat: 12, network_dim: 48, lr: 0.0001, trigger_word: ''
  });
  if(r.ok && r.zip_file) {
    toast(`Training package ready: ${r.images} images in ${r.zip_file}`);
    // Download the zip
    window.location.href = `/api/exports/download/${r.zip_file}`;
  } else {
    toast('Export failed','#f87171');
  }
}

async function tagSelected(status) {
  if(selectedDsImages.length === 0) return toast('Select images first','#f87171');
  await postAPI('/api/dataset/images/batch_tag', {ids: selectedDsImages, status});
  selectedDsImages = [];
  toast(`Marked as ${status}`);
  load();
}

async function trainFromSelected() {
  if(selectedDsImages.length === 0) return toast('Select images first','#f87171');
  const model = $('dsModelFilter').value;
  if(model === 'all') return toast('Select a specific model','#f87171');
  showTrainLora(model, $('dsTypeFilter').value === 'all' ? 'SFW' : $('dsTypeFilter').value);
  $('tlImagesInfo').textContent = `${selectedDsImages.length} images selected from Dataset`;
}

// ══════════════════ NAMED DATASETS ══════════════════
function showCreateDataset() {
  const models = allData.models || [];
  $('cdModel').innerHTML = models.map(m => `<option>${m.name}</option>`).join('');
  $('createDatasetModal').style.display = 'flex';
}

async function saveCreateDataset() {
  const name = $('cdName').value.trim();
  if(!name) return toast('Enter a dataset name','#f87171');
  const r = await postAPI('/api/dataset/create', {
    name, model: $('cdModel').value, type: $('cdType').value, notes: $('cdNotes').value
  });
  closeModal('createDatasetModal');
  if(r.ok) { toast(`Dataset "${name}" created`); load(); }
  else { toast('Failed to create','#f87171'); }
}

// ══════════════════ UPDATED UPLOAD WITH PROGRESS ══════════════════
async function uploadDatasetImages() {
  const input = $('dsFileInput');
  if(!input.files || input.files.length === 0) return toast('Select files','#f87171');
  const model = $('dsUploadModel').value;
  const type = $('dsUploadType').value;
  if(!model) return toast('Select a model','#f87171');

  const bar = $('dsProgressFill');
  const status = $('dsUploadStatus');
  const prog = $('dsUploadProgress');
  prog.style.display = 'block';
  bar.style.width = '0%';
  status.textContent = 'Starting upload...';

  const formData = new FormData();
  for(let f of input.files) formData.append('files', f);
  formData.append('model', model);
  formData.append('type', type.toLowerCase());
  const dsId = $('dsUploadDataset').value;
  if(dsId) formData.append('dataset_id', dsId);

  const xhr = new XMLHttpRequest();
  xhr.upload.onprogress = function(e) {
    if(e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      bar.style.width = pct + '%';
      status.textContent = `Uploading... ${pct}% (${e.loaded}/${e.total} bytes)`;
    }
  };
  xhr.onload = function() {
    if(xhr.status === 200) {
      const data = JSON.parse(xhr.responseText);
      if(data.ok) {
        bar.style.width = '100%';
        status.textContent = `✓ ${data.saved} images uploaded`;
        setTimeout(() => { prog.style.display = 'none'; load(); }, 1500);
      } else {
        status.textContent = '✗ ' + (data.error||'Upload failed');
      }
    } else {
      status.textContent = '✗ Upload failed';
    }
  };
  xhr.onerror = function() { status.textContent = '✗ Network error'; };
  xhr.open('POST', '/api/dataset/upload/files', true);
  xhr.send(formData);
  input.value = '';
}

// ══════════════════ INLINE MODEL EDIT ══════════════════
let editingModel = null;

function toggleEditModel() {
  const detail = document.getElementById('modelDetailContent');
  if(!detail) return;
  if(editingModel) {
    editingModel = null;
    renderModelDetail(selectedModel);
    return;
  }
  const m = allData.models.find(x => x.name === selectedModel) || {};
  editingModel = selectedModel;
  const bio = detail.querySelector('.model-detail-bio');
  if(bio) bio.innerHTML = `
    <div class="f-row" style="margin-top:6px">
      <div class="f-group"><label>Age</label><input class="f-control f-control-sm" id="editAge" value="${m.age||''}" style="width:50px"></div>
      <div class="f-group"><label>Ethnicity</label><input class="f-control f-control-sm" id="editEth" value="${m.ethnicity||''}" style="width:100px"></div>
      <div class="f-group"><label>Location</label><input class="f-control f-control-sm" id="editLoc" value="${m.location||''}" style="width:120px"></div>
      <div class="f-group"><label>Persona</label><input class="f-control f-control-sm" id="editPers" value="${m.persona||''}" style="width:200px"></div>
      <div class="f-group"><label>Kinks</label><input class="f-control f-control-sm" id="editKinks" value="${m.kinks||''}" style="width:150px"></div>
    </div>
    <div style="margin-top:8px">
      <button class="btn btn-primary btn-sm" onclick="saveModelEdit()">Save</button>
      <button class="btn btn-ghost btn-sm" onclick="toggleEditModel()">Cancel</button>
    </div>`;
  const editBtn = document.getElementById('editModelBtn');
  if(editBtn) editBtn.textContent = 'Cancel';
}

async function saveModelEdit() {
  const r = await postAPI('/api/models/update', {
    name: selectedModel,
    age: $('editAge').value, ethnicity: $('editEth').value,
    location: $('editLoc').value, persona: $('editPers').value, kinks: $('editKinks').value
  });
  if(r.ok) { toast('Saved'); editingModel = null; load(); }
  else { toast('Save failed','#f87171'); }
}

// ══════════════════ VAULT ══════════════════
function showVaultModal() {
  const models = allData.models || [];
  $('vModel').innerHTML = models.map(m => `<option>${m.name}</option>`).join('');
  $('vaultModal').style.display = 'flex';
}

async function saveVaultEntry() {
  const email = $('vEmail').value.trim();
  if(!email) return toast('Enter email','#f87171');
  await postAPI('/api/accounts/vault/add', {
    email, password: $('vPassword').value, model: $('vModel').value,
    used_at: $('vUsed').value, notes: $('vNotes').value, status: $('vStatus').value.toLowerCase()
  });
  closeModal('vaultModal');
  toast('Vault entry saved');
  $('vEmail').value = ''; $('vPassword').value = '';
  load();
}

// ══════════════════ SOCIAL MONITOR ══════════════════
function showSocialModal() {
  const models = allData.models || [];
  $('sModel').innerHTML = models.map(m => `<option>${m.name}</option>`).join('');
  $('socialModal').style.display = 'flex';
}

async function saveSocialEntry() {
  const handle = $('sHandle').value.trim();
  if(!handle) return toast('Enter handle','#f87171');
  await postAPI('/api/accounts/social/add', {
    handle, platform: $('sPlatform').value, model: $('sModel').value,
    followers: parseInt($('sFollowers').value) || 0,
    posts: parseInt($('sPosts').value) || 0,
    engagement: parseFloat($('sEng').value) || 0
  });
  closeModal('socialModal');
  toast('Social entry added');
  $('sHandle').value = '';
  load();
}

// ══════════════════ UPDATED ACCOUNTS ══════════════════
function renderAccounts() {
  const models = allData.models || [];
  const vault = allData.vault || [];
  const social = allData.social || [];
  const mf = $('acctModelFilter');
  if(mf) mf.innerHTML = '<option value="all">All models</option>' + models.map(m => `<option>${m.name}</option>`).join('');
  const filter = mf ? mf.value : 'all';

  const filteredSocial = filter === 'all' ? social : social.filter(s => s.model === filter);
  const filteredVault = filter === 'all' ? vault : vault.filter(v => v.model === filter);

  $('socialList').innerHTML = filteredSocial.length === 0
    ? '<div style="font-size:12px;color:#6b6b80;padding:8px">No accounts monitored. Add one.</div>'
    : `<div class="table-wrap"><table>
      <tr><th>Handle</th><th>Platform</th><th>Model</th><th>Followers</th><th>Posts</th><th>Eng%</th><th>Checked</th><th></th></tr>
      ${filteredSocial.map(s => `<tr>
        <td style="color:#d4d4d8">${s.handle}</td>
        <td>${s.platform}</td>
        <td>${s.model}</td>
        <td>${s.followers||0}</td>
        <td>${s.posts||0}</td>
        <td>${s.engagement||0}%</td>
        <td style="font-size:10px;color:#6b6b80">${(s.last_checked||'').slice(0,10)}</td>
        <td><button class="btn btn-xs btn-ghost" onclick="deleteSocial('${s.id}')">×</button></td>
      </tr>`).join('')}
    </table></div>`;

  $('vaultList').innerHTML = filteredVault.length === 0
    ? '<div style="font-size:12px;color:#6b6b80;padding:8px">No credentials stored. Add vault entries.</div>'
    : `<div class="table-wrap"><table>
      <tr><th>Email</th><th>Password</th><th>Model</th><th>Used at</th><th>Status</th><th>Notes</th><th></th></tr>
      ${filteredVault.map(v => `<tr>
        <td style="color:#d4d4d8">${v.email}</td>
        <td><span class="tag" onclick="this.textContent=this.textContent==='••••••'?'${v.password}':'••••••'" style="cursor:pointer">••••••</span></td>
        <td>${v.model}</td>
        <td style="font-size:11px;color:#6b6b80">${v.used_at||'—'}</td>
        <td><span class="tag ${v.status==='active'?'tag-green':v.status==='banned'?'tag-red':'tag-yellow'}">${v.status||'active'}</span></td>
        <td style="font-size:11px;color:#6b6b80">${v.notes||''}</td>
        <td><button class="btn btn-xs btn-ghost" onclick="deleteVault('${v.id}')">×</button></td>
      </tr>`).join('')}
    </table></div>`;
}

async function deleteVault(id) {
  await postAPI('/api/accounts/vault/delete', {id});
  toast('Deleted'); load();
}

async function deleteSocial(id) {
  await postAPI('/api/accounts/social/delete', {id});
  toast('Deleted'); load();
}

// ══════════════════ UPDATED TRAIN LORA ══════════════════
async function saveTrainLora() {
  const model = $('tlModel').value;
  const type = $('tlType').value;
  const source = $('tlSource').value;
  const customName = $('tlCustomName').value.trim();
  const loss = parseFloat($('tlLoss').value) || 0.08;
  const trigger = $('tlTrigger').value;
  const steps = parseInt($('tlSteps').value) || 1500;
  const lr = parseFloat($('tlLr').value) || 0.0001;
  const datasetImageIds = [...selectedDsImages];

  const existing = (allData.loras||[]).filter(l => l.model_id === model && l.type === type);
  const version = existing.length > 0 ? Math.max(...existing.map(l => l.version||0)) + 1 : 1;

  const payload = {
    model_id: model, version, type, source, custom_name: customName,
    images_trained: datasetImageIds.length || 120, loss,
    trigger_word: trigger, steps, lr, dataset_image_ids: datasetImageIds,
    base_model: 'sd_xl_base_1.0'
  };

  if(source === 'runpod') {
    // RunPod auto-train
    toast('Sending to RunPod...');
    const rp = await postAPI('/api/runpod/train', {
      ...payload, dataset_images_ids: datasetImageIds, lora_name: customName || `${model.toLowerCase()}_v${version}`
    });
    if(rp.ok) { toast(`RunPod training started: ${rp.runpod_job_id}`); }
    else { toast(`RunPod error: ${rp.error||'Failed'}`); return; }
  }

  const r = await postAPI('/api/lora/versions/add', payload);
  closeModal('trainLoraModal');
  selectedDsImages = [];
  if(source === 'export') toast('LoRA logged. Export feature coming — train manually');
  else toast(`LoRA ${customName||'v'+version} saved`);
  await postAPI('/api/models/update', {name: model, lora: 'trained'});
  load();
}

// ══════════════════ UPDATED SETTINGS (RunPod tab) ══════════════════
function renderSettingsTab(tab) {
  const s = allData.settings || {};
  const gen = s.general || {};
  const train = s.training || {};
  const accts = s.accounts || {};
  const rp = s.runpod || {};

  const content = {
      general: `<div class="card">
        <div class="card-title">General</div>
        <div class="f-row" style="margin-bottom:8px">
          <div class="f-group"><label>Currency</label><select class="f-control f-control-sm" id="stgCurrency"><option ${gen.currency==='USD'?'selected':''}>USD</option><option ${gen.currency==='EUR'?'selected':''}>EUR</option></select></div>
          <div class="f-group"><label>Timezone</label><select class="f-control f-control-sm" id="stgTimezone"><option ${(gen.timezone||'UTC+0')==='UTC+0'?'selected':''}>UTC+0</option><option>UTC-5</option></select></div>
          <div class="f-group"><label>Default NSFW</label><select class="f-control f-control-sm" id="stgDefaultNsfw"><option ${(gen.default_nsfw||'SFW')==='SFW'?'selected':''}>SFW</option><option>Mild</option></select></div>
        </div>
        <div class="f-row" style="margin-bottom:8px">
          <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${gen.auto_approve_sfw?'checked':''} id="stgAutoApprove"> Auto-approve SFW</label>
          <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${gen.manual_review_nsfw?'checked':''} id="stgManualNsfw"> Manual review NSFW</label>
        </div>
        <button class="btn btn-primary btn-sm" onclick="saveSettingsGeneral()">Save</button>
      </div>
      <div style="font-size:10px;color:#3a3a50;margin-top:8px">Drive: ${s._drive_status||'memory_only'}</div>`,

      training: `<div class="card">
        <div class="card-title">Training defaults</div>
        <div class="f-row" style="margin-bottom:8px">
          <div class="f-group"><label>Base model</label><input class="f-control f-control-sm" id="stgBaseModel" value="${train.base_model||'sd_xl_base_1.0'}" style="width:160px"></div>
          <div class="f-group"><label>Steps</label><input class="f-control f-control-sm" id="stgSteps" type="number" value="${train.default_steps||1500}" style="width:60px"></div>
          <div class="f-group"><label>LR</label><input class="f-control f-control-sm" id="stgLr" value="${train.default_lr||0.0001}" style="width:70px"></div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="saveSettingsTraining()">Save</button>
      </div>`,

      accounts: `<div class="card">
        <div class="card-title">Account sync</div>
        <div class="f-group" style="margin-bottom:8px"><label>Cron schedule</label><select class="f-control f-control-sm" id="stgCron"><option ${(accts.cron_schedule||'every 2h')==='every 2h'?'selected':''}>every 2h</option><option>every 4h</option><option>every 6h</option></select></div>
        <div class="f-group" style="margin-bottom:8px"><label>Platforms to sync</label><div style="display:flex;flex-wrap:wrap;gap:8px">
          ${(accts.platforms||['X','Telegram','Reddit','IG']).map(p => `<span class="tag tag-purple">${p}</span>`).join('')}
        </div></div>
        <button class="btn btn-primary btn-sm" onclick="toast('Settings saved')">Save</button>
      </div>`,

      keys: `<div class="card">
        <div class="card-title">API keys</div>
        <div class="f-group" style="margin-bottom:8px"><label>Fal.ai</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="••••••••" style="flex:1" disabled><button class="btn btn-xs btn-ghost">Test</button></div></div>
        <div class="f-group" style="margin-bottom:8px"><label>Replicate</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="••••••••" style="flex:1" disabled><button class="btn btn-xs btn-ghost">Test</button></div></div>
        <div class="f-group"><label>S3 / Cloud storage</label><div style="display:flex;gap:6px"><input class="f-control f-control-sm" value="Not configured" style="flex:1" disabled></div></div>
        <div style="font-size:10px;color:#3a3a50;margin-top:10px">Keys stored in Railway env vars</div>
      </div>`,

      runpod: `<div class="card">
      <div class="card-title">RunPod — Connection</div>
      <div class="f-row" style="margin-bottom:10px">
        <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:6px">
          <input type="checkbox" ${rp.enabled?'checked':''} id="rpEnabled" onchange="toggleRunpod()"> <strong>RunPod ${rp.enabled?'ON':'OFF'}</strong>
        </label>
        <span class="pill ${rp.enabled?'pill-green':'pill-gray'}">${rp.enabled?'Active':'Inactive'}</span>
      </div>
      <div id="rpConfigFields" style="${rp.enabled?'':'opacity:0.4;pointer-events:none'}">
        <div class="f-group" style="margin-bottom:6px"><label>API Key</label><input class="f-control f-control-sm" id="rpApiKey" value="${rp.api_key||''}" placeholder="rpr_..." style="width:100%"></div>
        <div class="f-row" style="margin-bottom:6px">
          <div class="f-group"><label>Training Endpoint</label><input class="f-control f-control-sm" id="rpTrainEndpoint" value="${rp.endpoint_id||''}" style="width:100%"></div>
          <div class="f-group"><label>Gen Endpoint</label><input class="f-control f-control-sm" id="rpGenEndpoint" value="${rp.gen_endpoint_id||''}" style="width:100%"></div>
        </div>
        <div class="f-row" style="margin-bottom:0">
          <div class="f-group"><label>Storage Volume ID</label><input class="f-control f-control-sm" id="rpStorageVol" value="${rp.storage_volume_id||''}" style="width:100%"></div>
          <div class="f-group"><label>Template</label><input class="f-control f-control-sm" id="rpTemplate" value="${rp.template||'sdxl_comfyui'}" style="width:160px"></div>
        </div>
        <div style="display:flex;gap:6px;margin-top:10px">
          <button class="btn btn-primary btn-sm" onclick="saveRunpodConfig()">Save Connection</button>
          <button class="btn btn-ghost btn-sm" onclick="testRunpod()">Test</button>
        </div>
        <div id="rpTestResult" style="margin-top:6px;font-size:12px"></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Training Pipeline — Dataset → LoRA .safetensors</div>
      <div style="font-size:10.5px;color:#6b6b80;margin-bottom:10px">Settings for training sessions. Takes ~10-15 min per LoRA on RunPod.</div>
      <div class="card-title" style="font-size:10px;color:#818cf8;margin-top:0">SFW Training (RealVisXL v5.0)</div>
      <div class="f-row" style="margin-bottom:8px">
        <div class="f-group"><label>Checkpoint</label><input class="f-control f-control-sm" id="rpSfwCkpt" value="${rp.sfw_checkpoint||'RealVisXL_v5.0'}" style="width:160px"></div>
        <div class="f-group"><label>Repeat</label><input class="f-control f-control-sm" id="rpSfwRepeat" type="number" value="${rp.sfw_repeat||12}" style="width:55px"></div>
        <div class="f-group"><label>Dim</label><input class="f-control f-control-sm" id="rpSfwDim" type="number" value="${rp.sfw_network_dim||48}" style="width:55px"></div>
        <div class="f-group"><label>LR</label><input class="f-control f-control-sm" id="rpSfwLr" value="${rp.sfw_lr||0.0001}" style="width:75px"></div>
        <div class="f-group"><label>Steps</label><input class="f-control f-control-sm" id="rpSfwSteps" type="number" value="${rp.sfw_steps||1500}" style="width:65px"></div>
      </div>
      <div class="card-title" style="font-size:10px;color:#f87171;margin-top:10px">NSFW Training (BigLust v5)</div>
      <div class="f-row" style="margin-bottom:0">
        <div class="f-group"><label>Checkpoint</label><input class="f-control f-control-sm" id="rpNsfwCkpt" value="${rp.nsfw_checkpoint||'biglust_v5'}" style="width:160px"></div>
        <div class="f-group"><label>Repeat</label><input class="f-control f-control-sm" id="rpNsfwRepeat" type="number" value="${rp.nsfw_repeat||15}" style="width:55px"></div>
        <div class="f-group"><label>Dim</label><input class="f-control f-control-sm" id="rpNsfwDim" type="number" value="${rp.nsfw_network_dim||64}" style="width:55px"></div>
        <div class="f-group"><label>LR</label><input class="f-control f-control-sm" id="rpNsfwLr" value="${rp.nsfw_lr||0.00008}" style="width:75px"></div>
        <div class="f-group"><label>Steps</label><input class="f-control f-control-sm" id="rpNsfwSteps" type="number" value="${rp.nsfw_steps||2000}" style="width:65px"></div>
      </div>
      <button class="btn btn-primary btn-sm" style="margin-top:10px" onclick="saveRunpodTraining()">Save Training Params</button>
    </div>

    <div class="card">
      <div class="card-title">Generation Pipeline — Prompt + LoRA → Images</div>
      <div style="font-size:10.5px;color:#6b6b80;margin-bottom:10px">Settings for generation batches. Varies prompt per image, applies ADetailer + upscale.</div>
      <div class="f-row" style="margin-bottom:8px">
        <div class="f-group"><label>CFG Scale</label><input class="f-control f-control-sm" id="rpCfg" value="${rp.default_cfg||7.0}" style="width:60px"></div>
        <div class="f-group"><label>Sampler</label><select class="f-control f-control-sm" id="rpSampler"><option ${'euler'} selected>Euler</option><option>DPM++ 2M</option></select></div>
        <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${rp.use_adetailer?'checked':''} id="rpADetailer"> ADetailer (face)</label>
        <label style="font-size:12px;color:#a1a1aa;display:flex;align-items:center;gap:4px"><input type="checkbox" ${rp.use_upscale?'checked':''} id="rpUpscale"> Upscale 2x</label>
      </div>
      <button class="btn btn-primary btn-sm" onclick="saveRunpodGen()">Save Gen Params</button>
    </div>`,
    data: `<div class="card">
          <div class="card-title">Data management</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">
            <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Models</button>
            <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Revenue</button>
            <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export Content</button>
            <button class="btn btn-sm btn-ghost" onclick="toast('Export started')">Export All</button>
          </div>
          <div style="padding:12px;background:#0f0f1a;border:1px solid #1f1f2e;border-radius:8px;margin-top:8px">
            <div style="font-size:12px;color:#f87171;font-weight:500">⚠ Danger zone</div>
            <div style="font-size:11px;color:#6b6b80;margin:6px 0">These actions cannot be undone.</div>
            <button class="btn btn-sm btn-red" onclick="if(confirm('Delete ALL data?')) toast('Data cleared')">Delete All Data</button>
          </div>
        </div>`
      };

      $('settingsContent').innerHTML = content[tab] || '<div>Unknown tab</div>';
    }

async function saveRunpodConfig() {
  const enabled = $('rpEnabled').checked;
  await postAPI('/api/settings/update', {runpod: {
    enabled, api_key: $('rpApiKey').value,
    endpoint_id: $('rpTrainEndpoint').value,
    gen_endpoint_id: $('rpGenEndpoint').value,
    template: $('rpTemplate').value,
    storage_volume_id: $('rpStorageVol').value,
  }});
  toast('Connection saved');
}

async function saveRunpodTraining() {
  await postAPI('/api/settings/update', {runpod: {
    sfw_checkpoint: $('rpSfwCkpt').value,
    sfw_repeat: parseInt($('rpSfwRepeat').value) || 12,
    sfw_network_dim: parseInt($('rpSfwDim').value) || 48,
    sfw_lr: parseFloat($('rpSfwLr').value) || 0.0001,
    sfw_steps: parseInt($('rpSfwSteps').value) || 1500,
    nsfw_checkpoint: $('rpNsfwCkpt').value,
    nsfw_repeat: parseInt($('rpNsfwRepeat').value) || 15,
    nsfw_network_dim: parseInt($('rpNsfwDim').value) || 64,
    nsfw_lr: parseFloat($('rpNsfwLr').value) || 0.00008,
    nsfw_steps: parseInt($('rpNsfwSteps').value) || 2000,
  }});
  toast('Training params saved');
}

async function saveRunpodGen() {
  await postAPI('/api/settings/update', {runpod: {
    default_cfg: parseFloat($('rpCfg').value) || 7.0,
    sampler: $('rpSampler').value,
    use_adetailer: $('rpADetailer').checked,
    use_upscale: $('rpUpscale').checked,
  }});
  toast('Generation params saved');
}

function toggleRunpod() {
  const enabled = $('rpEnabled').checked;
  $('rpConfigFields').style.opacity = enabled ? '1' : '0.4';
  $('rpConfigFields').style.pointerEvents = enabled ? 'auto' : 'none';
  document.querySelector('#rpEnabled').nextElementSibling.innerHTML = `RunPod Integration ${enabled?'ON':'OFF'}`;
}

async function testRunpod() {
  const key = $('rpApiKey').value;
  if(!key) return toast('Enter an API key first','#f87171');
  $('rpTestResult').textContent = 'Testing...';
  const r = await postAPI('/api/runpod/test', {api_key: key});
  if(r.ok) $('rpTestResult').innerHTML = '<span style="color:#34d399">✓ Connected!</span>';
  else $('rpTestResult').innerHTML = `<span style="color:#f87171">✗ ${r.error||'Failed'}</span>`;
}

// ══════════════════ INIT ══════════════════
load();
