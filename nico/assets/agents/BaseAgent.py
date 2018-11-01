import numpy as np
from pysc2.agents import base_agent
from pysc2.lib import actions, features
import math
import time

from assets.RL.DQN_module import DQN_module
from assets.smart_actions import SMART_ACTIONS_SIMPLE_NAVIGATION as SMART_ACTIONS
from assets.helperFunctions.flagHandling import set_flag_every, set_flag_from
from assets.helperFunctions.timestamps import print_timestamp as print_ts

np.set_printoptions(suppress=True, linewidth=np.nan, threshold=np.nan)  # only for terminal output visualization


class CompassAgent(base_agent.BaseAgent):
    """
    This is a simple agent that uses an PyTorch DQN_module as Q value approximator.
    Current implemented features of the agent:
    - Translation of smart actions (North, East, South, West) to PYSC2 conform actions.
    - Simple initializing with the help of an agent_file (no argument parsing necessary)
    - Policy switch between an imitation learning session and an epsilon greedy learning session.
    - Storage of experience into simple Experience Replay Buffer
    - Reward shaping which uses the covered timestep distance as reward.

    To be implemented:
    - Saving the hyperparameter file of the experiments for traceability and replicability.
    - Storing the DQN model weights in case of Runtime error, KeyboardInterrupt or Successful run.
    - Intermediate saving of model weights
    - Plotting the episodic environment rewards, shaped rewards over time
    """
    # ##########################################################################
    # Initializing the agent
    # ##########################################################################

    def __init__(self, agent_file):
        """
        steps_done: Total timesteps done in the agents lifetime.
        timesteps:  Timesteps performed in the current episode.
        choice:     Choice of epsilon greedy method (None if supervised)
        loss:       Action loss
        hist:       The history buffer for more complex minigames.
        """
        super(CompassAgent, self).__init__()
        self.unzip_hyperparameter_file(agent_file)
        self.steps_done = 0  # total_timesteps
        self.timesteps = 0  # timesteps in the current episode
        self.choice = None  # Choice of epsilon greedy
        self.loss = 0  # Action loss
        self.DQN = DQN_module(self.batch_size,
                              self.gamma,
                              self.history_length,
                              self.size_replaybuffer,
                              self.optim_learning_rate)
        self.device = self.DQN.device
        print_ts("Agent has been initalized")

    def unzip_hyperparameter_file(self, agent_file):
        """
        Unzipping the hyperparameter files and writing them into member variables.
        """
        self.screen_dim = agent_file['SCREEN_DIM']
        self.minimap_dim = agent_file['MINIMAP_DIM']
        self.x_map_dim = 84  # magic number
        self.y_map_dim = 64  # magic number
        self.action_dim = len(SMART_ACTIONS)
        self.map_dimensions = (self.x_map_dim, self.y_map_dim)
        self.gamma = agent_file['GAMMA']
        self.optim_learning_rate = agent_file['OPTIM_LR']
        self.batch_size = agent_file['BATCH_SIZE']
        self.target_update_period = agent_file['TARGET_UPDATE_PERIOD']
        self.history_length = agent_file['HIST_LENGTH']
        self.size_replaybuffer = agent_file['REPLAY_SIZE']
        self.device = agent_file['DEVICE']
        self.silentmode = agent_file['SILENTMODE']
        self.logging = agent_file['LOGGING']
        self.supervised_episodes = agent_file['SUPERVISED_EPISODES']
        self.exp_path = agent_file['EXP_PATH']

        epsilon_file = agent_file['EPSILON_FILE']
        self.epsilon = epsilon_file['EPSILON']
        self.eps_start = epsilon_file['EPS_START']
        self.eps_end = epsilon_file['EPS_END']
        self.eps_decay = epsilon_file['EPS_DECAY']

    def setup_interface(self):
        """
        Setting up agent interface for the environment.
        """
        self.agent_interface = features.AgentInterfaceFormat(
                            feature_dimensions=features.Dimensions(screen=self.screen_dim, minimap=self.minimap_dim),
                            use_feature_units=True)
        return self.agent_interface

    # ##########################################################################
    # Action Selection
    # ##########################################################################

    def prepare_timestep(self, obs):
        """
        timesteps:
        """
        # from PYSC2 base class
        self.steps += 1
        self.reward += obs.reward

        # Current episode
        self.timesteps += 1
        self.available_actions = obs.observation.available_actions

        # Calculate additional information for reward shaping
        self.feature_screen = obs.observation.feature_screen.player_relative
        self.feature_screen2 = obs.observation.feature_screen.selected
        self.state = self.feature_screen
        self.beacon_center, self.marine_center, self.distance = self.calculate_distance(self.feature_screen, self.feature_screen2)

    def policy(self, obs):
        """
        Choosing an action
        """
        # Set all variables at the start of a new timestep
        self.prepare_timestep(obs)

        # Action seletion according to active policy
        # action = [actions.FUNCTIONS.select_army("select")]

        if obs.first():  # Select Army in first step
            self.action = [actions.FUNCTIONS.select_army("select")]

        if obs.last():  # End episode in last step
            print_ts("Last step: epsilon is at {}, Total score is at {}".format(self.epsilon, self.reward))
            self._save_model()
            self.update_target_network()
            self.action = 'reset'

        # Action selection for regular step
        if not obs.first() and not obs.last():
            # For the first n episodes learn on forced actions.
            if self.episodes < self.supervised_episodes:
                self.action, self.action_idx = self.supervised_action()
            else:
                # Choose an action according to the policy
                self.action, self.action_idx = self.choose_action()
        return self.action

    def supervised_action(self):
        """
        This method selects an action which will force the marine in the
        direction of the beacon.
        Further improvements are possible.
        """
        relative_vector = self.marine_center - self.beacon_center
        action_choice = np.random.choice([True, False], p=[0.5, 0.5])

        right_to_beacon = relative_vector[0] > 0.
        left_to_beacon = relative_vector[0] < 0.
        vertically_aligned = relative_vector[0] == 0.

        below_beacon = relative_vector[1] > 0.
        above_beacon = relative_vector[1] < 0.
        horizontally_aligned = relative_vector[1] == 0.

        left = 0
        up = 1
        right = 2
        down = 3

        if (horizontally_aligned and vertically_aligned): # Hitting beacon, stay on last action
            last_action_idx = self.action_idx  # self.action_idx not defined in first timestep
            action_idx = last_action_idx
        if (horizontally_aligned and right_to_beacon):  # East
            action_idx = left
        if (below_beacon and vertically_aligned):  # South
            action_idx = up
        if (horizontally_aligned and left_to_beacon):  # West
            action_idx = right
        if (above_beacon and vertically_aligned):  # North
            action_idx = down
        if above_beacon and left_to_beacon:  # North-West
            if action_choice:
                action_idx = right
            if not action_choice:
                action_idx = down
        if (above_beacon and right_to_beacon):  # North-East
            if action_choice:
                action_idx = left
            if not action_choice:
                action_idx = down
        if (below_beacon and right_to_beacon): # South-East
            if action_choice:
                action_idx = left
            if not action_choice:
                action_idx = up
        if (below_beacon and left_to_beacon):  # South-West
            if action_choice:
                action_idx = right
            if not action_choice:
                action_idx = up
        chosen_action = self.translate_to_PYSC2_action(SMART_ACTIONS[action_idx])
        return [chosen_action], action_idx

    def choose_action(self, agent_mode='learn'):
        """
        chooses an action according to the current policy
        returns the chosen action id with x,y coordinates and the index of the action
        with respect to the SMART_ACTIONS constant. The additional index is used for
        the catergorical labeling of the actions as an "intermediate" solution for
        a restricted action space.
        """
        self.choice = self.epsilon_greedy()

        if self.choice == 'random' and agent_mode == 'learn':
            action_idx = np.random.randint(self.action_dim)
            chosen_action = self.translate_to_PYSC2_action(SMART_ACTIONS[action_idx])
        else:
            # Q-values berechnen
            with torch.no_grad():
                action_q_values = self.DQN.predict_q_values(self.state)

            # Beste Action bestimmen
            best_action_numpy = action_q_values.detach().numpy()
            action_idx = np.argmax(best_action_numpy)
            best_action = SMART_ACTIONS[action_idx]

            chosen_action = self.translate_to_PYSC2_action(best_action)
        # square brackets around chosen_action needed for internal pysc2 state machine
        return [chosen_action], action_idx

    def translate_to_PYSC2_action(self, action):
        """
        gets action from id list and passes valid args
        TODO: make this more intuitive and general
        """
        if self.can_do(actions.FUNCTIONS.Move_screen.id):
            if action is 'left':
                if not (self.marine_center[0] <= 0):
                    return actions.FUNCTIONS.Move_screen("now", self.marine_center + (-4, 0))
            if action is 'up':
                if not (self.marine_center[1] <= 0):
                    return actions.FUNCTIONS.Move_screen("now", self.marine_center + (0, -4))
            if action is 'right':
                if not (self.marine_center[0] >= 83):
                    return actions.FUNCTIONS.Move_screen("now", self.marine_center + (4, 0))
            if action is 'down':
                if not (self.marine_center[1] >= 63):
                    return actions.FUNCTIONS.Move_screen("now", self.marine_center + (0, 4))
        else:
            return actions.FUNCTIONS.no_op()

    def can_do(self, action):
        """
        shortcut for checking if action is available at the moment
        """
        return action in self.available_actions

    def epsilon_greedy(self):
        """
        returns a string in order to determine if the next action choice is
        going to be random or according to an decaying epsilon greeedy policy
        """
        self.epsilon = self.eps_end + (self.eps_start - self.eps_end) * np.exp(-1. * self.steps_done / self.eps_decay)
        self.steps_done += 1
        return np.random.choice(['random', 'greedy'], p=[self.epsilon, 1-self.epsilon])

    def _xy_locs(self, mask):
        """
        Mask should be a set of bools from comparison with a feature layer.
        """
        y, x = mask.nonzero()
        return list(zip(x, y))

    # ##########################################################################
    # Store transition in Replay Buffer
    # ##########################################################################

    def store_transition(self, next_obs):
        """
        Save the actual information in the history.
        As soon as there has been enough data, the experience is sampled from the replay buffer.
        """
        self.env_reward = next_obs.reward
        self.feature_screen_next = next_obs.observation.feature_screen.player_relative
        self.feature_screen_next2 = next_obs.observation.feature_screen.selected
        self.reward_shaped = self.reward_shaping()
        self.next_state = self.feature_screen_next

        # push next state on next state history stack
        #  self.next_state = next_state

        # save transition tuple to the memory buffer
        self.DQN.memory.push([self.state], [self.action_idx], self.reward_shaped, [self.next_state])

    # ##########################################################################
    # Reward shaping
    # ##########################################################################

    def calculate_distance(self, screen_player_relative, screen_selected):
        """
        Calculates the euclidean distance between beacon and marine.
        Using feature_screen.selected since marine vanishes behind beacon when
        using feature_screen.player_relative
        """
        marine_center = np.mean(self._xy_locs(screen_selected == 1), axis=0).round()
        beacon_center = np.mean(self._xy_locs(screen_player_relative == 3), axis=0).round()
        # print(screen_selected)
        # print(screen_player_relative)
        if isinstance(marine_center, float):
            # print(marine_center)
            # print(beacon_center)
            # print(screen_selected == 1)
            # print(screen_player_relative == 3)
            # print("############################################################")
            # print(screen_player_relative)
            # print(screen_selected)
            # time.sleep(100)
            marine_center = beacon_center
        distance = math.hypot(beacon_center[0] - marine_center[0],
                              beacon_center[1] - marine_center[1])

        return beacon_center, marine_center, distance

    def reward_shaping(self):
        """
        A new reward will be calculated based on the distance covered by the agent in the last step.
        """
        self.beacon_center_next, self.marine_center_next, self.distance_next = self.calculate_distance(self.feature_screen_next, self.feature_screen_next2)
        reward_shaped = self.distance - self.distance_next
        if self.distance == 0.0:
            reward_shaped = 100
        return reward_shaped
        # self.reward_combined = self.reward + self.reward_shaped


    # ##########################################################################
    # DQN module wrappers
    # ##########################################################################

    def get_memory_length(self):
        """
        Returns the length of the ReplayBuffer
        """
        return len(self.DQN.memory)

    def optimize(self):
        """
        Optimizes the DQN_module on a minibatch
        """
        self.DQN.optimize()

    # ##########################################################################
    # Print status information of timestep
    # ##########################################################################

    def print_status(self):
        """
        Method for direct status printing.
        The method is called at the end of each timestep when optimizing is
        active.
        """
        print(self.state_q_values_full)
        if self.episodes < self.supervised_episodes:
            q_max, q_min, q_mean, q_var, q_span, q_argmax = self.q_value_analysis(self.state_q_values)
            td_max, td_min, td_mean, td_var, td_span, td_argmax = self.q_value_analysis(self.td_target.unsqueeze(1))
            # print("environment reward: {:.2f}, step penalty: {:.2f}, reward total: {:.2f}".format(obs.reward, self.reward_shaped, self.reward_combined))
            # print("Q_VALUES: {}".format(self.state_q_values))
            # print("TD_TARGET: {}".format(self.td_target.unsqueeze(1)))
            print_ts("action: {}, idx: {}, Smart action: {}".format(self.action, self.action_idx, SMART_ACTIONS[self.action_idx]))
            print_ts("Q_VALUES: max: {:.3f}, min: {:.3f}, span: {:.3f}, mean: {:.3f}, var: {:.6f}, argmax: {}".format(q_max, q_min, q_span, q_mean, q_var, q_argmax))
            print_ts("TD_TARGET: max: {:.3f}, min: {:.3f}, span: {:.3f}, mean: {:.3f}, var: {:.6f}, argmax: {}".format(td_max, td_min, td_span, td_mean, td_var, td_argmax))
            print_ts("MEMORY SIZE: {}".format(len(DQN.memory)))
            print_ts("Epsilon: {:.2f}\t| choice: {}".format(self.epsilon, self.choice))
            print_ts("Episode {}\t| Step {}\t| Total Steps: {}".format(self.episodes, self.timesteps, self.steps))
            print_ts("Chosen action: {}".format(self.action))
            # print_ts("chosen coordinates [x,y]: {}".format((self.x_coord.item(), self.y_coord.item())))
            print_ts("Beacon center location [x,y]: {}".format(self.beacon_center))
            print_ts("Marine center location [x,y]: {}".format(self.marine_center))
            print_ts("Distance: {}, delta distance: {}".format(self.distance, self.reward_shaped))
            print_ts("Current Episode Score: {}\t| Total Score: {}".format(self.last_score, self.reward))
            print_ts("Environment reward in timestep: {}".format(self.env_reward))
            print_ts("Action Loss: {:.5f}".format(self.loss))
            print_ts("----------------------------------------------------------------")
        else:
            print(self.feature_screen)
            print(SMART_ACTIONS[self.action_idx])

    def log(self):
        pass
        buffer_size = 10 # This makes it so changes appear without buffering
        with open('output.log', 'w', buffer_size) as f:
                f.write('{}\n'.format(self.feature_screen))

    def _save_model(self, emergency=False):
        if emergency:
            save_path = self.exp_path + "/model/emergency_model.pt"
        else:
            save_path = self.exp_path + "/model/model.pt"

        # Path((self.exp_path + "/model")).mkdir(parents=True, exist_ok=True)
        self.DQN.save(save_path)

    ## logs rewards per epochs and cumulative reward in a csv file
    # def log_reward(self):
    #     r_per_epoch_save_path = self.exp_path  + "/csv/reward_per_epoch.csv"
    #     # Path((self._path + "/experiment/" + self._name + "/csv")).mkdir(parents=True, exist_ok=True)
    #
    #     d = {"sparse reward per epoch" : self.r_per_epoch,
    #          "sparse cumulative reward": self.list_score_cumulative,
    #          "pseudo reward per epoch" : self.list_pseudo_reward_per_epoch,
    #          "epsilon" : self.list_epsilon }
    #     df = pd.DataFrame(data=d)
    #     with open(r_per_epoch_save_path, "w") as f:
    #         df.to_csv(f, header=True, index=False)
    #
    #
    # def log_coordinates(self):
    #     save_path = self.exp_path + "/csv/coordinates.csv"
    #     # Path((self._path + "/experiment/" + self._name + "/csv")).mkdir(parents=True, exist_ok=True)
    #     d = {"x" : self.list_x,
    #          "y":  self.list_y}
    #     df = pd.DataFrame(data=d)
    #     with open(save_path, "w") as f:
    #         df.to_csv(f, header=True, index=False)

    # ##########################################################################
    # Ending Episode
    # ##########################################################################

    def update_target_network(self):
        """
        Transferring the estimator weights to the target weights
        """
        if self.episodes % self.target_update_period == 0:
            print_ts("About to update")
            self.DQN.update_target_net()
        self.reset()

    def reset(self):
        """
        Resetting the agent --> More explanation
        """
        super(CompassAgent, self).reset()
        self.timesteps = 0
