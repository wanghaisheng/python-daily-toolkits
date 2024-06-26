import argparse
import itertools
import os
import math
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np
from tqdm import tqdm

os.environ['MBAPY_AUTO_IMPORT_TORCH'] = 'False'
os.environ['MBAPY_FAST_LOAD'] = 'True'

# if __name__ == '__main__':
from mbapy.base import put_err, split_list
from mbapy.bio.peptide import AnimoAcid, Peptide
from mbapy.file import opts_file, get_valid_file_path
from mbapy.web import TaskPool
from mbapy.scripts._script_utils_ import clean_path, show_args
# else:
#     from ..base import put_err
#     from ..file import opts_file, get_valid_file_path
#     from ._script_utils_ import clean_path, show_args
#     from ..bio.peptide import AnimoAcid, Peptide


def calcu_substitution_value(args: argparse.Namespace):
    """
    Calculates the substitution value and plots a scatter plot with a linear 
    regression model. The function first processes the input arguments to 
    convert the strings to float values and stores them in arrays. It then 
    calculates the average substitution value and prints it on the console. 
    Next, the function fits a linear regression model to the data using the 
    LinearRegression class from scikit-learn and calculates the equation 
    parameters and R-squared value for the fit. Finally, it plots the linear 
    regression line on the scatter plot using matplotlib and displays the 
    equation and R-squared value using text annotations.
    
    该函数使用给定的参数计算取代值，并绘制线性回归模型的散点图。函数首先将参数中的字符串转换为
    浮点数，并将其存储在数组中。然后，计算取代值的平均值，并在控制台上打印。接下来，函数使用线
    性回归模型拟合数据，并计算拟合方程的参数和R平方值。最后，函数在散点图上绘制线性回归线，并
    显示方程和R平方值。
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.linear_model import LinearRegression
    
    a = np.array([float(i) for i in args.absorbance.split(',') if len(i)])
    m = np.array([float(i) for i in args.weight.split(',') if len(i)])
    mean_subval = np.mean(args.coff*a/m)
    print(f'\nSubstitution Value: {args.coff*a/m}')
    print(f'\nAvg Substitution Value: {mean_subval}')
    
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(0, max(20, m.max()*1.2))
    ax.set_ylim(0, max(0.4, a.max()*1.2))

    regressor = LinearRegression()
    regressor = regressor.fit(m.reshape(-1, 1), a.reshape(-1, 1))
    equation_a, equation_b = regressor.coef_.item(), regressor.intercept_.item()
    equation_r2 = '{:4.3f}'.format(regressor.score(m.reshape(-1, 1), a.reshape(-1, 1)))
    sns.regplot(x = m, y = a, color = 'black', marker = 'o', truncate = False, ax = ax)

    equationStr = f'OD = {equation_a:5.4f} * m {" " if equation_b<0 else "+ ":}{equation_b:5.4f}'
    print(equationStr, '\n', 'R^2 = ', equation_r2)
    plt.text(0.1, 0.1, '$'+equationStr+'$', fontsize=20)
    plt.text(0.1, 0.3, '$R^2 = $'+equation_r2, fontsize=20)
    plt.xticks(size = 20)
    plt.yticks(size = 20)
    ax.set_title(f'Avg Substitution Value: {mean_subval:.5f}', fontsize=25)
    ax.set_xlabel('Weight of Resin (mg)', fontsize=25)
    ax.set_ylabel('OD (304 nm)', fontsize=25)
    plt.show()


def calcu_mw(args: argparse.Namespace, _print = print):
    """
    Calculates the molecular weight (MW) of a peptide based on its amino acid sequence and a dictionary of weights for each amino acid.

    Args:
        args (Namespace): An object containing the command line arguments.
        _print (function, optional): A function used for printing. Defaults to the built-in print function.

    Returns:
        tuple: A tuple containing the peptide object and the expanded MW dictionary.

    Example:
        >>> args = Namespace(seq='A-C-D-E', weight='A-71.04,C-103.01,D-115.03,E-129.04', mass=True)
        >>> calcu_mw(args)
        peptide: ACDE
        MW: 418.12
        Chemical Formular: C5H10N2O3
        Exact Mass: 118.07
        (<peptide object>, {'A': '71.04', 'C': '103.01', 'D': '115.03', 'E': '129.04'})
    """
    expand_mw_dict = [i.split('-') for i in args.weight.split(',') if len(i) > 2]
    expand_mw_dict = {i[0]:i[1] for i in expand_mw_dict}
    peptide = Peptide(args.seq)
    _print(f'\npeptide: {peptide}')
    _print(f'MW: {peptide.calcu_mw(expand_mw_dict)}')
    if args.mass:
        _print(f'Chemical Formular: {peptide.get_molecular_formula()}, Exact Mass: {peptide.calcu_mass()}')
    return peptide, expand_mw_dict
    
    
@dataclass
class MutationOpts:
    AA_deletion: bool = True # whether delete AA can be performed
    AA_repeat: int = 1 # AA repeat times of AA
    N_protect_deletion: bool = True # whether delete N-terminal protect group can be performed
    C_protect_deletion: bool = True # whether delete C-terminal protect group can be performed
    R_protect_deletion: bool = True # whether delete R-terminal protect group can be performed
    
    def copy(self):
        return MutationOpts(self.AA_deletion, self.AA_repeat, self.N_protect_deletion,
                            self.C_protect_deletion, self.R_protect_deletion)
    
    def check_empty(self, _pos: List[int], seq: Peptide, args: argparse.Namespace):
        """
        return list of signals which is able to opt, if empty, the lis is also empty.
        """
        pos, repeat_pos, sum_repeat = _pos
        able = []
        if pos >= len(seq.AAs):
            return []
        if sum_repeat == 1:
            if self.AA_deletion and not args.disable_aa_deletion:
                able.append('AA_deletion')
            if self.AA_repeat > 0:
                able.append('AA_repeat')
            if seq.AAs[pos].N_protect != 'H' and self.N_protect_deletion:
                able.append('N_protect_deletion')
            if seq.AAs[pos].C_protect != 'OH' and self.C_protect_deletion:
                able.append('C_protect_deletion')
            if seq.AAs[pos].R_protect != 'H' and self.R_protect_deletion:
                able.append('R_protect_deletion')
        else:
            if seq.AAs[pos][repeat_pos].N_protect != 'H' and self.N_protect_deletion:
                able.append('N_protect_deletion')
            if seq.AAs[pos][repeat_pos].C_protect != 'OH' and self.C_protect_deletion:
                able.append('C_protect_deletion')
            if seq.AAs[pos][repeat_pos].R_protect != 'H' and self.R_protect_deletion:
                able.append('R_protect_deletion')
        return able
                
    def delete_AA(self, tree: 'MutationTree', max_repeat: int):
        """
        perform delete_AA mutation in tree.mutate branch, trun off the tree.branches.opt.AA_deletion.
            - THE AA CAN NOT BE REPEATED.
            
        Params:
            - tree: MutationTree, tree to opt.
        """
        pos, repeat_pos, sum_repeat = tree.pos
        # perform delete_AA mutation in tree.mutate branch
        tree.mutate.seq.AAs[pos] = []
        #  mutate branch MOVE TO NEXT NEW AA
        tree.mutate.pos[0] += 1
        tree.mutate.opts = MutationOpts(AA_repeat=max_repeat)
        # trun off the delete AA opt in remain branch
        tree.remain.opts.AA_deletion = False
        return tree
    
    def repeat_AA(self, tree: 'MutationTree'):
        """
        perform delete_AA mutation in tree.mutate branch, trun off the tree.branches.opt.AA_deletion.
            - THE AA CAN NOT BE REPEATED.
            
        Params:
            - tree: MutationTree, tree to opt.
        """
        pos, repeat_pos, sum_repeat = tree.pos
        # perform repeat_AA mutation in tree.mutate branch
        tree.mutate.seq.AAs[pos] = [tree.mutate.seq.AAs[pos].copy() \
            for _ in range(tree.opts.AA_repeat + 1)]
        # change repeated AAs' N/C protect group if needed
        if pos == 0 and tree.peptide.AAs[pos].N_protect != 'H':
            for aa in tree.mutate.seq.AAs[pos][1:]:
                aa.N_protect = 'H'
        elif pos == len(tree.peptide.AAs)-1 and tree.peptide.AAs[pos].C_protect != 'OH':
            for aa in tree.mutate.seq.AAs[pos][:-1]:
                aa.C_protect = 'OH'
        # change mutate branch 's pos 's sum_repeat to tree.opts.repeat_AA + 1
        tree.mutate.pos[2] = tree.opts.AA_repeat + 1
        # trun off the repeat AA opts in mutate branches
        tree.mutate.opts = MutationOpts(AA_repeat=0)
        # decrease the repeat AA opts in remain branches
        tree.remain.opts.AA_repeat -= 1
        return tree        

    def delete_NCR(self, tree: 'MutationTree', NCR: str):
        """
        perform delete_NCR mutation in tree.mutate branch, trun off the tree.branches.opt.X_protect_deletion
        Params:
            - tree: MutationTree, tree to opt.
            - NCR: str, N or C or R.
        """
        pos, repeat_pos, sum_repeat = tree.pos
        null_pg = 'H' if NCR in ['N', 'R'] else 'OH'
        # delete X-terminal protect group
        if sum_repeat == 1 and getattr(tree.mutate.seq.AAs[pos], f'{NCR}_protect') != null_pg:
            setattr(tree.mutate.seq.AAs[pos], f'{NCR}_protect', null_pg)
        elif sum_repeat > 1 and getattr(tree.mutate.seq.AAs[pos][repeat_pos], f'{NCR}_protect') != null_pg:
            setattr(tree.mutate.seq.AAs[pos][repeat_pos], f'{NCR}_protect', null_pg)
        # trun off the opts in two branches
        setattr(tree.mutate.opts, f'{NCR}_protect_deletion', False)
        setattr(tree.remain.opts, f'{NCR}_protect_deletion', False)
        return tree
                
    def perform_one(self, tree: 'MutationTree', args: argparse.Namespace):
        """
        Perform ONE mutation opt left in tree.opts, return this tree. Also check if it is a repeated AA.
        If it is a repeated AA depend on tree.pos[2], skip AA deletion and AA repeat.
            - If no opts left to do:
                - let two brance still be None.
                - return the tree.
            - IF HAS:
                - generate two branch, change branches' father
                - perform mutation in mutate branch
                - trun off opts in two branches
                - move pos ONLY in mutate branch.
                - DO NOT CHECK IF MEETS END in both this dot and two branches.
                - return the tree.
        """
        able = tree.opts.check_empty(tree.pos, tree.seq, args)
        if able:
            # generate two branch and set seq to None to free memory
            tree.generate_two_branch()
            # perform mutation
            if 'AA_deletion' in able:
                tree = self.delete_AA(tree, args.max_repeat)
            elif 'AA_repeat' in able:
                tree = self.repeat_AA(tree)
            elif 'N_protect_deletion' in able:
                tree = self.delete_NCR(tree, 'N')
            elif 'C_protect_deletion' in able:
                tree = self.delete_NCR(tree, 'C')
            elif 'R_protect_deletion' in able:
                tree = self.delete_NCR(tree, 'R')
            else:
                raise ValueError('error when check empty with MutationOpts')
        # return tree
        return tree
    
@dataclass
class MutationTree:
    peptide: Peptide # mother peptide, READ ONLY, remians unchanged
    seq: Peptide # this dot's peptide seqeunce to perform mutate
    opts: MutationOpts # opts left to perform
    # [current AA pos, current repeat pos, sum repeat in this AA in seq], if last number is 1, means no repeat in this AA
    pos: List[int] = field(default_factory = lambda: [0, 0, 1])
    father: 'MutationTree' = None # father dot
    remain: 'MutationTree' = None # father dot
    mutate: 'MutationTree' = None # father dot
    
    def copy(self, copy_peptide: bool = False, copy_branch: bool = False,
             father: 'MutationTree' = None, remain: 'MutationTree' = None,
             mutate: 'MutationTree' = None):
        """
        Params:
            - copy_peptide: bool, whether to copy mother peptide.
            - copy_branch: bool, whether to copy father, remain, mutate branch via deepcopy. If False, leave it None.
        """
        if copy_peptide:
            cp = MutationTree(self.peptide.copy(), self.seq.copy(), self.opts.copy(), [i for i in self.pos])
        else:
            cp = MutationTree(self.peptide, self.seq.copy(), self.opts.copy(), [i for i in self.pos])
        if copy_branch:
            cp.father = deepcopy(self.father)
            cp.remain = deepcopy(self.remain)
            cp.mutate = deepcopy(self.mutate)
        else:
            cp.father = father
            cp.remain = remain
            cp.mutate = mutate
        return cp
    
    def extract_mutations(self, flatten: bool = True):
        """
        extract all terminal dots from mutations(Tree)
            - flatten==True:  will CHANGE it's peptide.AAs, return the flattened peptide.
            - flatten==False: will simply return all leaves of MutationTree.
        """
        if self.mutate is None and self.remain is None:
            if flatten:
                self.seq.flatten(inplace=True)
                return [self.seq]
            else:
                return [self]
        else:
            final_seq = []
            final_seq.extend(self.remain.extract_mutations(flatten))
            final_seq.extend(self.mutate.extract_mutations(flatten))
            return final_seq
    
    def check_is_end_pos(self):
        """check if current AA is the last AA whether in repeat or mother peptide"""
        if self.pos[0] >= len(self.peptide.AAs) - 1 and self.pos[1] >= self.pos[2] - 1:
            return True
        return False
        
    def generate_two_branch(self):
        """Generate two branch with all None remian and mutate branch, return itself."""
        self.remain = self.copy(father=self)
        self.mutate = self.copy(father=self)
        return self
        
    def move_to_next(self, max_repeat: int):
        """
        move current AA pos to next repeat AA or next NEW AA
            - return True is moved, else False when is end."""
        if not self.check_is_end_pos():
            if self.pos[1] == self.pos[2] - 1:
                # repeat idx meets end or do not have a repeat, move to next NEW AA
                self.pos[0] += 1
                self.pos[1] = 0
                self.pos[2] = 1
            else:
                # move to next repeat AA
                self.pos[1] += 1
            # reset opts to full
            self.opts = MutationOpts(AA_repeat = max_repeat)
            return True
        return False
        
def mutate_peptide(tree: MutationTree, args: argparse.Namespace):
    """
    Parameters:
        - mutations: Tree object, store all mutations and there relationship.
        - max_repeat: int
    """
    # perofrm ONE mutation
    tree = tree.opts.perform_one(tree, args)
    # if NO mutaion can be done, 
    if tree.mutate is None and tree.remain is None:
        # try move current AA in this tree to next AA
        if tree.move_to_next(args.max_repeat):
            # move success, go on
            mutate_peptide(tree, args)
        else:
            # it is the end, return tree
            return tree
    else: # go on with two branches
        mutate_peptide(tree.mutate, args)
        mutate_peptide(tree.remain, args)
    return tree

def calcu_mutations_mw(seqs: List[Peptide], mass: bool = False, verbose: bool = True):
    peps, mw2pep = {}, {}
    for pep in tqdm(seqs,
                    desc='Gathering mutations and Calculating molecular weight',
                    disable=not verbose):
        full_pep = Peptide(None)
        full_pep.AAs.extend(aa.AAs for aa in pep)
        full_pep.flatten(inplace = True)
        if len(full_pep.AAs):
            pep_repr = str(full_pep)
            if pep_repr not in peps:
                peps[pep_repr] = len(peps)
                if mass:
                    mw = full_pep.calcu_mass()
                else:
                    mw = full_pep.calcu_mw()
                if mw in mw2pep:
                    mw2pep[mw].append(full_pep)
                else:
                    mw2pep[mw] = [full_pep]
    return peps, mw2pep

def calcu_mw_of_mutations(args: argparse.Namespace):
    """
    Calculates the molecular weight of mutations based on the given arguments.

    Args:
        args (object): An object that contains the following attributes:
            - seq (str): The input sequence.
            - weight (bool): If True, the weight of the peptide will be calculated instead of the mass.
            - max_repeat (int): The maximum number of repeat amino acids allowed in the peptide.
            - out (str): The output file path. If None, the output will be printed to the console.
            - mass (bool): If True, the mass of the peptide will be calculated instead of the weight.

    Prints the molecular weight of the mutations and the corresponding peptide sequences.

    The function first sets up a helper function, `_print`, for printing information to the console and/or a file.
    It then processes the `args.out` attribute to obtain a valid file path if it is a directory.
    Next, it opens the output file for writing if `args.out` is not None, otherwise it sets `f` to None.
    The function then prints the values of the input arguments using `_print`.
    After that, it calls the `calcu_mw` function to calculate the molecular weight of the peptide and obtain a dictionary of expanded molecular weights.
    Following that, it creates a `MutationTree` object to hold the peptide and its mutations.
    It then mutates the peptide according to the maximum repeat allowed.
    Next, it extracts the individual mutations from the `all_mutations` object.
    The function then initializes dictionaries to store the molecular weight to peptide mapping and the unique peptide sequences.
    It iterates over each individual mutation and calculates its molecular weight.
    If the molecular weight is already present in `mw2pep`, the mutation is appended to the list of peptides with the same molecular weight.
    Otherwise, a new entry is created in `mw2pep` with the molecular weight as the key and the mutation as the value.
    Finally, the function prints the number of mutations found and the details of each mutation, along with their respective indices.
    If an output file was specified, it is closed at the end.
    """
    # set _print
    def _print(content: str, f, verbose = True):
        if f is not None:
            f.write(content+'\n')
        if verbose:
            print(content)
    if args.out is not None:
        args.out = clean_path(args.out)
        if os.path.isdir(args.out):
            file_name = get_valid_file_path(" ".join(sys.argv[1:]))+'.txt'
            args.out = os.path.join(args.out, file_name)
        f = open(args.out, 'w')
    else:
        f = None
    # show args
    verbose = not args.disable_verbose
    show_args(args, ['seq', 'weight', 'max_repeat', 'disable_aa_deletion',
                     'out', 'mass', 'disable_verbose', 'multi_process'],
              printf = lambda x : _print(x, f))
    # show mother peptide info
    peptide, expand_mw_dict = calcu_mw(args, _print = lambda x : _print(x, f))
    # calcu mutations
    seq, mw2pep, peps = [], {}, {}
    for aa in tqdm(peptide.AAs, desc='Mutating peptide'):
        pep = Peptide(None)
        pep.AAs = [aa.copy()]
        aa_mutations = MutationTree(peptide=pep, seq=pep.copy(),
                                    opts=MutationOpts(AA_repeat=args.max_repeat),
                                    pos=[0, 0, 1])
        aa_mutations = mutate_peptide(aa_mutations, args)
        seq.append(aa_mutations.extract_mutations())
    # gather mutations, calcu mw and store in dict
    seqs = list(itertools.product(*seq))
    if args.multi_process == 1:
        peps, mw2pep = calcu_mutations_mw(seqs, mass=args.mass, verbose=True)
    else:
        print('Gathering mutations and Calculating molecular weight...')
        peps, mw2pep = {}, {}
        pool = TaskPool('process', args.multi_process)
        for i, batch in enumerate(split_list(seqs, args.process_batch)):
            pool.add_task(f'{i}', calcu_mutations_mw, batch, args.mass, False)
        pool.run()
        pool.wait_till(lambda : pool.count_done_tasks() == len(pool.tasks), verbose=True)
        for (_, (peps_i, mw2pep_i), _) in pool.tasks.values():
            peps.update(peps_i)
            for i in mw2pep_i:
                if i in mw2pep:
                    mw2pep[i].extend(mw2pep_i[i])
                else:
                    mw2pep[i] = mw2pep_i[i]
    # output info
    _print(f'\n{len(peps)-1} mutations found, followings include one original peptide seqeunce:\n', f)
    if verbose:
        idx, weigth_type = 0, 'Exact Mass' if args.mass else 'MW'
        for i, mw in enumerate(sorted(mw2pep)):
            _print(f'\n{weigth_type}: {mw:10.5f}', f, verbose)
            for j, pep in enumerate(mw2pep[mw]):
                mf = f'({pep.get_molecular_formula()})' if args.mass else ''
                _print(f'    pep-{i:>4}-{j:<4}({idx:8d})({len(pep.AAs)} AA){mf}: {pep}', f, verbose)
                idx += 1
    # handle f-print
    if f is not None:
        f.close()
        # save mw2pep and peps
        opts_file(str(args.out)+'.pkl', 'wb', data = {'mw2pep':mw2pep, 'peps':peps}, way = 'pkl')
        
def transfer_letters(args):
    # show args
    show_args(args, ['seq', 'src', 'trg', 'dpg', 'ddash', 'input', 'out'])
    # get input
    if args.input is not None:
        path = clean_path(args.input)
        peps = []
        for line in opts_file(path, way='lines'):
            try:
                peps.append(Peptide(line, args.src))
            except:
                put_err(f'error when parsing: {line}, skip')
    else:
        peps = [Peptide(args.seq, args.src)]
    # make output
    reprs = [pep.repr(args.trg, not args.dpg, not args.ddash) for pep in peps]
    if args.out is not None:
        from mbapy.file import opts_file
        path = clean_path(args.output)
        opts_file(path, 'w', data = '\n'.join(reprs))
    [print(r) for r in reprs]
    return reprs


_str2func = {
    'sb': calcu_substitution_value,
    'subval': calcu_substitution_value,
    
    'mw': calcu_mw,
    'molecularweight': calcu_mw,
    'molecular-weight': calcu_mw,
    
    'mmw': calcu_mw_of_mutations,
    'mutationweight': calcu_mw_of_mutations,
    'mutation-weight': calcu_mw_of_mutations,
    
    'letters': transfer_letters,
    'transfer-letters': transfer_letters,
}


def main(sys_args: List[str] = None):
    args_paser = argparse.ArgumentParser()
    subparsers = args_paser.add_subparsers(title='subcommands', dest='sub_command')
    
    sub_val_args = subparsers.add_parser('subval', aliases = ['sb'], description='calcu SPPS substitution value for a release test of resin.')
    sub_val_args.add_argument('-a', '-A', '--absorbance', '--Absorbance', type = str,
                              help='Absorbance (OD value), input as 0.503,0.533')
    sub_val_args.add_argument('-m', '-w', '--weight', type = str,
                              help='resin wight (mg), input as 0.165,0.155')
    sub_val_args.add_argument('-c', '--coff', default = 16.4, type = float,
                              help='coff, default is 16.4')
    
    molecularweight = subparsers.add_parser('molecularweight', aliases = ['molecular-weight', 'mw'], description='calcu MW of peptide.')
    molecularweight.add_argument('-s', '--seq', '--seqeunce', '--pep', '--peptide', type = str,
                                 help='peptide seqeunce, input as Fmoc-Cys(Acm)-Leu-OH or H-Cys(Trt)-Leu-OH')
    molecularweight.add_argument('-w', '--weight', type = str, default = '',
                                 help='MW of peptide AAs and protect group, input as Trt-243.34,Boc-101.13 and do not include weight of -H')
    molecularweight.add_argument('-m', '--mass', action='store_true', default=False,
                                 help='calcu Exact Mass instead of Molecular Weight.')
    
    mutationweight = subparsers.add_parser('mutationweight', aliases = ['mutation-weight', 'mmw'], description='calcu MW of each peptide mutations syn by SPPS.')
    mutationweight.add_argument('-s', '--seq', '--seqeunce', '--pep', '--peptide', type = str,
                                help='peptide seqeunce, input as Fmoc-Cys(Acm)-Leu-OH or H-Cys(Trt)-Leu-OH')
    mutationweight.add_argument('-w', '--weight', type = str, default = '',
                                help='MW of peptide AAs and protect group, input as Trt-243.34,Boc-101.13 and do not include weight of -H')
    mutationweight.add_argument('--max-repeat', type = int, default = 1,
                                help='max times for repeat a AA in sequence')
    mutationweight.add_argument('--disable-aa-deletion', action='store_true', default=False,
                                help='disable AA deletion in mutations.')
    mutationweight.add_argument('-o', '--out', type = str, default = None,
                                help='save results to output file/dir. Defaults None, do not save.')
    mutationweight.add_argument('-m', '--mass', action='store_true', default=False,
                                help='calcu Exact Mass instead of Molecular Weight.')
    mutationweight.add_argument('--disable-verbose', action='store_true', default=False,
                                help='disable verbose output to console.')
    mutationweight.add_argument('--multi-process', type = int, default = 1,
                                help='number of multi-process to use. Defaults 1, no multi-process.')
    mutationweight.add_argument('--process-batch', type = int, default = 500000,
                                help='number of peptides to process in each batch. Defaults %(default)% in a batch.')
    
    letters = subparsers.add_parser('letters', aliases = ['transfer-letters'], description='transfer AnimoAcid repr letters width.')
    letters.add_argument('-s', '--seq', '--seqeunce', '--pep', '--peptide', type = str, default='',
                                help='peptide seqeunce, input as Fmoc-Cys(Acm)-Leu-OH or ABC(Trt)DE')
    letters.add_argument('--src', '--source-width', type = int, choices=[1, 3], default = 3,
                                help='source repr width of AnimoAcid, only accept 1 and 3.')
    letters.add_argument('--trg', '--target-width', type = int, choices=[1, 3], default = 1,
                                help='traget repr width of AnimoAcid, only accept 1 and 3.')
    letters.add_argument('--dpg', '--disable-pg', action='store_true', default = False,
                                help='whether to include protect groups in target repr.')
    letters.add_argument('--ddash', '--disable-dash', action='store_true', default = False,
                                help='whether to include dash line in target repr.')
    letters.add_argument('-i', '--input', type = str, default = None,
                                help='input file where peptide seq exists in each line. Defaults None, do not save.')
    letters.add_argument('-o', '--out', type = str, default = None,
                                help='save results to output file/dir. Defaults None, do not save.')
    
    args = args_paser.parse_args(sys_args)
    
    if args.sub_command in _str2func:
        print(f'excuting command: {args.sub_command}')
        _str2func[args.sub_command](args)
    else:
        put_err(f'no such sub commmand: {args.sub_command}')

if __name__ == "__main__":
    # dev code. MUST BE COMMENTED OUT WHEN PUBLISHING
    # from mbapy.base import TimeCosts
    # @TimeCosts(5)
    # def func(idx, mp):
    # main(f'mmw -s Fmoc-Cys(Acm)-Val-Asn(Trt)-Cys(Acm)-Val-Asn(Trt) -m --multi-process 2 --process-batch 1000'.split())
    # # func(mp = 1) # func used     33.542s in total,      6.708s by mean (release run)
    # # func(mp = 3) # func used     74.241s in total,     14.848s by mean (release run)
    # # func(mp = 4) # func used     73.012s in total,     14.602s by mean (release run)
    
    # release code
    main()