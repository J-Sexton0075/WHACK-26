"""Genes (ported from WHACK v2). Five traits, two alleles each: farming, hunting, crafting, cooperation, aggression.

A child gets one randomly chosen allele from each parent (each may mutate) and its trait is the average of the two:
no dominant or recessive alleles. Lessons change a person's skill but never their alleles, so a taught skill is not
inherited. Alleles are stored on the person as  genes = {"farming": [a, b], ...}  with values between 0 and 1.

partial-wace stores skills as 1..10 and the two temperament traits as 0..100; the allele scale is 0..1, so
skill = allele x SKILL_MAX and trait = allele x 100.
Gene dice have their own stream, seeded from the world seed and the year, apart from the demography/social dice.
"""
import random

import sim_constants as C
from sim_core import num, clamp

TRAITS = C.GENE_TRAITS
_ATTR = {"farming": "farming_skill", "hunting": "hunting_skill", "crafting": "crafting_skill",
         "cooperation": "cooperation_trait", "aggression": "aggression_trait"}


def _scale(trait):
    return C.SKILL_MAX if trait in ("farming", "hunting", "crafting") else 100.0


def gene_value(a, trait):
    """The person's current phenotype on the allele scale (0..1)."""
    return clamp(num(getattr(a, _ATTR[trait], 0), 0) / _scale(trait), 0.0, 1.0)


def has_genes(a):
    g = getattr(a, "genes", None)
    return isinstance(g, dict) and all(isinstance(g.get(t), (list, tuple)) and len(g[t]) == 2 for t in TRAITS)


def ensure(w):
    """Give every person without alleles a pair per trait. Each pair sits evenly either side of the value they were
    given (up to GENE_SPREAD), so founders' traits are exactly what they were without genetics."""
    for a in w.agents.values():
        if has_genes(a):
            continue
        rng = random.Random(f"genes:{w.active_seed}:{a.agent_id}")
        genes = {}
        for t in TRAITS:
            v = gene_value(a, t)
            d = rng.uniform(0.0, C.GENE_SPREAD)
            d = min(d, v, 1.0 - v)                    # keep both alleles inside 0..1 so their average stays exactly v
            genes[t] = [round(v + d, 4), round(v - d, 4)] if rng.random() < 0.5 else [round(v - d, 4), round(v + d, 4)]
        a.genes = genes


def _pass_on(parent, trait, rng):
    allele = rng.choice(list(parent.genes[trait]))
    if rng.random() < C.MUTATION_RATE:
        allele += rng.uniform(-C.MUTATION_STEP, C.MUTATION_STEP)
    return round(clamp(allele, 0.0, 1.0), 4)


def inherit(child, p1, p2, rng):
    """Set the child's alleles and traits from its parents'. Returns the list of traits that mutated (for the log)."""
    child.genes = {}
    for t in TRAITS:
        pair = [_pass_on(p1, t, rng), _pass_on(p2, t, rng)]
        child.genes[t] = pair
        trait = max(C.GENE_TRAIT_MIN, (pair[0] + pair[1]) / 2.0)
        scaled = trait * _scale(t)
        if t in ("farming", "hunting", "crafting"):
            setattr(child, _ATTR[t], round(clamp(scaled, 1, C.SKILL_MAX), 1))
        else:
            setattr(child, _ATTR[t], int(round(clamp(scaled, 0, 100))))
