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

default_islands : list [
    Island(island_id="i1", 
           fertility=1,
           food_avail=1,
           wood_avail=1,
           regen_rate=1,
           weather="Cold",
           disease_rate=1,
           culture="Hardworking"
           ), # type: ignore
    Island(island_id="i2", 
           fertility=1,
           food_avail=1,
           wood_avail=1,
           regen_rate=1,
           weather="Temperate",
           disease_rate=1,
           culture="Evil and Dramatic"
           ), # type: ignore | shush
        
]