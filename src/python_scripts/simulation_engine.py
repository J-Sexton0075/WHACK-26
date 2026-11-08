"""The yearly simulation: partial-wace's four phases (harvest, survival, trade, regrowth) rebuilt on WHACK v2's economy,
with couples, lessons, feuds, migration and disasters added.

One call to run_step() simulates ONE year, then returns WorldState.serialize_state_for_frontend() as before.

Order inside a year (v2's simulate_year, minus the parts that were not asked for: policies and technology):
  disasters -> production -> children fed -> gifts to the hungry -> trade -> raids -> eating/heat/illness
  -> couples, lessons, feuds, migration -> ageing, deaths, births -> trust fades -> year summary

Dice are seeded from (world.active_seed, year), so the same world and seed always replay the same year.
Skills here are 1..10 and traits 0..100; sim_core converts them to the 0..1 units v2's formulas use.
"""
import copy
import random
from collections import defaultdict

import sim_constants as C
import disasters
import social_life
import genetics
from sim_core import (num, clamp, coop, aggr, skill, is_adult, food_need, role, best_occupation, living, gini,
                      hoard_level, island_capacity, log, bond, add_grudge, kill, fade_trust)
from world import Agent
from interface import get_world

LEGACY_SCARCITY = {"low": 0.2, "moderate": 0.5, "high": 0.8, "extreme": 1.0}
NEW_PERSON_FIELDS = (("last_fed", 1.0), ("parents", []), ("partner_id", None), ("partner_since", None),
                     ("mentor", None), ("grudges", {}), ("cause_of_death", ""), ("genes", {}))
DEFAULT_PRICES = {"food": 1.0, "wood": 1.0, "tools": 5.0}


