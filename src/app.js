import {requestWorldState, startSimulation, resetWorld, bundledDefaults} from './bridge.js';
import {W,H,drawSea,screenToWorld,hitTest,getLayout,makeIslandDragPreview} from './pixels.js';
import {mountRandomizer} from './randomizer.js';

const $ = s => document.querySelector(s);
const clone = obj => structuredClone(obj);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const asNumber = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const F = {
  island:[
    ['fertility','Fertility','number'],['food_availability','Food available','number'],
    ['wood_availability','Wood available','number'],['resource_regeneration_rate','Regeneration rate','number'],
    ['weather','Weather','text',['Cold','Temperate','Hot','Tropical','Dry','Stormy']],
    ['disease_risk','Disease risk','number'],['culture_trait','Culture','text',['Hardworking','Evil and Dramatic','Peaceful','Nomadic','Cooperative','Competitive']]
  ],
  agent:[
    ['name','Name','text'],['age','Age','number'],['occupation','Occupation','text',['farmer','hunter','builder','crafter','trader','fisher','unemployed']],
    ['personalityType','Personality','text',['Calm','Strategic','Nonchalant','Resourceful','Nice','Selfish','Intellectual','Cunning']],
    ['health','Health','number'],['wealth','Wealth','number'],['is_alive','Alive','boolean'],
    ['food','Food','number'],['wood','Wood','number'],['tools','Tools','number'],
    ['farming_skill','Farming skill','number'],['hunting_skill','Hunting skill','number'],['crafting_skill','Crafting skill','number'],
    ['cooperation_trait','Cooperation trait','number'],['aggression_trait','Aggression trait','number'],
    ['needs','Needs (JSON)','json'],['goals','Goals (JSON)','json'],['trust_graph','Trust graph (JSON)','json']
  ]
};
const mainAgentFields = F.agent.slice(0,4);
const advancedAgentFields = F.agent.slice(4);
const DEFAULT_AGENT = {agent_id:'',name:'New person',current_island_id:'',age:20,health:100,wealth:0,occupation:'farmer',is_alive:true,food:0,wood:0,tools:0,farming_skill:1,hunting_skill:1,crafting_skill:1,personalityType:'Calm',cooperation_trait:50,aggression_trait:50,needs:[],goals:[],trust_graph:{}};
const DEFAULT_ISLAND = {island_id:'',fertility:1,food_availability:1,wood_availability:1,resource_regeneration_rate:1,weather:'Temperate',disease_risk:1,culture_trait:'Peaceful'};
const MAX_ISLANDS = 7;
const MAX_PEOPLE_PER_ISLAND = 100;
const profileKey='partial-wace-profiles-v1';
let cachedProfiles;
try{cachedProfiles=JSON.parse(localStorage.getItem(profileKey)||'null')}catch{cachedProfiles=null}
const state={
  world:null,received:null,positions:{},basePositions:{},profiles:Array.isArray(cachedProfiles)&&cachedProfiles.length?cachedProfiles:[],
  associations:{},islandProfile:'island-default',activeTab:'build',openProfileId:null,selected:null,
  snapshots:[],viewIndex:null,fromBackend:false,loading:true,running:false,runSince:0,toastTimer:0,
  eventFilter:'',agentMore:false,islandCounter:0,agentCounter:0,
  seedIsDefault: false,
};
let lastMap=null;
let dragIsland=null;
let zoomIslandId = null;
const ZOOM_LEVEL = 3;
let drawTimer;
let noticeTimer;

function storeProfiles(){try{localStorage.setItem(profileKey,JSON.stringify(state.profiles))}catch{}}

/* ISLAND POSITIONS & TIME MACHINE STORAGE */

const sceneKey = 'partial-wace-scene-v1';
let waitingForRandomizedStart = false;

let previousScene = null;

try {
  previousScene = JSON.parse(
    localStorage.getItem(sceneKey) || 'null'
  );
} catch {}

// Saved coordinates may include islands with pending deletions.
let storedPositions =
  previousScene?.positions &&
  typeof previousScene.positions === 'object' &&
  !Array.isArray(previousScene.positions)
    ? clone(previousScene.positions)
    : {};

// Previous simulation snapshots.
let storedSnapshots = Array.isArray(previousScene?.snapshots)
  ? previousScene.snapshots
      .filter(s =>
        s?.world?.islands &&
        s?.world?.agents &&
        s?.positions
      )
      .map(clone)
  : [];

// Save the current screen layout and Time Machine.
function saveScene({commitDeletions = false} = {}) {
  if (waitingForRandomizedStart) return;

  if (state.world) {

    // Get the actual displayed coordinates,
    // including collision adjustments.
    for (const {id, x, y} of getLayout(
      state.world,
      state.positions
    )) {
      state.positions[id] = {x, y};
    }

    // Add/update positions, but do NOT remove missing
    // islands until Python successfully accepts a simulation.
    for (const [id, point] of Object.entries(state.positions)) {

      if (
        Number.isFinite(Number(point?.x)) &&
        Number.isFinite(Number(point?.y))
      ) {
        storedPositions[id] = {
          x: Number(point.x),
          y: Number(point.y)
        };
      }
    }
  }

  // Only commit coordinate deletions after a successful START.
  if (commitDeletions) {
    for (const id of Object.keys(storedPositions)) {
      if (!state.world?.islands?.[id]) {
        delete storedPositions[id];
      }
    }
  }

  try {
    localStorage.setItem(
      sceneKey,
      JSON.stringify({
        positions: storedPositions,
        snapshots: state.snapshots,
        seedIsDefault: state.seedIsDefault
      })
    );
  } catch (error) {
    console.warn(
      'Could not save island positions / Time Machine history:',
      error
    );
  }
}

// Wipe this simulation's saved visual state.
function clearSceneStorage() {
  storedPositions = {};
  storedSnapshots = [];

  state.positions = {};
  state.snapshots = [];

  try {
    localStorage.removeItem(sceneKey);
  } catch {}
}


/* DETECT A NEW PYTHON SESSION */

const bridgeRunKey = 'partial-wace-bridge-run-v1';

async function checkBridgeSession() {
  try {
    const response = await fetch('/api/health', {
      cache: 'no-store'
    });

    if (!response.ok) return;

    const info = await response.json();
    const currentRun = info.run_id;

    if (!currentRun) return;

    const previousRun = localStorage.getItem(bridgeRunKey);

    if (previousRun !== currentRun) {
      // Python has started a new session.
      // Discard the previous session's visual state.
      clearSceneStorage();

      state.seedIsDefault = true;

      localStorage.setItem(bridgeRunKey, currentRun);

      console.log(
        'New Python session: island positions and history cleared.'
      );

    } else {
      // Same Python session: this is just a browser load/reload.
      // Keep the existing history, positions and seed display.
      state.seedIsDefault =
        Boolean(previousScene?.seedIsDefault);
    }

  } catch (error) {
    console.warn(
      'Could not check Python session:',
      error
    );
  }
}


