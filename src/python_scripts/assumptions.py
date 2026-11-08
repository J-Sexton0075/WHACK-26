"""The model's assumptions, as data for the page: every number comes from sim_constants.py, so the page cannot disagree with the code.
(WHACK v2 listed its assumptions the same way, from civilisation.py.)"""
import sim_constants as C

# (constant, one plain sentence)
ECONOMY = [
    ("FOOD_NEED_ADULT", "Food an adult eats per year. A child (under ADULT_AGE) eats FOOD_NEED_CHILD."),
    ("FOOD_NEED_CHILD", "Food a child eats per year."),
    ("ADULT_AGE", "Age at which a person works and eats like an adult."),
    ("SKILL_MAX", "Skills run from 1 to this; production formulas use skill / SKILL_MAX."),
    ("REGEN_BASE", "Each year an island's wild food and wood regrow this share (x the island's regeneration rate) of the gap to their highest value."),
    ("SCARCITY_LOSS", "World scarcity 1.0 cuts farm output and the stock maxima by this share."),
    ("TOOL_BONUS", "Output rises by this share while a person holds a tool; tools wear out by TOOL_WEAR a year."),
    ("SHORTAGE_DAMAGE", "Health lost at a 100% food shortfall; a fully fed year heals RECOVERY."),
    ("ILLNESS_DAMAGE", "Health lost by someone who catches the island's everyday illness. The chance is the island's disease_risk."),
    ("CROSS_ISLAND_COST", "Extra price paid when buying from another island (only if islands trade)."),
    ("BIRTH_CHANCE", "Chance a birth attempt succeeds. Each island gets about two attempts a year, more on a bigger island, and needs room: (4 + 6 x fertility) x its size."),
    ("EVENT_LOG_CAP", "The event log keeps this many of the newest events."),
]
CONFLICT = [
    ("DISPUTE_SCALE", "Chance a trade is refused = this x average aggression x (1 - average cooperation); STRANGER_DISPUTE times likelier across the sea."),
    ("RAID_SCALE", "Chance a starving adult raids = this x aggression x (1 - cooperation); RAID_SUCCESS is the chance it works."),
    ("RAID_INJURY", "Health a failed raider loses."),
    ("TRUST_DECAY", "Trust keeps this share of its distance from neutral each year."),
]
SOCIAL = [
    ("PAIR_AGES", "Adults in this age range can form a couple."),
    ("PAIR_CHANCE", "Yearly chance that a single adult with an eligible unrelated neighbour on the island pairs up with the most compatible one (trust, similar cooperation)."),
    ("PAIR_TRUST", "Trust a new couple starts with; it grows by PAIR_TRUST_YEARLY each year together."),
    ("MENTOR_MIN_AGE", "A teacher is at least this old."),
    ("MENTEE_AGES", "A pupil is in this age range."),
    ("MENTOR_CHANCE", "Yearly chance a young person gets a lesson from a parent (if experienced) or else the most skilled adult on the island."),
    ("MENTOR_STEP", "A lesson closes this share of the gap in the teacher's best skill. Skills only move toward the teacher's and never past it."),
    ("GRUDGE_RAID", "Grudge a victim holds against a raider (a refused trade gives GRUDGE_QUARREL)."),
    ("GRUDGE_DECAY", "Grudges keep this share each year and are forgotten below GRUDGE_MIN."),
    ("FEUD_SCALE", "Retaliation chance = this x (own grudge + FEUD_FRIENDS x friends' grudges) x (0.5 + the victim's aggression), capped at FEUD_MAX."),
    ("FEUD_FRIEND_TRUST", "A friend is someone on the same island whom the victim trusts at least this much (or kin) and who shares the grudge."),
    ("FEUD_TAKE", "Share of the offender's food above need that the victim takes back in a retaliation; the offender also loses FEUD_INJURY health."),
    ("GRUDGE_RETALIATION", "Grudge the offender then holds against the victim, so feuds can escalate."),
]
MIGRATION = [
    ("MIGRATE_HUNGER", "Hunger motive: an adult who got less than this share of the food they need may leave for a cheaper-food island with room."),
    ("MIGRATE_PRICE_GAIN", "... where food costs at least this much less. Chance per year: MIGRATE_CHANCE."),
    ("FLIGHT_COOPERATION", "Feud-flight motive: a person at least this cooperative (0-1) ..."),
    ("FLIGHT_FEUDS", "... who is caught up in at least this many live feuds (held or suffered) may leave for the calmest island with room. Chance per year: FLIGHT_CHANCE x feuds / this, at most 0.9."),
    ("TRADE_MOVE_GAIN", "Trade motive: someone may move to an island where a good they have to sell fetches at least this much more."),
    ("TRADE_MOVE_TRADER", "Yearly chance a trader chases a better market; TRADE_MOVE_OTHER for anyone else with a big surplus."),
]
DISASTER_TEXT = {
    "plague": "One sweep through the islands you choose (all if none). Health damage and deaths among everyone it reaches.",
    "disease": "An epidemic that lasts several years. Each year about 60% of the people in range are exposed; weaker ones die.",
    "drought": "Lasts several years. Farm output and wild-food regrowth fall; nobody dies directly, they go hungry.",
    "tsunami": "Hits ONE island (random if none is chosen). Stores, goods and wild stocks are washed away and many drown.",
    "storm": "Like a tsunami but milder: it destroys part of the goods and stocks and kills few.",
}
DISASTER = [
    ("DISASTER_PARAMS", "Per type: lethality (chance an exposed person dies at scale 1), health_hit, contact (share exposed), goods and stock (share destroyed at scale 1)."),
    ("DROUGHT_LOSS", "A drought of scale 1 takes this share of farm output and regrowth."),
    ("VULNERABLE_AGES", "Anyone younger or older than this range is VULNERABLE_FACTOR times as likely to die; someone already at 0 health, up to WEAK_FACTOR more."),
    ("DEATH_CAP", "Nobody exposed has more than this chance of dying, whatever the scale."),
    ("RANDOM_DISASTER_SCALE", "A chance disaster (world setting 'chance per year') draws its scale between these."),
]
GENES = [
    ("GENE_TRAITS", "Five traits have two alleles each. A child gets one randomly chosen allele from each parent and its trait is their average (no dominant or recessive alleles)."),
    ("GENE_SPREAD", "A founder's two alleles for a trait sit up to this far either side of the value they were given, so founders look the same as without genetics."),
    ("MUTATION_RATE", "Chance that an inherited allele mutates."),
    ("MUTATION_STEP", "A mutation shifts the allele by up to this much; alleles stay between 0 and 1."),
    ("GENE_TRAIT_MIN", "A child's trait is the average of its two alleles, never below this."),
]
NOTES = [
    "Lessons change a person's skill but not their alleles, so a taught skill is not passed on to children.",
    "Gene dice have their own random stream. Children no longer follow the old parent-average rule, so a run with genetics is a different world from the same seed without it (world setting 'Genes').",
    "Skills are stored 1 to 10 and cooperation/aggression 0 to 100; an allele is 0 to 1, so a skill is the allele times 10 and a temperament trait the allele times 100.",
    "Scale runs from 0 to 1 for every disaster. 1 is the worst the model has: a plague or tsunami at scale 1 kills most of the people it reaches; 0.5 kills about half as many; 0 does nothing.",
    "The model has no sexes: any two unrelated single adults on one island can become a couple, and (with social life on) children are born only to couples.",
    "Feuds move food and health, never coins. Migration carries all belongings, and the partner and young children go too, so total coins only change when a whole family line dies out.",
    "Total coins = the sum of every living person's wealth. Inequality is the Gini coefficient of those coins: 0 means everyone holds the same, values towards 1 mean a few hold nearly everything.",
    "Dice are seeded from the world seed and the year, so the same world and seed replay the same year. Social life changes births, so a run with it on is a different world from the same seed with it off.",
    "Names: only the first generation can have chosen names. A child is named after the island it was born on (i1 = a, i2 = b ... i7 = g) and a running number for that island, so the 21st person registered on i1 is a21, wherever they later live.",
]
GROUPS = [("economy", "Economy and people", ECONOMY), ("conflict", "Conflict and trust", CONFLICT),
          ("social", "Social life: couples, lessons, feuds", SOCIAL), ("migration", "Migration", MIGRATION), ("genes", "Genes", GENES),
          ("disasters", "Disasters", DISASTER)]


