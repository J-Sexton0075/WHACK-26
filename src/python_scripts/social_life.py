"""Social life, ported from WHACK v2 (engine.py + social.py): couples, lessons, feuds, migration, and interviews.

Everything is stored on the people (partner_id, mentor, grudges, parents, trust_graph), so the frontend can
draw the relationship graph from any saved snapshot and the state round-trips as plain JSON.

The yearly dice come from the social RNG the engine passes in. Wealth is conserved: lessons change skills,
feuds move food and health (never coins), and migration carries a person's belongings with them.
"""
import json
import os
import re
import time
import urllib.request
from collections import defaultdict

import sim_constants as C
from sim_core import (num, clamp, coop, aggr, food_need, is_adult, role, kin, hoard_level, island_capacity, log,
                      trust_of, trust_score, bond, add_grudge, living)

SKILLS = ("farming", "hunting", "crafting")


def _event(w, kind, text, ids, **extra):
    log(w, kind, text, ids[0], participants=list(ids), **extra)


# ---------- couples ----------
def pair_up(w, people, srng):
    """Single adults on one island may become a couple: the most compatible unrelated neighbour (trust, similar cooperation)."""
    year = int(num(w.current_year, 1))
    for a in people:                                   # couples stay together and grow closer
        b = w.agents.get(a.partner_id) if a.partner_id else None
        if b is not None and b.is_alive and a.agent_id < b.agent_id:
            bond(a, b, C.PAIR_TRUST_YEARLY)
    lo, hi = C.PAIR_AGES
    free = [a for a in people if lo <= num(a.age) <= hi and not a.partner_id]
    for a in free:
        if a.partner_id:
            continue
        cands = [b for b in free if b.agent_id != a.agent_id and not b.partner_id
                 and b.current_island_id == a.current_island_id and not kin(a, b)]
        if not cands or srng.random() >= C.PAIR_CHANCE:
            continue
        b = max(cands, key=lambda x: (trust_of(a, x) + 0.5 * (1 - abs(coop(a) - coop(x))), x.agent_id))
        a.partner_id, b.partner_id = b.agent_id, a.agent_id
        a.partner_since = b.partner_since = year
        bond(a, b, C.PAIR_TRUST)
        _event(w, "couple", f"{a.name} and {b.name} became a couple on {a.current_island_id}.", (a.agent_id, b.agent_id), sub="pair")


def end_couples_by_death(w):
    for a in w.agents.values():
        b = w.agents.get(a.partner_id) if a.partner_id else None
        if a.partner_id and (not a.is_alive or b is None or not b.is_alive):
            a.partner_id, a.partner_since = None, None


# ---------- lessons ----------
def mentor_young(w, people, srng):
    """An experienced adult (a parent if there is one, else the most skilled) moves a young person's best skill a step toward their own."""
    year = int(num(w.current_year, 1))
    lo, hi = C.MENTEE_AGES
    for kid in people:
        if not (lo <= num(kid.age) <= hi) or srng.random() >= C.MENTOR_CHANCE:
            continue
        pool = [m for m in people if num(m.age) >= C.MENTOR_MIN_AGE and m.current_island_id == kid.current_island_id and m.agent_id != kid.agent_id]
        if not pool:
            continue
        raw = lambda p, k: num(getattr(p, f"{k}_skill", 1), 1) / C.SKILL_MAX
        mentor = max(pool, key=lambda m: (m.agent_id in (kid.parents or []), max(raw(m, k) for k in SKILLS), m.agent_id))
        skill = max(SKILLS, key=lambda k: raw(mentor, k))
        have, theirs = raw(kid, skill), raw(mentor, skill)
        if theirs - have < C.MENTOR_MIN_GAP:
            continue
        after = have + C.MENTOR_STEP * (theirs - have)
        setattr(kid, f"{skill}_skill", round(after * C.SKILL_MAX, 2))      # only the pupil changes, and only toward the teacher
        kid.mentor = {"mentor": mentor.agent_id, "skill": skill, "year": year}
        bond(kid, mentor, C.TRUST_MENTOR)
        _event(w, "lesson", f"{mentor.name} taught {kid.name} {skill}: {have * C.SKILL_MAX:.1f} to {after * C.SKILL_MAX:.1f} (the teacher has {theirs * C.SKILL_MAX:.1f}).",
               (mentor.agent_id, kid.agent_id), sub="mentor", skill=skill)


