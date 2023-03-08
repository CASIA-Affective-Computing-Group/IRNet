import cv2
import random
import numpy as np
import torch
from torch.utils.data import Dataset
import torchvision
import torchvision.transforms as transforms

from utils.randaugment import RandomAugment
from utils.utils_algo import *


def load_kmnist(args):
    
    print ('obtain train_loader')
    ## train_loader: (data, labels), only read data (target data: (60000, 32, 32, 3))
    temp_train = read_data(args.dataset, train=True)
    data_train, dlabels_train = temp_train.data.cpu().numpy(), temp_train.targets.cpu().numpy()
    data_train = data_train[:,:,:,np.newaxis]
    data_train = np.tile(data_train, (1, 1, 1, 3)) # [60000, 28, 28] => [60000, 28, 28, 3]
    assert np.min(dlabels_train) == 0, f'min(dlabels) != 0'

    ## train_loader: train_givenY
    dlabels_train = np.array(dlabels_train).astype('int')
    num_sample = len(dlabels_train)
    train_givenY = generate_uniform_cv_candidate_labels(dlabels_train, args.partial_rate) ## generate partial dlabels
    print('Average candidate num: ', np.mean(np.sum(train_givenY, axis=1)))
    bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
    print('Average bingo rate: ', bingo_rate)
    train_givenY = generate_noise_labels(dlabels_train, train_givenY, args.noise_rate)
    bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
    print('Average noise rate: ', 1 - bingo_rate)
 
    ## train_loader: train_givenY->plabel
    dlabels_train = np.array(dlabels_train).astype('float')
    train_givenY = np.array(train_givenY).astype('float')
    plabels_train = (train_givenY!=0).astype('float')

    partial_matrix_dataset = Augmentention(data_train, plabels_train, dlabels_train, train_flag=True)
    partial_matrix_train_loader = torch.utils.data.DataLoader(
        dataset=partial_matrix_dataset, 
        batch_size=args.batch_size,
        num_workers=args.workers,
        shuffle=True, 
        drop_last=True)

    #######################################################
    print ('obtain test_loader')
    temp_test = read_data(args.dataset, train=False)
    data_test, dlabels_test = temp_test.data.cpu().numpy(), temp_test.targets.cpu().numpy()
    data_test = data_test[:,:,:,np.newaxis]
    data_test = np.tile(data_test, (1, 1, 1, 3)) # [60000, 28, 28] => [60000, 28, 28, 3]
    assert np.min(dlabels_test) == 0, f'min(dlabels) != 0'

    ## (data, dlabels) -> test_loader
    test_dataset = Augmentention(data_test, dlabels_test, dlabels_test, train_flag=False)
    test_loader = torch.utils.data.DataLoader(
        dataset=test_dataset, 
        batch_size=args.batch_size,
        num_workers=args.workers,
        shuffle=False)

    return partial_matrix_train_loader, train_givenY, test_loader


class Augmentention(Dataset):
    def __init__(self, images, plabels, dlabels, train_flag=True):
        self.images = images
        self.plabels = plabels
        self.dlabels = dlabels
        self.train_flag = train_flag
        normalize_mean = (0.1918, 0.1918, 0.1918)
        normalize_std  = (0.3483, 0.3483, 0.3483)
        if self.train_flag == True:
            self.weak_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.RandomResizedCrop(size=32, scale=(0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomApply([transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)], p=0.8),
                transforms.RandomGrayscale(p=0.2),
                transforms.ToTensor(), 
                transforms.Normalize(normalize_mean, normalize_std) # the mean and std on cifar training set
                ])
            self.strong_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.RandomResizedCrop(size=32, scale=(0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                RandomAugment(3, 5),
                transforms.ToTensor(), 
                transforms.Normalize(normalize_mean, normalize_std) # the mean and std on cifar training set
                ])
        else:
            self.test_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.ToTensor(),
                transforms.Normalize(normalize_mean, normalize_std),
                ])


    def __len__(self):
        return len(self.dlabels)
        
    def __getitem__(self, index):
        if self.train_flag == True:
            each_image_w1 = self.weak_transform(self.images[index])
            each_image_w2 = self.weak_transform(self.images[index])
            each_image_w3 = self.weak_transform(self.images[index])
            each_image_s1 = self.strong_transform(self.images[index])
            each_image_s2 = self.strong_transform(self.images[index])
            each_image_s3 = self.strong_transform(self.images[index])
            each_plabel = self.plabels[index]
            each_dlabel = self.dlabels[index]
            return each_image_w1, each_image_w2, each_image_w3, each_image_s1, each_image_s2, each_image_s3, each_plabel, each_dlabel, index
        else:
            each_image = self.test_transform(self.images[index])
            each_dlabel = self.dlabels[index]
            return each_image, each_dlabel
