'''
Author: BHM-Bob 2262029386@qq.com
Date: 2023-04-04 16:45:23
LastEditors: BHM-Bob
LastEditTime: 2023-04-17 16:33:20
Description: 
'''
import scipy
import numpy as np
import pandas as pd
import statsmodels.api as sm
import scikit_posthocs as sp

import mbapy.plot as mp

#置信区间
def get_interval(mean = None, se = None, data = None, alpha:float = 0.95):
    """± 1.96 * SE or other depends on alpha"""
    assert se is not None or data is not None, 'se is None and data is None'
    kwargs = {
        'scale':se if se is not None else scipy.stats.sem(data)       
    }
    if mean is not None:
        kwargs.update({'loc':mean})
    if data is not None:
        kwargs.update({'df':len(data) - 1, 'loc':np.mean(data)})
    return scipy.stats.norm.interval(alpha = alpha, **kwargs)

#单样本T检验
from scipy.stats import ttest_1samp

def ttest_ind(x1, x2):
    """独立样本t检验(双样本T检验):检验两组独立样本均值是否相等"""
    levene = scipy.stats.levene(x1, x2)
    #levene 检验P值 > 0.05，接受原假设，认为两组方差相等
    #如不相等， scipy.stats.ttest_ind() 函数中的参数 equal_var 需要设置成 False
    return levene.pvalue, scipy.stats.ttest_ind(x1, x2, equal_var=levene.pvalue > 0.05)

#配对样本T检验:比较从同一总体下分出的两组样本在不同场景下，均值是否存在差异(两个样本的样本量要相同)
from scipy.stats import ttest_rel

#正态性检验：p > 0.05 为正态性
from scipy.stats import shapiro

#pearsonr相关系数：p > 0.05 为独立（不相关）
from scipy.stats import pearsonr
"""检验两个样本是否有线性关系"""

#卡方检验 Chi-Squared Test：p > 0.05 为独立（不相关）
from scipy.stats import chi2_contingency

# 方差分析检验（ANOVA） Analysis of Variance Test (ANOVA)：p < 0.05 为显著差异
from scipy.stats import f_oneway
"""检验两个或多个独立样本的均值是否有显著差异"""

def multicomp_turkeyHSD(factors:dict[str, list[str]], tag:str, df:pd.DataFrame, alpha:float = 0.05):
    """using statsmodels.stats.multicomp.pairwise_tukeyhsd\n
    Tukey的HSD法要求各样本的样本相等或者接近，在样本量相差很大的情况下还是建议使用其他方法\n
    Tukey的HSD检验比Bonferroni法更加的保守"""
    sub_df = mp.get_df_data(factors, [tag], df)
    return sm.stats.multicomp.pairwise_tukeyhsd(sub_df[tag], sub_df[list(factors.keys())[0]], alpha)

def multicomp_dunnett(factor:str, exp:list[str], control:str, df:pd.DataFrame, **kwargs):
    """using SciPy 1.11 scipy.stats.dunnett\n
    factors means colum name for expiremental factor and control factor"""
    exps = [np.array(df[factor][df[factor]==e]) for e in exp]
    return scipy.stats.dunnett(*exps, np.array(df[factor][df[factor]==control]), **kwargs)

def multicomp_bonferroni(factors:dict[str, list[str]], tag:str, df:pd.DataFrame, alpha:float = 0.05):
    """using scikit_posthocs.posthoc_dunn\n
    Bonferroni"""
    sub_df = mp.get_df_data(factors, [tag], df)
    return sp.posthoc_dunn(sub_df, val_col=tag, group_col=list(factors.keys())[0],
                           p_adjust='bonferroni')
    