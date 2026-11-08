"""Disasters: plague, disease, drought, tsunami, storm. Each has a scale from 0 to 1.

Scale 1 is the worst the model has: a plague or tsunami at scale 1 kills most of the people it reaches
(see DISASTER_PARAMS in sim_constants.py); scale 0.5 kills roughly half as many; scale 0 does nothing.

  plague   one sweep through the islands it names (all if none). Health damage, deaths.
  disease  an epidemic that lasts several years; each year 60% of the people in range are exposed.
  drought  lasts several years; farm output and wild-food regrowth fall by up to DROUGHT_LOSS. Nobody dies directly, they starve.
  tsunami  hits ONE island (random if none is named): stores, goods and stocks are washed away and many drown.
  storm    like a tsunami but milder.

Disasters come from world.disaster_schedule (queued in the frontend, fired in their year) and, if
world.disaster_rate > 0, at random. Dice come from the social RNG the engine passes in, so a seed replays.
"""
import sim_constants as C
from sim_core import num, clamp, log, mark_dead, inherit, living

LABEL = {"plague": "A plague", "disease": "An epidemic", "drought": "A drought", "tsunami": "A tsunami", "storm": "A great storm"}


def default_length(kind, scale):
    if kind == "drought":
        return 2 + round(4 * scale)
    if kind == "disease":
        return 2 + round(2 * scale)
    return 1


def clean(ev):
    """A tidy copy of a queued disaster, or None if it cannot be understood."""
    if not isinstance(ev, dict) or ev.get("type") not in C.DISASTER_TYPES:
        return None
    scale = clamp(num(ev.get("severity"), 0.5), 0.0, 1.0)
    length = int(num(ev.get("length"), 0)) or default_length(ev["type"], scale)
    return {"id": str(ev.get("id") or ""), "type": ev["type"], "severity": scale, "island": ev.get("island") or None,
            "year": int(num(ev.get("year"), 0)), "length": max(1, length)}


def island_scope(w, ev, srng):
    """Island ids a disaster reaches. A tsunami or storm hits one island: the named one, else a random one."""
    named = ev.get("island") if ev.get("island") in w.islands else None
    if named:
        return [named]
    if ev["type"] in ("tsunami", "storm") and w.islands:
        return [srng.choice(sorted(w.islands))]
    return sorted(w.islands)


def drought_factor(w, island_id):
    """Multiplier on farm output and wild-food regrowth on this island right now (1 = normal)."""
    year = int(num(w.current_year, 1))
    worst = 1.0
    for d in w.active_disasters or []:
        if d.get("type") == "drought" and num(d.get("start"), 0) <= year < num(d.get("end"), 0) and d.get("island") in (None, "", island_id):
            worst = min(worst, 1.0 - C.DROUGHT_LOSS * clamp(num(d.get("severity")), 0.0, 1.0))
    return worst


def active_in(w, island_id, kind=None):
    year = int(num(w.current_year, 1))
    return [d for d in (w.active_disasters or []) if num(d.get("start"), 0) <= year < num(d.get("end"), 0)
            and d.get("island") in (None, "", island_id) and (kind is None or d.get("type") == kind)]


def vulnerability(a):
    lo, hi = C.VULNERABLE_AGES
    age = 1.0 if lo <= num(a.age) <= hi else C.VULNERABLE_FACTOR
    return age * (1 + C.WEAK_FACTOR * (1 - clamp(num(a.health, 100), 0, 100) / 100.0))


