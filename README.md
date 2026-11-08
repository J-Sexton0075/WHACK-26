# tiny archipelago 🌴

A static, dependency-free **frontend** for the Python island simulator. Its sea,
islands, people, huts, palm trees and animations are deliberately handmade
pixel graphics, drawn on a small canvas and upscaled with nearest-neighbour
rendering. The controls are deliberately simple, square, and slightly kitbashed.

**The browser never simulates anything.** It visualizes data provided by Python and sends locally edited JSON back only when you press **Start simulation** (one press = one simulated year). The simulation itself lives in `python_scripts/` and is served by `bridge.py` (see the next section).

## Merged from WHACK v2

This version combines the partial-wace interface with the mechanics and views of WHACK v2.
Run it with `python bridge.py` and open the address it prints (default `http://localhost:8000`).

**Views.** The tabs above the map switch between **MAP**, **SPLIT** (map and graph side by side; they stack on a narrow window) and **GRAPH**. The choice and the graph's filters are remembered by the browser.

**Relationship graph.** One dot per living person, grouped by island, dot size = coins. Chips switch each kind of line on or off (with a count): **Couple, Feud, Family, Teacher & pupil, Trust, Distrust**. A slider sets how strong a trust/distrust line must be, and a menu limits the graph to one island. Click a dot to inspect the person, a line to read what it means. The graph is drawn from the world being shown, so it also works on Time Machine snapshots.

**Disasters (tab "DISASTERS").** Plague, epidemic (disease), drought, tsunami and storm, each with a **scale from 0 to 1**; at 1 a plague or tsunami kills most of the people it reaches. The tab shows a live estimate of what the chosen scale does, from the model's own numbers. Queue a disaster for a year (and an island, and for droughts/epidemics a length), or set a chance per year for random ones. Running disasters and queued ones show as tags on the map and in the stats strip.

**Migration.** With "Migration between islands" on, people may move for three reasons: **hunger**, **feud flight** (very cooperative people caught up in two or more feuds leave for the calmest island with room) and **trade** (traders, or anyone with a big surplus, chase markets that pay more). Partners and young children go with them, and every move is logged.

**Society.** With "Couples, lessons and feuds" on: any two unrelated single adults can become a couple (and only couples have children), young people learn from experienced adults, and raids and refused trades leave grudges that can turn into feuds. Trade between islands is a separate switch.

**Inspector.** A person shows family, partner, teachers/pupils and grudges (click to jump), their recent events, and an **Ask** box: pick a question or type one. Answers are built from that person's real record in the world on screen. By default they are rule-based; set `LLM_API_KEY` (and optionally `LLM_BASE_URL`, `LLM_MODEL`) in the environment of `bridge.py` to have a language model phrase them. A model's answer is discarded in favour of the rule-based one if it quotes a number that is not in the record. `MOCK_LLM=1` forces the rule-based answers even when a key is set.

**Running.** **Start simulation** now runs year after year, about one a second, until you press **Stop simulation** or nobody is left alive (it then stops by itself). The world is locked for editing while it runs; Stop, then edit. The Time Machine keeps the newest 150 years.

**Genes.** Five traits (farming, hunting, crafting, cooperation, aggression) have two alleles each. A child gets one randomly chosen allele from each parent, each allele may mutate, and the child's trait is the average of its two alleles (no dominant or recessive alleles). Lessons change a skill but not the alleles, so a taught skill is not inherited. Founders' alleles sit evenly either side of the value they were given, so they look unchanged. Constants: `GENE_SPREAD`, `MUTATION_RATE`, `MUTATION_STEP`, `GENE_TRAIT_MIN`. The **Genes** world setting turns it off (children then follow the old parent-average rule). The inspector shows a person's alleles.

**Names.** Only the first generation keeps chosen names. A child is named for the island they were born on (i1 = a, i2 = b, ... i7 = g) plus a running number for that island, e.g. `a21`, and keeps it wherever they move.

**Zoom.** Map: mouse wheel (about the pointer), the + / - buttons, or "zoom to island"; drag the open sea to pan once zoomed. Graph: wheel, + / - and FIT; drag the background to pan.

