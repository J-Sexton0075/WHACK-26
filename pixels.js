/** Low-resolution, hand-drawn-in-code canvas. Every visible map feature is pixel art. */
export const W = 480, H = 330;
const G = 3;
const colors = {
  sea:'#8bc4bc', wave:'#a3d0c3', waveDeep:'#6ea9a7', sand:'#e8d18e', sandLight:'#f3dfa4', sandDark:'#c4ae75',
  grass:'#92b77c', grassDeep:'#75a073', grassLight:'#a4bf80', tree:'#497c61', trunk:'#785c43',
  hut:'#c88365', hutRoof:'#7a5144', wood:'#bd945b', ink:'#344b44', foam:'#e1eed2',
};
const hash = (input) => {let h=2166136261;for(const c of String(input)) {h=Math.imul(h ^ c.charCodeAt(0),16777619);}return h>>>0;};
const rand = (seed) => {const x=Math.sin(seed*127.13+1.97)*43758.5453;return x-Math.floor(x);};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const radius = pop => 24 + Math.min(42,Math.sqrt(Math.max(0,pop))*7.5);
export const islandRadius = radius;

export function getLayout(world, positions={}) {
  const byIsland={};
  for(const a of Object.values(world?.agents || {}))if(a.current_island_id && a.is_alive!==false)byIsland[a.current_island_id]=(byIsland[a.current_island_id]||0)+1;
  const keys=Object.keys(world?.islands||{});
  const islands=keys.map((id,i)=>{
    const fallback={x:W*(.27+.45*(i%2))+(Math.floor(i/2)%3)*12,y:H*(.36+.28*(i%3===2?1:i%3))};
    const seed=hash(id);
    const r=radius(byIsland[id]||0), aspect=.88+rand(seed+9)*.25;
    const loc=positions[id]||fallback;
    return {id,x:clamp(Number(loc.x)||W/2,r+9,W-r-9),y:clamp(Number(loc.y)||H/2,r+14,H-r-14),r,aspect,pop:byIsland[id]||0,seed};
  });
  // Gently resolve island collisions on each draw/refresh, rather than scaling overlaps.
  for(let iter=0;iter<35;iter++) {
    let any=false;
    for(let i=0;i<islands.length;i++)for(let j=i+1;j<islands.length;j++) {
      const a=islands[i],b=islands[j],dx=b.x-a.x,dy=b.y-a.y;
      const d=Math.hypot(dx,dy)||.001, min=a.r*.85+b.r*.85+13;
      if(d<min){let nx=dx/d,ny=dy/d;if(d<1){const angle=rand(a.seed+b.seed)*6.28;nx=Math.cos(angle);ny=Math.sin(angle);}
        const amt=(min-d)*.51; a.x-=nx*amt;a.y-=ny*amt;b.x+=nx*amt;b.y+=ny*amt;any=true;
      }
    }
    for(const a of islands){a.x=clamp(a.x,a.r+6,W-a.r-6);a.y=clamp(a.y,a.r+12,H-a.r-9);}
    if(!any)break;
  }
  return islands;
}