# ---------- feuds ----------
def feud_chance(w, v, o, g):
    """Yearly chance that victim v strikes back at offender o, and which friends (same island, trusted or kin, with their own grudge) back them."""
    friends = [f for f in living(w) if f.current_island_id == v.current_island_id and f.agent_id not in (v.agent_id, o.agent_id)
               and (kin(v, f) or trust_of(v, f) >= C.FEUD_FRIEND_TRUST) and num((f.grudges or {}).get(o.agent_id, 0)) > 0]
    backing = sum(num(f.grudges[o.agent_id]) for f in friends)
    return min(C.FEUD_MAX, C.FEUD_SCALE * (g + C.FEUD_FRIENDS * backing) * (0.5 + aggr(v))), friends


def feuds(w, srng):
    """A victim of a raid or quarrel may strike back. The chance rises with their own grudge and their friends' grudges; the offender
    then holds a grudge too, so feuds can escalate. Only food and health move."""
    for v in sorted(w.agents.values(), key=lambda x: x.agent_id):
        if not v.is_alive or not v.grudges:
            continue
        for o_id, g in sorted(list(v.grudges.items())):
            o = w.agents.get(o_id)
            g = num(g)
            if o is None or not o.is_alive or o.current_island_id != v.current_island_id:
                continue
            p, friends = feud_chance(w, v, o, g)
            if srng.random() >= p:
                continue
            take = C.FEUD_TAKE * max(0.0, num(o.food) - food_need(o))
            o.food = num(o.food) - take
            v.food = num(v.food) + take
            o.health = num(o.health) - C.FEUD_INJURY
            v.grudges[o_id] = round(g * 0.3, 3)               # the victim is partly satisfied
            add_grudge(w, o, v, C.GRUDGE_RETALIATION)
            bond(v, o, C.TRUST_FEUD)
            backing = f", {len(friends)} friends backing" if friends else ""
            _event(w, "feud", f"{v.name} struck back at {o.name}: took {take:.1f} food (grudge {g:.2f}{backing}).",
                   (v.agent_id, o_id), sub="feud", grudge=round(g, 2), friends=len(friends), food=round(take, 1))
    for a in w.agents.values():                               # grudges fade and are forgotten
        for o_id in list(a.grudges or {}):
            o = w.agents.get(o_id)
            a.grudges[o_id] = round(num(a.grudges[o_id]) * C.GRUDGE_DECAY, 3)
            if a.grudges[o_id] < C.GRUDGE_MIN or o is None or not o.is_alive or not a.is_alive:
                del a.grudges[o_id]


# ---------- migration ----------
def feud_load(w):
    """Live feuds each person is caught up in (held or suffered), and the number of feuds inside each island."""
    load, per_island = defaultdict(int), defaultdict(int)
    for v in w.agents.values():
        if not v.is_alive:
            continue
        for o_id, g in (v.grudges or {}).items():
            o = w.agents.get(o_id)
            if o is not None and o.is_alive and num(g) >= C.GRUDGE_MIN:
                load[v.agent_id] += 1
                load[o_id] += 1
                if v.current_island_id == o.current_island_id:
                    per_island[v.current_island_id] += 1
    return load, per_island


