'''
Author: BHM-Bob 2262029386@qq.com
Date: 2023-04-04 16:45:23
LastEditors: BHM-Bob
LastEditTime: 2023-05-02 12:16:00
Description: 
'''
import scipy
import numpy as np
import pandas as pd
import statsmodels.api as sm
import scikit_posthocs as sp

import mbapy.plot as mp

def get_interval(mean = None, se = None, data = None, alpha:float = 0.95):
    """
    置信区间\n
    ± 1.96 * SE or other depends on alpha
    """
    assert se is not None or data is not None, 'se is None and data is None'
    kwargs = {
        'scale':se if se is not None else scipy.stats.sem(data)       
    }
    if mean is not None:
        kwargs.update({'loc':mean})
    if data is not None:
        kwargs.update({'df':len(data) - 1, 'loc':np.mean(data)})
    return scipy.stats.norm.interval(alpha = alpha, **kwargs)

def _get_x1_x2(x1 = None, x2 = None,
               factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None):
    if factors is not None and tag is not None and df is not None:
        sub_df = mp.get_df_data(factors, [tag], df)
        fac_name = list(factors.keys())[0]
        x1 = sub_df.loc[sub_df[fac_name] == factors[fac_name][0], [tag]].values
        if len(factors[fac_name]) == 2:
            x2 = sub_df.loc[sub_df[fac_name] == factors[fac_name][1], [tag]].values
        elif len(factors[fac_name]) > 2:
            raise ValueError('Only support 1 or 2 value of factors')
    return x1, x2

def ttest_1samp(x1 = None, x2:float = None,
                 factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """单样本T检验"""
    x1, x2 = _get_x1_x2(x1, x2, factors, tag, df)
    return scipy.stats.ttest_1samp(x1, x2, **kwargs)

def ttest_ind(x1 = None, x2 = None,
                 factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """
    独立样本t检验(双样本T检验):检验两组独立样本均值是否相等\n
    要求正太分布，正太检验结果由scipy.stats.levene计算并返回\n
    levene 检验P值 > 0.05，接受原假设，认为两组方差相等\n
    如不相等， scipy.stats.ttest_ind() 函数中的参数 equal_var 会设置成 False
    """
    x1, x2 = _get_x1_x2(x1, x2, factors, tag, df)
    levene = scipy.stats.levene(x1, x2)
    return levene.pvalue, scipy.stats.ttest_ind(x1, x2, equal_var=levene.pvalue > 0.05)

def ttest_rel(x1 = None, x2 = None,
                 factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """配对样本T检验:比较从同一总体下分出的两组样本在不同场景下，均值是否存在差异(两个样本的样本量要相同)"""
    x1, x2 = _get_x1_x2(x1, x2, factors, tag, df)
    return scipy.stats.ttest_rel(x1, x2, **kwargs)

def mannwhitneyu(x1 = None, x2 = None,
                 factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """
    Mann-Whitney U检验:数据不具有正态分布时使用。\n
    评估了两个抽样群体是否可能来自同一群体，这两个群体在数据方面是否具有相同的形状？\n
    证明这两个群体是否来自于具有不同水平的相关变量的人群。\n
    此包装函数同时支持直接输入和mbapy-style数据输入
    """
    x1, x2 = _get_x1_x2(x1, x2, factors, tag, df)
    return scipy.stats.mannwhitneyu(x1, x2, **kwargs)


def pearsonr(x1 = None, x2 = None,
             factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """
    pearsonr相关系数:检验两个样本是否有线性关系\n
    p > 0.05 为独立（不相关）
    """
    x1, _ = _get_x1_x2(x1, None, factors, tag, df)
    return scipy.stats.shapiro(x1)

def _get_observe(observed = None,
                 factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None):
    if observed is None and factors is not None and tag is not None and df is not None:
        @mp.pro_bar_data_R(list(factors.keys()), [tag], df, [''])
        def get_sum(values):
            return [values.sum()]
        ndf = get_sum()
        col = list(factors.keys())[0]
        rol = list(factors.keys())[1]
        mat = pd.DataFrame(np.zeros(shape = (len(factors[rol]), len(factors[col]))),
                           index=factors[rol], columns=factors[col])
        for c in factors[col]:
            for r in factors[rol]:
                mat[c][r] = sum(ndf.loc[(ndf[col] == c) & (ndf[rol] == r), [tag]].values)
        observed = mat
    return observed

def chi2_contingency(observed = None,
                      factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """
    卡方检验 Chi-Squared Test:\n
    p > 0.05 为独立(不相关)。\n
    若存在某一个格子的理论频数T<5或p值与规定的显著性水平(如0.05)相近时，改用Fisher's exact test\n
    1. 样本来自简单随机抽样
    2. 各个格子是相互独立的;
    3. 样本量应尽可能大。总观察数应不小于40，且每个格子的频数应大于等于5\n
    支持直接输入和mbapy-style数据输入\n
    mbapy-style: factors={'a':['a1', 'a2', ...], 'b':['b1', 'b2', ...]}, tag is value of 0/1 or number
    """
    observed = _get_observe(observed, factors, tag, df)
    return scipy.stats.chi2_contingency(observed, **kwargs), observed

def fisher_exact(observed = None,
                      factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None, **kwargs):
    """
    Fisher确切概率法 Fisher's exact test:\n
    2x2 contingency table, p > 0.05 为独立(不相关)\n
    支持直接输入和mbapy-style数据输入\n
    mbapy-style: factors={'a':['a1', 'a2'], 'b':['b1', 'b2']}
    """
    observed = _get_observe(observed, factors, tag, df)
    return scipy.stats.fisher_exact(observed, **kwargs), observed

def f_oneway(Xs:list = None,
             factors:dict[str, list[str]] = None, tag:str = None, df:pd.DataFrame = None):
    """
    方差分析检验(ANOVA) Analysis of Variance Test (ANOVA):p < 0.05 为显著差异\n
    检验两个或多个独立样本的均值是否有显著差异\n
    支持直接输入(Xs)和
    """
    if Xs is None and factors is not None and tag is not None and df is not None:
        sub_df = mp.get_df_data(factors, [tag], df)
        fac_name = list(factors.keys())[0]
        sub_facs = factors[fac_name]
        Xs = [sub_df.loc[sub_df[fac_name] == f, [tag]].values for f in sub_facs]
    return scipy.stats.f_oneway(*Xs)

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
    