function isViewingHistory(){return state.viewIndex !== null;}
function worldShown(){return isViewingHistory()?state.snapshots[state.viewIndex]?.world:state.world;}
function editable(){if(state.running||state.loading)return false;if(isViewingHistory()){toast('Restore this snapshot before editing it.');return false;}return true;}
function toast(message){const el=$('#toast');el.textContent=message;el.hidden=false;clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>el.hidden=true,3800);}
function mapMessage(message){const el=$('#mapMessage');el.textContent=message;el.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>el.hidden=true,3100);}
function pById(id){return state.profiles.find(p=>p.id===id);}
function profilesFor(type){return state.profiles.filter(p=>p.kind===type);}
function defaultProfile(type){return profilesFor(type)[0];}
function generateProfiles(world){
  if(state.profiles.length)return;
  const island=Object.values(world.islands||{})[0]||DEFAULT_ISLAND;
  const agent=Object.values(world.agents||{})[0]||DEFAULT_AGENT;
  state.profiles=[
    {id:'island-default',name:'Default island',kind:'island',params:pickProfile(island,'island')},
    {id:'agent-default',name:'Default person',kind:'agent',params:pickProfile(agent,'agent')},
  ];
  state.islandProfile='island-default';storeProfiles();
}
function pickProfile(source,kind){const base=kind==='island'?DEFAULT_ISLAND:DEFAULT_AGENT;
  const out={};for(const [key] of F[kind])out[key]=clone(source?.[key]??base[key]);return out;
}
function ensureProfiles(){
  if(!profilesFor('island').length)state.profiles.unshift({id:'island-default',name:'Default island',kind:'island',params:pickProfile(DEFAULT_ISLAND,'island')});
  if(!profilesFor('agent').length)state.profiles.push({id:'agent-default',name:'Default person',kind:'agent',params:pickProfile(DEFAULT_AGENT,'agent')});
  if(!pById(state.islandProfile))state.islandProfile=defaultProfile('island').id;
}
function emptyState(){return {current_year:1,max_years:30,active_seed:42,scarcity_level:0.5,price_index:{food:1,wood:1,tools:5},islands:{},agents:{},event_history:[]};}
function normalizeWorld(raw){
  const w=clone(raw||emptyState());w.islands ||= {};w.agents ||= {};w.event_history ||= [];
  w.price_index ||= {food:1,wood:1,tools:5};
  w.current_year ??= 1;
  w.max_years ??= 30;
  w.active_seed ??= 42;

  const legacyScarcity = {
    low: 0.2,
    moderate: 0.5,
    high: 0.8,
    extreme: 1.0
  };

  const rawScarcity = w.scarcity_level ?? 0.5;

  const numericScarcity =
    typeof rawScarcity === 'string' &&
    rawScarcity.toLowerCase() in legacyScarcity
      ? legacyScarcity[rawScarcity.toLowerCase()]
      : Number(rawScarcity);

  w.scarcity_level = Number.isFinite(numericScarcity)
    ? Math.round(
        Math.max(0, Math.min(1, numericScarcity)) * 10
      ) / 10
    : 0.5;

  return w;
}
function seedPositions(world,reset=false){
  const ids=Object.keys(world?.islands||{});
  const next=reset?{}:{...state.positions};
  ids.forEach((id,i)=>{
    if(next[id])return;
    // Pre-spread evenly over a sea grid before overlap relaxation.
    const n=ids.length,cols=Math.max(1,Math.ceil(Math.sqrt(n*1.5)));
    const rows=Math.ceil(n/cols),col=i%cols,row=Math.floor(i/cols);
    next[id]={x:W*(col+1)/(cols+1),y:H*(row+1)/(rows+1)};
  });
  for(const id of Object.keys(next))if(!ids.includes(id))delete next[id];
  state.positions=next;
}

function receivedState(world, origin) {

  const normalized = normalizeWorld(world);
  const previousAssociations = state.associations;

  state.world = normalized;
  state.received = clone(normalized);
  state.viewIndex = null;

  generateProfiles(normalized);
  ensureProfiles();

  state.associations = {};
  const defaultId = defaultProfile('agent')?.id;

  for (const id of Object.keys(normalized.agents)) {
    state.associations[id] =
      previousAssociations[id] && pById(previousAssociations[id])
        ? previousAssociations[id]
        : defaultId;
  }

  // On page load, recover the saved island positions.
  if (origin === 'initial') {
    state.positions = clone(storedPositions);
  }

  // Supply grid coordinates only for islands without saved positions.
  seedPositions(normalized, false);

  // Resolve overlaps and store the actual displayed coordinates.
  for (const {id, x, y} of getLayout(
    normalized,
    state.positions
  )) {
    state.positions[id] = {x, y};
  }

  state.basePositions = clone(state.positions);

  // Capture the Python-provided state for the Time Machine.
  const snapshot = {
    world: clone(normalized),
    positions: clone(state.positions),
    label: `Year ${normalized.current_year}`
  };

  if (origin === 'initial') {

    // Recover the previous Time Machine on page reload.
    state.snapshots = storedSnapshots.map(clone);

    const last = state.snapshots.at(-1);

    // Avoid recording the same state again just because
    // the browser refreshed.
    if (
      !last ||
      JSON.stringify(last.world) !== JSON.stringify(normalized)
    ) {
      state.snapshots.push(snapshot);
    }

  } else {

    // A simulation completed: record its actual returned state.
    state.snapshots.push(snapshot);

  }

  const firstIslandId = Object.keys(normalized.islands)[0];

  state.selected =
    state.selected && entityExists(state.selected, normalized)
      ? state.selected
      : firstIslandId
        ? {type: 'island', id: firstIslandId}
        : null;

  state.loading = false;
  state.running = false;

  renderAll();
}
function entityExists(s,w){return s?.type==='island'?!!w?.islands?.[s.id]:!!w?.agents?.[s?.id];}
function payload(){
  const w=clone(state.world);
  const original=state.received||emptyState();
  w.deleted_island_ids=Object.keys(original.islands||{}).filter(id=>!w.islands[id]);
  w.deleted_agent_ids=Object.keys(original.agents||{}).filter(id=>!w.agents[id]);
  return w;
}
// Visible to your hosting Python bridge's integration tests/devtools, no data changes.
window.PartialWace={getPayload:payload,getState:()=>clone(state.world),receiveWorld:(world)=>receivedState(world,'simulation')};
async function loadApp(){
  state.loading=true;
  updateStatus('CONNECTING...','busy');
  await checkBridgeSession();
  try{
    const world=await requestWorldState();state.fromBackend=true;receivedState(world,'initial');updateStatus('PYTHON CONNECTED','online');
  }catch(e){
    try{
      const world=await bundledDefaults();state.fromBackend=false;receivedState(world,'initial');
      updateStatus('BUNDLED DEFAULTS / OFFLINE','offline');
      mapMessage('Python bridge unavailable. Showing defaults.py data.');
      console.info('Python bridge unavailable, using exact bundled defaults:',e);
    }catch(f){state.world=emptyState();state.received=clone(state.world);state.loading=false;generateProfiles(state.world);ensureProfiles();seedPositions(state.world,true);state.snapshots=[{world:clone(state.world),positions:{},label:'Year 1'}];updateStatus('NO PYTHON CONNECTION','offline');renderAll();toast('Could not load Python state or bundled defaults.');console.error(e,f);}
  }
}
function updateStatus(message,mode){const el=$('#connectionStatus');el.textContent=message;el.className=`status-tag ${mode}`;}
async function startRun(){
  if(!editable())return;
  if(!state.fromBackend){toast('Connect your Python transport first; no simulation is fabricated offline.');return;}
  const sent = payload();

  // Remember the starting world, but do not save it yet.
  // Only needed for the first simulation after Randomize.
  const startingSnapshot = waitingForRandomizedStart
    ? {
        world: clone(state.world),
        positions: clone(state.positions),
        label: `Year ${state.world.current_year}`
      }
    : null;

  state.running = true;
  state.runSince = performance.now();
  updateStatus('PYTHON RUNNING...', 'busy');
  renderAll();
  let result,err;
  try{result=await startSimulation(sent);}catch(e){err=e;}
  const timeLeft=Math.max(0,2550-(performance.now()-state.runSince));
  if(timeLeft)await new Promise(r=>setTimeout(r,timeLeft));
  state.running=false;
  if(err){updateStatus('PYTHON ERROR','offline');toast(`Python simulation failed: ${err.message}`);renderAll();return;}
  state.fromBackend = true;

  // If this is the first simulation after Randomize,
  // add the starting world to the Time Machine.
  if (startingSnapshot) {
    state.snapshots = [startingSnapshot];
  }

  // Saving can resume now that Python succeeded.
  waitingForRandomizedStart = false;

  state.seedIsDefault = false;

  // This automatically appends the returned Year 2 snapshot.
  receivedState(result, 'simulation');

  // Persist both snapshots and the island coordinates.
  saveScene({commitDeletions: true});

  updateStatus('PYTHON CONNECTED', 'online');

  mapMessage(
    `Received new state - Year ${state.world.current_year}`
  );
}

