/** "Who is tied to whom": a small force simulation, islands as clusters (ported from WHACK v2's app.js).
 * Bigger dot = more coins. Click a dot for the person, a line for the relationship.
 * The graph only reads the world; selecting something calls back into app.js. */
import {KINDS, ORDER, buildRelations, sameEdge, isAlive} from './relations.js';

export const ISLAND_COLORS = ['#0b8f7c', '#e4572e', '#c28f00', '#2f66d0', '#8e44c9', '#2e9e3e', '#d6336c', '#00809d'];
const num = (v, d = 0) => Number.isFinite(Number(v)) ? Number(v) : d;

export function createGraph({canvas, getWorld, getPositions, getSelected, getFilters, nameOf, onNode, onEdge, onSummary}) {
  const G = {nodes: new Map(), edges: [], alpha: 0, hover: null, anchors: {}, names: [], meanW: 20, dirty: true, empty: ''};
  // the camera: screen = world * k + (x, y). Wheel or the +/- buttons zoom, dragging the background pans.
  const V = {k: 1, x: 0, y: 0, pan: null, moved: false};
  const K_MIN = .5, K_MAX = 8;
  const limitView = () => {
    const W = canvas.clientWidth || 600, H = canvas.clientHeight || 400;
    V.k = Math.min(K_MAX, Math.max(K_MIN, V.k));
    const [loX, hiX] = [W - V.k * W - 60, 60].sort((a, b) => a - b), [loY, hiY] = [H - V.k * H - 60, 60].sort((a, b) => a - b);
    V.x = Math.min(hiX, Math.max(loX, V.x));
    V.y = Math.min(hiY, Math.max(loY, V.y));
    G.dirty = true;
  };
  function zoomAt(factor, sx, sy) {                        // keep the point under (sx, sy) where it is
    const wx = (sx - V.x) / V.k, wy = (sy - V.y) / V.k;
    V.k = Math.min(K_MAX, Math.max(K_MIN, V.k * factor));
    V.x = sx - wx * V.k; V.y = sy - wy * V.k;
    limitView();
  }

  // bigger dot, more coins (relative to the average); dots shrink a little as the crowd grows
  const radius = n => Math.max(2.5, Math.min(18, 3.5 + 5 * Math.sqrt(Math.max(0, num(n.a.wealth)) / G.meanW))
    * Math.min(1, Math.max(.45, Math.sqrt(140 / G.nodes.size))));

  function layoutAnchors(w, W, H) {
    const ids = Object.keys(w.islands || {}), pos = getPositions() || {};
    const pts = ids.map((id, i) => ({id, x: num(pos[id]?.x, 100 + i * 60), y: num(pos[id]?.y, 100 + (i % 2) * 60)}));
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const padX = Math.min(120, W * .2), padY = Math.min(80, H * .22);
    G.anchors = {};
    pts.forEach((p, i) => {
      // the same arrangement as the map, stretched to fill the canvas
      const fx = maxX > minX ? (p.x - minX) / (maxX - minX) : .5, fy = maxY > minY ? (p.y - minY) / (maxY - minY) : .5;
      G.anchors[p.id] = {x: padX + fx * (W - 2 * padX), y: padY + 22 + fy * (H - 2 * padY - 22), c: ISLAND_COLORS[i % ISLAND_COLORS.length]};
    });
    G.names = ids;
  }

  function update() {
    const w = getWorld();
    if (!w) return;
    const W = canvas.clientWidth || 600, H = canvas.clientHeight || 400, f = getFilters();
    layoutAnchors(w, W, H);
    const alive = Object.values(w.agents || {}).filter(a => isAlive(a) && w.islands?.[a.current_island_id]
      && (f.island === 'all' || a.current_island_id === f.island));
    const ids = new Set(alive.map(a => a.agent_id));
    for (const id of [...G.nodes.keys()]) if (!ids.has(id)) G.nodes.delete(id);
    for (const a of alive) {
      const an = G.anchors[a.current_island_id] || {x: W / 2, y: H / 2};
      let n = G.nodes.get(a.agent_id);
      if (!n) {
        n = {id: a.agent_id, x: an.x + (Math.random() - .5) * 80, y: an.y + (Math.random() - .5) * 80, vx: 0, vy: 0};
        G.nodes.set(a.agent_id, n);
      }
      n.a = a;
      n.island = a.current_island_id;
    }
    G.meanW = alive.length ? Math.max(1, alive.reduce((s, a) => s + num(a.wealth), 0) / alive.length) : 20;
    G.edges = buildRelations(w, {minTrust: f.minTrust}).filter(e => G.nodes.has(e.a) && G.nodes.has(e.b));
    G.alpha = .8;
    G.dirty = true;
    const count = k => G.edges.filter(e => e.kind === k).length;
    const total = Object.values(w.agents || {}).filter(isAlive).length;
    const shown = G.edges.filter(e => f.visible[e.kind]).length;
    G.empty = !total ? 'Nobody lives here yet.'
      : !alive.length ? 'Nobody on this island.'
      : !shown ? 'No relationships to show. Start the simulation: couples, feuds, lessons and trust appear as years pass (or switch more kinds of line on).' : '';
    onSummary?.({people: alive.length, couples: count('partner'), feuds: count('feud'), family: count('family'), mentors: count('mentor'),
      trust: count('trust'), distrust: count('distrust'), empty: G.empty});
  }

  function tick() {
    if (!canvas.isConnected || !canvas.clientWidth || !canvas.clientHeight) return;
    const W = canvas.clientWidth, H = canvas.clientHeight, dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      update();
    }
    const c = canvas.getContext('2d'), ns = [...G.nodes.values()], f = getFilters();
    if (G.alpha > .02 && ns.length) {
      for (let i = 0; i < ns.length; i++) for (let j = i + 1; j < ns.length; j++) {
        const p = ns[i], q = ns[j];
        let dx = p.x - q.x, dy = p.y - q.y;
        const d2 = dx * dx + dy * dy + 1;
        if (d2 > 12000) continue;
        const force = 110 / d2, d = Math.sqrt(d2);
        dx = dx / d * force; dy = dy / d * force;
        p.vx += dx; p.vy += dy; q.vx -= dx; q.vy -= dy;
      }
      const PULL = {partner: [.06, 20], family: [.03, 26], mentor: [.012, 34]};
      for (const e of G.edges) {
        const p = G.nodes.get(e.a), q = G.nodes.get(e.b);
        if (!p || !q) continue;
        let k, want;
        if (PULL[e.kind]) [k, want] = PULL[e.kind];
        else if (e.kind === 'trust') { k = .02 * e.v; want = 26 + (1 - e.v) * 30; }
        else continue;                                   // feuds and distrust do not pull people together
        const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) + .1, force = k * (d - want) / d;
        p.vx += dx * force; p.vy += dy * force; q.vx -= dx * force; q.vy -= dy * force;
      }
      for (const n of ns) {
        const an = G.anchors[n.island] || {x: W / 2, y: H / 2};
        n.vx += (an.x - n.x) * .008; n.vy += (an.y - n.y) * .008; n.vx *= .82; n.vy *= .82;
        n.x = Math.min(W - 10, Math.max(10, n.x + n.vx * G.alpha * 1.6));
        n.y = Math.min(H - 10, Math.max(26, n.y + n.vy * G.alpha * 1.6));
      }
      G.alpha *= .985;
    } else if (!G.dirty) return;
    G.dirty = false;

    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, W, H);
    c.fillStyle = '#fffdf6';
    c.fillRect(0, 0, W, H);
    c.font = '700 11px ui-monospace, Consolas, monospace';
    c.textAlign = 'center';
    const short = G.names.length > 3;
    for (const name of G.names) {
      const an = G.anchors[name], count = ns.filter(q => q.island === name).length;
      if (f.island !== 'all' && f.island !== name) continue;
      c.fillStyle = an.c;
      c.fillText(short ? `${name} ${count}` : `Island ${name} (${count})`, Math.min(W - 40, Math.max(40, an.x * V.k + V.x)), 16);
    }
    c.setTransform(dpr * V.k, 0, 0, dpr * V.k, dpr * V.x, dpr * V.y);
    const sel = getSelected();
    const selId = sel?.type === 'agent' ? sel.id : null, selEdge = sel?.type === 'edge' ? sel.edge : null;
    for (const kind of ORDER) {
      if (!f.visible[kind]) continue;
      for (const e of G.edges) {
        if (e.kind !== kind) continue;
        const p = G.nodes.get(e.a), q = G.nodes.get(e.b);
        if (!p || !q) continue;
        const mine = selId && (e.a === selId || e.b === selId), chosen = sameEdge(selEdge, e);
        const base = kind === 'trust' || kind === 'distrust' ? Math.min(.8, .1 + Math.abs(e.v) * .5)
          : kind === 'feud' ? .45 + Math.min(.4, e.v * .4) : .9;
        c.globalAlpha = chosen ? 1 : base * (selId && !mine ? .3 : 1);
        c.strokeStyle = chosen ? '#000' : KINDS[kind].color;
        c.lineWidth = chosen ? 4 : kind === 'partner' ? 2.8 : kind === 'feud' ? 1.4 + Math.min(2.5, e.v * 3)
          : kind === 'family' ? 1.8 : kind === 'mentor' ? 1.5 : .6 + Math.abs(e.v) * 2;
        c.setLineDash(KINDS[kind].dash ? [5, 4] : []);
        c.beginPath(); c.moveTo(p.x, p.y); c.lineTo(q.x, q.y); c.stroke();
      }
    }
    c.setLineDash([]);
    c.globalAlpha = 1;
    for (const n of ns) {
      const r = radius(n);
      c.fillStyle = (G.anchors[n.island] || {c: '#999'}).c;
      c.beginPath(); c.arc(n.x, n.y, r, 0, 6.3); c.fill();
      c.strokeStyle = 'rgba(255,255,255,.9)'; c.lineWidth = 1; c.stroke();
      if (n.id === selId) { c.strokeStyle = '#000'; c.lineWidth = 2.5; c.beginPath(); c.arc(n.x, n.y, r + 2, 0, 6.3); c.stroke(); }
    }
    c.textAlign = 'left'; c.fillStyle = '#2a342e'; c.font = `700 ${11 / Math.sqrt(V.k)}px ui-monospace, Consolas, monospace`; c.lineJoin = 'round';
    for (const id of new Set([selId, G.hover])) {
      const n = G.nodes.get(id);
      if (!n) continue;
      c.lineWidth = 3.5 / V.k; c.strokeStyle = 'rgba(255,253,246,.92)';
      c.strokeText(nameOf(id), n.x + radius(n) + 5, n.y + 4);
      c.fillText(nameOf(id), n.x + radius(n) + 5, n.y + 4);
    }
  }

  function segDist(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }

  function pick(ev) {
    const r = canvas.getBoundingClientRect(), x = (ev.clientX - r.left - V.x) / V.k, y = (ev.clientY - r.top - V.y) / V.k, f = getFilters();
    let node = null, best = 1e9;
    for (const n of G.nodes.values()) {
      const d = Math.hypot(n.x - x, n.y - y);
      if (d < radius(n) + 4 / V.k && d < best) { best = d; node = n.id; }
    }
    if (node) return {node};
    let edge = null, near = 5.5 / V.k;
    for (const e of G.edges) {
      if (!f.visible[e.kind]) continue;
      const p = G.nodes.get(e.a), q = G.nodes.get(e.b);
      const d = segDist(x, y, p.x, p.y, q.x, q.y) - ORDER.indexOf(e.kind) * .15 / V.k;      // upper layers win ties
      if (d < near) { near = d; edge = e; }
    }
    return {edge};
  }

  canvas.addEventListener('mousedown', ev => {
    if (ev.button === 0) V.pan = {sx: ev.clientX, sy: ev.clientY, vx: V.x, vy: V.y};
    V.moved = false;
  });
  window.addEventListener('mousemove', ev => {
    if (!V.pan) return;
    const dx = ev.clientX - V.pan.sx, dy = ev.clientY - V.pan.sy;
    if (!V.moved && Math.hypot(dx, dy) < 5) return;
    V.moved = true;
    V.x = V.pan.vx + dx; V.y = V.pan.vy + dy;
    limitView();
    canvas.style.cursor = 'grabbing';
  });
  window.addEventListener('mouseup', () => { V.pan = null; });
  canvas.addEventListener('wheel', ev => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect();
    zoomAt(Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? .05 : .0015)), ev.clientX - r.left, ev.clientY - r.top);
  }, {passive: false});
  canvas.addEventListener('mousemove', ev => {
    if (V.pan && V.moved) return;
    const {node} = pick(ev);
    if (node !== G.hover) { G.hover = node || null; G.dirty = true; }
    canvas.style.cursor = node || pick(ev).edge ? 'pointer' : 'default';
  });
  canvas.addEventListener('mouseleave', () => { if (G.hover) { G.hover = null; G.dirty = true; } });
  canvas.addEventListener('click', ev => {
    if (V.moved) { V.moved = false; return; }               // that was a pan, not a click
    const {node, edge} = pick(ev);
    if (node) onNode(node); else if (edge) onEdge(edge);
  });

  return {
    update, tick,
    invalidate: () => { G.dirty = true; },
    reheat: () => { G.alpha = .8; G.dirty = true; },
    zoomBy: factor => zoomAt(factor, (canvas.clientWidth || 600) / 2, (canvas.clientHeight || 400) / 2),
    resetView: () => { V.k = 1; V.x = 0; V.y = 0; G.dirty = true; },
  };
}
