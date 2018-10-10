# torch imports
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision.transforms as T

# normal python imports
import numpy as np

## @package Architectures
#  Documentation for Architectures.
#
#  More details.

## Documentation for PytorchTutorialDQN
#
#  More details.
class PytorchTutorialDQN(nn.Module):

  def __init__(self, FLAGS):
    super(PytorchTutorialDQN, self).__init__()

    x_space = np.linspace(0, 83, FLAGS.xy_grid, dtype = int)
    y_space = np.linspace(0, 63, FLAGS.xy_grid, dtype = int)

    self.xy_space = np.transpose([np.tile(x_space, len(y_space)), np.repeat(y_space, len(x_space))])

    self.conv1 = nn.Conv2d(1, 16, kernel_size=5, stride=2)
    self.bn1 = nn.BatchNorm2d(16)
    self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=2)
    self.bn2 = nn.BatchNorm2d(32)
    self.conv3 = nn.Conv2d(32, 32, kernel_size=3, stride=2)
    self.bn3 = nn.BatchNorm2d(32)
    self.conv4 = nn.Conv2d(32, 64, kernel_size=3, stride=2)
    self.bn4 = nn.BatchNorm2d(64)

    self.tmp_w = self._get_filter_dimension(84, 5 , 0 , 2)
    self.tmp_w = self._get_filter_dimension(self.tmp_w, 3 , 0 , 2)
    self.tmp_w = self._get_filter_dimension(self.tmp_w, 3 , 0 , 2)
    self.tmp_w = self._get_filter_dimension(self.tmp_w, 3 , 0 , 2)

    self.fc1 = nn.Linear(64 * self.tmp_w * self.tmp_w, 512)

    self.head_actions = nn.Linear(512, len(self.xy_space))


  def _get_filter_dimension(self,w,f,p,s):
    '''
    calculates filter dimension according to following formula:
    (filter - width + 2*padding) / stride + 1
    '''
    return int((w - f + 2*p) / s + 1)

  def forward(self, screen):
    screen = F.relu(self.bn1(self.conv1(screen)))
    screen = F.relu(self.bn2(self.conv2(screen)))
    screen = F.relu(self.bn3(self.conv3(screen)))
    screen = F.relu(self.bn4(self.conv4(screen)))
    screen = screen.view(-1, 64 * self.tmp_w * self.tmp_w)
    screen = F.relu(self.fc1(screen))

    action_q = self.head_actions(screen)

    return action_q