async function reset() {

  if (state.running) return;

  state.loading = true;
  updateStatus('REQUESTING RESET...', 'busy');
  renderAll();

  try {

    const world = await resetWorld();

    state.fromBackend = true;
    state.associations = {};
    state.selected = null;

    // Reset succeeded. Discard the previous scene and history.
    clearSceneStorage();

    waitingForRandomizedStart = false;

    state.seedIsDefault = true;

    // Return the camera to the full world view.
    zoomIslandId = null;

    receivedState(world, 'initial');

    updateStatus('PYTHON CONNECTED', 'online');
    toast('World reset from Python. Saved history cleared.');

  } catch (e) {

    try {

      const world = await bundledDefaults();

      state.fromBackend = false;
      state.associations = {};
      state.selected = null;

      // Use a fresh scene if resetting from bundled defaults.
      clearSceneStorage();

      waitingForRandomizedStart = false;

      // Return the camera to the full world view.
      zoomIslandId = null;

      receivedState(world, 'initial');

      updateStatus('BUNDLED DEFAULTS / OFFLINE', 'offline');

      toast('Loaded bundled defaults. Saved history cleared.');

    } catch {

      state.loading = false;
      renderAll();
      toast(`Reset failed: ${e.message}`);

    }
  }
}
function nextId(kind){const prefix=kind==='island'?'i':'a',items=kind==='island'?state.world.islands:state.world.agents;
  let n=Math.max(0,...[...Object.keys(items),...Object.keys(kind==='island'?(state.received?.islands||{}):(state.received?.agents||{}))].map(k=>new RegExp(`^${prefix}(\\d+)$`).exec(k)?.[1]).filter(Boolean).map(Number));
  const key=kind==='island'?'islandCounter':'agentCounter';
  n=Math.max(n,state[key]);let id;do{id=prefix+(++n);}while(items[id]);state[key]=n;return id;
}
function addIsland(pos){
  if(!editable())return;
  if (Object.keys(state.world.islands).length >= MAX_ISLANDS) {
    toast('Maximum of 7 islands reached.');
    return;
  }
  const p=pById(state.islandProfile)||defaultProfile('island');
  const id=nextId('island');const params=clone(p.params);
  const island={...params,island_id:id};
  island.attributeDictionary=Object.fromEntries(Object.entries(island).filter(([key])=>key!=='attributeDictionary'));
  state.world.islands[id]=island;
  state.positions[id]={x:Math.min(W-50,Math.max(50,Number(pos?.x)||W*(.25+Math.random()*.5))),y:Math.min(H-50,Math.max(50,Number(pos?.y)||H*(.25+Math.random()*.5)))};
  state.selected={type:'island',id};renderAll();mapMessage(`Added ${id}, ${p.name}`);
}
function addAgent(profileId,islandId){
  if(!editable())return;
  const p=pById(profileId)||defaultProfile('agent');
  if(!p||!state.world.islands[islandId]){toast('Drop people on an island, not in the sea.');return;}
  const residents = Object.values(state.world.agents)
    .filter(a => a.current_island_id === islandId);

  if (residents.length >= MAX_PEOPLE_PER_ISLAND) {
    toast('This island already has 100 people.');
    return;
  }
  const id=nextId('agent');const person={...clone(DEFAULT_AGENT),...clone(p.params),agent_id:id,current_island_id:islandId};
  if(!person.name||person.name==='New person')person.name=`Settler ${id.slice(1)}`;
  state.world.agents[id]=person;state.associations[id]=p.id;
  renderAll();mapMessage(`${person.name} joined ${islandId}`);
}
function deleteAgent(id){if(!editable())return;delete state.world.agents[id];delete state.associations[id];if(state.selected?.type==='agent'&&state.selected?.id===id)state.selected=null;renderAll();}
function deleteIsland(id){if(!editable())return;for(const a of Object.values(state.world.agents))if(a.current_island_id===id){delete state.world.agents[a.agent_id];delete state.associations[a.agent_id];}delete state.world.islands[id];delete state.positions[id];state.selected=null;renderAll();mapMessage(`${id} removed (including its people)`);}
function setPopulation(islandId, profileId, count) {
  if (!editable()) return;

  const residents = Object.values(state.world.agents)
    .filter(a => a.current_island_id === islandId);

  const current = residents.filter(
    a => state.associations[a.agent_id] === profileId
  );

  const target = Math.max(
    0,
    Math.min(MAX_PEOPLE_PER_ISLAND, Math.trunc(asNumber(count)))
  );

  const additional = target - current.length;

  if (
    additional > 0 &&
    residents.length + additional > MAX_PEOPLE_PER_ISLAND
  ) {
    toast('Maximum of 100 people per island.');
    renderInspector();
    return;
  }

  if (target > current.length) {
    for (let n = current.length; n < target; n++) {
      addAgentQuiet(profileId, islandId);
    }
  } else if (target < current.length) {
    for (const a of current.slice(target)) {
      delete state.world.agents[a.agent_id];
      delete state.associations[a.agent_id];
    }
  }

  renderAll();
}
function addAgentQuiet(profileId,islandId){const p=pById(profileId)||defaultProfile('agent'),id=nextId('agent');
  const agent={...clone(DEFAULT_AGENT),...clone(p.params),agent_id:id,current_island_id:islandId};
  if(!agent.name||agent.name==='New person')agent.name=`Settler ${id.slice(1)}`;
  state.world.agents[id]=agent;state.associations[id]=p.id;
}
function select(type, id) {
  const w = worldShown();

  if (!(type === 'island' ? w?.islands?.[id] : w?.agents?.[id])) {
    return;
  }

  state.selected = {type, id};
  renderInspector();
  renderMapLabels();
}
function focusedIslandId() {
  const w = worldShown();
  const selected = state.selected;

  if (!w || !selected) return null;

  if (selected.type === 'island') {
    return w.islands[selected.id] ? selected.id : null;
  }

  if (selected.type === 'agent') {
    const islandId =
      w.agents[selected.id]?.current_island_id;

    return w.islands[islandId] ? islandId : null;
  }

  return null;
}