def _value(name):
    v = getattr(C, name)
    if isinstance(v, dict):
        return "; ".join(f"{k}: lethality {p['lethality']}, health_hit {p['health_hit']}, contact {p['contact']}, goods {p['goods']}, stock {p['stock']}"
                         for k, p in v.items())
    if isinstance(v, (tuple, list)):
        if name == "GENE_TRAITS":
            return ", ".join(v)
        return " to ".join(str(x) for x in v)
    return v


def build() -> dict:
    return {
        "groups": [{"id": gid, "title": title, "items": [{"name": n, "value": _value(n), "text": t} for n, t in rows]} for gid, title, rows in GROUPS],
        "notes": NOTES,
        "disasters": {k: {"text": DISASTER_TEXT[k], "lethality": p["lethality"], "health_hit": p["health_hit"], "instant": p["instant"],
                          "contact": p["contact"], "goods": p["goods"], "stock": p["stock"],
                          "default_length_hint": "2 to 6 years" if k == "drought" else "2 to 4 years" if k == "disease" else "one year"}
                      for k, p in C.DISASTER_PARAMS.items()},
        "drought_loss": C.DROUGHT_LOSS,
        "avg_vulnerability": 1.1,       # typical multiplier from age and health, used only for the on-screen estimate
        "note": "These constants are modelling choices, not measurements: change them in sim_constants.py and the outcomes can change.",
    }
