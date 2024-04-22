import argparse
import glob
import os
from pathlib import Path
from typing import Dict, List

import scipy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.environ['MBAPY_AUTO_IMPORT_TORCH'] = 'False'
os.environ['MBAPY_FAST_LOAD'] = 'True'
from mbapy.base import put_err
from mbapy.plot import get_palette, save_show

if __name__ == '__main__':
    from mbapy.file import get_paths_with_extension, get_valid_file_path
    from mbapy.scripts._script_utils_ import clean_path, show_args
else:
    from ..file import get_paths_with_extension, get_valid_file_path
    from ._script_utils_ import clean_path, show_args


def plot_mass_load_file(path: Path):
    lines = path.read_text().splitlines()
    df = pd.DataFrame([line.split('\t') for line in lines[1:]],
                        columns = lines[0].split('\t'))
    if df.shape[1] == 2 and df.columns[0] == 'Time' and df.columns[1] == 'Intensity':
        # setattr(df, '_content_type', 'base peak') # NOTE: this does not work
        df._attrs['content_type'] = 'base peak'
        return df.astype(float)
    elif df.shape[1] == 2 and df.columns[0] == 'Time' and df.columns[1] == 'Absorbance':
        df._attrs['content_type'] = 'absorbance'
        return df.astype(float)
    elif df.shape[1] == 2 and df.columns[0] == 'Mass/Charge' and df.columns[1] == 'Intensity':
        df._attrs['content_type'] = 'mass-charge'
        return df.astype(float)
    elif df.shape[1] == 10:
        df._attrs['content_type'] = 'peak list'
        return df.astype({'Mass/Charge':float, 'Height':float, 'Charge':int,
                            'Monoisotopic':str, 'Mass (charge)':str,
                            'Mass/charge (charge)':str})
    else:
        return put_err(f'Can not recognizable txt file: {path}, skip.')

def plot_mass_plot_basepeak(name:str, base_peak: pd.DataFrame, args):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(base_peak['Time'], base_peak['Intensity'], color = args.color)
    plt.xticks(size = 20)
    plt.yticks(size = 20)
    plt.yscale('log')
    ax.set_title(f'{name} (TIC of TOF MS)', fontsize=25)
    ax.set_xlabel('Time (min)', fontsize=25)
    ax.set_ylabel('Intensity (cps)', fontsize=25)
    save_show(os.path.join(args.output, f'{name} base peak.png'), dpi = 600)
    
def plot_mass_plot_absorbance(name:str, df: pd.DataFrame, args):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df['Time'], df['Absorbance'], color = args.color)
    plt.xticks(size = 20)
    plt.yticks(size = 20)
    ax.set_title(f'{name} (Absorbance)', fontsize=25)
    ax.set_xlabel('Time (min)', fontsize=25)
    au_units = ('m' if df['Absorbance'].max() > 10 else '') + 'AU'
    ax.set_ylabel(f'Absorbance ({au_units})', fontsize=25)
    ax.set_xlim(0, df['Time'].max())
    save_show(os.path.join(args.output, f'{name} absorbance.png'), dpi = 600)

def _plot_vlines(x, y, col, label = None):
    plt.vlines(x, 0, y, colors = [col] * len(x), label = label)
    plt.scatter(x, y, c = col)
    
def plot_mass_plot_peaklist(name:str, df: pd.DataFrame, args):
    fig, ax = plt.subplots(figsize=(10, 6))
    if args.xlim:
        xlim = [float(i) for i in args.xlim.split(',')]
        df = df[(df['Mass/Charge'] >= xlim[0]) & (df['Mass/Charge'] <= xlim[1])]
        print(f'x-axis data limit set to {xlim}')
    idx = df['Monoisotopic'] == 'Yes'
    _plot_vlines(df['mass_data'], df['Height'], args.color)
    labels_ms = np.array(list(args.labels.keys()))
    for ms, h, c in zip(df['mass_data'][idx], df['Height'][idx],
                        df['Charge'][idx]):
        matched = np.where(np.abs(labels_ms - ms) < args.labels_eps)[0]
        if matched.size > 0:
            label, color = args.labels.get(labels_ms[matched[0]])
            _plot_vlines([ms], [h], color, label)
            ax.text(ms, h, f'* {ms:.2f}({c:d})', fontsize=15, color = color)
        else:
            ax.text(ms, h, f'* {ms:.2f}({c:d})', fontsize=15, color = args.color)
    plt.xticks(size = 20)
    plt.yticks(size = 20)
    plt.yscale('log')
    axis_lim = (1-args.expand, 1+args.expand)
    plt.xlim(df['mass_data'].min() * axis_lim[0], df['mass_data'].max() * axis_lim[1])
    plt.ylim(df['Height'].min() * axis_lim[0], df['Height'].max() * axis_lim[1])
    ax.set_title(f'{name} (Peak List of TOF MS)', fontsize=25)
    ax.set_xlabel(f'Mass{"" if args.mass else "/charge"}', fontsize=25)
    ax.set_ylabel('Intensity (cps)', fontsize=25)
    plt.legend(fontsize=15, loc = args.legend_pos, bbox_to_anchor = (args.legend_pos_bbox1, args.legend_pos_bbox2))
    save_show(os.path.join(args.output, f'{name} peak list.png'), dpi = 600)
    