function updateZoom(layout) {
  const canvas = $('#seaCanvas');

  if (!zoomIslandId) {
    canvas.style.transform = 'none';
    return;
  }

  const island = layout.find(i => i.id === zoomIslandId);

  if (!island) {
    zoomIslandId = null;
    canvas.style.transform = 'none';
    return;
  }

  const z = ZOOM_LEVEL;

  // Prevent the camera from looking beyond the sea edges.
  const focusX = Math.max(
    W / (2 * z),
    Math.min(W - W / (2 * z), island.x)
  );

  const focusY = Math.max(
    H / (2 * z),
    Math.min(H - H / (2 * z), island.y)
  );

  const offsetX = (0.5 - z * focusX / W) * 100;
  const offsetY = (0.5 - z * focusY / H) * 100;

  canvas.style.transform =
    `translate(${offsetX}%, ${offsetY}%) scale(${z})`;
}
function renderAll(){
  renderBuildTabs();
  renderInspector();
  renderTimeline();
  renderMapLabels();

  saveScene();
}
function renderMapLabels(){
  const w=worldShown()||emptyState();
  const n=Object.keys(w.islands).length,nA=Object.keys(w.agents).length;
  const agents = Object.values(w.agents);

  const totalWealth = agents.reduce(
    (sum, a) => sum + asNumber(a.wealth),
    0
  );

  const living = agents.filter(a => a.is_alive !== false);

  const averageHealth = living.length
    ? living.reduce((sum, a) => sum + asNumber(a.health), 0)
        / living.length
    : null;

  $('#worldWealth').textContent = new Intl.NumberFormat('en-GB', {
    maximumFractionDigits: 1
  }).format(totalWealth);

  $('#worldHealth').textContent = averageHealth === null
    ? '—'
    : `${averageHealth.toFixed(1)}%`;
  $('#mapSummary').textContent=`${n} island${n===1?'':'s'} - ${nA} peopl${nA===1?'e':'e'}`;
  if (zoomIslandId && !w.islands[zoomIslandId]) {
    zoomIslandId = null;
  }

  const zoomButton = $('#zoomBtn');

  zoomButton.disabled = !zoomIslandId && !focusedIslandId();

  zoomButton.textContent = zoomIslandId
    ? '− WORLD VIEW'
    : '+ ZOOM TO ISLAND';
  $('#mapCorner').textContent =
    isViewingHistory()
      ? `ARCHIVE - YEAR ${w.current_year}`
      : state.running
        ? 'FAST-FORWARD'
        : `SEED ${state.seedIsDefault ? '-' : w.active_seed}`;
  $('#yearLabel').textContent=`YEAR ${w.current_year} / ${w.max_years}`;
  $('#emptyHint').hidden=n!==0;
  $('#mapLoading').hidden=!state.running;
  $('#startBtn').disabled=state.loading||state.running||isViewingHistory();
  $('#startBtn').innerHTML=state.running?'<span class="play-icon">-></span> Simulating...':'<span class="play-icon">-></span> Start simulation';
  $('#resetBtn').disabled=state.running||state.loading;
  $('#randomizeBtn').disabled =
    state.running ||
    state.loading ||
    isViewingHistory() ||
    !randomizer?.ready;
  $('#randomizeOptionsBtn').disabled =
    state.running ||
    state.loading ||
    !randomizer?.ready;
  $('#logCount').textContent=(w.event_history||[]).length;
}
function renderTimeline(){const tl=$('#timeline');tl.innerHTML=state.snapshots.map((s,i)=>{
  const latest=i===state.snapshots.length-1;
  const active=(state.viewIndex===null&&latest)||(state.viewIndex===i);
  return `<button type="button" class="timeline-step ${active?'current':''} ${state.viewIndex===i?'viewing':''}" data-view-index="${i}">${String(i+1).padStart(2,'0')} / ${esc(s.label)}</button>`;
}).join('');$('#restoreBtn').hidden=!isViewingHistory();
  $('#timelineNote').textContent=isViewingHistory()?`Viewing snapshot ${state.viewIndex+1}. Restore to branch from this state, or click the last snapshot to return.`:
    state.snapshots.length>1?'Snapshots are local views of actual states received from Python. No intermediate years are invented.':'Start simulation to record a returned state. The fast-forward animation does not calculate data.';
}
function fieldMarkup([key,label,type,options],value,entity,kind,id){
  const fieldKey=kind==='profile'?'data-profile-field':kind==='world'?'data-world-field':'data-entity-field';
  const meta=`${fieldKey}="${esc(key)}" ${kind==='profile'?`data-profile-id="${esc(id)}"`:kind==='world'?'':`data-entity-type="${esc(entity)}" data-entity-id="${esc(id)}"`}`;
  const display=value===undefined?'':type==='json'?JSON.stringify(value):String(value);
  const opts=options?.length?`list="opts-${esc(key)}"`:'';
  const input=type==='boolean'?`<select class="field-input" ${meta}><option value="true" ${value===true?'selected':''}>Yes</option><option value="false" ${value===false?'selected':''}>No</option></select>`:
    type==='json'?`<textarea class="field-input" style="height:58px;resize:vertical" ${meta}>${esc(display)}</textarea>`:
    `<input class="field-input" type="${type==='number'?'number':'text'}" ${type==='number'?'step="any"':''} value="${esc(display)}" ${opts} ${meta}/>`;
  return `<label class="row-field"><span class="field-label">${esc(label)}</span>${input}</label>`;
}
function optionsDatalist(){const entries=new Map();for(const category of Object.values(F))for(const [key,,type,options] of category)if(type==='text'&&options?.length)entries.set(key,options);
  return Array.from(entries.entries()).map(([key,opts])=>`<datalist id="opts-${esc(key)}">${opts.map(o=>`<option value="${esc(o)}"></option>`).join('')}</datalist>`).join('');
}
function renderBuildTabs(){
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.tab===state.activeTab));
  const el=$('#leftContent');let html='';
  if(state.activeTab==='build'){
    const w=worldShown()||emptyState();
    html=`<div class="section"><div class="section-head"><span class="section-title"><span class="num">01 /</span> NEW LAND</span><span class="badge-counter">DRAG + DROP</span></div>
      <div class="place-card" id="islandDrag" draggable="true" role="button" tabindex="0"><span class="tile-icon land"></span><div><strong>Place an island</strong><small>drag into the sea</small></div></div>
      <label class="row-field"><span class="field-label">Island profile for new land</span><select id="activeIslandProfile" class="field-input">${profilesFor('island').map(p=>`<option value="${esc(p.id)}" ${p.id===state.islandProfile?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label>
      <button class="full-btn" data-action="place-island" type="button">+ PLACE ISLAND IN SEA</button><p class="section-note">One profile at a time. Change it before placing the next island.</p></div>
      <div class="section"><div class="section-head"><span class="section-title"><span class="num">02 /</span> NEW PEOPLE</span><span class="badge-counter">${profilesFor('agent').length} TYPES</span></div>
      ${profilesFor('agent').map((p,i)=>`<div class="person-tool" draggable="true" data-person-drag="${esc(p.id)}" tabindex="0"><span class="mini-person" style="--shirt:${['#5d8981','#b47668','#968358','#7b8795'][i%4]}"></span><span class="grow ellipsis"><strong class="ellipsis">${esc(p.name)}</strong><small>drag onto an island -></small></span><span class="mini-arrow">⋮⋮</span></div>`).join('')}
      <p class="section-note">Or click an island and set how many of each profile should live there.</p></div>
      <div class="section"><div class="section-head"><span class="section-title"><span class="num">03 /</span> WORLD SETTINGS</span></div>
      ${fieldMarkup(['current_year','Current year','number'],w.current_year,'','world')}
      ${fieldMarkup(['max_years','Max years','number'],w.max_years,'','world')}
      ${state.seedIsDefault && !isViewingHistory()
        ? `<label class="row-field">
            <span class="field-label">Seed</span>
            <input
              class="field-input"
              type="number"
              step="any"
              placeholder="-"
              value=""
              data-world-field="active_seed"
            />
          </label>`
        : fieldMarkup(['active_seed','Seed','number'],w.active_seed,'','world')}
      <label class="row-field">
        <span class="field-label">Scarcity (0.0–1.0)</span>
        <input
          class="field-input"
          type="number"
          min="0"
          max="1"
          step="0.1"
          value="${Number(w.scarcity_level).toFixed(1)}"
          data-world-field="scarcity_level"
        />
      </label>
      <div class="divider-caption">PRICE INDEX</div>
      ${Object.entries(w.price_index||{}).map(([k,v])=>fieldMarkup([`price_index.${k}`,k.charAt(0).toUpperCase()+k.slice(1),'number'],v,'','world')).join('')}
      <div class="divider-line"></div><div class="subtle-note">World data stays local until START is pressed. Deletions of IDs received from Python are included in that request.</div>${optionsDatalist()}</div>`;
  }else if(state.activeTab==='profiles'){
    html=`<div class="section"><div class="section-title">REUSABLE BLUEPRINTS</div><p class="section-note">Blueprints affect <b>new</b> islands and people. Existing objects keep their own parameters.</p></div>`;
    for(const kind of ['island','agent']){
      html+=`<div class="section"><div class="section-head"><span class="section-title">${kind==='island'?'ISLAND':'PERSON'} PROFILES</span><span class="badge-counter">${profilesFor(kind).length}</span></div>`;
      for(const p of profilesFor(kind)){
        const open=state.openProfileId===p.id;
        html+=`<div class="profile-row"><div class="profile-header"><div class="grow"><strong class="ellipsis" style="display:block;font:700 12px var(--mono)">${esc(p.name)}</strong><small class="profile-meta">${kind==='island'?'Land blueprint':'Person blueprint'}</small></div><div class="profile-actions"><button class="tiny-btn" data-action="edit-profile" data-id="${esc(p.id)}" title="Edit profile">${open?'−':'✎'}</button>${profilesFor(kind).length>1?`<button class="tiny-btn danger" data-action="delete-profile" data-id="${esc(p.id)}" title="Delete profile">×</button>`:''}</div></div>`;
        if(open)html+=`<div class="profile-form"><label class="row-field"><span class="field-label">Profile name</span><input class="field-input" data-profile-name="${esc(p.id)}" value="${esc(p.name)}"></label>${F[kind].map(f=>fieldMarkup(f,p.params[f[0]],'','profile',p.id)).join('')}</div>`;
        html+='</div>';
      }
      html+=`<button class="add-profile" data-action="create-profile" data-kind="${kind}">+ NEW ${kind==='island'?'ISLAND':'PERSON'} PROFILE</button></div>`;
    }
    html+=optionsDatalist();
  }else html=eventsHTML(worldShown()||emptyState());
  el.innerHTML=html;
}
function eventsHTML(w){
  const entries=(w.event_history||[]).map((e,i)=>({...e,_index:i})).filter(e=>
    !state.eventFilter||`${e.event_type||''} ${e.description||''} ${e.primary_agent_id||''}`.toLowerCase().includes(state.eventFilter.toLowerCase()));
  return `<div class="section"><div class="section-head"><span class="section-title">EVENT HISTORY</span><span class="badge-counter">${(w.event_history||[]).length} ENTRIES</span></div><input id="eventSearch" class="field-input" placeholder="Filter events..." value="${esc(state.eventFilter)}"/><p class="section-note">Logged by Python. Click a person to inspect them.</p></div><div class="section" style="border-bottom:0">${entries.length?entries.slice().reverse().map(e=>eventHTML(e,w)).join(''):'<p class="subtle-note">No events to show yet. After a simulation, any returned <code>event_history</code> entries will appear here.</p>'}</div>`;
}
function eventHTML(e,w){
  const people=Object.values(w.agents||{}),lookup=new Map(people.map(p=>[p.agent_id,p]));
  const linkFor=id=>lookup.has(id)?`<button class="agent-link" data-agent-link="${esc(id)}">${esc(lookup.get(id).name||id)}</button>`:esc(id);
  const text=String(e.description??'');
  const tokens=people.flatMap(p=>[p.name,p.agent_id].filter(Boolean).map(name=>({name,id:p.agent_id}))).sort((a,b)=>b.name.length-a.name.length);
  // Keep track of everyone mentioned in the description.
  const mentionedIds = new Set();
  
  // Find people mentioned in the event description.
  // Make their names clickable and remember their IDs.
  let linked = '';
  let remaining = text;

  while (remaining.length) {

    const candidates = tokens
      .map(t => ({
        ...t,
        at: remaining.toLowerCase().indexOf(
          String(t.name).toLowerCase()
        )
      }))
      .filter(t => t.at >= 0);

    if (!candidates.length) {
      linked += esc(remaining);
      break;
    }

    candidates.sort(
      (a, b) => a.at - b.at || b.name.length - a.name.length
    );

    const next = candidates[0];

    // Remember this person for the PEOPLE field.
    mentionedIds.add(next.id);

    // Keep the existing clickable links in the description.
    linked += esc(remaining.slice(0, next.at));
    linked += linkFor(next.id);

    remaining = remaining.slice(next.at + next.name.length);
  }

  const payload =
    e.payload && typeof e.payload === 'object'
      ? e.payload
      : {};

  const ids = new Set([
    e.primary_agent_id,

    ...[
      'agent_id',
      'target_agent_id',
      'other_agent_id',
      'secondary_agent_id'
    ].map(k => payload[k]),

    ...(Array.isArray(payload.participants)
      ? payload.participants
      : []),

    // Include everyone mentioned in the description.
    ...mentionedIds
  ]);

  const linkedPeople = [...ids].filter(
    id => lookup.has(id)
  );

  return `<article class="event-card"><div class="event-meta">YEAR ${esc(e.year??'?')} / EVENT ${String((e._index||0)+1).padStart(3,'0')}</div><div class="event-title">${esc(e.event_type||'Event')}</div><div class="event-text">${linked||'<span class="muted">No description</span>'}</div>${linkedPeople.length?`<div class="divider-caption">PEOPLE: ${linkedPeople.map(linkFor).join(', ')}</div>`:''}</article>`;
}
function renderInspector(){
  const w=worldShown()||emptyState(),s=state.selected;
  if(!s||!entityExists(s,w)){
    $('#inspectorTitle').textContent='Inspector';$('#inspectFoot').textContent='CLICK A PATCH OF LAND TO EDIT';
    $('#inspectorContent').innerHTML=`<div class="no-selection"><div class="ascii">- - -</div>Nothing selected.<br/>Click a patch of land<br/>or one of the tiny people.</div>`;
    return;
  }
  if(s.type==='island')renderIslandInspector(w,s.id);else renderAgentInspector(w,s.id);
}
function renderIslandInspector(w,id){
  const island=w.islands[id];if(!island)return;
  const agents=Object.values(w.agents).filter(a=>a.current_island_id===id);
  const alive=agents.filter(a=>a.is_alive!==false).length;
  $('#inspectorTitle').textContent=`Island ${id}`;$('#inspectFoot').textContent='EVERY EDIT STAYS LOCAL UNTIL START';
  let html=`<div class="inspector-hero"><div class="hero-swatch">#</div><div class="hero-info"><strong>${esc(id)} <span style="font-weight:400">/ land</span></strong><small>${alive} resident${alive===1?'':'s'}, ${esc(island.weather||'Unknown')} weather<br>${esc(island.culture_trait||'No culture')}</small></div></div>`;
  html+=`<div class="inspector-section"><h3>ISLAND PARAMETERS <span> / editable</span></h3><div class="form-grid">${F.island.map((f,i)=>`<div class="${f[2]==='text'?'span2':''}">${fieldMarkup(f,island[f[0]],'island','entity',id)}</div>`).join('')}</div>${optionsDatalist()}</div>`;
  html+=`<div class="inspector-section"><h3>POPULATION <span> / ${agents.length} total</span></h3><div class="subtle-note">Set a total for each profile. New people inherit that profile's parameters.</div>`;
  for(const p of profilesFor('agent')){
    const count=agents.filter(a=>state.associations[a.agent_id]===p.id).length;
    html+=`<div class="population-row"><div class="population-title ellipsis">${esc(p.name)}<small>${esc(p.params.occupation||'Person')}</small></div><div class="stepper"><button class="tiny-btn" data-action="population-minus" data-island="${esc(id)}" data-profile="${esc(p.id)}" title="Remove person">−</button><input type="number" min="0" max="100" class="field-input" style="width:45px;height:26px;text-align:center;padding:2px" data-population-count="${esc(p.id)}" data-island="${esc(id)}" value="${count}" aria-label="Count of ${esc(p.name)}"/><button class="tiny-btn" data-action="population-plus" data-island="${esc(id)}" data-profile="${esc(p.id)}" title="Add person">+</button></div></div>`;
  }
  html+='</div>';
  html+=`<div class="inspector-section"><h3>RESIDENT LIST <span> / click to inspect</span></h3>${agents.length?agents.map((a,i)=>`<div class="person-item" data-select-agent="${esc(a.agent_id)}"><span class="mini-person" style="--shirt:${['#628e7e','#b67864','#91947c'][i%3]}"></span><div class="grow ellipsis"><strong class="ellipsis">${esc(a.name||a.agent_id)}</strong><small>${esc(a.agent_id)}, ${esc(a.occupation||'unknown')}${a.is_alive===false?', deceased':''}</small></div><span class="mini-arrow">›</span></div>`).join(''):'<p class="subtle-note">Nobody lives here. Add a few above.</p>'}</div>`;
  html+=`<div class="inspector-section"><button class="danger-btn" data-action="delete-island" data-id="${esc(id)}">X REMOVE ISLAND + RESIDENTS</button></div>`;
  $('#inspectorContent').innerHTML=html;
}
function renderAgentInspector(w,id){const a=w.agents[id];if(!a)return;
  $('#inspectorTitle').textContent=a.name||id;$('#inspectFoot').textContent=`PERSON ${id}, PYTHON SCHEMA`;
  const islandName=w.islands[a.current_island_id]?a.current_island_id:'Not assigned';
  
  let html = `
    <div class="inspector-hero">

      <div class="hero-swatch agent">
        <span class="mini-person"></span>
      </div>

      <div class="hero-info">

        <strong>${esc(a.name || id)}</strong>

        <small>
          ${esc(id)}, ${esc(islandName)}<br>
          ${esc(a.occupation || 'Unknown')}, age ${esc(a.age)}
        </small>

        <div class="agent-vitals">

          <div class="agent-vital">
            <span>HEALTH</span>
            <b>${asNumber(a.health).toFixed(1)}%</b>
          </div>

          <div class="agent-vital">
            <span>WEALTH</span>
            <b>${asNumber(a.wealth).toFixed(1)}</b>
          </div>

        </div>

      </div>

    </div>
  `;

  
  // Display the person's trust relationships using names.
  const trustEntries = Object.entries(a.trust_graph || {})
    .sort((a, b) => Number(b[1]) - Number(a[1]));

  html += `
    <div class="trust-panel">

      <div class="trust-heading">
        <strong>TRUSTS:</strong>
        <span>${trustEntries.length} connections</span>
      </div>

      ${
        trustEntries.length
          ? trustEntries.map(([agentId, score]) => {

              const other = w.agents[agentId];
              const name = other?.name || agentId;

              const scoreText = Number.isFinite(Number(score))
                ? Number(score).toFixed(0) + '/100'
                : String(score);

              return `
                <div class="trust-row">

                  <div class="trust-person-info">

                    ${
                      other
                        ? `<button
                             type="button"
                             class="trust-person-link"
                             data-select-agent="${esc(agentId)}"
                           >${esc(name)}</button>`
                        : `<span>${esc(name)} (not in world)</span>`
                    }

                    <small>${esc(agentId)}</small>

                  </div>

                  <strong class="trust-score">
                    ${esc(scoreText)}
                  </strong>

                </div>
              `;

            }).join('')
          : `<div class="trust-empty">
               No trust relationships recorded.
             </div>`
      }

    </div>
  `;

  html+=`<div class="inspector-section"><h3>PERSON PARAMETERS</h3><div class="form-grid">${mainAgentFields.map(f=>`<div class="${f[2]==='text'?'span2':''}">${fieldMarkup(f,a[f[0]],'agent','entity',id)}</div>`).join('')}<div class="span2"><label class="row-field"><span class="field-label">Current island</span><select class="field-input" data-entity-field="current_island_id" data-entity-type="agent" data-entity-id="${esc(id)}">${Object.keys(w.islands).map(i=>`<option ${a.current_island_id===i?'selected':''} value="${esc(i)}">${esc(i)}</option>`).join('')}</select></label></div></div><button class="full-btn" data-action="toggle-advanced">${state.agentMore?'− HIDE':'＋ SHOW'} EXTRA PYTHON ATTRIBUTES</button></div>`;
  if(state.agentMore)html+=`<div class="inspector-section"><h3>EXTRA ATTRIBUTES</h3>${advancedAgentFields.map(f=>fieldMarkup(f,a[f[0]],'agent','entity',id)).join('')}</div>`;
  html+=`<div class="inspector-section"><button class="full-btn" data-action="back-island" data-id="${esc(a.current_island_id)}"><- BACK TO ${esc(a.current_island_id)}</button><button style="margin-top:9px" class="danger-btn" data-action="delete-agent" data-id="${esc(id)}">× REMOVE THIS PERSON</button></div>`;
  $('#inspectorContent').innerHTML=html+optionsDatalist();
}
function changeField(el){
  if(!editable()){renderAll();return;}
    if (
    el.dataset.worldField === 'active_seed' &&
    el.value.trim() === ''
  ) {
    renderAll();
    return;
  }
  const valueOf=()=>{
    const type=el.getAttribute('type');
    if(el.tagName==='SELECT'&&(el.value==='true'||el.value==='false'))return el.value==='true';
    if(type==='number')return asNumber(el.value);
    if(el.tagName==='TEXTAREA')try{return JSON.parse(el.value)}catch{toast('Invalid JSON field. Change not saved.');return undefined;}
    return el.value;
  };
  let value = valueOf();
  if (value === undefined) return;

  if (el.dataset.worldField === 'scarcity_level') {
    const n = Number(el.value);

    if (
      el.value.trim() === '' ||
      !Number.isFinite(n) ||
      n < 0 ||
      n > 1
    ) {
      toast('Scarcity must be between 0.0 and 1.0.');
      renderAll();
      return;
    }

    value = Math.round(n * 10) / 10;
  }
  if(el.dataset.entityField){
    const type=el.dataset.entityType,id=el.dataset.entityId,key=el.dataset.entityField;
    const thing=type==='island'?state.world.islands[id]:state.world.agents[id];
    if(!thing)return;
    if (
      type === 'agent' &&
      key === 'current_island_id' &&
      value !== thing.current_island_id &&
      Object.values(state.world.agents).filter(
        a => a.current_island_id === value
      ).length >= MAX_PEOPLE_PER_ISLAND
    ) {
      toast('Destination island already has 100 people.');
      renderAll();
      return;
    }
    thing[key]=value;
    if(type==='island'&&thing.attributeDictionary&&key in thing.attributeDictionary)thing.attributeDictionary[key]=value;
    if(type==='agent'&&key==='current_island_id'&&!state.world.islands[value]){toast('Choose a real island.');return;}
    renderAll();return;
  }
  if(el.dataset.profileField){const p=pById(el.dataset.profileId);if(!p)return;p.params[el.dataset.profileField]=value;storeProfiles();renderBuildTabs();return;}
  if(el.dataset.profileName){const p=pById(el.dataset.profileName);if(!p)return;p.name=String(value)||p.name;storeProfiles();renderBuildTabs();return;}
  if (el.dataset.worldField) {

    // If the user changes the seed, stop displaying "-".
    if (el.dataset.worldField === 'active_seed') {
      state.seedIsDefault = false;
    }

    const path = el.dataset.worldField.split('.');

    if (path.length === 2) {
      state.world[path[0]] ||= {};
      state.world[path[0]][path[1]] = value;
    } else {
      state.world[path[0]] = value;
    }

    renderAll();
  }
}
function actionHandler(target){
  const el=target.closest('[data-action]');if(!el)return;
  const action=el.dataset.action,id=el.dataset.id;
  switch(action){
    case 'place-island':addIsland();break;
    case 'delete-island':deleteIsland(id);break;
    case 'delete-agent':deleteAgent(id);break;
    case 'back-island':select('island',id);break;
    case 'toggle-advanced':state.agentMore=!state.agentMore;renderInspector();break;
    case 'population-plus':case 'population-minus':{
      const islandId=el.dataset.island,profileId=el.dataset.profile;
      const count=Object.values(state.world.agents).filter(a=>a.current_island_id===islandId&&state.associations[a.agent_id]===profileId).length;
      setPopulation(islandId,profileId,count+(action==='population-plus'?1:-1));break;
    }
    case 'create-profile':{
      if(!editable())break;
      const kind=el.dataset.kind,source=defaultProfile(kind),n=Date.now().toString(36);
      const p={id:`${kind}-p-${n}`,kind,name:`New ${kind==='island'?'island':'person'} profile`,params:clone(source?.params||pickProfile(kind==='island'?DEFAULT_ISLAND:DEFAULT_AGENT,kind))};
      state.profiles.push(p);state.openProfileId=p.id;storeProfiles();renderBuildTabs();break;
    }
    case 'edit-profile':state.openProfileId=state.openProfileId===id?null:id;renderBuildTabs();break;
    case 'delete-profile':{
      if(!editable())break;
      const p=pById(id);if(!p||profilesFor(p.kind).length===1)break;
      state.profiles=state.profiles.filter(p=>p.id!==id);
      for(const aid of Object.keys(state.associations))if(state.associations[aid]===id)state.associations[aid]=defaultProfile('agent')?.id;
      ensureProfiles();storeProfiles();renderAll();break;
    }
  }
}
function installEvents(){
  $('#startBtn').addEventListener('click',startRun);$('#resetBtn').addEventListener('click',reset);
  
  // Expand or collapse the world statistics box.
  $('#worldStatsToggle').addEventListener('click', () => {
    const body = $('#worldStatsBody');
    const button = $('#worldStatsToggle');

    const opening = body.hidden;

    body.hidden = !opening;

    button.textContent = opening
      ? 'WORLD STATS [-]'
      : 'WORLD STATS [+]';

    button.setAttribute('aria-expanded', String(opening));
  });
  $('#zoomBtn').addEventListener('click', () => {
    if (zoomIslandId) {
      zoomIslandId = null;
    } else {
      const id = focusedIslandId();

      if (!id) {
        toast('Select an island or one of its people first.');
        return;
      }

      zoomIslandId = id;
    }

    renderMapLabels();
  });
  $('#closeInspector').addEventListener('click',()=>{state.selected=null;renderInspector();});
  $('.side-tabs').addEventListener('click',e=>{const t=e.target.closest('[data-tab]');if(!t)return;state.activeTab=t.dataset.tab;renderBuildTabs();});
  $('#leftContent').addEventListener('click',e=>{
    const a=e.target.closest('[data-agent-link]');if(a){select('agent',a.dataset.agentLink);return;}
    actionHandler(e.target);
  });
  $('#inspectorContent').addEventListener('click',e=>{
    const person=e.target.closest('[data-select-agent]');if(person){select('agent',person.dataset.selectAgent);return;}
    actionHandler(e.target);
  });
  $('#leftContent').addEventListener('change',e=>{
    if(e.target.id==='activeIslandProfile'){state.islandProfile=e.target.value;return;}
    if(e.target.id==='eventSearch'){state.eventFilter=e.target.value;renderBuildTabs();return;}
    if(e.target.matches('[data-world-field],[data-profile-field],[data-profile-name]'))changeField(e.target);
  });
  $('#leftContent').addEventListener('input',e=>{if(e.target.id==='eventSearch'){const cursor=e.target.selectionStart;state.eventFilter=e.target.value;renderBuildTabs();const sr=$('#eventSearch');sr?.focus();sr?.setSelectionRange(cursor,cursor);}});
  $('#inspectorContent').addEventListener('change',e=>{
    if(e.target.dataset.populationCount){setPopulation(e.target.dataset.island,e.target.dataset.populationCount,e.target.value);return;}
    if(e.target.matches('[data-entity-field]'))changeField(e.target);
  });
  $('#timeline').addEventListener('click',e=>{
    if(state.running||state.loading)return;const target=e.target.closest('[data-view-index]');if(!target)return;
    const i=Number(target.dataset.viewIndex);state.viewIndex=i===state.snapshots.length-1?null:i;
    state.selected=null;renderAll();
  });
  $('#restoreBtn').addEventListener('click',()=>{
    if(!isViewingHistory()||state.running)return;
    const s=state.snapshots[state.viewIndex];state.world=clone(s.world);state.positions=clone(s.positions);
    state.snapshots=state.snapshots.slice(0,state.viewIndex+1);state.viewIndex=null;
    state.selected=null;renderAll();toast('Historical state restored locally. Next START sends this branch to Python.');
  });
  $('#leftContent').addEventListener('dragstart',e=>{
    const island=e.target.closest('#islandDrag'),person=e.target.closest('[data-person-drag]');
    if(!island&&!person)return;
    e.dataTransfer.effectAllowed='copy';
    e.dataTransfer.setData('text/plain',JSON.stringify(island?{kind:'island'}:{kind:'agent',profileId:person.dataset.personDrag}));
    e.dataTransfer.setData('application/x-partial-wace',island?'island':`agent:${person.dataset.personDrag}`);
  });
  const map=$('#mapFrame'),canvas=$('#seaCanvas');
  map.addEventListener('dragover',e=>{if(state.running||state.loading||isViewingHistory())return;e.preventDefault();e.dataTransfer.dropEffect='copy';map.classList.add('drop-target');});
  map.addEventListener('dragleave',e=>{if(!map.contains(e.relatedTarget))map.classList.remove('drop-target');});
  map.addEventListener('drop',e=>{
    e.preventDefault();map.classList.remove('drop-target');if(!editable())return;
    let data;try{data=JSON.parse(e.dataTransfer.getData('text/plain'));}catch{return;}
    const p=screenToWorld(e,canvas);
    if(data.kind==='island')addIsland(p);
    else if(data.kind==='agent'){
      const hit=hitTest(state.world,state.positions,p,false);
      if(hit?.type==='island')addAgent(data.profileId,hit.id);else toast('Drop the person onto a landmass.');
    }
  });
  // Check whether the pointer is outside the sea box.
  function outsideSea(e) {
    const r = map.getBoundingClientRect();

    return (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    );
  }

  // Begin dragging an island.
  canvas.addEventListener('pointerdown', e => {
    if (state.running || state.loading) return;

    const p = screenToWorld(e, canvas);
    const hit = hitTest(
      worldShown(),
      isViewingHistory()
        ? state.snapshots[state.viewIndex].positions
        : state.positions,
      p
    );

    if (!hit) {
      state.selected = null;
      renderInspector();
      return;
    }

    select(hit.type, hit.id);

    if (hit.type !== 'island' || isViewingHistory()) return;

    const island = getLayout(state.world, state.positions)
      .find(i => i.id === hit.id);

    if (!island) return;

    const r = canvas.getBoundingClientRect();

    dragIsland = {
      id: hit.id,
      pointerId: e.pointerId,
      startClientX: e.clientX,
      startClientY: e.clientY,
      grabX: e.clientX - (r.left + island.x / W * r.width),
      grabY: e.clientY - (r.top + island.y / H * r.height),
      active: false,
      preview: null
    };

    canvas.setPointerCapture(e.pointerId);
  });

  // Move the island, including beyond the canvas.
  window.addEventListener('pointermove', e => {
    if (!dragIsland || e.pointerId !== dragIsland.pointerId) return;

    const drag = dragIsland;
    const distance = Math.hypot(
      e.clientX - drag.startClientX,
      e.clientY - drag.startClientY
    );

    if (!drag.active && distance < 7) return;

    const r = canvas.getBoundingClientRect();

    if (!drag.active) {
      drag.active = true;

      const preview = makeIslandDragPreview(
        state.world,
        state.positions,
        drag.id
      );

      if (preview) {
        preview.className = 'island-drag-preview';
        preview.style.width = `${220 * r.width / W}px`;
        preview.style.height = `${190 * r.height / H}px`;

        document.body.appendChild(preview);
        drag.preview = preview;
      }
    }

    // Follow the pointer with the pixel-art preview.
    if (drag.preview) {
      drag.preview.style.left =
        `${e.clientX - drag.grabX - 110 * r.width / W}px`;

      drag.preview.style.top =
        `${e.clientY - drag.grabY - 105 * r.height / H}px`;

      drag.preview.classList.toggle(
        'delete-preview',
        outsideSea(e)
      );
    }

    // Only update the island's position when inside the sea.
    if (!outsideSea(e)) {
      const x = (e.clientX - drag.grabX - r.left) / r.width * W;
      const y = (e.clientY - drag.grabY - r.top) / r.height * H;

      state.positions[drag.id] = {
        x: Math.max(30, Math.min(W - 30, x)),
        y: Math.max(30, Math.min(H - 30, y))
      };
    }
  });

  // Release the island.
  window.addEventListener('pointerup', e => {
    if (!dragIsland || e.pointerId !== dragIsland.pointerId) return;

    const drag = dragIsland;
    dragIsland = null;

    drag.preview?.remove();

    if (canvas.hasPointerCapture(e.pointerId)) {
      canvas.releasePointerCapture(e.pointerId);
    }

    if (!drag.active) return;

    if (outsideSea(e)) {
      // Released outside the sea: delete the island.
      deleteIsland(drag.id);
    } else {
      // Released inside the sea: keep its new position.
      const layout = getLayout(state.world, state.positions);

      for (const island of layout) {
        state.positions[island.id] = {
          x: island.x,
          y: island.y
        };
      }

      renderAll();
    }
  });

  // Cancelled drag: keep the island rather than deleting it.
  window.addEventListener('pointercancel', e => {
    if (!dragIsland || e.pointerId !== dragIsland.pointerId) return;

    dragIsland.preview?.remove();
    dragIsland = null;
    renderAll();
  });
  canvas.addEventListener('pointermove',e=>{if(dragIsland)return;const hit=hitTest(worldShown(),isViewingHistory()?state.snapshots[state.viewIndex].positions:state.positions,screenToWorld(e,canvas));canvas.style.cursor=hit?'pointer':'crosshair';});
  canvas.addEventListener('pointerleave',()=>canvas.style.cursor='crosshair');
  $('#islandDrag')?.addEventListener('keydown',e=>{if(e.key==='Enter')addIsland();});
}
function frame() {
  const world = worldShown();

  if (world) {
    const pos = isViewingHistory()
      ? state.snapshots[state.viewIndex].positions
      : state.positions;

    lastMap = drawSea(
      $('#seaCanvas'),
      world,
      pos,
      state.selected,
      state.running ? {since: state.runSince} : null,
      dragIsland?.active ? dragIsland.id : null
    );
    updateZoom(lastMap.layout);
  }

  drawTimer = requestAnimationFrame(frame);
}
installEvents();

const randomizer = mountRandomizer({
  getProfiles: () => state.profiles,
  getWorld: () => state.world,
  getReceived: () => state.received,
  canEdit: editable,

  apply: ({world, associations, positions}) => {

    // Randomize starts a fresh world.
    // Clear the previous Time Machine and saved positions.
    clearSceneStorage();

    waitingForRandomizedStart = true;

    // Exit any historical view and return to normal map zoom.
    state.viewIndex = null;
    zoomIslandId = null;

    // Apply the newly generated world.
    state.world = world;
    state.seedIsDefault = false;
    state.associations = associations;
    state.positions = positions;

    seedPositions(world, false);

    // Let the existing island layout solve overlaps.
    const layout = getLayout(world, state.positions);

    state.positions = Object.fromEntries(
      layout.map(i => [i.id, {x:i.x, y:i.y}])
    );

    const first = Object.keys(world.islands)[0];

    state.selected = first
      ? {type:'island', id:first}
      : null;

    renderAll();

    mapMessage(
      'New random starting state, Not sent to Python yet'
    );
  },

  toast,
  onReady: () => renderMapLabels()
});

loadApp();
frame();