**Import.** The **Import** button (top right) replaces the world with one from a `.json` file, in the same shape as `/api/world` (plus an optional `"positions"` map for where the islands sit). `data/seven_islands.json` is ready to use: 7 named-by-id islands with different fertility, stocks, weather, disease risk and culture, and 10 to 17 people each (12, 17, 10, 13, 15, 11, 16 = 94), every one with a different name, varying skills, temperament, age, health and coins, and a few acquaintances so the graph has lines from year 1. Import, then press Start. Like Randomize, the world is not sent to Python until you press Start.

**Numbers.** The strip above the map and the world-stats box show people, **total coins**, the **inequality (Gini) coefficient** of coins, average health, couples and feuds.

**Model assumptions.** The panel at the bottom of the page ("WHAT THE MODEL ASSUMES") lists every tunable, built from `python_scripts/sim_constants.py`, so it cannot disagree with the engine.

### Python files added or changed

- `sim_constants.py`: every tunable (economy, conflict, society, migration, disasters).
- `sim_core.py`: shared helpers (trust, grudges, death and inheritance, Gini).
- `disasters.py`, `social_life.py`, `genetics.py`: the new mechanics and the interview.
- `assumptions.py`: the assumptions panel as data.
- `simulation_engine(1).py`: rewritten, one year per call (the browser calls it repeatedly to run continuously).
- `world(3).py`, `defaults(3).py`: new person/world fields; defaults now start people with 20 coins and islands with stocks of 60 food and 60 wood (the old all-1 placeholders starved everyone within a few years).

After changing `defaults(3).py` or `assumptions.py`, refresh the bundled copies with:

```bash
python bridge.py --export-defaults data/defaults.json --export-assumptions data/assumptions.json
```

A copy of the files as they were before this merge is in `../_backup_before_v2_merge/`.

## Quick start

Unzip and serve the folder as static files:

```bash
cd tiny-archipelago
python -m http.server 8000
```

Visit `http://localhost:8000`. The app tries to request live Python state on every
load. Without a working bridge, it **clearly shows an offline label** and loads
`data/defaults.json`, a static translation of the values actually present in your
uploaded `defaults.py` and the constructors in `world.py`. This is for layout
and editing while integrating. **Start simulation will not fabricate a result** in
offline mode.

There is no `npm install`, build step, or external CDN.

## Connecting your existing Python pipe

Choose **one** transport method. The frontend does not require a particular
backend framework.

### A. JavaScript adapter supplied by your Python host / webview (recommended if already piping)

Before `app.js` loads, expose these asynchronous methods:

```js
window.ISLAND_SIM_BRIDGE = {
  requestWorldState: async () => /* return WorldState.serialize_state_for_frontend() */,
  startSimulation: async (editedState) => /* pass editedState to Python, await and return new world state */,
  resetWorld: async () => /* reset Python and return initial world state */,
};
```

Snake-case aliases `request_world_state`, `start_simulation`, `reset_world` also work.
These functions may return a parsed object or a JSON string.

You can also inject a received state directly using
`window.TinyArchipelago.receiveWorld(serializedWorld)`.

### B. JSON endpoints supplied by your existing server

In `index.html`, before the `<script type="module" src="./app.js">` line, set:

```html
<script>
  window.ISLAND_SIM_CONFIG = {
    worldUrl: '/your-existing/read-world-endpoint',     // GET on load/reload
    simulateUrl: '/your-existing/start-endpoint',       // POST on Start
    resetUrl: '/your-existing/reset-endpoint',          // POST on Reset
  };
</script>
```

The shipped defaults are placeholder `/api/world`, `/api/simulate`, and `/api/reset`
paths; **no route implementation is included**. You must point them at the real
endpoints or provide the adapter above. The `GET` and `POST` bodies use JSON.
The simulation response must contain the new serialized world state. Supported
shapes are `{...worldState}`, `{state: worldState}`, and
`{world_state: worldState, event_history: [...]}`.

## JSON contract (based on the uploaded Python source)

The top-level payload is your actual `WorldState.serialize_state_for_frontend()`:

