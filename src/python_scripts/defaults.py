from world import Agent, Island

default_agents : list = [
    Agent("a1","Shiraz","i1",18,"Calm"),
    Agent("a2","Theo","i1",26,"Strategic"),
    Agent("a3","Angshuman","i1",18,"Nonchalant"),
    Agent("a4","Jacob","i1",18,"Resourceful"),
    Agent("a5","Samuel","i1",34,"Mean and Cunning"),
    Agent("a6","Laura","i2",22,"Nice"),
    Agent("a7","Tommy","i2",78,"Senile"),
    Agent("a8","Jack","i2",19,"Selfish"),
    Agent("a9","Ben","i2",48,"Intellectual"),
    Agent("a10","Tams","i2",31,"Nice")
]

# Starting skills (1-10), traits (0-100) and trades for the ten founders. With every skill at 1 and every trait at 50
# (the earlier placeholder values) nobody could feed themselves, and nobody differed enough to pair up, trade or fall out.
# id: (farming, hunting, crafting, cooperation, aggression, occupation)
_founders : dict = {
    "a1":  (5, 3, 4, 65, 20, "farmer"),
    "a2":  (4, 4, 7, 45, 40, "crafter"),
    "a3":  (3, 6, 4, 50, 30, "hunter"),
    "a4":  (6, 4, 5, 60, 30, "farmer"),
    "a5":  (4, 5, 6, 20, 80, "hunter"),
    "a6":  (6, 3, 5, 80, 15, "farmer"),
    "a7":  (3, 2, 3, 50, 20, "farmer"),
    "a8":  (4, 6, 4, 25, 65, "hunter"),
    "a9":  (5, 3, 8, 55, 35, "crafter"),
    "a10": (7, 4, 4, 75, 20, "farmer"),
}
for _agent in default_agents:
    (_agent.farming_skill, _agent.hunting_skill, _agent.crafting_skill,
     _agent.cooperation_trait, _agent.aggression_trait, _agent.occupation) = _founders[_agent.agent_id]

default_islands : list = [
    Island(island_id="i1",
           fertility=1,
           food_avail=60,      # current wild food stock (it regrows up to its highest value)
           wood_avail=60,
           regen_rate=1.5,
           weather="Cold",
           disease_rate=0.1,   # chance per person per year of catching the island's everyday illness
           culture="Hardworking"
           ), # type: ignore
    Island(island_id="i2",
           fertility=1,
           food_avail=60,
           wood_avail=60,
           regen_rate=1.5,
           weather="Temperate",
           disease_rate=0.1,
           culture="Evil and Dramatic"
           ), # type: ignore | shush

]
