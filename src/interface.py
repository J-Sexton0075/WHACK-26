import main
from world import WorldState, Island, Agent
from attributes import AttributeCollection
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



# overwrites the stored data from the dictionary passed in from the frontend
# assumes the format is the exact same as the output dictionary
# param new_data
#       the new data to overwrite the old data with
def update_from_frontend_default(new_data : dict) -> None:
    # Step 1: Update the 'other' values
    get_world().update_general_values(
        {
            "current_year" : new_data["current_year"],
            "max_years" : new_data["max_years"],
            "active_seed" : new_data["active_seed"],
            "scarcity_level" : new_data["scarcity_level"],
            "price_index" : new_data["price_index"]
        }
    )
    # Step 2: Check for old islands and update attributes. If the island is new, ensure its details are added.
    islands_dict : dict = new_data["islands"]
    agents_dict : dict = new_data["agents"]
    for key, val in islands_dict.items():
        if get_world().entities_has_island(key):
            ## Update
            collection : AttributeCollection = AttributeCollection(val) ## I'm not certain but in an ideal world... this is it?
            get_world().entities_get_island(key).changeVariables(collection.toList())
        else:
            ## Add
            get_world().entities_add_island(Island( # I really, really dislike this but I can't be bothered to improve it right now
                island_id=val["island_id"],
                fertility=val["fertility"],
                food_avail=val["food_avail"],
                wood_avail=val["wood_avail"],
                regen_rate=val["regen_rate"],
                weather=val["weather"],
                disease_rate=val["disease_rate"],
                culture=val["creature"]
            ))
    # Step 3: Check for old agents and update attributes. If the agent is new, ensure its details are added.
    for key, val in agents_dict().items():
        if get_world().entities_has_agent(key):
            ## Update
            collection : AttributeCollection = AttributeCollection(val) ## I'm not certain but in an ideal world... this is it?
            get_world().entities_get_agent(key).changeVariables(collection.toList())
        else:
            ## Add
            get_world().entities_add_agent(Agent( # I really, really dislike this but I can't be bothered to improve it right now
                agent_id=val["agent_id"],
                name=val["name"],
                current_island_id=["current_island_id"],
                age=["age"],
                personality_type=["personality_type"],
                occupation=["occupation"]
            ))

    # Step 4: check for deleted islands
    for i in get_world().islands.keys:
        if i not in islands_dict.keys: # The island has been deleted
            get_world().entities_remove_island(i)
    # Step 5: check for deleted agents
    for i in get_world().agents.keys:
        if i not in agents_dict.keys: # The agent has been deleted
            get_world().entities_remove_agent(i)