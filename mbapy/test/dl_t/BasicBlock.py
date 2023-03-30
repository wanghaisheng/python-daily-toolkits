'''
Author: BHM-Bob 2262029386@qq.com
Date: 2022-11-04 12:33:19
LastEditors: BHM-Bob
LastEditTime: 2023-03-24 22:15:10
Description: Test for Basic Blocks
'''
import sys

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.append(r'../../../')

import dl_torch.bb as bb

x = torch.arange(16, dtype = torch.float32, device = 'cuda').reshape([1, 1, 4, 4])
t = F.unfold(x, 3, 1, 1, 1)
t = (
    t.reshape(1, 1, 9, 16)
    .permute(0, 1, 3, 2)
    .reshape(1, 1 * 16, 9)
)
print(t)
net = bb.SCANN(4, 1, 1, 1, 1, 3,'linear', 0.3).to('cuda')
print(net(x).shape, "torch.Size([1, 1, 4, 4])")

x = torch.rand([32, 128, 32], device = 'cuda')
net = bb.MultiHeadAttentionLayer(32, 8, 0.3, 'cuda').to('cuda')
print(net(x, x, x).shape, "torch.Size([32, 128, 32])")
net = bb.EncoderLayer(0, 0, 32, 8, 64, 0.3, 'cuda').to('cuda')
print(net(x).shape, "torch.Size([32, 128, 32])")
net = bb.Trans(128, 128, 32, 3, 8, 128, 0.3, 'cuda', bb.EncoderLayer).to('cuda')
print(net(x).shape, "torch.Size([32, 128, 32])")
net = bb.Trans(128, 128, 32, 3, 8, 128, 0.3, 'cuda').to('cuda')
print(net(x).shape, "torch.Size([32, 128])")
net = bb.Trans(128, 128, 32, 3, 8, 128, 0.3, 'cuda', use_enhanced_fc_q = True).to('cuda')
print(net(x).shape, "torch.Size([32, 128])")
net = bb.Trans(128, 32, 32, 3, 8, 128, 0.3, 'cuda', use_enhanced_fc_q = True).to('cuda')
print(net(x).shape, "torch.Size([32, 32])")

x = torch.rand([32, 128, 32], device = 'cuda')
net = bb.OutEncoderLayerAvg(128, 32, 32, 8, 64, 0.3, 'cuda').to('cuda')
print(net(x).shape, "torch.Size([32, 32])")
net = bb.TransAvg(128, 32, 32, 3, 8, 128, 0.3, 'cuda', use_enhanced_fc_q = True).to('cuda')
print(net(x).shape, "torch.Size([32, 32])")

x = torch.rand([8, 16, 32, 32], device = 'cuda')
net = bb.ResBlock(16, 128, 2).to('cuda')
print(net(x).shape, "torch.Size([8, 128, 16, 16])")
net = bb.ResBlockR(16, 128, 2).to('cuda')
print(net(x).shape, "torch.Size([8, 128, 16, 16])")
net = bb.SABlock(16, 32).to('cuda')
print(net(x).shape, "torch.Size([8, 32, 32, 32])")
net = bb.SABlockR(16, 32).to('cuda')
print(net(x).shape, "torch.Size([8, 32, 32, 32])")

x = torch.rand([8, 16, 128], device = 'cuda')
net = bb.SABlock1D(16, 32).to('cuda')
print(net(x).shape, "torch.Size([8, 32, 128])")
net = bb.SABlock1DR(16, 32).to('cuda')
print(net(x).shape, "torch.Size([8, 32, 128])")