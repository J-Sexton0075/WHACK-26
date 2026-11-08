from world import WorldState, Island, Agent
from attributes import AttributeCollection
import main
# additional world interface methods.

# Returns the current world the program is working with
# returns the current world
def get_world():
    return main.world

# generics

# edits a given island's attributes inside a given world. 
# param world 
#       the world which is being edited
# param island_id
#       the island which is being edited
# param changing
#       An AttributeCollection representing all the attributes which are being edited
def edit_island_attributes_generic(world : WorldState, island_id, changing : AttributeCollection) -> None:
    world.entities_get_island(island_id).changeVariables(changing.toList())

# edits a given island's attributes inside a given world. 
# param world 
#       the world which is being edited
# param island_id
#       the agent which is being edited
# param changing
#       An AttributeCollection representing all the attributes which are being edited
def edit_agent_attributes_generic(world : WorldState, agent_id, changing : AttributeCollection) -> None:
    world.entities_get_agent(agent_id).changeVariables(changing.toList())

# gets the dictionary representation (for backend) of the island in the given world 
# param world 
#       the world which is being edited
# param island_id
#       the island which is being edited
# returns a dictionary representation of the island
def get_island_dict_generic(world : WorldState, island_id) -> dict:
    return world.entities_get_island(island_id).to_dict()

# gets the dictionary representation (for backend) of the agent in the given world 
# param world 
#       the world which is being edited
# param agent_id
#       the agent which is being edited
# returns a dictionary representation of the agent
def get_agent_dict_generic(world : WorldState, island_id) -> dict:
    return world.entities_get_agent(island_id).to_dict()

# versions of the methods using main.world instead

# edits a given island's attributes inside the current world
# param island_id
#       the island which is being edited
# param changing
#       An AttributeCollection representing all the attributes which are being edited
def edit_island_attributes_default(island_id, changing : AttributeCollection) -> None:
    get_world().entities_get_island(island_id).changeVariables(changing.toList())

# edits a given agent's attributes inside the current world
# param agent_id
#       the agent which is being edited
# param changing
#       An AttributeCollection representing all the attributes which are being edited
def edit_agent_attributes_default(agent_id, changing : AttributeCollection) -> None:
    get_world().entities_get_agent(agent_id).changeVariables(changing.toList())

# gets the dictionary representation (for backend) of the island in the current world 
# param island_id
#       the island which is being edited
# returns a dictionary representation of the island
def get_island_dict_default(island_id) -> dict:
    return get_world().entities_get_island(island_id).to_dict()

# gets the dictionary representation (for backend) of the agent in the current world 
# param agent_id
#       the agent which is being edited
# returns a dictionary representation of the agent
def get_agent_dict_generic_default(island_id) -> dict:
    return get_world().entities_get_agent(island_id).to_dict()