def plot_mass_plot_masscharge(name: str, df: pd.DataFrame, args):
    # find peaks
    peaks_cache_path = os.path.join(args.output, f'{name} peaks.cache.npy')
    if args.use_peaks_cache and os.path.exists(peaks_cache_path):
        peaks = np.load(peaks_cache_path)
        print(f'loaded peaks from cache: {peaks_cache_path}')
    else:
        print('searching peaks...')
        peaks = scipy.signal.find_peaks_cwt(df['Intensity'], args.min_peak_width)
        np.save(peaks_cache_path, peaks)
    # filter peaks
    if peaks.any():
        df = df.iloc[peaks, :]
    if args.xlim:
        xlim = [float(i) for i in args.xlim.split(',')]
        df = df[(df['Mass/Charge'] >= xlim[0]) & (df['Mass/Charge'] <= xlim[1])]
        print(f'x-axis data limit set to {xlim}')
    min_height = df['Intensity'].max() * args.min_height_percent / 100
    df = df[df['Intensity'] >= min_height] # save time in searching, widths should be small
    print(f'min-height set to {min_height}')
    print(f'searching done. {len(df)} peaks found.')
    df.to_csv(os.path.join(args.output, f'{name} {df._attrs["content_type"]}.csv'))
    # plot
    fig, ax = plt.subplots(figsize=(10, 6))
    _plot_vlines(df['Mass/Charge'], df['Intensity'], args.color)
    labels_ms = np.array(list(args.labels.keys()))
    for ms, h in zip(df['Mass/Charge'], df['Intensity']):
        matched = np.where(np.abs(labels_ms - ms) < args.labels_eps)[0]
        if matched.size > 0:
            label, color = args.labels.get(labels_ms[matched[0]])
            _plot_vlines([ms], [h], color, label)
            ax.text(ms, h, f'* {ms:.2f}', fontsize=15, color = color)
        else:
            ax.text(ms, h, f'* {ms:.2f}', fontsize=15, color = args.color)
    # fix style
    plt.xticks(size = 20)
    plt.yticks(size = 20)
    plt.yscale('log')
    axis_lim = (1-args.expand, 1+args.expand)
    plt.xlim(df['Mass/Charge'].min() * axis_lim[0], df['Mass/Charge'].max() * axis_lim[1])
    plt.ylim(df['Intensity'].min() * axis_lim[0], df['Intensity'].max() * axis_lim[1])
    ax.set_title(f'{name} (Mass/Charge of TOF MS)', fontsize=25)
    ax.set_xlabel(f'Mass/Charge', fontsize=25)
    ax.set_ylabel('Intensity (cps)', fontsize=25)
    plt.legend(fontsize=15, loc = args.legend_pos, bbox_to_anchor = (args.legend_pos_bbox1, args.legend_pos_bbox2))
    save_show(os.path.join(args.output, f'{name} Mass-Charge.png'), dpi = 600)
    
def plot_mass(args):           
    # process input and output args
    # after process, output whether be str or be None if recursive
    args.dir = clean_path(args.dir)
    if args.output is None:
        args.output = args.dir
        if not os.path.isdir(args.output):
            print(f'given output {args.output} is a file, change it to parent dir')
            args.output = args.output.parent
    if args.recursive and args.output:
        args.output = None
    use_recursive_output = args.recursive and args.output is None
    # process labels args
    labels, colors = {}, get_palette(len(args.labels.split(';')), mode = 'hls')
    for idx, i in enumerate(args.labels.split(';')):
        if i:
            pack = i.split(',')
            mass, label, color = pack[0], pack[1], pack[2] if len(pack) == 3 else colors[idx]
            labels[float(mass)] = [label, color]
    args.labels = labels
    if ',' in args.legend_pos:
        args.legend_pos = args.legend_pos.split(',')
        args.legend_pos = (float(args.legend_pos[0]), float(args.legend_pos[1]))
    # find base peak file and peak list file
    paths = get_paths_with_extension(args.dir, ['txt'], args.recursive)
    dfs = {path:plot_mass_load_file(Path(path)) for path in paths}
    dfs = {k:v for k,v in dfs.items() if v is not None}
    if not dfs:
        raise FileNotFoundError(f'can not find txt files in {args.dir}')
    # show args
    show_args(args, ['dir', 'output', 'recursive', 'labels', 'labels_eps', 'legend_pos',
                     'legend_pos_bbox1', 'legend_pos_bbox2', 'color', 'min_height',
                     'min_height_percent', 'min_peak_width', 'xlim', 'mass', 'expand'])
    # show data general info and output peak list DataFrame
    for n,df in dfs.items():
        path = Path(n).resolve()
        name = path.stem
        if use_recursive_output:
            args.output = str(path.parent)
        print(f'\n\n\n\n\n{name}: {df._attrs["content_type"]}:\n', df)
        df.to_csv(os.path.join(args.output, f'{name} {df._attrs["content_type"]}.csv'))
        # process Mass (charge) and identify mass
        if df._attrs['content_type'] == 'peak list':
            df['Mass (charge)'] = df['Mass (charge)'].str.extract(r'(\d+\.\d+)', expand=False).astype(float)
            df['Mass/charge (charge)'] = df['Mass/charge (charge)'].str.extract(r'(\d+\.\d+)', expand=False).astype(float)
            df['mass_data'] = df['Mass (charge)'] if args.mass else df['Mass/charge (charge)']
            drop_idx = df[df['Height'] < args.min_height].index
            if not drop_idx.empty:
                print(f'drop data with min-height: {args.min_height} and only these data remained:\n',
                      df[df['Height'] >= args.min_height])
                df.drop(drop_idx, axis = 0, inplace = True)
        if not df.empty:
            # plot each df
            print(f'plotting {name}: {df._attrs["content_type"]}')
            if df._attrs["content_type"] == 'base peak':
                plot_mass_plot_basepeak(name, df, args)
            elif df._attrs["content_type"] == 'absorbance':
                plot_mass_plot_absorbance(name, df, args)
            elif df._attrs["content_type"] == 'peak list': # avoid drop all data but still draw
                plot_mass_plot_peaklist(name, df, args)
            elif df._attrs["content_type"] =='mass-charge':
                plot_mass_plot_masscharge(name, df, args)
            else:    
                put_err(f'can not recognize data type: {df._attrs["content_type"]}, skip.')
        else:
            print(f'no data left after filtering, skip {name}: {df._attrs["content_type"]}')


