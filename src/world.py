import json

class Island:
    def __init__(self, island_id, fertility, food_avail, wood_avail, regen_rate, weather, disease_rate, culture):
        self.island_id = island_id
        
        # Core Engine States
        self.fertility = fertility    
        self.food_availability = food_avail
        self.wood_availability = wood_avail
        self.resource_regeneration_rate = regen_rate  #how quick they can regrow their plants or resources. 
        
        # Extended Environment States
        self.weather = weather #text based such as "Cold" or "Temperate" or "Hot"
        self.disease_risk = disease_rate
        
        # Cultural States for AI Context
        self.culture_trait = culture

        self.attributeDictionary = self.to_dict()

    def changeVariables(self,arraysToChange): #arrayToChange - if there is a 0 it means no change so keep it the same. 2D array input from frontend
        for array in arraysToChange:
            variable_name = array[0]
            new_value = array[1]
            
            if new_value != "No Change" and variable_name in self.__dict__:
                self.__dict__[variable_name] = new_value

    def to_dict(self):
        #Creates a snapshot copy of current attributes for MiroFish/Frontend.
        return self.__dict__.copy()

    def passToMiroFish(self):
        pass



class Agent:
    def __init__(self, agent_id, name, current_island_id, age, personality_type, occupation="farmer"):
        # Base Identifiers
        self.agent_id = agent_id
        self.name = name
        self.current_island_id = current_island_id
        
        # Physical & Economic State
        self.age = age
        self.health = 100         # 0 (dead) to 100 (perfect)
        self.wealth = 0.0
        self.occupation = occupation
        self.is_alive = True
        
        # Inventory (Merged)
        self.food = 0
        self.wood = 0
        self.tools = 0
        
        # Skills (Merged, 1 to 10 scale)
        self.farming_skill = 1
        self.hunting_skill = 1
        self.crafting_skill = 1
        
        # Persona & Psychology (Merged)
        self.personalityType = personality_type
        self.cooperation_trait = 50   # 0 to 100
        self.aggression_trait = 50    # 0 to 100
        self.needs = []               # e.g., ["food", "tools"]
        self.goals = []               # e.g., ["accumulate wealth"]
        self.trust_graph = {}         # Maps other agent_ids to a trust score (0-100)

    def changeVariables(self,arraysToChange): #arrayToChange - if there is a 0 it means no change so keep it the same. 2D array input from frontend
        for array in arraysToChange:
            variable_name = array[0]
            new_value = array[1]
            
            if new_value != "No Change" and variable_name in self.__dict__:
                self.__dict__[variable_name] = new_value

    def to_dict(self):
        return self.__dict__.copy()


class WorldState:
    def __init__(self):
        self.current_year = 1
        self.max_years = 30
        self.active_seed = 42
        self.scarcity_level = "moderate"
        
        # Global Markets
        self.price_index = {"food": 1.0, "wood": 1.0, "tools": 5.0}
        
        # World Entities (Stored in dictionaries using their IDs as keys)
        self.islands = {}
        self.agents = {}
        self.event_history = []  # List of raw dictionaries for UI events

    def get_alive_agents(self):
        return [agent for agent in self.agents.values() if agent.is_alive]
        
    def get_island_agents(self, island_id):
        return [agent for agent in self.get_alive_agents() if agent.current_island_id == island_id]


    # Adds an island to the world entities. 
    # param island
    #       the island to add to the world's entities
    # returns none
    def entities_add_island(self, island : Island) -> None:
        self.islands[island.island_id] = island
    # Adds an agent the world entities
    # param agent
    #       the agent to add to the world's entities
    # returns none
    def entities_add_agent(self, agent : Agent) -> None:
        self.agents[agent.agent_id] = agent

    # Returns an island in the world entities
    # param island_id
    #       the key of the island that should be fetched
    # returns the fetched island
    # throws an error if you try to fetch an island that doesn't exist so please don't do that
    def entities_get_island(self, island_id) -> Island:
        return self.islands[island_id]
    # Returns an agent in the world entities
    # param agent_id
    #       the key of the agent that should be fetched
    # returns the fetched agent
    # throws an error if you try to fetch an agent that doesn't exist
    def entities_get_agent(self, agent_id) -> Agent:
        return self.agents[agent_id]

    # Returns whether an island in the world exists
    # param island_id 
    #       the key of the island that should be checked
    # returns whether the island exists in the world
    def entities_has_island(self, island_id) -> bool:
        return island_id in self.islands.keys
        
    # Returns whether an agent in the world exists
    # param agent_id 
    #       the key of the agent that should be checked
    # returns whether the agent exists in the world
    def entities_has_agent(self, agent_id) -> bool:
        return agent_id in self.agents.keys

    # Removes a given island from the world
    # param island_id
    #       the key of the island that should be removed
    def entities_remove_island(self, island_id) -> None:
        self.islands.pop(island_id)

    # Removes a given agent from the world
    # param agent_id
    #       the key of the agent that should be removed
    def entities_remove_agent(self, agent_id) -> None:
        self.agents.pop(agent_id)

    def log_event(self, event_type, agent_id, description, payload=None):
        event = {
            "year": self.current_year,
            "event_type": event_type,
            "primary_agent_id": agent_id,
            "description": description,
            "payload": payload if payload else {}
        }
        self.event_history.append(event)
        
    def serialize_state_for_frontend(self):
        #Packages the world into a Dictionary ready for FastAPI to send to React
        return {
            "current_year": self.current_year,
            "max_years": self.max_years,
            "active_seed": self.active_seed,
            "scarcity_level": self.scarcity_level,
            "price_index": self.price_index,
            "islands": {i_id: island.to_dict() for i_id, island in self.islands.items()},
            "agents": {a_id: agent.to_dict() for a_id, agent in self.agents.items()},
            "event_history": self.event_history
        }

    # Updates the values that aren't associated with islands or agents
    def update_general_values(self, sliced_vals : dict) -> None:
        self.current_year = sliced_vals["current_year"]
        self.max_years = sliced_vals["max_years"]
        self.active_seed = sliced_vals["active_seed"]
        self.scarcity_level = sliced_vals["scarcity_level"]
        self.price_index = sliced_vals["price_index"]


    def changeVariables(self,arraysToChange): #arrayToChange - if there is a 0 it means no change so keep it the same. 2D array input from frontend
        for array in arraysToChange:
            variable_name = array[0]
            new_value = array[1]
            
            if new_value != "No Change" and variable_name in self.__dict__:
                self.__dict__[variable_name] = new_value

