/** Relationship helpers (ported from WHACK v2's app.js / social.py). Pure functions, no DOM.
 *
 * Everything is derived from the people in the world being shown, so it works on any Time Machine snapshot:
 *   family    parents[]           (edge: parent -> child)
 *   partner   partner_id          (edge: a -> b, a < b)
 *   mentor    mentor{mentor,...}  (edge: teacher -> pupil)
 *   feud      grudges{id: x}      (edge: holder of the grudge -> the person it is held against)
 *   trust / distrust   trust_graph (0-100, 50 = neutral), turned into -1..1 and averaged over both directions
 */
export const KINDS = {
  family:   {label: 'Family',           color: '#b8860b'},
  partner:  {label: 'Couple',           color: '#d6336c'},
  mentor:   {label: 'Teacher & pupil',  color: '#2f66d0', dash: true},
  feud:     {label: 'Feud',             color: '#d0342c'},
  trust:    {label: 'Trust',            color: '#3f9a54'},
  distrust: {label: 'Distrust',         color: '#e07b1a'},
};
export const ORDER = ['distrust', 'trust', 'family', 'mentor', 'partner', 'feud']; // drawn bottom to top
export const TRUST_FLOOR = 0.15;                                                   // default "minimum strength" for trust lines

const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
export const isAlive = agent => !!agent && agent.is_alive !== false;
const round2 = x => Math.round(x * 100) / 100;

export function buildRelations(world, {minTrust = TRUST_FLOOR} = {}) {
  const agents = world?.agents || {};
  const alive = id => isAlive(agents[id]);
  const edges = [];

  const pairTrust = new Map();                       // "a|b" (sorted) -> [-1..1 values, one per direction recorded]
  for (const a of Object.values(agents)) {
    if (!isAlive(a)) continue;
    for (const [otherId, score] of Object.entries(a.trust_graph || {})) {
      if (otherId === a.agent_id || !alive(otherId) || !Number.isFinite(Number(score))) continue;
      const key = a.agent_id < otherId ? `${a.agent_id}|${otherId}` : `${otherId}|${a.agent_id}`;
      (pairTrust.get(key) || pairTrust.set(key, []).get(key)).push((num(score) - 50) / 50);
    }
  }
  const trustBetween = (x, y) => {
    const list = pairTrust.get(x < y ? `${x}|${y}` : `${y}|${x}`);
    return list ? list.reduce((s, v) => s + v, 0) / list.length : 0;
  };

  for (const [key, list] of pairTrust) {
    const v = list.reduce((s, x) => s + x, 0) / list.length;
    if (Math.abs(v) < minTrust) continue;
    const [a, b] = key.split('|');
    edges.push({a, b, kind: v > 0 ? 'trust' : 'distrust', v: round2(v)});
  }
  for (const c of Object.values(agents)) {
    if (!isAlive(c)) continue;
    for (const p of c.parents || [])
      if (alive(p)) edges.push({a: p, b: c.agent_id, kind: 'family', v: round2(Math.max(0, trustBetween(p, c.agent_id)))});
    if (c.partner_id && c.agent_id < c.partner_id && alive(c.partner_id) && agents[c.partner_id].partner_id === c.agent_id)
      edges.push({a: c.agent_id, b: c.partner_id, kind: 'partner', v: round2(trustBetween(c.agent_id, c.partner_id)), since: c.partner_since});
    const m = c.mentor;
    if (m && typeof m === 'object' && alive(m.mentor))
      edges.push({a: m.mentor, b: c.agent_id, kind: 'mentor', v: round2(trustBetween(m.mentor, c.agent_id)), skill: m.skill, since: m.year});
    for (const [o, g] of Object.entries(c.grudges || {}))
      if (alive(o) && num(g) >= 0.05) edges.push({a: c.agent_id, b: o, kind: 'feud', v: round2(num(g))});
  }
  return edges;
}

export const sameEdge = (x, y) => !!x && !!y && x.a === y.a && x.b === y.b && x.kind === y.kind;