const rect=(c,x,y,w,h,color)=>{c.fillStyle=color;c.fillRect(Math.round(x),Math.round(y),Math.ceil(w),Math.ceil(h));};
function drawPalm(c,x,y,seed){
  rect(c,x,y-10,2,16,colors.trunk);rect(c,x+2,y-6,2,10,colors.trunk);
  rect(c,x-8,y-13,18,3,colors.tree);rect(c,x-11,y-10,5,3,colors.tree);rect(c,x+8,y-10,5,4,colors.tree);
  rect(c,x-4,y-17,13,3,colors.tree);rect(c,x,y-20,5,4,colors.grassDeep);
  if(rand(seed)>.4){rect(c,x+6,y-13,3,3,colors.grassLight);}
}
function drawHouse(c,x,y,seed){
  rect(c,x-7,y-5,16,12,'#d7b27a');rect(c,x-9,y-8,20,4,colors.hutRoof);rect(c,x-5,y-11,13,3,'#9b6950');
  rect(c,x+1,y+2,4,5,'#6b5040');rect(c,x-5,y-1,3,3,'#718c76');
  if(rand(seed)>.6)rect(c,x+12,y-1,3,6,colors.wood);
}
function shapeNoise(seed,theta){return 1+.13*Math.sin(theta*5+rand(seed)*6)+.1*Math.sin(theta*8+seed%9)+.08*Math.sin(theta*13+seed%13);}
function drawIsland(c,island,selected,year){
  const {x,y,r,aspect,seed}=island;
  const w=r*1.07,h=r*.64*aspect;
  // blocky rim: hand-laid terrain tiles, no vector smooth graphics
  for(let dy=-h-6;dy<h+6;dy+=G)for(let dx=-w-6;dx<w+6;dx+=G) {
    const angle=Math.atan2(dy/h,dx/w), limit=shapeNoise(seed,angle);
    const dist=Math.hypot(dx/w,dy/h);
    if(dist>limit)continue;
    const rr=rand(seed+Math.floor(dx/G)*13+Math.floor(dy/G)*17);
    rect(c,x+dx,y+dy+4,G,G,colors.sandDark);
    rect(c,x+dx,y+dy,G,G, dist>limit-.19 ? (rr>.62?colors.sandLight:colors.sand) : (rr>.80?colors.grassLight:rr<.18?colors.grassDeep:colors.grass));
  }
  for(let n=0;n<Math.max(7,Math.floor(r/2));n++){
    const xx=(rand(seed+n*31)-.5)*w*1.5, yy=(rand(seed+n*29+7)-.5)*h*1.15;
    rect(c,x+xx,y+yy,2,2,rand(seed+n*47)>.5?colors.grassLight:colors.grassDeep);
  }
  // A small palm, a few makeshift buildings, always grid-snapped.
  drawPalm(c,x-w*.37,y-h*.24,seed);
  if(r>31)drawPalm(c,x+w*.32,y-h*.18,seed+15);
  drawHouse(c,x+w*.12,y+h*.07,seed+12);
  if(island.pop>6)drawHouse(c,x-w*.27,y+h*.26,seed+4);
  if(island.pop>17)drawHouse(c,x+w*.39,y+h*.29,seed+7);
  if(island.pop>1){
    rect(c,x+w*.67,y+h*.42,3,8,colors.wood);rect(c,x+w*.66,y+h*.6,20,3,colors.wood);rect(c,x+w*.81,y+h*.62,2,3,colors.hutRoof);
  }
  if(selected){
    // pixel selection corners (not anti-aliased glows)
    const ox=w+11,oy=h+12;
    for(const sx of [-1,1])for(const sy of [-1,1]){
      rect(c,x+sx*ox-4,y+sy*oy,10,2,'#fff1a7');rect(c,x+sx*ox,y+sy*oy-4,2,10,'#fff1a7');
    }
  }
  rect(c,x-w*.51,y-h-17,Math.min(52,island.id.length*5+11),11,'#345f59');
  c.font='bold 8px monospace';c.fillStyle='#fff5d3';c.textBaseline='top';c.fillText(island.id,x-w*.51+4,y-h-15);
}
/** Small pixel tags under an island: disasters running there now (red) and queued ones due by this year (amber). */
const TAG_TEXT={plague:'PLAGUE',disease:'EPIDEMIC',drought:'DROUGHT',tsunami:'TSUNAMI',storm:'STORM'};
function drawDisasterTags(c,island,world){
  const year=Number(world?.current_year)||1,tags=[];
  const here=d=>!d.island||d.island===island.id;
  for(const d of world?.active_disasters||[])
    if(here(d)&&Number(d.start)<=year&&year<Number(d.end))tags.push([TAG_TEXT[d.type]||String(d.type).toUpperCase(),'#b24a38']);
  for(const d of world?.disaster_schedule||[])
    if(here(d)&&d.island&&Number(d.year)<=year)tags.push([`${TAG_TEXT[d.type]||String(d.type).toUpperCase()}?`,'#c08a2b']);
  if(!tags.length)return;
  const h=island.r*.64*island.aspect;
  c.font='bold 8px monospace';c.textBaseline='top';
  tags.slice(0,3).forEach(([text,color],i)=>{
    const w=text.length*5+8,x=island.x-w/2,y=island.y+h+10+i*12;
    rect(c,x,y,w,11,color);c.fillStyle='#fff5d3';c.fillText(text,x+4,y+2);
  });
}
export function getPersonPositions(world,layout,time=0,running=false){
  const byId=new Map(layout.map(x=>[x.id,x]));
  const groups={};const out=[];
  for(const a of Object.values(world?.agents||{}))if(a.current_island_id && a.is_alive!==false && byId.has(a.current_island_id)) {
    (groups[a.current_island_id] ||= []).push(a);
  }
  for(const [id,agents] of Object.entries(groups)){
    const island=byId.get(id),count=agents.length;
    agents.forEach((a,i)=>{
      const seed=hash(a.agent_id),angle=i*2.39996323+rand(seed)*.9,spread= Math.sqrt((i+1)/(count+1));
      let px=island.x+Math.cos(angle)*island.r*.71*spread;
      let py=island.y+Math.sin(angle)*island.r*.39*spread;
      if(running){px+=Math.sin(time*.009+seed)*5+Math.sin(time*.021+i)*2;py+=Math.sin(time*.013+seed*2)*3;}
      out.push({id:a.agent_id,x:px,y:py,agent:a,seed});
    });
  }
  return out;
}
function person(c,p,selected,time,running){
  const {x,y,seed}=p,skin=['#b97855','#e7b78d','#a66f54','#e7a97d'][seed%4];
  const shirt=['#496e78','#c98362','#d3b763','#788a65','#a56b6b'][seed%5];
  rect(c,x-2,y-10,5,3,seed%3===0?'#78543e':'#514b42');
  rect(c,x-2,y-7,5,5,skin);rect(c,x-2,y-2,5,6,shirt);rect(c,x-4,y-1,2,4,shirt);rect(c,x+3,y,2,4,shirt);
  rect(c,x-2,y+4,2,4,'#4b5650');rect(c,x+1,y+4,2,4,'#4b5650');
  if(selected){rect(c,x-5,y-14,11,2,'#ffea90');rect(c,x-5,y-14,2,5,'#ffea90');rect(c,x+4,y-14,2,5,'#ffea90');}
  if(running && rand(seed+Math.floor(time/690))>.81){
    rect(c,x+5,y-18,13,9,'#fff8d8');rect(c,x+16,y-10,2,3,'#fff8d8');
    rect(c,x+8,y-15,2,2,'#666759');rect(c,x+12,y-15,2,2,'#666759');
  }
}

