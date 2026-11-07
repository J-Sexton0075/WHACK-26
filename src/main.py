from exceptions import *
from attributes import Attribute, AttributeCollection
from interface import Agent, Island, WorldState
import defaults

def main():
    setup_defaults() # setup defult values for the world state
    ## pass defaults to frontend

def restart(): 
    if __name__ == "main":
        main()

def load():
    if __name__ == "main":
        main()

def setup_defaults():
    # Add default values to the 
    for i in defaults.default_islands:
        world.entities_add_island(i)
    for i in defaults.default_agents:
        world.entities_add_agent(i)


world = WorldState()
if __name__ == "main":
    main();
