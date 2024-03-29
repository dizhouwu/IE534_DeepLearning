# -*- coding: utf-8 -*-
"""ie534_hw4_tiny.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1btj7RwgXd0DRA5rHchClLtt3Aq4kmcMi
"""




import os
import numpy as np
import torch
import time
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torchvision import datasets, transforms
from torch.autograd import Variable
from torchvision import transforms
from PIL import Image

batch_size=100


def create_val_folder(val_dir):
    """
    This method is responsible for separating validation images into separate sub folders
    """
    path = os.path.join(val_dir, 'images')  # path where validation data is present now
    filename = os.path.join(val_dir, 'val_annotations.txt')  # file where image2class mapping is present
    fp = open(filename, "r")  # open file in read mode
    data = fp.readlines()  # read line by line

    # Create a dictionary with image names as key and corresponding classes as values
    val_img_dict = {}
    for line in data:
        words = line.split("\t")
        val_img_dict[words[0]] = words[1]
    fp.close()
    # Create folder if not present, and move image into proper folder
    for img, folder in val_img_dict.items():
        newpath = (os.path.join(path, folder))
        if not os.path.exists(newpath):  # check if folder exists
            os.makedirs(newpath)
        if os.path.exists(os.path.join(path, img)):  # Check if image exists in default directory
            os.rename(os.path.join(path, img), os.path.join(newpath, img))
    return

transforms_train = transforms.Compose([
    transforms.RandomCrop(64, padding=4),
    transforms.RandomHorizontalFlip(),
    transforms.ToTensor(),
])

transform_val = transforms.Compose([
    transforms.ToTensor(),
])

# Implement basic block in Fig1
# Reference: https://zhuanlan.zhihu.com/p/62525824
# Reference: https://courses.grainger.illinois.edu/ie534/fa2019/secure/lecture_resnet_distributed_training.pdf 
class BasicBlock(nn.Module):
    expansion =1 
    def __init__(self, in_channels, out_channels, stride=1, downsample=None):
        super(BasicBlock,self).__init__()
        
        self.conv1 = nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=stride, padding=1)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(out_channels, out_channels, kernel_size=3, stride=1, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels) 
        self.downsample = downsample
    
    def forward(self,x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)
        
        out += identity
        out = self.relu(out)

        return out

# Implement ResNets in Fig2 with basic block
class ResNet(nn.Module):
    def __init__(self, basic_block, num_blocks_list, num_classes):
        super(ResNet, self).__init__()

        self.in_channels = 32
        self.conv1 =nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout2d(0.2)
        self.conv2 = self._make_layer(basic_block, 32, num_blocks_list[0])
        self.conv3 = self._make_layer(basic_block, 64, num_blocks_list[1],stride=2)
        self.conv4 = self._make_layer(basic_block, 128, num_blocks_list[2],stride=2)
        self.conv5 = self._make_layer(basic_block, 256, num_blocks_list[3],stride=2)
        #self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.maxpool = nn.MaxPool2d(2,2)
        self.fc = nn.Linear(256*4*4, num_classes)

    def forward(self, x):

        x = self.relu(self.bn1(self.conv1(x)))
        x = self.dropout(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.conv5(x)

        x = self.maxpool(x)
        x = x.view(x.shape[0], -1)
        x = self.fc(x)

        return x

    def _make_layer(self, basic_block, out_channels, num_blocks, stride=1):
        downsample = None
        if stride != 1 or self.in_channels != out_channels*basic_block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.in_channels, out_channels*basic_block.expansion,
                            kernel_size=1, stride = stride, padding = 0),
                nn.BatchNorm2d(out_channels*basic_block.expansion))
        
        layers = []
        layers.append(basic_block(self.in_channels, out_channels, stride, downsample))
        self.in_channels = out_channels * basic_block.expansion
        for _ in range(1, num_blocks):
            layers.append(basic_block(self.in_channels, out_channels))
        return nn.Sequential(*layers)

# from torchsummary import summary

# summary(resnet, input_size=(3, 64, 64))

train_dir = '/u/training/tra180/bruce/tiny-imagenet-200/train'
train_dataset = datasets.ImageFolder(train_dir, transform=transforms_train)
train_loader = torch.utils.data.DataLoader(train_dataset, batch_size= batch_size, shuffle=True, num_workers=8)

val_dir = '/u/training/tra180/bruce/tiny-imagenet-200/val/'
if 'val_' in os.listdir(val_dir+'images/')[0]:
    create_val_folder(val_dir)
    val_dir = val_dir +'images/'
else:
    val_dir = val_dir + 'images/'

val_dataset = datasets.ImageFolder(val_dir, transform=transforms.ToTensor())
val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=8)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
resnet = ResNet(BasicBlock, [2,4,4,2], 200).to(device)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(resnet.parameters())

best_test_accuracy = 0.0

start = time.time()

test_accuracy_list = []
for epoch in range(30):
    resnet.train()
    running_loss = 0.0
    for i, data in enumerate(train_loader, 0): # Reference: https://zhuanlan.zhihu.com/p/42501145
        inputs, labels = data
        inputs, labels = Variable(inputs).cuda(), Variable(labels).cuda()
        optimizer.zero_grad()
        outputs = resnet(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        if epoch > 6:
            for group in optimizer.param_groups:
                for p in group['param']:
                    state = optimizer.state[p]
                    if 'step' in state.keys():
                        if state['step']>=1023:
                            state['step'] = 1000
     
        optimizer.step()

        running_loss+=loss.item()

        if i % 2000 == 1999:
            print('[%d, %5d] loss: %.3f' % (epoch + 1, i + 1, running_loss / 2000))
            running_loss = 0.0
        
    correct = 0
    total = 0
    resnet.eval()
    for j, data in enumerate(val_loader, 0):
        
        inputs, labels = data
        inputs, labels = Variable(inputs).cuda(), Variable(labels).cuda()
        outputs = resnet(inputs)
        _, predicted = torch.max(outputs.data, 1)
        correct += (predicted == labels.data).cpu().sum()
        #correct += predicted.eq(labels).float().sum().item()
        total += len(labels)

    test_accuracy_list.append(correct/total)

    if correct/total > 0.51:
        with open('tiny_test_accuracy.txt','w') as f:
            for listitem in test_accuracy_list:
                f.write("%s\n" % listitem)

    #print(f'accuracy every epoch {(correct/total):.3f}')
    if correct/total > best_test_accuracy:
        best_test_accuracy = correct/total


        
end = time.time()
print('Total training time:', end-start)
print('The best test accuracy is', best_test_accuracy)



