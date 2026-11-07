from exceptions import *
from attributes import Attribute, AttributeCollection
from interface import Agent, Island, WorldState
import defaults

# Main method. entry point for the rest of the program
def main() -> None:
    setup_defaults() # setup defult values for the world state
    ## pass defaults to frontend
    request_world_state() ## pass this to frontend when you know how that works

# restart. currently defaults to main method.
# call when restarting the simulation
def restart() -> None: 
    if __name__ == "main":
        main()

# load. currently defaults to main method
# call when loading the app for the first time
def load():
    if __name__ == "main":
        main()

# Requests the world state in a serialised format for passing to the frontend
# returns a serialised dictionary for the entire world state
def request_world_state() -> dict:
    return world.serialize_state_for_frontend()

# Sets up the world with default values. 
# see defaults.py.
def setup_defaults() -> None:
    # Add default values to the 
    for i in defaults.default_islands:
        world.entities_add_island(i)
    for i in defaults.default_agents:
        world.entities_add_agent(i)


world = WorldState()
if __name__ == "main":
    main();