def strike(w, kind, scale, islands, srng, label=None):
    """One blow of a disaster against the people (and goods) on the given islands. Returns (deaths, hurt)."""
    p = C.DISASTER_PARAMS[kind]
    scope = set(islands)
    people = sorted((a for a in living(w) if a.current_island_id in scope), key=lambda x: x.agent_id)
    if p["goods"]:
        keep = 1.0 - clamp(scale * p["goods"], 0.0, 1.0)
        for a in people:
            a.food, a.wood, a.tools = num(a.food) * keep, num(a.wood) * keep, num(a.tools) * keep
    if p["stock"]:
        keep = 1.0 - clamp(scale * p["stock"], 0.0, 1.0)
        for i in islands:
            isl = w.islands[i]
            isl.food_availability = round(num(isl.food_availability) * keep, 2)
            isl.wood_availability = round(num(isl.wood_availability) * keep, 2)
    dead, hurt = [], 0
    for a in people:
        if srng.random() >= p["contact"]:
            continue
        vuln = vulnerability(a)
        if srng.random() < min(C.DEATH_CAP, p["lethality"] * scale * vuln):
            dead.append(a)
            continue
        hit = p["health_hit"] * scale * srng.uniform(0.3, 1.0) * vuln
        if hit >= 1:
            a.health = num(a.health) - hit
            hurt += 1
        if a.health <= 0:
            dead.append(a)
    for a in dead:                      # mark everyone first, then share estates, so the dead do not inherit from each other
        mark_dead(a, kind)
    for a in dead:
        inherit(w, a)
        log(w, "death", f"{a.name} died aged {int(num(a.age))} ({kind}).", a.agent_id, cause=kind)
    return len(dead), hurt


def fire(w, ev, srng):
    """Start one disaster this year."""
    kind, scale = ev["type"], ev["severity"]
    scope = island_scope(w, ev, srng)
    where = "all islands" if len(scope) == len(w.islands) and len(scope) > 1 else ", ".join(scope)
    if kind in ("drought", "disease"):
        end = int(num(w.current_year, 1)) + int(ev.get("length") or default_length(kind, scale))
        for i in (scope if len(scope) != len(w.islands) else [None]):
            w.active_disasters.append({"id": ev.get("id") or f"x{len(w.active_disasters) + 1}", "type": kind, "severity": scale,
                                       "island": i, "start": int(num(w.current_year, 1)), "end": end})
        log(w, "disaster", f"{LABEL[kind]} (scale {scale:.2f}) begins on {where} and lasts until year {end - 1}.",
            type=kind, severity=scale, islands=scope)
        return                           # a drought works through production; an epidemic's first exposure is tick(), this same year
    deaths, hurt = strike(w, kind, scale, scope, srng)
    log(w, "disaster", f"{LABEL[kind]} (scale {scale:.2f}) strikes {where}: {deaths} dead, {hurt} hurt.",
        type=kind, severity=scale, islands=scope, deaths=deaths, hurt=hurt)


def tick(w, srng):
    """Epidemics that are running expose people again every year; spent disasters are dropped."""
    year = int(num(w.current_year, 1))
    w.active_disasters = [d for d in (w.active_disasters or []) if isinstance(d, dict) and num(d.get("end"), 0) > year]
    for d in list(w.active_disasters):
        if d.get("type") != "disease" or num(d.get("start"), 0) > year:
            continue
        scope = [d["island"]] if d.get("island") in w.islands else sorted(w.islands)
        deaths, hurt = strike(w, "disease", clamp(num(d.get("severity")), 0, 1), scope, srng)
        if deaths or hurt:
            log(w, "disaster", f"The epidemic (scale {num(d.get('severity')):.2f}) on {', '.join(scope) if len(scope) < len(w.islands) else 'all islands'}"
                               f" this year: {deaths} dead, {hurt} sick.", type="disease", severity=d.get("severity"), deaths=deaths, hurt=hurt)


def begin_year(w, srng):
    """Fire this year's queued disasters, maybe add a random one, then run the epidemics already under way."""
    year = int(num(w.current_year, 1))
    if not isinstance(w.disaster_schedule, list):
        w.disaster_schedule = []
    due, later = [], []
    for raw in w.disaster_schedule:
        ev = clean(raw)
        if ev is None:
            continue                      # unreadable entries are dropped
        (due if ev["year"] <= year else later).append(ev)
    w.disaster_schedule = later
    if num(w.disaster_rate) > 0 and srng.random() < clamp(num(w.disaster_rate), 0.0, 1.0):
        kind = srng.choice(list(C.DISASTER_TYPES))
        lo, hi = C.RANDOM_DISASTER_SCALE
        due.append({"id": f"r{year}", "type": kind, "severity": round(srng.uniform(lo, hi), 2), "island": None, "year": year,
                    "length": 0})
    for ev in due:
        fire(w, ev, srng)
    tick(w, srng)
