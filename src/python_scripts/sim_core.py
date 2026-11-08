"""Shared helpers for the merged model: unit conversions, trust, grudges, death and inheritance.

partial-wace stores skills as 1..10 and traits as 0..100; WHACK v2's formulas use 0..1. The accessors here
convert, so the ported formulas stay recognisable. Nothing in this file rolls dice.
"""
import sim_constants as C


def num(value, default=0.0):
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if x == x and abs(x) != float("inf") else default


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------- reading a person ----------
def coop(a):
    return clamp(num(getattr(a, "cooperation_trait", 50), 50) / 100.0, 0.0, 1.0)


def aggr(a):
    return clamp(num(getattr(a, "aggression_trait", 50), 50) / 100.0, 0.0, 1.0)


def skill(a, name):
    """Skill in 0.05..1 (v2 units) from the 1..10 value stored on the person."""
    return clamp(num(getattr(a, f"{name}_skill", 1), 1) / C.SKILL_MAX, 0.05, 1.0)


def is_adult(a):
    return num(a.age) >= C.ADULT_AGE


def food_need(a):
    return C.FOOD_NEED_ADULT if is_adult(a) else C.FOOD_NEED_CHILD


def role(a):
    """What the person does for a living in the model. Builders craft, fishers hunt; traders and the unemployed only keep a garden."""
    o = str(getattr(a, "occupation", "") or "").lower()
    if o == "farmer":
        return "farmer"
    if o in ("hunter", "fisher"):
        return "hunter"
    if o in ("crafter", "builder"):
        return "crafter"
    return "idle"


def best_occupation(a):
    return max((("farmer", skill(a, "farming")), ("hunter", skill(a, "hunting")), ("crafter", skill(a, "crafting"))), key=lambda t: t[1])[0]


def living(w):
    return [a for a in w.agents.values() if a.is_alive]


def gini(values):
    """Inequality coefficient of a list of holdings: 0 = everybody has the same, towards 1 = one person has everything."""
    xs = sorted(max(0.0, num(v)) for v in values)
    n, total = len(xs), sum(xs)
    return sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(xs)) / (n * total) if n and total > 0 else 0.0


def kin(a, b):
    pa, pb = list(getattr(a, "parents", []) or []), list(getattr(b, "parents", []) or [])
    return a.agent_id in pb or b.agent_id in pa or bool(set(pa) & set(pb))


def island_capacity(isl):
    """People an island supports: (4 + 6 x fertility) x its size, where size = founders / 5 the first time the engine saw it."""
    return (4 + 6 * max(0.0, num(isl.fertility, 1))) * max(1.0, num(getattr(isl, "capacity_scale", 1.0), 1.0))


def hoard_level(a):
    """Food a person will not sell or give away: 1.5 years of need if fully cooperative, 3 if fully selfish."""
    return food_need(a) * (1.5 + 1.5 * (1 - coop(a)))


# ---------- the event log ----------
def log(w, kind, text, agent=None, **payload):
    w.log_event(kind, agent if agent is not None else "SYSTEM", text, payload or None)


# ---------- trust: stored on each person, 0..100, 50 = neutral; v2 worked in -1..1 ----------
def trust_score(a, other_id):
    return num((getattr(a, "trust_graph", None) or {}).get(other_id, 50), 50)


def trust_of(a, b):
    """Trust between two people in -1..1: the average of the two directions they have recorded."""
    seen = [trust_score(x, y.agent_id) for x, y in ((a, b), (b, a)) if y.agent_id in (x.trust_graph or {})]
    return ((sum(seen) / len(seen)) - 50) / C.TRUST_SCALE if seen else 0.0


def bond(a, b, delta):
    """Move trust between two people both ways by `delta` (v2 units, -1..1)."""
    if a.agent_id == b.agent_id:
        return
    for x, y in ((a, b), (b, a)):
        if not isinstance(x.trust_graph, dict):
            x.trust_graph = {}
        x.trust_graph[y.agent_id] = round(clamp(trust_score(x, y.agent_id) + delta * C.TRUST_SCALE, 0, 100), 1)


def fade_trust(w):
    """Trust drifts 5% a year back to neutral; links to the dead or to people who no longer exist are dropped."""
    for a in w.agents.values():
        if not isinstance(a.trust_graph, dict):
            a.trust_graph = {}
        if not a.is_alive:
            continue            # a dead person's last record is left as it was
        for other_id in list(a.trust_graph):
            other = w.agents.get(other_id)
            score = 50 + (num(a.trust_graph[other_id], 50) - 50) * C.TRUST_DECAY
            if other is None or not other.is_alive or abs(score - 50) < 1.0:
                del a.trust_graph[other_id]
            else:
                a.trust_graph[other_id] = round(score, 1)


def add_grudge(w, victim, offender, amount):
    if not w.social_life or victim.agent_id == offender.agent_id:
        return
    if not isinstance(victim.grudges, dict):
        victim.grudges = {}
    victim.grudges[offender.agent_id] = round(num(victim.grudges.get(offender.agent_id, 0.0)) + amount, 3)


# ---------- death ----------
def inherit(w, dead):
    """The estate is split between living people on the same island (else anywhere), so coins are never destroyed."""
    heirs = [x for x in living(w) if x.current_island_id == dead.current_island_id and x.agent_id != dead.agent_id] or \
            [x for x in living(w) if x.agent_id != dead.agent_id]
    if not heirs:
        return
    for good in ("wealth", "food", "wood", "tools"):
        share = num(getattr(dead, good, 0)) / len(heirs)
        for h in heirs:
            setattr(h, good, num(getattr(h, good, 0)) + share)
        setattr(dead, good, 0.0)


def mark_dead(a, cause):
    a.is_alive = False
    a.health = 0
    a.cause_of_death = cause
    a.partner_id = None
    a.partner_since = None


def kill(w, a, cause, text=None, announce=True):
    """Mark the person dead, share out their belongings, log it."""
    mark_dead(a, cause)
    inherit(w, a)
    if announce:
        log(w, "death", text or f"{a.name} died aged {int(num(a.age))} ({cause}).", a.agent_id, cause=cause)
