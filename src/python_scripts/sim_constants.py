"""Every tunable number of the merged island model, in one place (ported from WHACK v2's engine.py).

These are MODELLING ASSUMPTIONS, not measurements. They are listed, with a plain sentence each, at the
bottom of the page (see assumptions.py), so changing a value here changes what the page reports.

Scales used by the partial-wace data model:
  * skills are 1..10, traits (cooperation / aggression) are 0..100, health is 0..100
  * trust_graph scores are 0..100 with 50 = neutral (v2 used -1..1; TRUST_SCALE converts)
  * island food_availability / wood_availability are the CURRENT wild stocks
"""

# ---------- economy and demography ----------
FOOD_NEED_ADULT = 3.0        # food an adult eats per year
FOOD_NEED_CHILD = 1.5        # food a child eats per year
WOOD_NEED = 1.0              # wood burned per person per year (cooking, heat)
ADULT_AGE = 15
TOOL_BONUS = 0.30            # +30% output while holding a tool
TOOL_WEAR = 0.25             # tools used up per year of use
WOOD_PER_TOOL = 2.0
SHORTAGE_DAMAGE = 45         # health lost at a 100% food shortfall
RECOVERY = 6                 # health regained in a fed year
SKILL_MAX = 10.0             # skills run 1..10; production uses skill / SKILL_MAX
REGEN_BASE = 0.30            # share of the gap to the stock maximum that regrows per year, times the island's regeneration rate
SCARCITY_LOSS = 0.5          # scarcity 1.0 cuts farm output and island stock maxima by this share
CROSS_ISLAND_COST = 0.25     # extra price paid when buying across the sea
ILLNESS_DAMAGE = 10          # health lost by someone who catches the island's everyday illness (chance = the island's disease_risk)
EVENT_LOG_CAP = 300          # event_history keeps the newest entries only
BIRTH_CHANCE = 0.35          # per attempt; each island gets about 2 attempts a year, scaled by its size

# ---------- conflict ----------
DISPUTE_SCALE = 0.45         # chance a trade is refused = this x average aggression x (1 - average cooperation)
STRANGER_DISPUTE = 1.5       # disputes are this much likelier across the sea
RAID_SCALE = 0.7             # a starving adult raids with probability = this x aggression x (1 - cooperation)
RAID_SUCCESS = 0.6
RAID_INJURY = 15             # health lost by a failed raider

# ---------- trust (0..100 scores, 50 = neutral; deltas below are in v2's -1..1 units) ----------
TRUST_SCALE = 50
TRUST_TRADE, TRUST_GIFT, TRUST_QUARREL, TRUST_RAID, TRUST_FAMILY = 0.04, 0.12, -0.10, -0.30, 0.5
TRUST_DECAY = 0.95           # trust fades 5% a year towards neutral

# ---------- social life ----------
PAIR_AGES = (18, 45)         # adults in this age range can form a couple
PAIR_CHANCE = 0.30           # yearly chance that a single adult with an eligible neighbour pairs up
PAIR_TRUST = 0.35            # trust a new couple starts with
PAIR_TRUST_YEARLY = 0.05     # trust a couple gains each year together
MENTOR_MIN_AGE = 30
MENTEE_AGES = (8, 24)
MENTOR_CHANCE = 0.5
MENTOR_STEP = 0.15           # a lesson closes this share of the gap in the mentor's best skill
MENTOR_MIN_GAP = 0.05        # no lesson if the mentor is less than this much better (0..1 skill units)
TRUST_MENTOR = 0.08
GRUDGE_RAID = 0.6
GRUDGE_QUARREL = 0.25
GRUDGE_DECAY = 0.9
GRUDGE_MIN = 0.05
FEUD_SCALE = 0.5
FEUD_FRIENDS = 0.5
FEUD_FRIEND_TRUST = 0.2
FEUD_MAX = 0.6
FEUD_TAKE = 0.5
FEUD_INJURY = 10
GRUDGE_RETALIATION = 0.5
TRUST_FEUD = -0.25

# ---------- migration ----------
MIGRATE_HUNGER = 0.8         # hunger motive: an adult who got less than this share of the food they need
MIGRATE_CHANCE = 0.5
MIGRATE_PRICE_GAIN = 0.2     # ... may move to an island with room whose food is this much cheaper
FLIGHT_COOPERATION = 0.65    # feud-flight motive: people at least this cooperative ...
FLIGHT_FEUDS = 2             # ... who are caught up in at least this many live feuds (held or suffered) ...
FLIGHT_CHANCE = 0.45         # ... leave with this chance (x feuds / FLIGHT_FEUDS, capped at 0.9) for the calmest island with room
TRADE_MOVE_GAIN = 0.30       # trade motive: a surplus good sells for this much more on another island
TRADE_MOVE_TRADER = 0.30     # yearly chance a trader chases that better market
TRADE_MOVE_OTHER = 0.06      # ... and a non-trader with a big surplus

# ---------- disasters ----------
# scale 0..1. Lethality is the chance an EXPOSED person dies at scale 1 (before the vulnerability factor).
DISASTER_TYPES = ("plague", "disease", "drought", "tsunami", "storm")
DISASTER_PARAMS = {
    #            lethality  health_hit  contact  goods_lost  stock_lost
    "plague":  dict(lethality=0.70, health_hit=50, contact=1.0, goods=0.0, stock=0.0, instant=True),
    "disease": dict(lethality=0.35, health_hit=30, contact=0.6, goods=0.0, stock=0.0, instant=False),
    "tsunami": dict(lethality=0.80, health_hit=40, contact=1.0, goods=1.0, stock=0.8, instant=True),
    "storm":   dict(lethality=0.15, health_hit=20, contact=0.5, goods=0.6, stock=0.5, instant=True),
    "drought": dict(lethality=0.0,  health_hit=0,  contact=0.0, goods=0.0, stock=0.0, instant=False),
}
DROUGHT_LOSS = 0.85          # a drought of scale 1 leaves this share of farm output and regrowth lost
VULNERABLE_AGES = (5, 55)    # under 5 or over 55: 1.5x as likely to die in a disaster
VULNERABLE_FACTOR = 1.5
WEAK_FACTOR = 0.25           # plus up to this much more for someone already at 0 health
DEATH_CAP = 0.95
RANDOM_DISASTER_SCALE = (0.15, 0.8)   # scale of a chance disaster is drawn between these

# ---------- genes (WHACK v2) ----------
GENE_SPREAD = 0.2        # a founder's two alleles sit up to this far either side of the value they were given
MUTATION_RATE = 0.05     # chance that an inherited allele mutates
MUTATION_STEP = 0.1      # a mutation shifts the allele by up to this much; alleles stay between 0 and 1
GENE_TRAIT_MIN = 0.05    # a child's trait is the average of its two alleles, never below this
GENE_TRAITS = ("farming", "hunting", "crafting", "cooperation", "aggression")