/** A sentence (HTML-escaped) explaining what a line in the graph means. */
export function edgeText(e, nameOf, esc) {
  const A = esc(nameOf(e.a)), B = esc(nameOf(e.b));
  return {
    family: `<b>Family.</b> ${A} is a parent of ${B}. Children are fed by their parents first.`,
    partner: `<b>Couple.</b> ${A} and ${B} have been together since year ${esc(e.since ?? '?')}. Trust between them is ${e.v}. With social life on, only couples have children.`,
    mentor: `<b>Teacher and pupil.</b> ${A} has been teaching ${B} ${esc(e.skill)} (last lesson in year ${esc(e.since ?? '?')}). Each lesson moves the pupil's skill part of the way toward the teacher's.`,
    feud: `<b>Feud.</b> ${B} wronged ${A} (a raid or a quarrel) and ${A} holds a grudge of ${e.v}. The bigger it is, and the more of ${A}'s friends share it, the likelier ${A} strikes back. People who are very cooperative and caught up in several feuds may leave the island.`,
    trust: `<b>Trust.</b> ${A} and ${B} trust each other at ${e.v} (scale -1 to 1). It grows with gifts, fair trades, family and lessons, and fades about 5% a year.`,
    distrust: `<b>Distrust.</b> ${A} and ${B} are at ${e.v} (scale -1 to 1). Refused trades, quarrels, raids and feuds push trust down.`,
  }[e.kind] || '';
}

/** Every line touching one person, with their role in it. */
export function linksOf(edges, id) {
  const out = [];
  for (const e of edges) {
    if (e.a !== id && e.b !== id) continue;
    const first = e.a === id;
    const role = {
      family: first ? 'parent of' : 'child of', partner: 'partner', mentor: first ? 'teaches' : 'taught by',
      feud: first ? 'holds a grudge against' : 'is the target of a grudge from', trust: 'trusts', distrust: 'distrusts',
    }[e.kind];
    const detail = e.kind === 'partner' ? `since year ${e.since ?? '?'}` : e.kind === 'mentor' ? `${e.skill}, year ${e.since ?? '?'}`
      : e.kind === 'feud' ? `grudge ${e.v}` : e.kind === 'family' ? '' : `${e.v}`;
    out.push({kind: e.kind, other: first ? e.b : e.a, role, detail, v: e.v, edge: e});
  }
  return out;
}

/** The last few events that mention a person (as the main actor, a participant, or by name). */
export function personEvents(world, agent, n = 10) {
  if (!agent) return [];
  const name = String(agent.name || '').trim();
  const pattern = name ? new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`) : null;
  return (world?.event_history || [])
    .filter(e => e.event_type !== 'year_summary' && e.event_type !== 'trade'
      && (e.primary_agent_id === agent.agent_id
        || (Array.isArray(e.payload?.participants) && e.payload.participants.includes(agent.agent_id))
        || (pattern && pattern.test(String(e.description || '')))))
    .slice(-n).map(e => ({year: e.year, text: String(e.description || ''), type: e.event_type}));
}

/** Gini coefficient: 0 = everyone holds the same, towards 1 = one person holds nearly everything. */
export function gini(values) {
  const xs = values.map(v => Math.max(0, num(v))).sort((a, b) => a - b);
  const n = xs.length, total = xs.reduce((s, x) => s + x, 0);
  return n && total > 0 ? xs.reduce((s, x, i) => s + (2 * (i + 1) - n - 1) * x, 0) / (n * total) : 0;
}

/** The headline numbers for the stats strip (computed from whatever world is on screen). */
export function worldStats(world) {
  const living = Object.values(world?.agents || {}).filter(isAlive);
  const coins = living.reduce((s, a) => s + num(a.wealth), 0);
  const edges = buildRelations(world, {minTrust: 2});            // minTrust 2 drops all trust lines: only couples, feuds, family, lessons
  return {
    population: living.length,
    coins,
    gini: gini(living.map(a => a.wealth)),
    health: living.length ? living.reduce((s, a) => s + num(a.health), 0) / living.length : null,
    couples: edges.filter(e => e.kind === 'partner').length,
    feuds: edges.filter(e => e.kind === 'feud').length,
  };
}