_str2func = {
    'plot-mass': plot_mass,
}


def main(sys_args: List[str] = None):
    args_paser = argparse.ArgumentParser()
    subparsers = args_paser.add_subparsers(title='subcommands', dest='sub_command')
    
    plot_mass_args = subparsers.add_parser('plot-mass', description='plot mass spectrum')
    # set dir argument
    plot_mass_args.add_argument("-d", "--dir", type = str, default='.',
                                help="txt file directory, default is %(default)s")
    plot_mass_args.add_argument('-r', '--recursive', action='store_true', default=False,
                                help='search input directory recursively, default is %(default)s')
    # set output file argument
    plot_mass_args.add_argument("-o", "--output", type = str, default=None,
                                help="output file dir or path, default is %(default)s, means same as input dir")
    # set draw argument
    plot_mass_args.add_argument('--use-peaks-cache', action='store_true', default=False,
                                help='use peaks cache to speed up plot, default is %(default)s')
    plot_mass_args.add_argument('-m', '--mass', action='store_true', default=False,
                                help='draw Mass instead of Mass/charge which is Mass+z, default is %(default)s')
    plot_mass_args.add_argument('-min', '--min-height', type = int, default=0,
                                help='filter data with min height in peak list plot, default is %(default)s')
    plot_mass_args.add_argument('-minp', '--min-height-percent', type = float, default=10,
                                help='filter data with min height percent to hightest in mass/charge plot, default is %(default)s')
    plot_mass_args.add_argument('--min-peak-width', type = float, default=4,
                                help='filter peaks with min width in Mass/Charge plot, default is %(default)s')
    plot_mass_args.add_argument('-xlim', type = str, default=None,
                                help='set x-axis limit, input as "200,2000", default is %(default)s')
    plot_mass_args.add_argument('-col', '--color', type = str, default='black',
                                help='draw color, default is %(default)s')
    plot_mass_args.add_argument('-labels', '--labels', type = str, default='',
                                help='labels, input as 1000,Pep1;1050,Pep2, default is %(default)s')
    plot_mass_args.add_argument('--labels-eps', type = float, default=0.5,
                                help='eps to recognize labels, default is %(default)s')
    plot_mass_args.add_argument('-expand', '--expand', type = float, default=0.2,
                                help='how much the x-axis and y-axisto be expanded, default is %(default)s')
    plot_mass_args.add_argument('-lpos', '--legend-pos', type = str, default='upper center',
                                help='legend position, can be string as "upper center", or be float as 0.1,0.2, default is %(default)s')
    plot_mass_args.add_argument('-lposbbox1', '--legend-pos-bbox1', type = float, default=1.2,
                                help='legend position bbox 1 to anchor, default is %(default)s')
    plot_mass_args.add_argument('-lposbbox2', '--legend-pos-bbox2', type = float, default=1,
                                help='legend position bbox 2 to anchor, default is %(default)s')

    
    args = args_paser.parse_args(sys_args)
    
    if args.sub_command in _str2func:
        print(f'excuting command: {args.sub_command}')
        _str2func[args.sub_command](args)
    else:
        put_err(f'no such sub commmand: {args.sub_command}')

if __name__ == "__main__":
    # dev code, MUST COMMENT OUT BEFORE RELEASE
    # main(['plot-mass', '-d', r'data_tmp/scripts/mass'])
    
    main()