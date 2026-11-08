#!/usr/bin/env python3
"""Partial Wace local JSON bridge — this is the ONLY new file needed.

No frontend or supplied Python source files are modified by this program.
No simulation rules or mock results are implemented in this file.

The existing frontend already calls:
    GET  /api/world     -> initial WorldState.serialize_state_for_frontend() JSON
    POST /api/simulate  -> edited world JSON in; updated Python world JSON out
    POST /api/reset     -> fresh defaults from Python

The default mode calls SimulationEngine.run_step() from YOUR Python files.
For an external backend, use --mode relay. In relay mode, a separate Python
process GETs /api/next to obtain the full frontend submission (including
its deleted_*_ids), then POSTs /api/result with the simulated world state.

Examples:
    python src/bridge.py --python-dir ./python_scripts --frontend-dir .
    python src/bridge.py --python-dir ../my-python-code --frontend-dir .
    python src/bridge.py --mode relay --python-dir ../my-python-code --frontend-dir .

Open http://localhost:8000/ after starting this program. The bridge and
browser communicate over localhost only; no internet service is used.
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import queue
import sys
import threading
import uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
REQUIRED_PY_MODULES = ("main", "world", "defaults", "interface",
                       "attributes", "exceptions")
MODULE_LOAD_ORDER = ("exceptions", "attributes", "world", "defaults",
                     "main", "interface", "sim_constants", "sim_core", "genetics", "disasters",
                     "social_life", "assumptions", "simulation_engine")
MAX_BODY = 16 * 1024 * 1024
# World-level settings merged in from WHACK v2. The frontend edits them and sends them back on every Start.
EXTRA_WORLD_KEYS = ("social_life", "migration_enabled", "island_trade", "genetics", "disaster_rate",
                    "disaster_schedule", "active_disasters")


def source_file(directory: Path, stem: str) -> Path | None:
    """Use normal module names or unchanged upload names such as main(3).py."""
    ordinary = directory / f"{stem}.py"
    if ordinary.is_file():
        return ordinary
    numbered = []
    for path in directory.glob(f"{stem}*.py"):
        match = re.fullmatch(re.escape(stem) + r"\s*\((\d+)\)\.py", path.name)
        if match:
            numbered.append((int(match.group(1)), path))
    return max(numbered, default=(0, None), key=lambda item: item[0])[1]


def locate_python_dir(explicit: str | None) -> Path:
    if explicit:
        directory = Path(explicit).expanduser().resolve()
        missing = [name + ".py" for name in REQUIRED_PY_MODULES
                   if source_file(directory, name) is None]
        if missing:
            raise FileNotFoundError(f"Missing Python files in {directory}: {', '.join(missing)}")
        return directory
    for candidate in (HERE, HERE / "python_scripts", HERE.parent,
                      HERE.parent / "python_scripts"):
        if all(source_file(candidate, name) for name in REQUIRED_PY_MODULES):
            return candidate
    raise FileNotFoundError(
        "Could not find your Python scripts. Supply --python-dir PATH (the folder "
        "containing main.py, world.py, defaults.py, interface.py, etc.)."
    )


def locate_frontend_dir(explicit: str | None) -> Path:
    if explicit:
        directory = Path(explicit).expanduser().resolve()
        if not (directory / "index.html").is_file() or not (directory / "app.js").is_file():
            raise FileNotFoundError(f"Not a Partial Wace Mundus Novus frontend directory: {directory}")
        return directory
    for candidate in (HERE, HERE / "partial-wace", HERE.parent / "partial-wace"):
        if (candidate / "index.html").is_file() and (candidate / "app.js").is_file():
            return candidate
    raise FileNotFoundError(
        "Could not find the existing frontend. Supply --frontend-dir PATH "
        "(the folder containing index.html and app.js)."
    )


def load_existing_python(directory: Path):
    # Load the user's exact files under their normal module import names.
    # Numbered upload names work without renaming or rewriting their files.
    # The load order respects imports in the supplied Python scripts.
    for name in MODULE_LOAD_ORDER:
        path = source_file(directory, name)
        if path is None:
            continue  # simulation_engine.py is optional in relay mode.
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return (sys.modules["main"], sys.modules["world"],
            sys.modules.get("simulation_engine") if source_file(directory, "simulation_engine") else None)


def optional_module(directory: Path, name: str):
    """social_life (interviews) and assumptions (the model-assumptions panel) are optional extras."""
    return sys.modules.get(name) if source_file(directory, name) else None


def require_state(value: object) -> dict:
    """Accept the exact world dictionary or an optional {state:...} wrapper."""
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    state = value.get("world_state", value.get("state", value))
    if not isinstance(state, dict):
        raise ValueError("The supplied world state must be a JSON object")
    for key in ("islands", "agents"):
        if not isinstance(state.get(key), dict):
            raise ValueError(f"Expected '{key}' to be a dictionary keyed by IDs")
    return state


def field(record: dict, primary: str, alias: str | None = None, default=None):
    if primary in record:
        return record[primary]
    if alias and alias in record:
        return record[alias]
    return default


class Bridge:
    def __init__(self, main, world, engine_module, mode: str, timeout: int, social=None, assumptions=None):
        self.main = main
        self.world_module = world
        self.engine_module = engine_module
        self.social = social
        self.assumptions = assumptions
        self.mode = mode
        self.timeout = timeout
        self.run_id = uuid.uuid4().hex
        self.lock = threading.RLock()
        self.jobs = queue.Queue()
        self.pending = {}  # request ID -> (threading.Event, returned state/error holder)
        self.last_submission = None
        with self.lock:
            self._reset_locked()

    def _reset_locked(self) -> dict:
        # main.load() and main.restart() only operate when run as __main__ in
        # the supplied scripts; explicitly call their setup function instead.
        self.main.world = self.world_module.WorldState()
        self.main.setup_defaults()
        # defaults.py stores object instances, not factories. Make independent
        # copies so simulation changes never mutate the defaults for next reset.
        self.main.world.islands = copy.deepcopy(self.main.world.islands)
        self.main.world.agents = copy.deepcopy(self.main.world.agents)
        return copy.deepcopy(self.main.request_world_state())

    def current(self) -> dict:
        with self.lock:
            return copy.deepcopy(self.main.request_world_state())

    def reset(self) -> dict:
        with self.lock:
            for event, holder in self.pending.values():
                holder["error"] = "Simulation was reset before a result arrived"
                event.set()
            self.pending.clear()
            while not self.jobs.empty():
                try:
                    self.jobs.get_nowait()
                except queue.Empty:
                    break
            self.last_submission = None
            return self._reset_locked()

    def _create_island(self, island_id: str, data: dict):
        cls = self.world_module.Island
        return cls(island_id=island_id,
                   fertility=field(data, "fertility", default=1),
                   food_avail=field(data, "food_availability", "food_avail", 1),
                   wood_avail=field(data, "wood_availability", "wood_avail", 1),
                   regen_rate=field(data, "resource_regeneration_rate", "regen_rate", 1),
                   weather=field(data, "weather", default="Temperate"),
                   disease_rate=field(data, "disease_risk", "disease_rate", 1),
                   culture=field(data, "culture_trait", "culture", "Peaceful"))

    def _create_agent(self, agent_id: str, data: dict):
        cls = self.world_module.Agent
        return cls(agent_id=agent_id,
                   name=field(data, "name", default=agent_id),
                   current_island_id=data.get("current_island_id", ""),
                   age=field(data, "age", default=20),
                   personality_type=field(data, "personalityType", "personality_type", "Calm"),
                   occupation=field(data, "occupation", default="farmer"))

    def _build_world(self, submitted: dict):
        """Translate frontend's complete JSON snapshot into a new WorldState (does not touch main.world).

        interface.py in the newest supplied files has no update_from_frontend
        function, so this adapter uses the existing WorldState/Island/Agent
        constructors instead.
        Missing IDs are removed: this is how frontend deletions are applied.
        """
        old = self.main.world
        new = self.world_module.WorldState()
        for key in ("current_year", "max_years", "active_seed",
                    "scarcity_level", "price_index", "event_history") + EXTRA_WORLD_KEYS:
            setattr(new, key, copy.deepcopy(submitted.get(key, getattr(old, key, getattr(new, key, None)))))
        if not isinstance(new.event_history, list):
            raise ValueError("event_history must be a list")
        for key in ("disaster_schedule", "active_disasters"):
            if not isinstance(getattr(new, key), list):
                raise ValueError(f"{key} must be a list")
        for key in ("social_life", "migration_enabled", "island_trade"):
            setattr(new, key, bool(getattr(new, key)))
        for island_id, data in submitted["islands"].items():
            if not isinstance(island_id, str) or not isinstance(data, dict):
                raise ValueError("Every island needs a string ID and an object of attributes")
            obj = (copy.deepcopy(old.islands[island_id]) if island_id in old.islands
                   else self._create_island(island_id, data))
            obj.__dict__.update(copy.deepcopy(data))
            obj.island_id = island_id
            new.entities_add_island(obj)
        for agent_id, data in submitted["agents"].items():
            if not isinstance(agent_id, str) or not isinstance(data, dict):
                raise ValueError("Every agent needs a string ID and an object of attributes")
            obj = (copy.deepcopy(old.agents[agent_id]) if agent_id in old.agents
                   else self._create_agent(agent_id, data))
            obj.__dict__.update(copy.deepcopy(data))
            obj.agent_id = agent_id
            if obj.current_island_id not in new.islands:
                raise ValueError(f"Agent {agent_id} refers to missing island {obj.current_island_id!r}")
            new.entities_add_agent(obj)
        return new

    def _apply_locked(self, submitted: dict) -> None:
        # The frontend already sends deleted_island_ids/deleted_agent_ids when
        # appropriate. Keep them in last_submission for any external consumer;
        # the authoritative dictionaries built above perform the actual deletions.
        self.main.world = self._build_world(submitted)

    def interview(self, raw: dict) -> dict:
        """Ask one person a question. The frontend sends the world it is showing, so the answer matches the screen."""
        if self.social is None:
            raise RuntimeError("social_life.py was not found in the Python directory, so interviews are unavailable")
        if not isinstance(raw, dict):
            raise ValueError("Expected a JSON object")
        agent_id, question = raw.get("agent_id"), raw.get("question")
        if not isinstance(agent_id, str) or not isinstance(question, str) or not question.strip():
            raise ValueError("An interview needs agent_id and a non-empty question")
        with self.lock:
            shown = raw.get("world")
            world = self._build_world(require_state(shown)) if isinstance(shown, dict) else self.main.world
            try:
                return self.social.interview(world, agent_id, question)
            except KeyError:
                raise ValueError(f"No such person: {agent_id}")

    def model_assumptions(self) -> dict:
        if self.assumptions is None:
            raise RuntimeError("assumptions.py was not found in the Python directory")
        return self.assumptions.build()

    def simulate(self, raw: dict) -> dict:
        state = require_state(raw)
        with self.lock:
            if self.mode == "relay" and self.pending:
                raise RuntimeError("A previous simulation request is still awaiting a result")
            self.last_submission = copy.deepcopy(raw)
            self._apply_locked(state)
            if self.mode == "engine":
                if self.engine_module is None:
                    raise RuntimeError("No simulation_engine.py found; use --mode relay for an external backend")
                before = copy.deepcopy(self.main.world)
                try:
                    result = self.engine_module.SimulationEngine(self.main.world).run_step()
                    return copy.deepcopy(require_state(result))
                except Exception:
                    self.main.world = before
                    raise
            request_id = uuid.uuid4().hex
            done = threading.Event()
            holder = {"state": None, "error": None}
            self.pending[request_id] = (done, holder)
            self.jobs.put({"request_id": request_id, "world_state": copy.deepcopy(raw)})

        # Wait without holding the world lock so the backend can POST its result.
        arrived = done.wait(self.timeout)
        with self.lock:
            self.pending.pop(request_id, None)
            if not arrived:
                raise TimeoutError("No result received from the Python/backend process")
            if holder["error"]:
                raise RuntimeError(holder["error"])
            return copy.deepcopy(holder["state"])

    def next_job(self, seconds: float) -> dict | None:
        try:
            return self.jobs.get(timeout=max(0.0, min(seconds, 30.0)))
        except queue.Empty:
            return None

    def publish(self, raw: dict) -> dict:
        state = require_state(raw)
        request_id = raw.get("request_id") if isinstance(raw, dict) else None
        with self.lock:
            # /api/result can also load a standalone Python-produced state.
            if request_id is None and len(self.pending) == 1:
                request_id = next(iter(self.pending))
            if request_id is not None and request_id not in self.pending:
                raise ValueError("Unknown or expired request_id")
            self._apply_locked(state)
            actual = copy.deepcopy(self.main.request_world_state())
            if request_id is not None:
                event, holder = self.pending[request_id]
                holder["state"] = actual
                event.set()
            return actual


def make_handler(frontend: Path, bridge: Bridge):
    class Handler(SimpleHTTPRequestHandler):
        server_version = "PartialWace/bridge"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(frontend), **kwargs)

        def _json(self, status: int, value):
            payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _body(self):
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("Invalid Content-Length") from error
            if n < 1 or n > MAX_BODY:
                raise ValueError("Expected JSON body between 1 byte and 16 MB")
            return json.loads(self.rfile.read(n))

        def do_GET(self):
            parsed = urlsplit(self.path)
            try:
                if parsed.path == "/api/world":
                    return self._json(200, bridge.current())
                if parsed.path == "/api/health":
                    return self._json(200, {
                        "ok": True,
                        "mode": bridge.mode,
                        "run_id": bridge.run_id,
                        "interviews": bridge.social is not None
                    })
                if parsed.path == "/api/assumptions":
                    return self._json(200, bridge.model_assumptions())
                if parsed.path == "/api/next":
                    timeout = float(parse_qs(parsed.query).get("timeout", ["0"])[0])
                    return self._json(200, bridge.next_job(timeout) or {})
                if parsed.path.startswith("/api/"):
                    return self._json(404, {"error": "Unknown bridge endpoint"})
                return super().do_GET()
            except Exception as error:
                return self._json(400, {"error": str(error)})

        def do_POST(self):
            path = urlsplit(self.path).path
            try:
                data = self._body()
                if path == "/api/reset":
                    return self._json(200, bridge.reset())
                if path == "/api/simulate":
                    return self._json(200, bridge.simulate(data))
                if path == "/api/result":
                    return self._json(200, bridge.publish(data))
                if path == "/api/interview":
                    return self._json(200, bridge.interview(data))
                return self._json(404, {"error": "Unknown bridge endpoint"})
            except TimeoutError as error:
                return self._json(504, {"error": str(error)})
            except (ValueError, TypeError, KeyError) as error:
                return self._json(400, {"error": str(error)})
            except Exception as error:
                self.log_error("Bridge/Python error: %s", error)
                return self._json(500, {"error": str(error)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Partial Wace Mundus Novus local Python-to-browser bridge")
    parser.add_argument("--python-dir", help="Directory containing your UNMODIFIED Python scripts")
    parser.add_argument("--frontend-dir", help="Directory containing the UNMODIFIED index.html/app.js")
    parser.add_argument("--mode", choices=("engine", "relay"), default="engine",
                        help="Call supplied simulation_engine.run_step, or wait for an external result")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TINY_PORT", "8000")))
    parser.add_argument("--timeout", type=int, default=110,
                        help="Seconds to await an external result in relay mode (default 110)")
    parser.add_argument("--export-defaults", metavar="PATH",
                        help="Write the Python defaults to PATH as JSON (data/defaults.json) and exit")
    parser.add_argument("--export-assumptions", metavar="PATH",
                        help="Write the model assumptions to PATH as JSON (data/assumptions.json, the offline copy) and exit")
    args = parser.parse_args()
    scripts = locate_python_dir(args.python_dir)
    frontend = locate_frontend_dir(args.frontend_dir)
    python_main, python_world, engine = load_existing_python(scripts)
    state = Bridge(python_main, python_world, engine, args.mode, args.timeout,
                   social=optional_module(scripts, "social_life"), assumptions=optional_module(scripts, "assumptions"))
    if args.export_defaults or args.export_assumptions:
        for target, value in ((args.export_defaults, state.current), (args.export_assumptions, state.model_assumptions)):
            if target:
                Path(target).write_text(json.dumps(value(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(f"Wrote {target}")
        return
    if args.mode == "engine" and engine is None:
        parser.error("Your Python directory has no simulation_engine.py; pass --mode relay instead")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(frontend, state))
    server.daemon_threads = True
    print(f"Partial Wace Mundus Novus frontend: http://localhost:{args.port}")
    print(f"Python scripts (unchanged): {scripts}")
    print(f"Frontend files (unchanged): {frontend}")
    print(f"Bridge mode: {args.mode}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nBridge stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