class SimulationEngine:
    def __init__(self, world=None):
        self.world = world if world is not None else get_world()

    # ------------------------------------------------------------------ entry point
    def run_step(self) -> dict:
        w = self.world
        year = int(num(w.current_year, 1))
        self.rng = random.Random(f"demography:{w.active_seed}:{year}")    # births, deaths, illness
        self.srng = random.Random(f"social:{w.active_seed}:{year}")       # trade disputes, raids, disasters, social life
        self.grng = random.Random(f"genes:{w.active_seed}:{year}")        # which allele a child gets, and mutations
        raw = w.scarcity_level
        scarcity = LEGACY_SCARCITY.get(raw.lower(), 0.5) if isinstance(raw, str) else num(raw, 0.5)
        self.scarcity = clamp(scarcity, 0.0, 1.0)
        w.scarcity_level = round(self.scarcity, 1)
        self.born = self.died = 0
        self.deals = defaultdict(lambda: [0, 0.0])
        start_pop = len(living(w))

        self.prepare()
        disasters.begin_year(w, self.srng)
        self.produce()
        self.feed_children()
        self.share_with_hungry()
        self.trade()
        self.raids()
        self.consume()
        if w.social_life:
            social_life.step(w, self.srng)
        self.demographics()
        social_life.end_couples_by_death(w)
        fade_trust(w)
        self.finish_year(start_pop)
        w.current_year = year + 1
        return w.serialize_state_for_frontend()

    # ------------------------------------------------------------------ set-up
    def prepare(self):
        """Fill in anything the frontend did not send, and tidy links that point at people who no longer exist."""
        w = self.world
        here = defaultdict(int)
        for a in living(w):
            here[a.current_island_id] += 1
        for iid, isl in w.islands.items():
            isl.fertility = max(0.0, num(isl.fertility, 1))
            isl.food_availability = max(0.0, num(isl.food_availability))
            isl.wood_availability = max(0.0, num(isl.wood_availability))
            isl.resource_regeneration_rate = max(0.0, num(isl.resource_regeneration_rate, 1))
            isl.disease_risk = clamp(num(isl.disease_risk), 0.0, 1.0)
            isl.food_max = max(num(getattr(isl, "food_max", 0)), isl.food_availability)       # the stock regrows up to its highest value so far
            isl.wood_max = max(num(getattr(isl, "wood_max", 0)), isl.wood_availability)
            if not hasattr(isl, "capacity_scale"):
                isl.capacity_scale = max(1.0, here[iid] / 5.0)
            if not isinstance(getattr(isl, "prices", None), dict):
                isl.prices = {}
            for good, price in DEFAULT_PRICES.items():
                isl.prices.setdefault(good, price)
        for a in w.agents.values():
            for name, default in NEW_PERSON_FIELDS:      # people saved before the merge lack the social fields
                if not hasattr(a, name) or (getattr(a, name) is None and isinstance(default, (list, dict))):
                    setattr(a, name, copy.deepcopy(default))
            if not isinstance(a.trust_graph, dict):
                a.trust_graph = {}
            if not isinstance(a.grudges, dict):
                a.grudges = {}
            a.grudges = {o: g for o, g in a.grudges.items() if o in w.agents and o != a.agent_id}
            partner = w.agents.get(a.partner_id) if a.partner_id else None
            if a.partner_id and (not a.is_alive or partner is None or not partner.is_alive or partner.partner_id != a.agent_id):
                a.partner_id, a.partner_since = None, None
        if getattr(w, "genetics", True):
            genetics.ensure(w)
        self.update_prices()

    def base_price(self, good):
        return max(0.01, num(self.world.price_index.get(good), DEFAULT_PRICES[good]) if isinstance(self.world.price_index, dict) else DEFAULT_PRICES[good])

    def update_prices(self):
        """Each island's prices follow what its people have against what they need; the world's price_index is the base."""
        w = self.world
        for iid, isl in w.islands.items():
            pop = [a for a in living(w) if a.current_island_id == iid]
            if not pop:
                continue
            ratio = sum(num(a.food) for a in pop) / max(sum(food_need(a) for a in pop) * 1.5, 0.1)
            isl.prices["food"] = round(self.base_price("food") * clamp(1.0 / max(ratio, 0.25), 0.4, 4.0), 2)
            wood_ratio = sum(num(a.wood) for a in pop) / max(len(pop) * 2, 0.1)
            isl.prices["wood"] = round(self.base_price("wood") * clamp(1.0 / max(wood_ratio, 0.33), 0.4, 3.0), 2)
            having = sum(1 for a in pop if num(a.tools) >= 1) / len(pop)
            isl.prices["tools"] = round(self.base_price("tools") * clamp(6.0 - 4.0 * having, 2.0, 8.0) / 4.0, 2)

    # ------------------------------------------------------------------ production
    def produce(self):
        w = self.world
        land = 1 - C.SCARCITY_LOSS * self.scarcity
        people = living(w)
        for iid, isl in w.islands.items():
            dry = disasters.drought_factor(w, iid)
            workers = [a for a in people if a.current_island_id == iid and is_adult(a)]
            tool_of = lambda a: C.TOOL_BONUS if num(a.tools) >= 1 else 0.0
            want = {a.agent_id: 6.0 * (0.4 + skill(a, "hunting")) * (1 + tool_of(a)) for a in workers if role(a) == "hunter"}
            total_want = sum(want.values())
            take_ratio = min(1.0, isl.food_availability * 0.6 / total_want) if total_want else 0.0     # hunters never take more than 60% of the stock
            for a in workers:
                r = role(a)
                if r == "farmer":
                    a.food = num(a.food) + 11.0 * (0.4 + skill(a, "farming")) * isl.fertility * (1 + tool_of(a)) * dry * land
                elif r == "hunter":
                    got = want[a.agent_id] * take_ratio
                    a.food = num(a.food) + got
                    isl.food_availability -= got
                elif r == "crafter":
                    gather = min(isl.wood_availability, 6.0 * (0.4 + skill(a, "crafting")))
                    isl.wood_availability -= gather
                    a.wood = num(a.wood) + gather
                    n_tools = min(num(a.wood) // C.WOOD_PER_TOOL, 1 + skill(a, "crafting") * 2)
                    a.wood -= n_tools * C.WOOD_PER_TOOL
                    a.tools = num(a.tools) + n_tools
                    a.food = num(a.food) + 2.0          # a small garden, so crafters rely on trade rather than on nothing
                else:
                    a.food = num(a.food) + 2.0          # traders and the unemployed keep a garden too
                if r != "crafter":
                    g = min(isl.wood_availability, 1.5)  # everyone gathers a little firewood
                    isl.wood_availability -= g
                    a.wood = num(a.wood) + g
                if num(a.tools) >= 1:
                    a.tools = max(0.0, num(a.tools) - C.TOOL_WEAR)
            rate = C.REGEN_BASE * isl.resource_regeneration_rate
            isl.food_availability += max(0.0, isl.food_max * land - isl.food_availability) * min(1.0, rate) * dry
            isl.wood_availability += max(0.0, isl.wood_max * land - isl.wood_availability) * min(1.0, rate * 1.2)
            isl.food_availability = round(isl.food_availability, 2)
            isl.wood_availability = round(isl.wood_availability, 2)

    def feed_children(self):
        """Children cannot work, so their parents (or, if those died, the most cooperative adults on the island) feed them first."""
        w = self.world
        for c in [a for a in living(w) if not is_adult(a)]:
            need = food_need(c) - num(c.food)
            if need <= 0:
                continue
            carers = [w.agents[p] for p in (c.parents or []) if p in w.agents and w.agents[p].is_alive]
            if not carers:
                carers = sorted((a for a in living(w) if is_adult(a) and a.current_island_id == c.current_island_id),
                                key=lambda a: (-coop(a), a.agent_id))
            for p in carers:
                give = min(need, max(0.0, num(p.food) - food_need(p)))   # carers keep enough for themselves first
                p.food = num(p.food) - give
                c.food = num(c.food) + give
                need -= give
                if need <= 0:
                    break
            if num(c.wood) < C.WOOD_NEED:
                for p in carers:
                    give = min(C.WOOD_NEED - num(c.wood), max(0.0, num(p.wood) - C.WOOD_NEED))
                    p.wood = num(p.wood) - give
                    c.wood = num(c.wood) + give

    def share_with_hungry(self):
        """Voluntary gifts: a cooperative neighbour gives cooperation x (food beyond 1.2 years of need) to the hungriest person."""
        w = self.world
        for iid in w.islands:
            pop = [a for a in living(w) if a.current_island_id == iid]
            for donor in sorted(pop, key=lambda a: (-coop(a), a.agent_id)):
                spare = num(donor.food) - food_need(donor) * 1.2
                if spare <= 0:
                    continue
                hungry = sorted((a for a in pop if a.agent_id != donor.agent_id and num(a.food) < food_need(a)),
                                key=lambda a: (num(a.food) - food_need(a), a.agent_id))
                if not hungry:
                    break
                budget = coop(donor) * spare
                for r in hungry:
                    give = min(budget, food_need(r) - num(r.food))
                    if give < 0.05:
                        break
                    donor.food = num(donor.food) - give
                    r.food = num(r.food) + give
                    budget -= give
                    bond(donor, r, C.TRUST_GIFT)

    # ------------------------------------------------------------------ trade and conflict
    def dispute_chance(self, s, b):
        p = C.DISPUTE_SCALE * (aggr(s) + aggr(b)) / 2 * (1 - (coop(s) + coop(b)) / 2)
        return min(0.9, p * (C.STRANGER_DISPUTE if s.current_island_id != b.current_island_id else 1.0))

    def trade(self):
        w = self.world
        self.update_prices()
        wood_need = C.WOOD_NEED
        rules = (
            ("food", lambda a: max(0.0, food_need(a) - num(a.food)), lambda a: max(0.0, num(a.food) - hoard_level(a))),
            ("wood", lambda a: max(0.0, wood_need - num(a.wood)),
             lambda a: max(0.0, num(a.wood) - wood_need * 2 - (C.WOOD_PER_TOOL * 2 if role(a) == "crafter" else 0))),
            ("tools", lambda a: 1.0 if (num(a.tools) < 1 and role(a) != "crafter") else 0.0,
             lambda a: max(0.0, num(a.tools) - 1) if role(a) == "crafter" else 0.0),
        )
        for good, need_fn, surplus_fn in rules:
            pool_all = living(w)
            buyers = sorted((a for a in pool_all if need_fn(a) > 0), key=lambda a: (-need_fn(a), a.agent_id))
            pool = sorted((s for s in pool_all if surplus_fn(s) > 0), key=lambda s: (-coop(s), s.agent_id))
            for b in buyers:
                sellers = [s for s in pool if s.current_island_id == b.current_island_id and s.agent_id != b.agent_id and surplus_fn(s) > 0]
                if w.island_trade:
                    sellers += [s for s in pool if s.current_island_id != b.current_island_id and surplus_fn(s) > 0]
                for s in sellers:
                    need = need_fn(b)
                    if need <= 0:
                        break
                    qty = min(need, surplus_fn(s))
                    cross = s.current_island_id != b.current_island_id
                    price = w.islands[s.current_island_id].prices[good] * (1.3 - 0.3 * coop(s) + (C.CROSS_ISLAND_COST if cross else 0.0))
                    qty = min(qty, max(0.0, num(b.wealth)) / price)         # a buyer can only spend the coins they have
                    if qty < 0.05:
                        continue
                    if self.srng.random() < self.dispute_chance(s, b):       # the seller refuses; the buyer tries someone else
                        bond(s, b, C.TRUST_QUARREL)
                        add_grudge(w, b, s, C.GRUDGE_QUARREL)
                        log(w, "dispute", f"{s.name} refused to sell {good} to {b.name} after a quarrel.", s.agent_id,
                            participants=[s.agent_id, b.agent_id])
                        continue
                    cost = qty * price
                    setattr(s, good, num(getattr(s, good)) - qty)
                    setattr(b, good, num(getattr(b, good)) + qty)
                    s.wealth = num(s.wealth) + cost
                    b.wealth = num(b.wealth) - cost
                    bond(s, b, C.TRUST_TRADE)
                    d = self.deals[b.current_island_id]
                    d[0] += 1
                    d[1] += cost
        for iid, (count, volume) in sorted(self.deals.items()):
            log(w, "trade", f"Trading on {iid}: {count} deals worth {volume:.1f} coins.", None, island=iid, deals=count, volume=round(volume, 1))

    def raids(self):
        """A starving, aggressive, uncooperative adult may steal food from the best-stocked neighbour. Coins are never stolen."""
        w = self.world
        for a in sorted(living(w), key=lambda x: x.agent_id):
            if not is_adult(a) or num(a.food) >= 0.6 * food_need(a):
                continue
            targets = [t for t in living(w) if t.current_island_id == a.current_island_id and t.agent_id != a.agent_id
                       and num(t.food) > food_need(t) * 1.2]
            if not targets or self.srng.random() >= C.RAID_SCALE * aggr(a) * (1 - coop(a)):
                continue
            t = max(targets, key=lambda x: (num(x.food) - food_need(x), x.agent_id))
            pair = [a.agent_id, t.agent_id]
            bond(a, t, C.TRUST_RAID)
            add_grudge(w, t, a, C.GRUDGE_RAID)
            if self.srng.random() < C.RAID_SUCCESS:
                loot = min(0.5 * (num(t.food) - food_need(t)), 1.5 * (food_need(a) - num(a.food)))
                t.food = num(t.food) - loot
                a.food = num(a.food) + loot
                log(w, "raid", f"{a.name} raided {t.name} and took {loot:.1f} food.", a.agent_id, participants=pair)
            else:
                a.health = num(a.health) - C.RAID_INJURY
                log(w, "raid", f"{a.name} tried to raid {t.name} and was driven off.", a.agent_id, participants=pair)

    def consume(self):
        w = self.world
        for a in living(w):
            need = food_need(a)
            eaten = min(num(a.food), need)
            a.food = num(a.food) - eaten
            fed = eaten / need
            wood_used = min(num(a.wood), C.WOOD_NEED)
            a.wood = num(a.wood) - wood_used
            cold = 1 - wood_used / C.WOOD_NEED
            a.last_fed = round(fed, 2)
            damage = C.SHORTAGE_DAMAGE * (1 - fed) + 8 * cold
            if damage > 0:
                a.health = num(a.health) - damage
                if fed < 0.7:
                    log(w, "shortage", f"{a.name} went hungry ({fed:.0%} fed).", a.agent_id)
            else:
                a.health = min(100, num(a.health) + C.RECOVERY)
            isl = w.islands.get(a.current_island_id)
            if isl is not None and self.rng.random() < isl.disease_risk:     # the island's everyday illness (partial-wace's own rule)
                a.health = num(a.health) - C.ILLNESS_DAMAGE
                log(w, "disease", f"{a.name} caught an illness ({isl.weather} weather). Health is now {num(a.health):.0f}.", a.agent_id)
            a.food = num(a.food) * 0.8      # food spoils: only 80% of the leftover keeps

    # ------------------------------------------------------------------ people
    def next_agent_number(self):
        ids = [int(a[1:]) for a in self.world.agents if len(a) > 1 and a[0] == "a" and a[1:].isdigit()]
        return max(ids, default=0) + 1

    def island_letter(self, island_id):
        """Islands i1..i7 are a..g. (Any other island id gets the letter of its place in the list.)"""
        digits = str(island_id)[1:] if str(island_id)[:1] == "i" else ""
        n = int(digits) if digits.isdigit() else 1 + list(self.world.islands).index(island_id) if island_id in self.world.islands else 1
        return chr(ord("a") + (n - 1) % 26)

    def new_name(self, island_id):
        """Only the first generation has chosen names. A child is named for the island it was born on (i1 = a, i2 = b, ...)
        and a running number for that island: the 21st person registered on island i1 is "a21", wherever they later live."""
        w = self.world
        isl = w.islands[island_id]
        taken = {str(a.name).lower() for a in w.agents.values()} | {str(i).lower() for i in w.agents}
        count = int(num(getattr(isl, "birth_count", 0)))
        if count <= 0:           # the first time: start after the people already registered on this island
            count = sum(1 for a in w.agents.values() if a.current_island_id == island_id)
        letter = self.island_letter(island_id)
        count += 1
        while f"{letter}{count}" in taken:
            count += 1
        isl.birth_count = count
        return f"{letter}{count}"

    def new_child(self, p1, p2, island_id):
        w, rng = self.world, self.rng
        number = self.next_agent_number()
        child = Agent(f"a{number}", self.new_name(island_id), island_id, 0, rng.choice([p1.personalityType, p2.personalityType]), occupation="unemployed")
        if getattr(w, "genetics", True):
            genetics.ensure(w)                                   # parents may have been added since the year began
            genetics.inherit(child, p1, p2, self.grng)           # one allele from each parent; trait = their average
        else:
            child.genes = {}
            for k in ("farming", "hunting", "crafting"):
                mid = (num(getattr(p1, f"{k}_skill", 1), 1) + num(getattr(p2, f"{k}_skill", 1), 1)) / 2
                setattr(child, f"{k}_skill", round(clamp(mid + rng.uniform(-1.5, 1.5), 1, C.SKILL_MAX), 1))
            for k in ("cooperation_trait", "aggression_trait"):
                mid = (num(getattr(p1, k, 50), 50) + num(getattr(p2, k, 50), 50)) / 2
                setattr(child, k, int(round(clamp(mid + rng.uniform(-15, 15), 5, 98))))
        child.food = child.wood = child.tools = 0
        child.wealth = 0.0
        child.parents = [p1.agent_id, p2.agent_id]
        for p in (p1, p2):
            give = num(p.wealth) * 0.15          # each parent hands the child a share of their coins
            p.wealth = num(p.wealth) - give
            child.wealth += give
            bond(child, p, C.TRUST_FAMILY)
        bond(p1, p2, C.TRUST_FAMILY / 2)
        w.entities_add_agent(child)
        self.born += 1
        return child

    def demographics(self):
        w, rng = self.world, self.rng
        for a in sorted(living(w), key=lambda x: x.agent_id):
            a.age = int(num(a.age)) + 1
            old_age = max(0, a.age - 58) * 0.02
            frail = 0.25 if num(a.health) < 25 else 0.0
            if num(a.health) <= 0 or rng.random() < 0.004 + old_age + frail:
                if num(a.health) <= 0:
                    cause = "hunger" if num(a.last_fed, 1) < 0.7 else "illness"
                elif frail and frail >= old_age:
                    cause = "frailty"
                elif old_age >= 0.004:
                    cause = "old age"
                else:
                    cause = "an accident"
                kill(w, a, cause)
                self.died += 1
            elif a.age == C.ADULT_AGE and str(a.occupation or "").lower() in ("", "unemployed"):
                a.occupation = best_occupation(a)       # a child comes of age and takes up their best trade
        for iid, isl in w.islands.items():
            for _ in range(max(2, round(2 * num(isl.capacity_scale, 1)))):
                here = [a for a in living(w) if a.current_island_id == iid]
                fertile = [a for a in here if 18 <= num(a.age) <= 42 and num(a.health) > 60 and num(a.last_fed, 1) >= 0.9]
                if w.social_life:      # a child needs a couple, both fertile, living on this island
                    ids = {a.agent_id for a in fertile}
                    couples = sorted(((a, w.agents[a.partner_id]) for a in fertile if a.partner_id in ids and a.agent_id < a.partner_id),
                                     key=lambda c: c[0].agent_id)
                    ready = bool(couples)
                else:
                    couples = []
                    ready = len(fertile) >= 2
                if not ready or len(here) >= island_capacity(isl) or isl.prices["food"] > 2.0:
                    break
                if rng.random() < C.BIRTH_CHANCE:
                    p1, p2 = rng.choice(couples) if w.social_life else rng.sample(fertile, 2)
                    child = self.new_child(p1, p2, iid)
                    log(w, "birth", f"{child.name} was born on {iid} to {p1.name} and {p2.name}.", child.agent_id,
                        participants=[child.agent_id, p1.agent_id, p2.agent_id])

    # ------------------------------------------------------------------ bookkeeping
    def finish_year(self, start_pop):
        w = self.world
        alive = living(w)
        coins = sum(num(a.wealth) for a in alive)
        died = max(self.died, start_pop + self.born - len(alive))      # includes deaths from disasters, raids and feuds
        log(w, "year_summary",
            f"Year {int(num(w.current_year, 1))} ended: {len(alive)} people (was {start_pop}; {self.born} born, {died} died), "
            f"{coins:.1f} coins, inequality {gini(a.wealth for a in alive):.2f}.",
            None, population=len(alive), births=self.born, deaths=died, coins=round(coins, 1))


# =====================================================================
# QUICK TESTING BLOCK
# =====================================================================
if __name__ == "__main__":
    from main import setup_defaults, world

    setup_defaults()
    engine = SimulationEngine(world)
    for _ in range(5):
        engine.run_step()
    for event in world.event_history[-15:]:
        print(f"[{event['event_type'].upper()}] {event['description']}")