def migrate(w, people, srng):
    """People may sail to another island for one of three reasons, and take their partner and young children with them:
      hunger  an adult who went short of food, to a clearly cheaper-food island with room;
      feuds   a very cooperative adult caught up in several feuds, to the calmest island with room;
      trade   a trader (or someone with a big surplus) to an island that pays clearly more for what they sell."""
    if not w.migration_enabled or len(w.islands) < 2:
        return
    pop = defaultdict(int)
    for a in people:
        pop[a.current_island_id] += 1
    load, per_island = feud_load(w)
    density = lambda i: per_island[i] / max(1, pop[i])
    room = lambda i: pop[i] < island_capacity(w.islands[i])
    moved = set()
    for a in sorted(people, key=lambda x: x.agent_id):
        if not is_adult(a) or a.agent_id in moved:
            continue
        home = a.current_island_id
        if home not in w.islands:
            continue
        hp = w.islands[home].prices
        motive = dest = None
        # 1. hunger
        if num(a.last_fed, 1) < C.MIGRATE_HUNGER:
            options = sorted((w.islands[i].prices["food"], i) for i in w.islands
                             if i != home and room(i) and w.islands[i].prices["food"] <= hp["food"] * (1 - C.MIGRATE_PRICE_GAIN))
            if options and srng.random() < C.MIGRATE_CHANCE:
                motive, dest = "hunger", options[0][1]
        # 2. feud flight: the peaceable leave a quarrelsome island
        if motive is None and coop(a) >= C.FLIGHT_COOPERATION and load[a.agent_id] >= C.FLIGHT_FEUDS:
            options = sorted((density(i), i) for i in w.islands if i != home and room(i) and density(i) < density(home))
            if options and srng.random() < min(0.9, C.FLIGHT_CHANCE * load[a.agent_id] / C.FLIGHT_FEUDS):
                motive, dest = "feuds", options[0][1]
        # 3. trade: go where what you sell is worth more
        if motive is None:
            trader = str(a.occupation or "").lower() == "trader"
            held = {"food": num(a.food) - hoard_level(a), "wood": num(a.wood) - 2 * C.WOOD_NEED,
                    "tools": num(a.tools) - 1 if role(a) == "crafter" else 0.0}
            chance = C.TRADE_MOVE_TRADER if trader else (C.TRADE_MOVE_OTHER if max(held.values()) > 1 else 0.0)
            if chance and srng.random() < chance:
                best = None
                for i in sorted(w.islands):
                    if i == home or not room(i):
                        continue
                    for good, amount in held.items():
                        if not trader and amount <= 1:
                            continue
                        gain = w.islands[i].prices[good] / max(0.01, hp[good]) - 1
                        if gain >= C.TRADE_MOVE_GAIN and (best is None or gain > best[0]):
                            best = (gain, i)
                if best:
                    motive, dest = "trade", best[1]
        if motive is None:
            continue
        group = [a] + [x for x in people if x.agent_id != a.agent_id and x.current_island_id == home and x.agent_id not in moved
                       and (a.partner_id == x.agent_id or (not is_adult(x) and a.agent_id in (x.parents or [])))]
        for m in group:
            m.current_island_id = dest
            moved.add(m.agent_id)
        pop[home] -= len(group)
        pop[dest] += len(group)
        why = {"hunger": "hungry", "feuds": "fleeing feuds", "trade": "to trade"}[motive]
        _event(w, "migration", f"{a.name} left {home} for {dest} ({why}), with {len(group) - 1} others.",
               [m.agent_id for m in group], sub="migrate", motive=motive, src=home, dest=dest)


def step(w, srng):
    """Couples, lessons, feuds and migration, in that order."""
    people = sorted(living(w), key=lambda a: a.agent_id)
    pair_up(w, people, srng)
    mentor_young(w, people, srng)
    feuds(w, srng)
    migrate(w, people, srng)


# ---------- interviews (rule-based; an LLM may phrase the answer if LLM_API_KEY is set) ----------
try:                                         # same optional .env loading as v2's ai.py
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    load_dotenv()
except Exception:
    pass

_breaker_until = 0.0


def numbers_in(text):
    return {float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)}


def only_known_numbers(text, facts):
    """True if every number in the text appears in the facts: how an LLM is kept from inventing figures."""
    return numbers_in(text) <= numbers_in(json.dumps(facts))


