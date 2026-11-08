import random
from world import WorldState
from interface import get_world

class SimulationEngine:
    def __init__(self, world: WorldState = None):
        self.world = world if world is not None else get_world()

    def run_step(self) -> dict:
        
        #Executes one full simulation year using all agent and island attributes,logging events and returning the updated state for the frontend.
        
        # Log timeline start
        self.world.log_event("year_start", "SYSTEM", f"Year {self.world.current_year} simulation cycle started.")

        
        #PHASE 1: HARVESTING & PRODUCTION
        # Agents harvest resources scaled by their island's environment & personal skills
        for agent in self.world.get_alive_agents():
            island = self.world.entities_get_island(agent.current_island_id)
            if not island:
                continue

            # Calculate food & wood yields using island fertility & resource pools
            food_gained = int(island.fertility * agent.farming_skill * random.uniform(1.0, 1.5))
            wood_gained = int((island.wood_availability / 50.0) * agent.hunting_skill * random.uniform(1.0, 1.3))

            agent.food += food_gained
            agent.wood += wood_gained

            self.world.log_event(
                "harvest",
                agent.agent_id,
                f"{agent.name} harvested {food_gained} food and {wood_gained} wood on island {island.island_id}."
            )

        # ---------------------------------------------------------------------
        # PHASE 2: CONSUMPTION & HEALTH / SURVIVAL
        # ---------------------------------------------------------------------
        # Agents consume food to survive, and suffer weather/disease risks
        for agent in self.world.get_alive_agents():
            island = self.world.entities_get_island(agent.current_island_id)
            food_needed = 2

            # 1. Food intake evaluation
            if agent.food >= food_needed:
                agent.food -= food_needed
                agent.health = min(100, agent.health + 5)
            else:
                shortage = food_needed - agent.food
                agent.food = 0
                agent.health -= shortage * 20
                self.world.log_event(
                    "starvation",
                    agent.agent_id,
                    f"{agent.name} suffered starvation! Health reduced to {agent.health}."
                )

            # 2. Island weather & disease risk evaluation
            if island and random.random() < island.disease_risk:
                agent.health -= 10
                self.world.log_event(
                    "disease",
                    agent.agent_id,
                    f"{agent.name} caught an illness due to {island.weather} weather. Health is now {agent.health}."
                )

            # 3. Death condition check
            if agent.health <= 0:
                agent.is_alive = False
                agent.health = 0
                self.world.log_event(
                    "death",
                    agent.agent_id,
                    f"{agent.name} has passed away."
                )

        # ---------------------------------------------------------------------
        # PHASE 3: INTER-AGENT TRADING
        # ---------------------------------------------------------------------
        # Agents on the same island attempt bilateral resource trades
        for island_id in self.world.islands:
            island_agents = self.world.get_island_agents(island_id)

            if len(island_agents) >= 2:
                for i in range(len(island_agents) - 1):
                    a1 = island_agents[i]
                    a2 = island_agents[i + 1]

                    # Trade condition: a1 has surplus food & needs wood; a2 has surplus wood & needs food
                    if a1.food > 4 and a2.wood > 4:
                        a1.food -= 2
                        a1.wood += 2
                        a2.food += 2
                        a2.wood -= 2

                        # Update mutual trust scores dynamically
                        a1.trust_graph[a2.agent_id] = min(100, a1.trust_graph.get(a2.agent_id, 50) + 10)
                        a2.trust_graph[a1.agent_id] = min(100, a2.trust_graph.get(a1.agent_id, 50) + 10)

                        self.world.log_event(
                            "trade",
                            a1.agent_id,
                            f"{a1.name} traded 2 food to {a2.name} for 2 wood on island {island_id}."
                        )

        # ---------------------------------------------------------------------
        # PHASE 4: RESOURCE REGENERATION & YEAR ADVANCEMENT
        # ---------------------------------------------------------------------
        for island in self.world.islands.values():
            island.food_availability += int(10 * island.resource_regeneration_rate)
            island.wood_availability += int(10 * island.resource_regeneration_rate)

        self.world.current_year += 1
        
        # Return serialized dictionary ready for FastAPI / React frontend
        return self.world.serialize_state_for_frontend()


# =====================================================================
# QUICK TESTING BLOCK
# =====================================================================
if __name__ == "__main__":
    from main import setup_defaults, world

    # Load default agents & islands setup in defaults.py / main.py
    setup_defaults()

    # Create the simulation engine
    engine = SimulationEngine(world)

    print("--- RUNNING YEAR 1 STEP ---")
    updated_frontend_data = engine.run_step()

    # Print log feed output
    for event in world.event_history:
        print(f"[{event['event_type'].upper()}] {event['description']}")