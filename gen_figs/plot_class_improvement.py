"""
Creates plot of classes sorted by their classification after applying our geo-prior.

First run geo_prior/run_evaluation.py with the following settings:
    eval_params = {}
    eval_params['dataset'] = 'inat_2017'
    eval_params['eval_split'] = 'val'
    eval_params['model_type'] = '_full_final'
    eval_params['save_op'] = True

Most of the other plots use iNat2018. However, here we use iNat2017 here as it
has a bigger validation set, resulting in a more meaningful plot.
"""

import torch
import numpy as np
import matplotlib.pyplot as plt
import json
import os
from sklearn.metrics import confusion_matrix

import sys
sys.path.append('../')
from geo_prior import models
from geo_prior.paths import get_paths
import geo_prior.datasets as dt
import geo_prior.grid_predictor as grid


model_path = '../models/model_inat_2017_full_final.pth.tar'
data_dir = get_paths('inat_2017_data_dir')
time_of_year = 0.5  # i.e. half way through the year
op_dir = 'images/class_improvement/'
if not os.path.isdir(op_dir):
    os.makedirs(op_dir)


# model_preds.npz is generated by run_evaluation - see above
ops = np.load('../geo_prior/model_preds.npz')
val_classes = ops['val_classes']
pred_no_prior = ops['pred_no_prior']
pred_geo_net = ops['pred_geo_net']
dataset = str(ops['dataset'])
split = str(ops['split'])
num_classes = np.unique(val_classes).shape[0]
if dataset != 'inat_2017' or split != 'val':
    print('WARNING: This script expects the iNat2017 val dataset!')
    assert False


# create confusion matrices - not really needed for this but can be used to
# look at the class distribution for a particular category e.g.
# plt.plot(cm_geo_net[class_of_interest, :])
cm_no_prior = confusion_matrix(val_classes, pred_no_prior, range(num_classes))
cm_no_prior = cm_no_prior.astype(np.float32) / cm_no_prior.sum(axis=1)[:, np.newaxis]
cm_no_prior = (cm_no_prior + cm_no_prior.T)/2.0
cm_geo_net = confusion_matrix(val_classes, pred_geo_net, range(num_classes))
cm_geo_net = cm_geo_net.astype(np.float32) / cm_geo_net.sum(axis=1)[:, np.newaxis]
cm_geo_net = (cm_geo_net + cm_geo_net.T)/2.0

# compute accuracy difference
cm_diff = np.triu(cm_geo_net, 1) - np.triu(cm_no_prior, 1)
acc_diff = np.diag(cm_geo_net) - np.diag(cm_no_prior)
sort_inds = np.argsort(acc_diff)

plt.close('all')
plt.figure(1)
plt.plot(acc_diff[sort_inds]*100, lw=2)
plt.grid(True)
plt.ylim([-100, 100])
pad = int(len(sort_inds)*0.005)
plt.xlim([-pad, len(sort_inds)+pad])
plt.title(dataset + ' - ' + split, fontsize=16)
plt.ylabel('accuracy difference (%)', fontsize=14)
plt.xlabel('sorted categories', fontsize=14)

print('Saving images to: ' + op_dir)
op_file_name = op_dir + dataset + '_' + split + '.pdf'
plt.savefig(op_file_name)


# # load class names
with open(data_dir + 'categories2017.json') as da:
    cls_data = json.load(da)
class_names = [cc['name'] for cc in cls_data]
class_ids = [cc['id'] for cc in cls_data]
class_dict = dict(zip(class_ids, class_names))

# worst and best classes
class_of_interest_1 = sort_inds[1]  # 2nd worst
class_of_interest_2 = sort_inds[-2] # 2nd best

print('Worst improvment: ' + str(class_of_interest_1) + ' ' + class_dict[class_of_interest_1])
print('Best improvment: ' + str(class_of_interest_2) + ' ' + class_dict[class_of_interest_2])


# load model
net_params = torch.load(model_path, map_location='cpu')
params = net_params['params']
model = models.FCNet(num_inputs=params['num_feats'], num_classes=params['num_classes'],
                     num_filts=params['num_filts'], num_users=params['num_users']).to(params['device'])

model.load_state_dict(net_params['state_dict'])
model.eval()

# load ocean mask
mask = np.load(get_paths('mask_dir') + 'ocean_mask.npy')

# grid predictor - for making dense predictions for each lon/lat location
gp = grid.GridPredictor(mask, params, mask_only_pred=True)

# make predictions for both classes
if not params['use_date_feats']:
    print('Trained model not using date features')

grid_pred_1 = gp.dense_prediction(model, class_of_interest_1, time_step=time_of_year)
grid_pred_2 = gp.dense_prediction(model, class_of_interest_2, time_step=time_of_year)


plt.figure(2)
plt.imshow(1-grid_pred_1, cmap='afmhot', vmin=0, vmax=1)
plt.title(class_dict[class_of_interest_1] + ' ' + str(class_of_interest_1))

plt.figure(3)
plt.imshow(1-grid_pred_2, cmap='afmhot', vmin=0, vmax=1)
plt.title(class_dict[class_of_interest_2] + ' ' + str(class_of_interest_2))


op_file_name_1 = op_dir + str(class_of_interest_1).zfill(4) + '.png'
op_file_name_2 = op_dir + str(class_of_interest_2).zfill(4) + '.png'
plt.imsave(op_file_name_1, 1-grid_pred_1, cmap='afmhot', vmin=0, vmax=1)
plt.imsave(op_file_name_2, 1-grid_pred_2, cmap='afmhot', vmin=0, vmax=1)

plt.show()