```json
{
  "current_year": 1,
  "max_years": 30,
  "active_seed": 42,
  "scarcity_level": "moderate",
  "price_index": {"food": 1.0, "wood": 1.0, "tools": 5.0},
  "islands": {"i1": {"island_id": "i1", "fertility": 1, "food_availability": 1, "wood_availability": 1, "resource_regeneration_rate": 1, "weather": "Cold", "disease_risk": 1, "culture_trait": "Hardworking", "attributeDictionary": {}}},
  "agents": {"a1": {"agent_id": "a1", "name": "Shiraz", "current_island_id": "i1", "age": 18, "personalityType": "Calm", "occupation": "farmer"}},
  "event_history": [],
  "deleted_island_ids": [],
  "deleted_agent_ids": []
}
```

The short objects above are abbreviated *for documentation*, not actual data.
In the real app, unknown fields and all extra `world.py` agent properties are
preserved. In particular, use the Python wire keys `food_availability`,
`resource_regeneration_rate`, `disease_risk`, `culture_trait`, and
`personalityType`; do not silently rename them to the informal labels used in
the feature description.

The two **extra** arrays, `deleted_island_ids` and `deleted_agent_ids`, are
computed when Start is pressed. Only IDs present in the **latest received
world state** but absent from the current edited world are included. Deleting
an object created locally and not yet submitted never appears in those arrays.
Removed objects are also omitted from the `islands` and `agents` dictionaries.
Deleting an island removes its residents in the same edit.

Profiles, layout coordinates, visual animation and local history are **UI-only
metadata** and are not included in the JSON sent to Python.

## Controls

- **Build:** drag `Place an island` into the sea or use the `+ PLACE` button;
  choose the island profile used for each new landmass. Drag people profiles
  onto a specific island. Click an island to edit its Python fields, assign
  exact counts of each people profile, and open its resident list.
- **Move and delete:** drag land around the sea; drop it onto either UI sidebar
  to remove the island and its people. There is also a dedicated Delete button.
- **Profiles:** create, rename, edit or remove reusable island and people
  blueprints. Every parameter's *field name* is fixed; numeric values accept
  any number and text values offer suggestions while allowing custom entries.
  Editing a profile changes **future** instances, not existing ones.
- **Event log:** displays Python's `event_history`. Click a recognized person
  name or ID to view their attributes. It also supports the
  `primary_agent_id` and common `payload` agent reference fields.
- **Timeline:** each successfully received simulation output becomes a local
  snapshot. Click earlier snapshots to inspect them; Restore to branch from
  one. There are no invented intermediate states.
- **Fast-forward:** while awaiting the Python simulation response, sprites
  wander and interact under rapid pixel day/night cycles and scanlines.
  This is purely visual; none of this animation alters the world state.

## A note on the attached Python files

The provided Python files appear to be in-progress. For example:

- `defaults.py` currently writes `default_islands : list [` without an `=`.
- `main.py` imports `Agent`, `Island`, `WorldState` through `interface.py`; their
  definitions actually live in `world.py`, and those imports form a circular
  dependency.
- `interface.py`'s `update_from_frontend_default` references `"creature"`
  instead of `"culture_trait"`, calls `agents_dict()` although it is a dict,
  and has other indexing/iteration issues.

Those files have **not** been changed here, as requested. Their owner will need
to correct the Python side and provide the transport before end-to-end
simulation is possible. The frontend itself is ready to receive and display a
correct serialized state.

## Files

- `index.html` — layout and UI entry point
- `styles.css` — squared-off, homemade UI styling
- `pixels.js` — pixel canvas renderer, island growth, collision resolution,
  pixel sprites and purely cosmetic simulation animation
- `app.js` — user interactions, profiles, editing, local snapshots and payloads
- `bridge.js` — minimal Python transport adapter, configurable
- `data/defaults.json` — static initial values derived from supplied Python

### One-file offline preview

A separate `tiny-archipelago-demo.html` is included alongside the ZIP download.
Open it directly in a browser to inspect the design and edit bundled defaults;
it cannot produce a simulated result until your Python transport is connected.
The source ZIP is the recommended version for integration and editing.
