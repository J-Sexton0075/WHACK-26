from world import WorldState, Island, Agent
from attributes import AttributeCollection
# additional world interface methods


def edit_island_attributes(world : WorldState, island_id, changing : AttributeCollection):
    world.entities_get_island[island_id].changeVariables(changing.toList())

def edit_agent_attributes(world : WorldState, agent_id, changing : AttributeCollection):
    world.entities_get_agent[agent_id].changeVariables(changing.toList())
    