export function drawSea(canvas,world,positions,selection,runState,hiddenIslandId=null){
  const c=canvas.getContext('2d',{alpha:false});c.imageSmoothingEnabled=false;
  const t=performance.now(),running=!!runState;
  rect(c,0,0,W,H,colors.sea);
  for(let i=0;i<125;i++){
    const seed=i*239,wx=rand(seed+11)*W,wy=rand(seed+17)*H;
    const shift=running?Math.floor(t/130)%16:Math.floor(t/1100)%8;
    rect(c,(wx+shift)%W,wy,3+Math.floor(rand(seed+7)*6),1,i%3===0?colors.waveDeep:colors.wave);
    if(i%6===0)rect(c,(wx-4+shift)%W,wy+3,3,1,colors.foam);
  }
  for(let x=14;x<W;x+=70)for(let y=19;y<H;y+=90){
    rect(c,x+4,y+9,7,1,'#a8d4c9');rect(c,x+11,y+8,5,1,'#a8d4c9');
  }
  const layout=getLayout(world,positions);
  for (const island of layout) {
  if (island.id === hiddenIslandId) continue;
  drawIsland(c, island, selection?.type === 'island' && selection?.id === island.id, world?.current_year);
  drawDisasterTags(c, island, world);
}

const people = getPersonPositions(world, layout, t, running);

for (const p of people) {
  if (world.agents[p.id]?.current_island_id === hiddenIslandId) continue;
  person(c, p, selection?.type === 'agent' && selection?.id === p.id, t, running);
}
  if(running){
    const cycle=(t-(runState.since||t))/270;
    const darkness=(1+Math.sin(cycle))/2;
    c.fillStyle=`rgba(24,42,71,${(darkness*.66).toFixed(2)})`;c.fillRect(0,0,W,H);
    // choppy scanline fast-forward effect
    for(let y=0;y<H;y+=11)rect(c,0,y,W,1,`rgba(227,240,225,${(.04+darkness*.05).toFixed(2)})`);
    rect(c,11,11,39,16,'#263f51');c.font='bold 12px monospace';c.fillStyle='#f7e3a0';c.fillText('>>',19,14);
    if(darkness>.5){rect(c,W-26,16,6,6,'#f3eab8');rect(c,W-30,12,2,2,'#f3eab8');}
    else {rect(c,W-27,13,9,9,'#f8dc82');rect(c,W-31,17,2,3,'#f8dc82');}
  }
  return {layout,people};
}
export function makeIslandDragPreview(world, positions, islandId) {
  const island = getLayout(world, positions)
    .find(i => i.id === islandId);

  if (!island) return null;

  const canvas = document.createElement('canvas');
  canvas.width = 220;
  canvas.height = 190;

  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;

  const previewIsland = {
    ...island,
    x: 110,
    y: 105
  };

  drawIsland(ctx, previewIsland, false, world.current_year);

  const people = getPersonPositions(world, [previewIsland]);
  for (const p of people) {
    person(ctx, p, false, 0, false);
  }

  return canvas;
}
export function screenToWorld(event,canvas){const r=canvas.getBoundingClientRect();return {x:(event.clientX-r.left)/r.width*W,y:(event.clientY-r.top)/r.height*H};}
export function hitTest(world,positions,p,preferPeople=true){
  const layout=getLayout(world,positions);const people=getPersonPositions(world,layout);
  if(preferPeople)for(let i=people.length-1;i>=0;i--)if(Math.abs(people[i].x-p.x)<7&&Math.abs(people[i].y-p.y+3)<12)return {type:'agent',id:people[i].id};
  for(let i=layout.length-1;i>=0;i--){const a=layout[i];if(Math.hypot((p.x-a.x)/(a.r*1.06),(p.y-a.y)/(a.r*.7*a.aspect))<1.12)return {type:'island',id:a.id};}
  return null;
}
