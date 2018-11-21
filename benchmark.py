import argparse
import os
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
parser.add_argument('--upscale_factor', default=4, type=int, choices=[2, 3, 4, 8],
                    help='super resolution upscale factor')
parser.add_argument('--model_name', default='upscale_4.pth', type=str, help='super resolution model name')
parser.add_argument('--test_path', default='data/test', type=str, help='test image data path')
opt = parser.parse_args()

UPSCALE_FACTOR = opt.upscale_factor
MODEL_NAME = opt.model_name
TEST_PATH = opt.test_path

results = {'Set5': {'psnr': [], 'ssim': []}, 'Set14': {'psnr': [], 'ssim': []}, 'BSD100': {'psnr': [], 'ssim': []},
           'Urban100': {'psnr': [], 'ssim': []}, 'SunHays80': {'psnr': [], 'ssim': []}}

model = Model(UPSCALE_FACTOR).eval()
if torch.cuda.is_available():
    model = model.to('cuda')
    model.load_state_dict(torch.load('epochs/' + MODEL_NAME))
else:
    model.load_state_dict(torch.load('epochs/' + MODEL_NAME), map_location='cpu')

test_set = TestDatasetFromFolder(TEST_PATH, upscale_factor=UPSCALE_FACTOR)
test_loader = DataLoader(dataset=test_set, num_workers=4, batch_size=1, shuffle=False)
test_bar = tqdm(test_loader, desc='[testing benchmark datasets]')

out_path = 'results/SRF_' + str(UPSCALE_FACTOR) + '/'
if not os.path.exists(out_path):
    os.makedirs(out_path)

for image_name, lr_image, hr_restore_img, hr_image in test_bar:
    image_name = image_name[0]
    if torch.cuda.is_available():
        lr_image, hr_image = lr_image.to('cuda'), hr_image.to('cuda')

    sr_image = model(lr_image)
    mse = ((sr_image - hr_image) ** 2).mean().item()
    psnr_value = 10 * log10(1 / mse)
    ssim_value = ssim(sr_image, hr_image).item()

    image = torch.stack(
        [hr_restore_img.squeeze(0), hr_image.cpu().detach().squeeze(0), sr_image.cpu().detach().squeeze(0)])
    utils.save_image(image, out_path + image_name.split('.')[0] + '_psnr_%.4f_ssim_%.4f.' % (psnr_value, ssim_value) +
                     image_name.split('.')[-1], nrow=1, padding=5, pad_value=255)

    # save psnr\ssim
    results[image_name.split('_')[0]]['psnr'].append(psnr_value)
    results[image_name.split('_')[0]]['ssim'].append(ssim_value)

out_path = 'statistics/'
saved_results = {'psnr': [], 'ssim': []}
for item in results.values():
    psnr_value = np.array(item['psnr'])
    ssim_value = np.array(item['ssim'])
    if (len(psnr_value) == 0) or (len(ssim_value) == 0):
        psnr_value = 'No data'
        ssim_value = 'No data'
    else:
        psnr_value = psnr_value.mean()
        ssim = ssim_value.mean()
    saved_results['psnr'].append(psnr_value)
    saved_results['ssim'].append(ssim_value)

data_frame = pd.DataFrame(saved_results, results.keys())
data_frame.to_csv(out_path + 'srf_' + str(UPSCALE_FACTOR) + '_test_results.csv', index_label='DataSet')
