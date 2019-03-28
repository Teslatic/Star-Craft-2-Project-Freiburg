AGENT_TYPE = 'collectmineralshards' # move2beacon/collectmineralshards/defeatroaches
ACTION_TYPE = 'grid'  # compass/grid/original

EXP_NAME = 'delete_'

GAMMA = 0.99
OPTIM_LR = 0.0001


EPS_START = 1
EPS_END = 0.1
EPS_DECAY = 2.5e08 # larger number -> slower decay

BATCH_SIZE = 32
REPLAY_SIZE = 1500000
TARGET_UPDATE_PERIOD = 5

MODE = 'learning'
SUPERVISED_EPISODES = 0


MODEL_SAVE_PERIOD = 1000


# GRID_DIM_X x GRID_DIM_Y
GRID_DIM_X = 20
GRID_DIM_Y = 20
NOISE_BOUND = 0

agent_specs = {
    'AGENT_TYPE': AGENT_TYPE,
    'ACTION_TYPE': ACTION_TYPE,
    'EXP_NAME': EXP_NAME,

    'GAMMA': GAMMA,  # Standard 0.99
    'OPTIM_LR': OPTIM_LR,  # Standard 0.001

    'EPS_START': EPS_START,
    'EPS_END': EPS_END,
    'EPS_DECAY': EPS_DECAY,

    'BATCH_SIZE': BATCH_SIZE,  # Standard 32
    'REPLAY_SIZE': REPLAY_SIZE,
    'TARGET_UPDATE_PERIOD': TARGET_UPDATE_PERIOD,   # Standard 5

    'MODE': MODE,
    'SUPERVISED_EPISODES': SUPERVISED_EPISODES,
    'MODEL_SAVE_PERIOD': MODEL_SAVE_PERIOD,

    'GRID_DIM_X': GRID_DIM_X,
    'GRID_DIM_Y': GRID_DIM_Y,
    'NOISE_BOUND': NOISE_BOUND # only for grid agent, standard is 1
}
