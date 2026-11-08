/**
 * Frontend transport adapter ONLY. This module does not run or approximate a
 * simulation. Wire these methods up to whichever Python transport you provide.
 *
 * Two integration methods:
 * 1. Set window.ISLAND_SIM_BRIDGE = { requestWorldState, startSimulation, resetWorld }
 *    before app.js loads, to use JS methods exposed by your Python/webview pipe.
 * 2. Set window.ISLAND_SIM_CONFIG = { worldUrl, simulateUrl, resetUrl } to use
 *    your existing HTTP endpoints (defaults are placeholders, NOT an API server).
 *
 * The expected data is WorldState.serialize_state_for_frontend() from world.py.
 */
export const DEFAULT_CONFIG = {
  worldUrl: '/api/world',
  simulateUrl: '/api/simulate',
  resetUrl: '/api/reset',
  interviewUrl: '/api/interview',
  assumptionsUrl: '/api/assumptions',
  timeoutMs: 120000,
};
const config = () => ({...DEFAULT_CONFIG, ...(window.ISLAND_SIM_CONFIG || {})});
const methods = () => window.ISLAND_SIM_BRIDGE || window.islandSimulationBridge || null;

function validateAndUnwrap(result) {
  if (typeof result === 'string') result = JSON.parse(result);
  const state = result?.world_state ?? result?.state ?? result;
  if (!state || typeof state !== 'object' || !state.islands || !state.agents) {
    throw new Error('Python response did not contain islands and agents dictionaries.');
  }
  if (state !== result && result?.event_history) state.event_history = result.event_history;
  if (state !== result && result?.events) state.event_history = result.events;
  return state;
}

async function httpJson(url, method, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config().timeoutMs);
  try {
    const response = await fetch(url, {
      method,
      headers: {'Accept': 'application/json', ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
      ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      signal: controller.signal,
      cache: 'no-store',
    });
    if (!response.ok) {
      let detail = '';
      try { detail = (await response.json())?.error || ''; } catch { /* not JSON */ }
      throw new Error(`${method} ${url}: HTTP ${response.status}${detail ? ` - ${detail}` : ''}`);
    }
    return await response.json();
  } finally { clearTimeout(timeout); }
}

export async function requestWorldState() {
  const b = methods();
  if (b?.requestWorldState || b?.request_world_state) {
    return validateAndUnwrap(await (b.requestWorldState ?? b.request_world_state).call(b));
  }
  return validateAndUnwrap(await httpJson(config().worldUrl, 'GET'));
}

export async function startSimulation(world) {
  const b = methods();
  if (b?.startSimulation || b?.start_simulation) {
    return validateAndUnwrap(await (b.startSimulation ?? b.start_simulation).call(b, world));
  }
  return validateAndUnwrap(await httpJson(config().simulateUrl, 'POST', world));
}

export async function resetWorld() {
  const b = methods();
  if (b?.resetWorld || b?.reset_world) {
    const r = await (b.resetWorld ?? b.reset_world).call(b);
    return r ? validateAndUnwrap(r) : requestWorldState();
  }
  const {resetUrl} = config();
  if (resetUrl) {
    const r = await httpJson(resetUrl, 'POST', {});
    return r?.islands || r?.state || r?.world_state ? validateAndUnwrap(r) : requestWorldState();
  }
  return requestWorldState();
}

/**
 * Ask one person a question (WHACK v2's "interview"). `world` is the world the user is looking at, so the
 * answer matches the screen. Returns {answer, source: 'template' | 'llm', name, question}.
 * A JS adapter may provide askPerson(agentId, question, world) / ask_person; otherwise POST interviewUrl.
 */
export async function askPerson(agentId, question, world) {
  const b = methods();
  if (b?.askPerson || b?.ask_person) {
    const r = await (b.askPerson ?? b.ask_person).call(b, agentId, question, world);
    return typeof r === 'string' ? JSON.parse(r) : r;
  }
  return httpJson(config().interviewUrl, 'POST', {agent_id: agentId, question, world});
}

/** The model's assumptions for the panel at the bottom of the page: live from Python, else the bundled copy. */
export async function loadAssumptions() {
  try {
    return await httpJson(config().assumptionsUrl, 'GET');
  } catch {
    return httpJson('./data/assumptions.json', 'GET');
  }
}

export async function bundledDefaults() {
  // A single-file offline preview can embed the exact Python defaults.
  if (window.TINY_BUNDLED_DEFAULTS) return validateAndUnwrap(structuredClone(window.TINY_BUNDLED_DEFAULTS));
  return validateAndUnwrap(await httpJson('./data/defaults.json', 'GET'));
}
