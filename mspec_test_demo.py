'''
@Autuor: LZ-CH
@Contact: 2443976970@qq.com

Note: this repository could only be used when CUDA is available!!!
'''

import torch
import torch.nn as nn
import torchvision
import os
import time
import model
import numpy as np
import glob
import time
import cv2
from tools.decomposition import lplas_decomposition as decomposition
from model import MSPEC_Net
from tools.calculate_psnr_ssim import calculate_psnr_ssim
from tiler import Tiler, Merger
import random
from tiling import ConstSizeTiles
import argparse
from tqdm import tqdm


def exposure_correction(MSPEC_net,data_input):
	if data_input.dtype == 'uint8':
		data_input = data_input/255
	_,L_list = decomposition(data_input)
	L_list = [torch.from_numpy(data).float().permute(2,0,1).unsqueeze(0).cuda() for data in L_list]
	Y_list = MSPEC_net(L_list)
	predict = Y_list[-1].squeeze().permute(1,2,0).detach().cpu().numpy()
	return predict
			
def down_correction(MSPEC_net,data_input):
	maxsize = max([data_input.shape[0],data_input.shape[1]])
	insize = 512
	
	scale_ratio = insize/maxsize
	im_low = cv2.resize(data_input,(0, 0), fx=scale_ratio, fy=scale_ratio,interpolation = cv2.INTER_CUBIC)
	top_pad,left_pad = insize - im_low.shape[0],insize - im_low.shape[1]
	im = cv2.copyMakeBorder(im_low, top_pad, 0, left_pad, 0, cv2.BORDER_DEFAULT)
	out = exposure_correction(MSPEC_net,im)
	out = out[top_pad:,left_pad:,:]
	final_out = out

	'''
	A simple upsampling method is used here. 
	If you want to achieve better results, please 
	use the bgu in the original matlab code to upsample.
	'''

	final_out = cv2.resize(final_out,(data_input.shape[1],data_input.shape[0]))

	return final_out
		


def evaluate(MSPEC_net,image_path,savedir):

	data_input = cv2.imread(image_path)

	start = time.time()
	output_image = down_correction(MSPEC_net,data_input)
	end_time = (time.time() - start)
	image_basename=os.path.basename(image_path)
	if output_image.dtype == 'uint8':
		cv2.imwrite( os.path.join(savedir,image_basename),output_image)
	else:
		cv2.imwrite( os.path.join(savedir,image_basename),output_image*255)


if __name__ == '__main__':
# test_images
	parser = argparse.ArgumentParser()
	parser.add_argument("--input_dir", type=str, required=True)
	parser.add_argument("--output_dir", type=str, required=True)
	args = parser.parse_args()

	with torch.no_grad():
		MSPEC_net = MSPEC_Net().cuda()
		MSPEC_net = torch.nn.DataParallel(MSPEC_net)
		MSPEC_net.load_state_dict(torch.load('./snapshots/MSPECnet_woadv.pth'))
		MSPEC_net.eval()
		test_list = glob.glob(args.input_dir + "/*") 
		if not os.path.exists(args.output_dir):
			os.makedirs(args.output_dir)

		for n,imagepath in tqdm(enumerate(test_list), total=len(test_list), desc="Running MSPECNet..."):
			evaluate(MSPEC_net, imagepath, args.output_dir)
