import argparse
import os
import shutil
from math import log10

import numpy as np
import pandas as pd
import torch
import torchvision.utils as utils
from torch.utils.data import DataLoader
from tqdm import tqdm

from model import Model
from utils import ssim, TestDatasetFromFolder

parser = argparse.ArgumentParser(description='Test Benchmark Datasets')
parser.add_argument('--upscale_factor', default=4, type=int, choices=[2, 3, 4], help='super resolution upscale factor')
parser.add_argument('--model_name', default='upscale_4.pth', type=str, help='super resolution model name')
parser.add_argument('--test_path', default='data/test', type=str, help='test image data path')
parser.add_argument('--test_mode', default='GPU', type=str, choices=['GPU', 'CPU'], help='using GPU or CPU')
opt = parser.parse_args()

UPSCALE_FACTOR = opt.upscale_factor
MODEL_NAME = opt.model_name
TEST_PATH = opt.test_path
USE_CUDA = True if opt.test_mode == 'GPU' else False

dataset_names = ['Set5', 'Set14', 'BSDS100', 'Urban100', 'Manga109']
results = {'Set5': {'psnr': [], 'ssim': []}, 'Set14': {'psnr': [], 'ssim': []}, 'BSDS100': {'psnr': [], 'ssim': []},
           'Urban100': {'psnr': [], 'ssim': []}, 'Manga109': {'psnr': [], 'ssim': []}}

model = Model(UPSCALE_FACTOR).eval()
if USE_CUDA:
    model = model.to('cuda')
    model.load_state_dict(torch.load('epochs/' + MODEL_NAME))
else:
    model.load_state_dict(torch.load('epochs/' + MODEL_NAME, map_location='cpu'))

out_path = 'results/SRF_' + str(UPSCALE_FACTOR) + '/'
if not os.path.exists(out_path):
    os.makedirs(out_path)

for dataset_name in dataset_names:

    saved_path = out_path + dataset_name + '/'
    if os.path.exists(saved_path):
        # make sure it only save once
        shutil.rmtree(saved_path)
    os.makedirs(saved_path)

    test_set = TestDatasetFromFolder(TEST_PATH + '/' + dataset_name, upscale_factor=UPSCALE_FACTOR)
    test_loader = DataLoader(dataset=test_set, num_workers=4, batch_size=1, shuffle=False)
    test_bar = tqdm(test_loader, desc='[testing %s benchmark dataset]' % dataset_name)

    for image_name, lr_image, hr_restore_img, hr_image in test_bar:
        image_name = image_name[0]
        if USE_CUDA:
            lr_image, hr_image = lr_image.to('cuda'), hr_image.to('cuda')

        sr_image = model(lr_image)
        # only compute the PSNR and SSIM on YCbCr color space and only on Y channel
        sr_image_l = 0.299 * sr_image[:, 0, :, :] + 0.587 * sr_image[:, 1, :, :] + 0.114 * sr_image[:, 2, :, :]
        hr_image_l = 0.299 * hr_image[:, 0, :, :] + 0.587 * hr_image[:, 1, :, :] + 0.114 * hr_image[:, 2, :, :]
        mse = ((sr_image_l - hr_image_l) ** 2).mean().detach().cpu().item()
        psnr_value = 10 * log10(1 / mse)
        ssim_value = ssim(sr_image_l.unsqueeze(1), hr_image_l.unsqueeze(1)).detach().cpu().item()

        image = torch.stack([hr_restore_img.squeeze(0), hr_image.detach().cpu().squeeze(0), sr_image.detach()
                            .cpu().squeeze(0)])
        utils.save_image(image, saved_path + image_name.split('.')[0] + '_psnr_%.4f_ssim_%.4f.' %
                         (psnr_value, ssim_value) + image_name.split('.')[-1], nrow=3, padding=5, pad_value=255)

        # save psnr\ssim
        results[dataset_name]['psnr'].append(psnr_value)
        results[dataset_name]['ssim'].append(ssim_value)

out_path = 'statistics/'
saved_results = {'psnr': [], 'ssim': []}
for item in results.values():
    psnr_value = np.array(item['psnr']).mean()
    ssim_value = np.array(item['ssim']).mean()
    saved_results['psnr'].append(psnr_value)
    saved_results['ssim'].append(ssim_value)

data_frame = pd.DataFrame(saved_results, results.keys())
data_frame.to_csv(out_path + 'srf_' + str(UPSCALE_FACTOR) + '_test_results.csv', index_label='DataSet')
