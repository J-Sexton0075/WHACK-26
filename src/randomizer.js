
const STORAGE_KEY = 'partial-wace-randomizer-v1';

let random01 = Math.random;

function seededRandom(seed) {
  let t = Number(seed) >>> 0;

  return function () {
    t = (t + 0x6D2B79F5) >>> 0;

    let x = t;
    x = Math.imul(x ^ (x >>> 15), x | 1);
    x ^= x + Math.imul(x ^ (x >>> 7), x | 61);

    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

const copy = value => structuredClone(value);

const esc = value => String(value ?? '').replace(
  /[&<>"']/g,
  c => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;',
    '"':'&quot;', "'":'&#39;'
  }[c])
);

const pick = items =>
  items[Math.floor(random01() * items.length)];

const randint = (a, b) =>
  Math.ceil(a) +
  Math.floor(random01() * (Math.floor(b) - Math.ceil(a) + 1));

const clamp = (n, low, high) =>
  Math.max(low, Math.min(high, n));

const labelize = s => ({
  personalityType: 'Personality',
  culture_trait: 'Culture',
  is_alive: 'Alive',
  active_seed: 'World seed'
}[s] || s.replaceAll('_', ' ').replaceAll('.', ' / '))
  .replace(/^./, x => x.toUpperCase());

function merge(defaultValue, saved) {
  if (saved === undefined) return copy(defaultValue);

  if (Array.isArray(defaultValue))
    return Array.isArray(saved) ? copy(saved) : copy(defaultValue);

  if (
    defaultValue && typeof defaultValue === 'object' &&
    saved && typeof saved === 'object' && !Array.isArray(saved)
  ) {
    const result = copy(defaultValue);

    for (const [key, value] of Object.entries(saved)) {
      result[key] = key in result
        ? merge(result[key], value)
        : copy(value);
    }

    return result;
  }

  return typeof saved === typeof defaultValue
    ? saved
    : copy(defaultValue);
}

function weightedProfile(profiles, weights) {
  const candidates = profiles
    .map(p => ({
      profile: p,
      weight: Math.max(0, Number(weights?.[p.id] ?? 1))
    }))
    .filter(x => Number.isFinite(x.weight) && x.weight > 0);

  const total = candidates.reduce((sum, x) => sum + x.weight, 0);

  if (!total)
    throw new Error('Select at least one usable profile for each entity type.');

  let roll = random01() * total;

  for (const item of candidates) {
    roll -= item.weight;
    if (roll < 0) return item.profile;
  }

  return candidates.at(-1).profile;
}

function randomValue(rule) {
  if ('values' in rule) return pick(rule.values);

  if ('true_probability' in rule)
    return random01() < clamp(Number(rule.true_probability), 0, 1);

  if (rule.integer)
    return randint(Number(rule.min), Number(rule.max));

  return Number((
    Number(rule.min) +
    random01() * (Number(rule.max) - Number(rule.min))
  ).toFixed(rule.decimals ?? 3));
}

function randomFields(target, rules) {
  for (const [key, rule] of Object.entries(rules)) {
    if (!rule.enabled) continue;

    const path = key.split('.');
    let at = target;

    for (const part of path.slice(0, -1))
      at = (at[part] ||= {});

    at[path.at(-1)] = randomValue(rule);
  }
}

function randomSubset(source, a, b) {
  const pool = [...new Set(source)];
  const count = randint(
    Math.min(a, pool.length),
    Math.min(b, pool.length)
  );

  const out = [];

  for (let i = 0; i < count; i++)
    out.push(pool.splice(randint(0, pool.length - 1), 1)[0]);

  return out;
}

function validate(config, profiles) {
  const check = (name, a, b, low, high) => {
    if (
      ![a, b].every(Number.isFinite) ||
      a > b || a < low || b > high
    )
      throw new Error(
        `${name}: choose a valid minimum and maximum (${low}–${high}).`
      );
  };

  check('Islands', config.islands.min, config.islands.max, 0, 7);

  check(
    'People per island',
    config.population.min_per_island,
    config.population.max_per_island,
    0, 100
  );

  // Validate the optional Randomizer seed.
  if (
    config.seed.enabled &&
    (
      !Number.isInteger(config.seed.value) ||
      config.seed.value < 0 ||
      config.seed.value > 4294967295
    )
  ) {
    throw new Error(
      'Randomizer seed must be a whole number from 0 to 4294967295.'
    );
  }

  for (const [group, entries] of Object.entries(config.fields)) {
    for (const [name, rule] of Object.entries(entries)) {
      if (!rule.enabled) continue;

      if ('min' in rule) {
        check(`${group} / ${name}`, rule.min, rule.max, -1e9, 1e9);

        if (rule.integer && Math.ceil(rule.min) > Math.floor(rule.max))
          throw new Error(`No whole numbers in ${name}'s range.`);
      }

      if ('values' in rule && !rule.values.length)
        throw new Error(`Enter at least one value for ${name}.`);
    }
  }

  for (const key of ['needs', 'goals']) {
    const r = config.complex[key];
    if (r.enabled)
      check(key, r.min_items, r.max_items, 0, 20);
  }

  const t = config.complex.trust_graph;

  if (t.enabled) {
    check('Trust links', t.min_links, t.max_links, 0, 40);
    check('Trust score', t.score_min, t.score_max, 0, 100);
  }

  if (
    config.islands.max > 0 &&
    !profiles.some(p =>
      p.kind === 'island' &&
      Number(config.weights.island[p.id] ?? 1) > 0
    )
  )
    throw new Error('Enable at least one island profile.');

  if (
    config.population.max_per_island > 0 &&
    !profiles.some(p =>
      p.kind === 'agent' &&
      Number(config.weights.agent[p.id] ?? 1) > 0
    )
  )
    throw new Error('Enable at least one person profile.');
}

function makeIdFactory(received, kind) {
  const prefix = kind === 'island' ? 'i' : 'a';
  const collection = kind === 'island' ? 'islands' : 'agents';

  const used = new Set(
    Object.keys(received?.[collection] || {})
  );

  let counter = Math.max(
    0,
    ...[...used].map(id => {
      const match = new RegExp(`^${prefix}(\\d+)$`).exec(id);
      return match ? Number(match[1]) : 0;
    })
  );

  return () => {
    let id;

    do {
      id = `${prefix}${++counter}`;
    } while (used.has(id));

    used.add(id);
    return id;
  };
}

function generate(config, original, profiles, received) {
  validate(config, profiles);

  const previousRandom = random01;

  random01 = config.seed.enabled
    ? seededRandom(config.seed.value)
    : Math.random;

  try {

    const newIslandId = makeIdFactory(received, 'island');
    const newAgentId = makeIdFactory(received, 'agent');

  const world = copy(original);
  world.islands = {};
  world.agents = {};
  world.event_history = [];

  randomFields(world, config.fields.world);

  world.max_years = Math.max(
    1, Math.round(Number(world.max_years) || 1)
  );

  world.current_year = clamp(
    Math.round(Number(world.current_year) || 1),
    1, world.max_years
  );

  const associations = {};

  const islandTemplate =
    Object.values(original.islands || {})[0] || {};

  const agentTemplate =
    Object.values(original.agents || {})[0] || {};

  const numIslands = randint(
    config.islands.min,
    config.islands.max
  );

  // Create the islands.
  for (let i = 0; i < numIslands; i++) {
    const profile = weightedProfile(
      profiles.filter(p => p.kind === 'island'),
      config.weights.island
    );

    const id = newIslandId();

    const island = {
      ...copy(islandTemplate),
      ...copy(profile.params),
      island_id: id
    };

    randomFields(island, config.fields.island);

    // Keep Python's nested island attribute dictionary in sync.
    island.attributeDictionary = Object.fromEntries(
      Object.entries(island)
        .filter(([key]) => key !== 'attributeDictionary')
    );

    world.islands[id] = island;
  }

  // Populate the islands.
  for (const islandId of Object.keys(world.islands)) {
    const population = randint(
      config.population.min_per_island,
      config.population.max_per_island
    );

    for (let i = 0; i < population; i++) {
      const profile = weightedProfile(
        profiles.filter(p => p.kind === 'agent'),
        config.weights.agent
      );

      const id = newAgentId();

      const agent = {
        ...copy(agentTemplate),
        ...copy(profile.params),
        agent_id: id,
        current_island_id: islandId
      };

      randomFields(agent, config.fields.agent);
      if (config.seed.enabled) {
        world.active_seed = Number(config.seed.value);
      }

      if (
        config.population.name_mode === 'generated' ||
        !String(agent.name || '').trim()
      ) {
        agent.name =
          `${config.population.name_prefix.trim() || 'Settler'} ${id}`;
      }

      // Do not copy relationship IDs from another world.
      agent.trust_graph = {};

      world.agents[id] = agent;
      associations[id] = profile.id;
    }
  }

  // Populate complex person attributes.
  for (const agent of Object.values(world.agents)) {
    for (const key of ['needs', 'goals']) {
      const rule = config.complex[key];

      if (rule.enabled)
        agent[key] = randomSubset(
          rule.pool,
          rule.min_items,
          rule.max_items
        );
    }

    const t = config.complex.trust_graph;

    if (t.enabled) {
      const peers = Object.values(world.agents)
        .filter(p =>
          p.current_island_id === agent.current_island_id &&
          p.agent_id !== agent.agent_id
        )
        .map(p => p.agent_id);

      const selected = randomSubset(
        peers,
        Math.min(t.min_links, peers.length),
        Math.min(t.max_links, peers.length)
      );

      for (const id of selected)
        agent.trust_graph[id] = randint(
          t.score_min, t.score_max
        );
    }
  }

  // Visual layout only. These positions are not Python parameters.
  const positions = {};

  if (config.layout.scatter) {
    const margin = clamp(
      Number(config.layout.margin) || 0, 0, 125
    );

    for (const id of Object.keys(world.islands)) {
      positions[id] = {
        x: margin + random01() * (480 - 2 * margin),
        y: margin + random01() * (330 - 2 * margin)
      };
    }
  }

  return {world, associations, positions};

  } finally {
    random01 = previousRandom;
  }
}

export function mountRandomizer({
  getProfiles, getWorld, getReceived,
  canEdit, apply, toast, onReady
}) {
  const button = document.querySelector('#randomizeBtn');
  const options = document.querySelector('#randomizeOptionsBtn');
  const panel = document.querySelector('#randomizePanel');
  const wrapper = document.querySelector('.randomize-wrap');

  const instance = {ready: false};

  let defaults = null;
  let config = null;

  button.disabled = true;
  options.disabled = true;

  const field = (attributes, value, type = 'number') =>
    `<input class="rng-input" ${attributes}
      type="${type}"
      ${type === 'number' ? 'step="any"' : ''}
      value="${esc(value)}">`;

  const range = (title, left, right, a, b) =>
    `<div class="rng-rule">
      <span class="rng-rule-name">${esc(title)}</span>
      <div class="rng-controls">
        ${field(`data-rng-path="${left}"`, a)}
        <span>to</span>
        ${field(`data-rng-path="${right}"`, b)}
      </div>
    </div>`;

  const option = (label, path, value) =>
    `<label class="rng-toggle">
      <input type="checkbox" data-rng-path="${path}"
        ${value ? 'checked' : ''}> ${esc(label)}
    </label>`;

  function ruleRow(group, key, rule) {
    const attrs = prop =>
      `data-rng-group="${group}"
       data-rng-field="${esc(key)}"
       data-rng-prop="${prop}"`;

    let controls = '';

    if ('min' in rule) {
      controls = `
        ${field(attrs('min'), rule.min)}
        <span>to</span>
        ${field(attrs('max'), rule.max)}
        <label title="Whole numbers">
          <input type="checkbox" ${attrs('integer')}
            ${rule.integer ? 'checked' : ''}> int
        </label>`;
    } else if ('values' in rule) {
      controls = field(
        attrs('values'),
        rule.values.join(', '),
        'text'
      );
    } else if ('true_probability' in rule) {
      controls = `
        <span>Chance of true</span>
        ${field(attrs('true_probability'), rule.true_probability)}`;
    }

    return `<div class="rng-rule">
      <label class="rng-rule-name">
        <input type="checkbox" ${attrs('enabled')}
          ${rule.enabled ? 'checked' : ''}>
        ${esc(labelize(key))}
      </label>
      <div class="rng-controls">${controls}</div>
    </div>`;
  }

  function complexRow(key, rule) {
    const att = prop =>
      `data-rng-complex="${key}" data-rng-prop="${prop}"`;

    const pair = (left, right) =>
      `${field(att(left), rule[left])}
       <span>to</span>
       ${field(att(right), rule[right])}`;

    const controls = key === 'trust_graph'
      ? `<span>Links</span>${pair('min_links', 'max_links')}
         <span>Score</span>${pair('score_min', 'score_max')}`
      : `<span>Items</span>${pair('min_items', 'max_items')}
         ${field(att('pool'), rule.pool.join(', '), 'text')}`;

    return `<div class="rng-rule">
      <label class="rng-rule-name">
        <input type="checkbox" ${att('enabled')}
          ${rule.enabled ? 'checked' : ''}>
        ${esc(labelize(key))}
      </label>
      <div class="rng-controls">${controls}</div>
    </div>`;
  }

  function drawPanel() {
    if (!config) return;

    const profileRows = kind =>
      getProfiles()
        .filter(p => p.kind === kind)
        .map(p => `
          <label class="rng-weight">
            <span>${esc(p.name)}</span>
            ${field(
              `data-rng-weight="${kind}"
               data-rng-profile="${esc(p.id)}"`,
              config.weights[kind][p.id] ?? 1
            )}
          </label>`)
        .join('') || '<p>No profiles yet.</p>';

    const rules = kind =>
      Object.entries(config.fields[kind])
        .map(([key, rule]) => ruleRow(kind, key, rule))
        .join('');

    panel.innerHTML = `
      <div class="rng-title">
        <b>RANDOMIZER SETTINGS</b>
        <button id="randomizeCloseBtn" type="button"
          aria-label="Close">×</button>
      </div>

      <p class="rng-help">
        Saved in this browser. Zero profile weight means
        never use that profile. Replaces the editable local world only.
      </p>

      <details open>
        <summary>01 / POPULATION & MAP</summary>
        ${option(
          'Use a fixed randomizer seed',
          'seed.enabled',
          config.seed.enabled
        )}

        <label class="rng-rule">
          <span class="rng-rule-name">Randomizer seed</span>
          ${field(
            'data-rng-path="seed.value"',
            config.seed.value
          )}
        </label>

        ${range(
          'Number of islands',
          'islands.min', 'islands.max',
          config.islands.min, config.islands.max
        )}

        ${range(
          'People per island',
          'population.min_per_island',
          'population.max_per_island',
          config.population.min_per_island,
          config.population.max_per_island
        )}

        <label class="rng-rule">
          <span class="rng-rule-name">Person naming</span>
          <select class="rng-input"
            data-rng-path="population.name_mode">
            <option value="generated"
              ${config.population.name_mode === 'generated'
                ? 'selected' : ''}>
              Generated names
            </option>
            <option value="profile"
              ${config.population.name_mode === 'profile'
                ? 'selected' : ''}>
              Keep profile names
            </option>
          </select>
        </label>

        <label class="rng-rule">
          <span class="rng-rule-name">Generated name prefix</span>
          ${field(
            'data-rng-path="population.name_prefix"',
            config.population.name_prefix, 'text'
          )}
        </label>

        ${option(
          'Scatter islands randomly',
          'layout.scatter',
          config.layout.scatter
        )}

        <label class="rng-rule">
          <span class="rng-rule-name">Map margin</span>
          ${field(
            'data-rng-path="layout.margin"',
            config.layout.margin
          )}
        </label>
      </details>

      <details>
        <summary>02 / WHICH PROFILES?</summary>
        <p class="rng-help">
          Each profile's weight controls how often it is chosen.
          New profiles default to weight 1.
        </p>
        <b>ISLAND PROFILES</b>
        ${profileRows('island')}
        <b>PERSON PROFILES</b>
        ${profileRows('agent')}
      </details>

      <details>
        <summary>03 / ISLAND PARAMETERS</summary>
        <p class="rng-help">
          Unticked fields keep their chosen profile's value.
        </p>
        ${rules('island')}
      </details>

      <details>
        <summary>04 / PERSON PARAMETERS</summary>
        ${rules('agent')}
        ${Object.entries(config.complex)
          .map(([key, rule]) => complexRow(key, rule)).join('')}
      </details>

      <details>
        <summary>05 / WORLD PARAMETERS</summary>
        ${rules('world')}
      </details>

      <button id="randomizeRestoreBtn"
        class="rng-restore" type="button">
        ↶ RESTORE RANDOMIZER DEFAULTS
      </button>`;
  }

  function show(open) {
    panel.hidden = !open;
    options.setAttribute('aria-expanded', String(open));
    if (open) drawPanel();
  }

  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    } catch {
      toast('Could not save randomizer settings in this browser.');
    }
  }

  function read(el) {
    if (el.type === 'checkbox') return el.checked;

    if (el.type === 'number') {
      if (!el.value.trim() || !Number.isFinite(Number(el.value)))
        throw new Error('Please enter a valid number.');
      return Number(el.value);
    }

    if (
      el.dataset.rngProp === 'values' ||
      el.dataset.rngProp === 'pool'
    )
      return el.value.split(',').map(x => x.trim()).filter(Boolean);

    return el.value;
  }

  panel.addEventListener('change', e => {
    const el = e.target;

    if (!el.matches(
      '[data-rng-path],[data-rng-group],' +
      '[data-rng-complex],[data-rng-weight]'
    )) return;

    try {
      const value = read(el);

      if (el.dataset.rngPath) {
        const keys = el.dataset.rngPath.split('.');
        let target = config;

        for (const k of keys.slice(0, -1))
          target = target[k];

        target[keys.at(-1)] = value;

      } else if (el.dataset.rngWeight) {
        config.weights[el.dataset.rngWeight][
          el.dataset.rngProfile
        ] = Math.max(0, value);

      } else if (el.dataset.rngGroup) {
        config.fields[el.dataset.rngGroup][
          el.dataset.rngField
        ][el.dataset.rngProp] = value;

      } else if (el.dataset.rngComplex) {
        config.complex[el.dataset.rngComplex][
          el.dataset.rngProp
        ] = value;
      }

      save();

    } catch (error) {
      toast(error.message);
      drawPanel();
    }
  });

  panel.addEventListener('click', e => {
    if (e.target.closest('#randomizeCloseBtn'))
      show(false);

    if (e.target.closest('#randomizeRestoreBtn')) {
      config = copy(defaults);

      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {}

      drawPanel();
      toast('Randomizer settings restored to file defaults.');
    }
  });

  button.addEventListener('click', () => {
    if (!instance.ready || !canEdit()) return;

    try {
      const result = generate(
        config, getWorld(), getProfiles(), getReceived()
      );

      apply(result);
      show(false);

      toast(
        `Randomized ${Object.keys(result.world.islands).length} ` +
        `islands and ${Object.keys(result.world.agents).length} ` +
        `people. Press START to send to Python.`
      );

    } catch (error) {
      toast(`Randomizer: ${error.message}`);
    }
  });

  options.addEventListener('click', () => {
    if (instance.ready) show(panel.hidden);
  });

  document.addEventListener('pointerdown', e => {
    if (!panel.hidden && !wrapper.contains(e.target))
      show(false);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !panel.hidden)
      show(false);
  });

  (async () => {
    try {
      const response = await fetch(
        './data/randomize.json',
        {cache: 'no-store'}
      );

      if (!response.ok)
        throw new Error(`HTTP ${response.status}`);

      defaults = await response.json();

      let saved = null;

      try {
        saved = JSON.parse(
          localStorage.getItem(STORAGE_KEY) || 'null'
        );
      } catch {}

      config = merge(defaults, saved || {});
      // Remove the old textual scarcity choices from saved settings.
      delete config.fields.world.scarcity_level.values;
      instance.ready = true;
      options.disabled = false;
      onReady();

    } catch (error) {
      toast(
        `Could not load data/randomize.json: ${error.message}`
      );
    }
  })();

  return instance;
}
