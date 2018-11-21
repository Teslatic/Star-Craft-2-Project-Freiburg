#!/usr/bin/env python3

# python imports
from absl import app

# gym imports
import gym
import gym_ghost

# custom imports
from specs.agent_specs import agent_specs
from specs.env_specs import mv2beacon_specs
from assets.helperFunctions.initializingHelpers import setup_agent
from assets.helperFunctions.FileManager import log_reports
from assets.splash.squidward import print_squidward


def main(argv):
    print_squidward()
    agent = setup_agent(agent_specs)
    env = gym.make("sc2-v0")
    obs, reward, done, info = env.setup(mv2beacon_specs)

    while(True):
        # Action selection
        action = agent.policy(obs, reward, done, info)

        if (action is 'reset'):
            obs, reward, done, info = env.reset()
        else:
            # Peforming selected action
            obs, reward, done, info = env.step(action)
            dict_agent_report, exp_root_dir = agent.evaluate(obs, reward, done, info)

            log_reports(dict_agent_report, exp_root_dir)



if __name__ == "__main__":
    app.run(main)