def ask_text(system, user, max_tokens=500):
    """One optional LLM call (OpenAI-compatible). Returns None without a key, with MOCK_LLM=1, or on any failure."""
    global _breaker_until
    key = os.getenv("LLM_API_KEY")
    if not key or os.getenv("MOCK_LLM") == "1" or time.time() < _breaker_until:
        return None
    base = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    body = {"model": os.getenv("LLM_MODEL", "openai/gpt-oss-20b"), "temperature": 0.8, "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    request = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode("utf-8"),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())["choices"][0]["message"]["content"].strip()
    except Exception as error:
        print("interview LLM call failed:", type(error).__name__, error)
        _breaker_until = time.time() + 20
        return None


def persona_text(w, a):
    isl = w.islands.get(a.current_island_id)
    culture = f" ({isl.culture_trait} culture)" if isl is not None and getattr(isl, "culture_trait", None) else ""
    traits = f"cooperation {num(a.cooperation_trait):.0f}/100, aggression {num(a.aggression_trait):.0f}/100"
    return f"{a.name} is {int(num(a.age))}, a {str(a.personalityType).lower()} {a.occupation} on {a.current_island_id}{culture}; {traits}."


def person_events(w, a, n=10):
    pat = re.compile(rf"\b{re.escape(str(a.name))}\b") if a.name else None
    out = []
    for e in w.event_history:
        if e.get("event_type") in ("year_summary", "market"):
            continue
        mine = e.get("primary_agent_id") == a.agent_id or a.agent_id in ((e.get("payload") or {}).get("participants") or []) \
            or (pat is not None and pat.search(str(e.get("description", ""))))
        if mine:
            out.append(f"year {e.get('year')}: {e.get('description')}")
    return out[-n:]


def interview_facts(w, a):
    name = lambda i: w.agents[i].name if i in w.agents else i
    trusts = sorted(((num(s), i) for i, s in (a.trust_graph or {}).items() if i in w.agents and w.agents[i].is_alive), reverse=True)
    ranked = [((s - 50) / C.TRUST_SCALE, i) for s, i in trusts]
    kids = [x.name for x in w.agents.values() if a.agent_id in (x.parents or []) and x.is_alive]
    pupils = [x.name for x in w.agents.values() if x.is_alive and isinstance(x.mentor, dict) and x.mentor.get("mentor") == a.agent_id]
    isl = w.islands.get(a.current_island_id)
    f = {"year": w.current_year, "who": persona_text(w, a), "status": "alive" if a.is_alive else "dead",
         "occupation": a.occupation, "island": a.current_island_id, "age": int(num(a.age)), "health": round(num(a.health)),
         "fed_percent": round(100 * num(a.last_fed, 1)),
         "owns": {"food": round(num(a.food), 1), "wood": round(num(a.wood), 1), "tools": round(num(a.tools), 1), "coins": round(num(a.wealth), 1)},
         "cooperation": round(coop(a), 2), "aggression": round(aggr(a), 2),
         "family": {"parents": [name(p) for p in (a.parents or []) if p in w.agents and w.agents[p].is_alive], "children": kids},
         "trusts": [{"name": name(i), "trust": round(v, 2)} for v, i in ranked[:3] if v >= 0.1],
         "distrusts": [{"name": name(i), "trust": round(v, 2)} for v, i in ranked[::-1][:2] if v <= -0.1],
         "partner": name(a.partner_id) if a.partner_id in w.agents else None,
         "teacher": name(a.mentor["mentor"]) if isinstance(a.mentor, dict) and a.mentor.get("mentor") in w.agents else None,
         "pupils": pupils,
         "grudges_held": [{"against": name(o), "strength": round(num(g), 2)} for o, g in sorted((a.grudges or {}).items()) if o in w.agents],
         "grudges_suffered": [name(v.agent_id) for v in w.agents.values() if v.is_alive and a.agent_id in (v.grudges or {})],
         "disasters_now": [f"{d['type']} (scale {num(d.get('severity')):.2f}, until year {int(num(d.get('end'))) - 1})"
                           for d in (w.active_disasters or []) if d.get("island") in (None, "", a.current_island_id)],
         "island_culture": getattr(isl, "culture_trait", None) if isl is not None else None,
         "last_events": person_events(w, a)}
    return f


TOPICS = [
    (r"hungr|food|eat|starv|famine|harvest", "food"), (r"trade|sell|buy|price|market|deal", "trade"),
    (r"partner|spouse|love|marri|couple|wife|husband", "partner"), (r"feud|grudge|enem|hate|revenge|quarrel|fight", "feuds"),
    (r"move|migrat|leave|sail|abroad|another island", "move"),
    (r"plague|disease|drought|tsunami|storm|disaster|wave|epidemic|flood", "disaster"),
    (r"friend|trust|neighbo|who", "people"), (r"famil|child|parent|born|son|daughter|teach|learn|pupil", "family"),
    (r"afraid|worr|fear|future|hope|goal|want|need|dream", "goals"), (r"rich|wealth|coin|money|poor", "money"),
    (r"health|sick|ill\b", "health"),
]


def interview_template(f, question):
    if f["status"] == "dead":
        last = f["last_events"][-1] if f["last_events"] else "no record"
        return f"(No answer. This person has died. Last record: {last}.)"
    topic = next((t for pat, t in TOPICS if re.search(pat, question.lower())), "self")
    o = f["owns"]
    if topic == "food":
        mood = "I am hungry." if f["fed_percent"] < 70 else "I have enough to eat."
        return f"{mood} I got {f['fed_percent']}% of the food I need this year, and I hold {o['food']} food."
    if topic == "trade":
        tr = [e for e in f["last_events"] if "sold" in e or "traded" in e or "refused" in e]
        return ("Recently: " + tr[-1] + ".") if tr else f"I have not traded much lately. I hold {o['coins']} coins and {o['tools']} tools."
    if topic == "partner":
        return f"I share my life with {f['partner']}." if f["partner"] else "I am on my own at the moment."
    if topic == "feuds":
        held = ", ".join(f"{g['against']} ({g['strength']})" for g in f["grudges_held"])
        suffered = ", ".join(f["grudges_suffered"])
        if not held and not suffered:
            return "I have no quarrels with anyone."
        return (f"I hold a grudge against {held}. " if held else "") + (f"{suffered} holds a grudge against me." if suffered else "")
    if topic == "move":
        mv = [e for e in f["last_events"] if " left " in e]
        return ("Yes: " + mv[-1] + ".") if mv else f"I have lived on {f['island']} and I have not sailed anywhere lately."
    if topic == "disaster":
        if f["disasters_now"]:
            return "We are living through " + ", ".join(f["disasters_now"]) + "."
        d = [e for e in f["last_events"] if any(k in e for k in ("plague", "epidemic", "drought", "tsunami", "storm"))]
        return ("Not now, but I remember: " + d[-1] + ".") if d else "Nothing terrible is happening to us right now."
    if topic == "people":
        t = ", ".join(f"{x['name']} ({x['trust']})" for x in f["trusts"]) or "nobody in particular"
        d = ", ".join(f"{x['name']} ({x['trust']})" for x in f["distrusts"])
        return f"I trust {t}." + (f" I do not trust {d}." if d else "")
    if topic == "family":
        fam = f["family"]
        return (f"My parents: {', '.join(fam['parents']) or 'gone'}. My children: {', '.join(fam['children']) or 'none'}."
                + (f" Teacher: {f['teacher']}." if f["teacher"] else "") + (f" Pupils: {', '.join(f['pupils'])}." if f["pupils"] else ""))
    if topic == "money":
        return f"I own {o['coins']} coins, {o['food']} food, {o['wood']} wood and {o['tools']} tools."
    if topic == "health":
        return f"My health is {f['health']} out of 100. I am {f['age']} years old."
    if topic == "goals":
        return f"{f['who']}"
    return f"{f['who']} I have health {f['health']}."


def interview(w, agent_id, question, use_llm=True):
    a = w.agents.get(agent_id)
    if a is None:
        raise KeyError(agent_id)
    question = str(question).strip()[:300]
    f = interview_facts(w, a)
    answer, source = interview_template(f, question), "template"
    if use_llm and a.is_alive:
        system = ("You are playing one person in a simulated island society, answering an interviewer in first person, in 1-3 sentences, in character. "
                  "Use ONLY the facts in the JSON about yourself. If asked something the facts do not cover, say you do not know. "
                  "Every number you write must appear in the JSON. Never mention JSON, facts or the simulation.")
        text = ask_text(system, json.dumps({"facts": f, "question": question}))
        if text and only_known_numbers(text, f):
            answer, source = text, "llm"
    return {"agent": agent_id, "name": a.name, "question": question, "answer": answer, "source": source}
