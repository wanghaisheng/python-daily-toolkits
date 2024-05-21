import argparse
import os
from collections import OrderedDict
from functools import partial
from pathlib import Path
from typing import Dict, List, Union, Tuple, Callable

import scipy
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.environ['MBAPY_AUTO_IMPORT_TORCH'] = 'False'
os.environ['MBAPY_FAST_LOAD'] = 'True'
from mbapy.base import put_err
from mbapy.plot import get_palette, save_show
from mbapy.file import decode_bits_to_str, get_paths_with_extension, get_valid_file_path
from mbapy.sci_instrument.hplc.waters import WatersData
from mbapy.sci_instrument.hplc._utils import plot_hplc as _plot_hplc, process_file_labels, process_peak_labels
from mbapy.scripts._script_utils_ import clean_path, Command, excute_command


class plot_hplc(Command):
    def __init__(self, args: argparse.Namespace, printf=print) -> None:
        super().__init__(args, printf)
        self.dfs = {}
        self.SUPPORT_SYSTEMS = {'waters'}
        self.name2model = {'waters': WatersData}
        
    @staticmethod
    def make_args(args: argparse.ArgumentParser):
        args.add_argument('-i', '--input', type = str, default='.',
                          help="data file directory, default is %(default)s.")
        args.add_argument('-s', '--system', type = str, default='waters',
                          help="HPLC system. Default is %(default)s, only accept arw file exported by Waters.")
        args.add_argument('-r', '--recursive', action='store_true', default=False,
                          help='search input directory recursively, default is %(default)s.')
        args.add_argument('-merge', action='store_true', default=False,
                          help='merge multi files into one plot, default is %(default)s.')
        args.add_argument('-o', '--output', type = str, default=None,
                          help="output file dir or path. Default is %(default)s, means same as input dir")
        # set draw argument
        args.add_argument('--min-peak-width', type = float, default=4,
                          help='filter peaks with min width in hplc/Charge plot, default is %(default)s.')
        args.add_argument('-xlim', type = str, default='0,None',
                          help='set x-axis limit, input as "0,15", default is %(default)s.')
        args.add_argument('-flabels', '--file-labels', type = str, default='',
                          help='labels, input as 228,blue;304,red, default is %(default)s.')
        args.add_argument('-lpos', '--file-legend-pos', type = str, default='upper center',
                          help='legend position, can be string as "upper center", default is %(default)s')
        args.add_argument('-lposbbox', '--file-legend-bbox', type = str, default='1.3,0.5',
                          help='legend position bbox 1 to anchor, default is %(default)s')
        args.add_argument('-dpi', type = int, default=600,
                          help='set dpi of output image, default is %(default)s.')
        args.add_argument('-show', action='store_true', default=False,
                          help='show plot window, default is %(default)s.')
        return args

    def load_dfs_from_data_file(self):
        if self.args.system == 'waters':
            paths = get_paths_with_extension(self.args.input, ['arw'], recursive=self.args.recursive)
            dfs = [self.data_model(path) for path in paths]
            dfs = {data.get_tag():data for data in dfs}
        return dfs

    def process_args(self):
        assert self.args.system in {'waters'}, f'not support HPLC system: {self.args.system}'
        # process self.args
        self.args.input = clean_path(self.args.input)
        self.args.output = clean_path(self.args.output) if self.args.output else self.args.input
        if not os.path.isdir(self.args.output):
            print(f'given output {self.args.output} is a file, change it to parent dir')
            self.args.output = self.args.output.parent
        self.args.file_legend_bbox = eval(f'({self.args.file_legend_bbox})') # NOTE: can be invoked
        self.data_model = self.name2model[self.args.system]
        # file labels
        self.args.file_labels = process_file_labels(self.args.file_labels)

    def main_process(self):
        def _save_fig(root, name, dpi, show, bbox_extra_artists):
            path = get_valid_file_path(os.path.join(root, f"{name.replace('/', '-')}.png"))
            print(f'saving plot to {path}')
            save_show(path, dpi, show=show, bbox_extra_artists = bbox_extra_artists)
        # load origin dfs from data file
        self.dfs = self.load_dfs_from_data_file()
        if not self.dfs:
            raise FileNotFoundError(f'can not find data files in {self.args.input}')
        # show data general info and output peak list DataFrame
        if self.args.merge:
            if self.args.system == 'waters':
                dfs = list(self.dfs.values())
                ax, legends = _plot_hplc(dfs, **self.args.__dict__)
                _save_fig(self.args.output, "merge.png", self.args.dpi, self.args.show, legends)
        else:
            for tag, data in self.dfs.items():
                print(f'plotting data for {tag}')
                data.save_processed_data()
                ax, legends = _plot_hplc(data, **self.args.__dict__)
                _save_fig(self.args.output, f"{tag.replace('/', '-')}.png", self.args.dpi, self.args.show, legends)


class explore_hplc(plot_hplc):
    from nicegui import ui
    def __init__(self, args: argparse.Namespace, printf=print) -> None:
        super().__init__(args, printf)
        self.now_name = ''
        self.fig = None
        self.dfs = OrderedDict()
        self.dfs_checkin = {}
        self.dfs_refinment_x = {}
        self.dfs_refinment_y = {}
        self.stored_dfs = {}
        self._expansion = []
        self._bbox_extra_artists = None
        self.is_bind_lim = False
        self.xlim_number_min = None
        self.xlim_number_max = None
        self.xlim_search_number_min = None
        self.xlim_search_number_max = None
        
    @staticmethod
    def make_args(args: argparse.ArgumentParser):
        args.add_argument('-i', '--input', type = str, default='.',
                          help="data file directory, default is %(default)s.")
        args.add_argument('-s', '--system', type = str, default='waters',
                          help="HPLC system. Default is %(default)s, only accept arw file exported by Waters.")
        args.add_argument('-url', '--url', type = str, default='localhost',
                          help="url to connect to, default is %(default)s.")
        args.add_argument('-port', '--port', type = int, default=8011,
                          help="port to connect to, default is %(default)s.")
        return args
    
    def process_args(self):
        assert self.args.system in {'waters'}, f'not support HPLC system: {self.args.system}'
        self.args.input = clean_path(self.args.input)
        self.data_model = self.name2model[self.args.system]
        
    async def load_data(self, event):
        from nicegui import ui
        for name, content in zip(event.names, event.contents):
            if self.args.system == 'waters':
                if name.endswith('.arw'):
                    self.stored_dfs[name] = self.data_model()
                    self.stored_dfs[name].load_raw_data_from_bytes(content)
                else:
                    ui.notify(f'{name} is not a arw file, skip')
                    continue
            ui.notify(f'loaded {name}')
        self.make_tabs.refresh()
        
    def _push_df_from_tabs(self, event):
        if event.value:
            self.dfs[event.sender.text] = self.stored_dfs[event.sender.text]
        else:
            self.dfs.pop(event.sender.text, None)
        self._ui_refinment_numbers.refresh()
        
    @ui.refreshable
    def make_tabs(self):
        from nicegui import ui
        with ui.card().classes('h-full'):
            for name in sorted(self.stored_dfs):
                if name not in self.dfs_checkin:
                    self.dfs_checkin[name] = False
                ui.checkbox(text = name, value = self.dfs_checkin[name],
                            on_change=self._push_df_from_tabs).bind_value_to(self.dfs_checkin, name)
                
    @ui.refreshable
    def make_fig(self):
        from nicegui import ui
        plt.close(self.fig)
        with ui.pyplot(figsize=self.args.fig_size, close=False) as fig:
            self.fig = fig.fig
            if self.dfs:
                ax, self._bbox_extra_artists = _plot_hplc(list(self.dfs.values()), ax = self.fig.gca(),
                                                          dfs_refinment_x=self.dfs_refinment_x,
                                                          dfs_refinment_y=self.dfs_refinment_y,
                                                          file_label_fn=partial(process_file_labels, file_col_mode=self.args.file_col_mode),
                                                          peak_label_fn=partial(process_peak_labels, peak_col_mode=self.args.peak_col_mode),
                                                          **self.args.__dict__)
                ax.tick_params(axis='both', which='major', labelsize=self.args.axis_ticks_fontsize)
                ax.set_xlabel(self.args.xlabel, fontsize=self.args.axis_label_fontsize)
                ax.set_ylabel(self.args.ylabel, fontsize=self.args.axis_label_fontsize)
                ax.set_xlim(left=self.args.xlim[0], right=self.args.xlim[1])
                ax.set_ylim(bottom=self.args.ylim[0], top=self.args.ylim[1])
                plt.tight_layout()
            
    def _ui_only_one_expansion(self, e):
        if e.value:
            for expansion in self._expansion:
                if expansion != e.sender:
                    expansion.set_value(False)
                    
    @ui.refreshable
    def _ui_refinment_numbers(self):
        from nicegui import ui
        # update dfs_refinment
        self.dfs_refinment_x = {n: (0 if n not in self.dfs_refinment_x else self.dfs_refinment_x[n]) for n in self.dfs}
        self.dfs_refinment_y = {n: (0 if n not in self.dfs_refinment_y else self.dfs_refinment_y[n]) for n in self.dfs}
        # update refinment numbers GUI
        for (n, x), (_, y) in zip(self.dfs_refinment_x.items(), self.dfs_refinment_y.items()):
            ui.label(n).tooltip(n)
            with ui.row():
                ui.number(label='x', value=x, step=0.01, format='%.4f').bind_value_to(self.dfs_refinment_x, n).classes('w-2/5')
                ui.number(label='y', value=y, step=0.01, format='%.4f').bind_value_to(self.dfs_refinment_y, n).classes('w-2/5')
            
    def _ui_bind_xlim_onchange(self, e):
        if self.is_bind_lim:
            if e.sender == self.xlim_number_min:
                self.xlim_search_number_min.set_value(e.value)
            elif e.sender == self.xlim_search_number_min:
                self.xlim_number_min.set_value(e.value)
            elif e.sender == self.xlim_number_max:
                self.xlim_search_number_max.set_value(e.value)
            elif e.sender == self.xlim_search_number_max:
                self.xlim_number_max.set_value(e.value)
                    
    def save_fig(self):
        from nicegui import ui
        path = os.path.join('./', self.args.file_name)
        ui.notify(f'saving figure to {path}')
        save_show(path, dpi = self.args.dpi, show = False, bbox_extra_artists = self._bbox_extra_artists)
        
    @staticmethod
    def _apply_v2list(v, lst, idx):
        lst[idx] = v
    
    def main_process(self):
        from nicegui import app, ui
        from mbapy.game import BaseInfo
        # make global settings
        # do not support xlim because it makes confusion with peak searching
        self.args = BaseInfo(file_labels = '', peak_labels = '', merge = False, recursive = False,
                             min_peak_width = 0.1, min_height = 0.01, start_search_time = 0, end_search_time = None,
                             show_tag_text = True, labels_eps = 0.1,
                             file_legend_pos = 'upper right', file_legend_bbox = [1.3, 0.75],
                             peak_legend_pos = 'upper right', peak_legend_bbox = [1.3, 1],
                             title = '', xlabel = 'Time (min)', ylabel = 'Absorbance (AU)',
                             axis_ticks_fontsize = 20,axis_label_fontsize = 25, 
                             file_col_mode = 'hls', peak_col_mode = 'Set1',
                             show_tag_legend = True, show_file_legend = True,
                             tag_fontsize = 15, tag_offset = [0.05,0.05], marker_size = 80, marker_offset = [0,0.05],
                             title_fontsize = 25, legend_fontsize = 15, line_width = 2,
                             xlim = [0, None], ylim = [None, None],
                             fig_size = [10, 8], fig = None, dpi = 600, file_name = '',
                             **self.args.__dict__)
        # load dfs from input dir
        for name, dfs in self.load_dfs_from_data_file().items():
            self.stored_dfs[name] = dfs
        # GUI
        with ui.header(elevated=True).style('background-color: #3874c8'):
            ui.label('mbapy-cli HPLC | HPLC Data Explorer').classes('text-h4')
            ui.space()
            ui.checkbox('bind lim', value=self.is_bind_lim).bind_value_to(self, 'is_bind_lim').tooltip('bind value of search-lim and plot-lim')
            ui.checkbox('merge', value=self.args.merge).bind_value_to(self.args,'merge').bind_value_from(self, 'dfs', lambda dfs: len(dfs) > 1)
            ui.button('Plot', on_click=self.make_fig.refresh, icon='refresh').props('no-caps')
            ui.button('Save', on_click=self.save_fig, icon='save').props('no-caps')
            ui.button('Show', on_click=plt.show, icon='open_in_new').props('no-caps')
            ui.button('Exit', on_click=app.shutdown, icon='power')
        with ui.splitter(value = 20).classes('w-full h-full h-56') as splitter:
            with splitter.before:
                ui.upload(label = 'Load File', multiple=True, auto_upload=True, on_multi_upload=self.load_data).props('no-caps')
                tabs = self.make_tabs()
            with splitter.after:
                with ui.row().classes('w-full h-full'):
                    with ui.column().classes('h-full'):
                        # data filtering configs
                        with ui.expansion('Data Filtering', icon='filter_alt', value=True, on_value_change=self._ui_only_one_expansion) as expansion1:
                            self._expansion.append(expansion1)
                            ui.select(list(self.SUPPORT_SYSTEMS), label='HPLC System', value=self.args.system).bind_value_to(self.args,'system').bind_value_to(self, 'data_model', lambda s: self.name2model[s]).classes('w-full')
                            ui.number('min peak width', value=self.args.min_peak_width, min = 0, step = 0.10).bind_value_to(self.args,'min_peak_width').tooltip('in minutes')
                            ui.number('min height', value=self.args.min_height, min = 0, step=0.01).bind_value_to(self.args, 'min_height')
                            ui.number('labels eps', value=self.args.labels_eps, min=0, format='%.2f').bind_value_to(self.args, 'labels_eps')
                            self.xlim_search_number_min = ui.number('start search time', value=self.args.start_search_time, min = 0, on_change=self._ui_bind_xlim_onchange).bind_value_to(self.args,'start_search_time').tooltip('in minutes')
                            self.xlim_search_number_max = ui.number('end search time', value=self.args.end_search_time, min = 0, on_change=self._ui_bind_xlim_onchange).bind_value_to(self.args, 'end_search_time').tooltip('in minutes')
                        # data refinment configs
                        with ui.expansion('Data Refinment', icon='auto_fix_high', on_value_change=self._ui_only_one_expansion) as expansion2:
                            self._expansion.append(expansion2)
                            self._ui_refinment_numbers()
                        # configs for fontsize
                        with ui.expansion('Configs for Fontsize', icon='format_size', on_value_change=self._ui_only_one_expansion) as expansion3:
                            self._expansion.append(expansion3)
                            with ui.row().classes('w-full'):
                                ui.input('title', value=self.args.title).bind_value_to(self.args, 'title')
                                ui.number('title fontsize', value=self.args.title_fontsize, min=0, step=0.5, format='%.1f').bind_value_to(self.args, 'title_fontsize')
                            with ui.row().classes('w-full'):
                                ui.input('xlabel', value=self.args.xlabel).bind_value_to(self.args, 'xlabel')
                                ui.input('ylabel', value=self.args.ylabel).bind_value_to(self.args, 'ylabel')
                            with ui.row().classes('w-full'):
                                ui.number('axis label fontsize', value=self.args.axis_label_fontsize, min=0, step=0.5, format='%.1f').bind_value_to(self.args, 'axis_label_fontsize')
                                ui.number('axis ticks fontsize', value=self.args.axis_ticks_fontsize, min=0, step=0.5, format='%.1f').bind_value_to(self.args, 'axis_ticks_fontsize')
                            ui.checkbox('show tag text', value=self.args.show_tag_text).bind_value_to(self.args,'show_tag_text')
                            with ui.row().classes('w-full'):
                                ui.number('tag fontsize', value=self.args.tag_fontsize, min=0, step=0.5, format='%.1f').bind_value_to(self.args, 'tag_fontsize')
                                ui.number('marker size', value=self.args.marker_size, min=0, step=5, format='%.1f').bind_value_to(self.args,'marker_size')
                            with ui.row().classes('w-full'):
                                ui.number('tag offset x', value=self.args.tag_offset[0], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.tag_offset, 0))
                                ui.number('marker offset x', value=self.args.marker_offset[0], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.marker_offset, 0))
                            with ui.row().classes('w-full'):
                                ui.number('tag offset y', value=self.args.tag_offset[1], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.tag_offset, 1))
                                ui.number('marker offset y', value=self.args.marker_offset[1], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.marker_offset, 1))
                            ui.number('line width', value=self.args.line_width, min=0, step=0.5, format='%.1f').bind_value_to(self.args, 'line_width')
                        # configs for legend
                        with ui.expansion('Configs for Legend', icon='more', on_value_change=self._ui_only_one_expansion) as expansion4:
                            self._expansion.append(expansion4)
                            with ui.row().classes('w-full'):
                                ui.checkbox('show file legend', value=self.args.show_file_legend).bind_value_to(self.args,'show_file_legend')
                                ui.checkbox('show peak legend', value=self.args.show_tag_legend).bind_value_to(self.args,'show_tag_legend')
                            with ui.row().classes('w-full'):
                                ui.textarea('file labels').bind_value_to(self.args, 'file_labels').props('clearable').tooltip('input as label1,color1;label2,color2')
                                ui.textarea('peak labels').bind_value_to(self.args, 'peak_labels').props('clearable').tooltip('input as peaktime,label,color;...')
                            with ui.row().classes('w-full'):
                                col_mode_option = ['hls', 'Set1', 'Set2', 'Set3', 'Dark2', 'Paired', 'Pastel1', 'Pastel2', 'tab10', 'tab20', 'tab20b', 'tab20c']
                                ui.select(label='file col mode', options = col_mode_option, value=self.args.file_col_mode).bind_value_to(self.args, 'file_col_mode').classes('w-2/5')
                                ui.select(label='peak col mode', options = col_mode_option, value=self.args.peak_col_mode).bind_value_to(self.args, 'peak_col_mode').classes('w-2/5')
                            ui.number('legend fontsize', value=self.args.legend_fontsize, min=0, step=0.5, format='%.2f').bind_value_to(self.args, 'legend_fontsize')
                            with ui.row().classes('w-full'):
                                all_loc = ['best', 'upper right', 'upper left', 'lower left', 'lower right', 'right', 'center left', 'center right', 'lower center', 'upper center', 'center']
                                ui.select(label='file legend loc', options=all_loc, value=self.args.file_legend_pos).bind_value_to(self.args, 'file_legend_pos').classes('w-2/5')
                                ui.select(label='peak legend loc', options=all_loc, value=self.args.peak_legend_pos).bind_value_to(self.args, 'peak_legend_pos').classes('w-2/5')
                            with ui.row().classes('w-full'):
                                ui.number('file bbox1', value=self.args.file_legend_bbox[0], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.file_legend_bbox, 0)).classes('w-2/5')
                                ui.number('peak bbox1', value=self.args.peak_legend_bbox[0], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.peak_legend_bbox, 0)).classes('w-2/5')
                            with ui.row().classes('w-full'):
                                ui.number('file bbox2', value=self.args.file_legend_bbox[1], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.file_legend_bbox, 1)).classes('w-2/5')
                                ui.number('peak bbox2', value=self.args.peak_legend_bbox[1], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.peak_legend_bbox, 1)).classes('w-2/5')
                        # configs for saving
                        with ui.expansion('Configs for Saving', icon='save', on_value_change=self._ui_only_one_expansion) as expansion5:
                            self._expansion.append(expansion5)
                            with ui.row().classes('w-full'):
                                self.xlim_number_min = ui.number('xlim-min', value=self.args.xlim[0], step=0.1, format='%.2f', on_change=self._ui_bind_xlim_onchange).on_value_change(lambda e: self._apply_v2list(e.value, self.args.xlim, 0))
                                self.xlim_number_max = ui.number('xlim-max', value=self.args.xlim[1], step=0.1, format='%.2f', on_change=self._ui_bind_xlim_onchange).on_value_change(lambda e: self._apply_v2list(e.value, self.args.xlim, 1))
                            with ui.row().classes('w-full'):
                                ui.number('ylim-min', value=self.args.ylim[0], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.ylim, 0))
                                ui.number('ylim-max', value=self.args.ylim[1], step=0.01, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.ylim, 1))
                            ui.number('figure width', value=self.args.fig_size[0], min=1, step=0.5, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.fig_size, 0)).classes('w-2/5')
                            ui.number('figure height', value=self.args.fig_size[1], min=1, step=0.5, format='%.2f').on_value_change(lambda e: self._apply_v2list(e.value, self.args.fig_size, 1)).classes('w-2/5')
                            dpi_input = ui.number('DPI', value=self.args.dpi, min=100, step=100, format='%d').bind_value_to(self.args, 'dpi')
                            ui.select(options=[100, 300, 600], value=dpi_input.value, label='Quick Set DPI').bind_value_to(dpi_input).classes('w-full')
                            ui.input('figure file name', value=self.args.file_name).bind_value_to(self.args, 'file_name')
                    with ui.card():
                        ui.label(f'selected {len(self.dfs)} data files').classes('text-h6').bind_text_from(self, 'dfs', lambda dfs: f'selected {len(dfs)} data files')
                        self.make_fig()
        ## run GUI
        ui.run(host = self.args.url, port = self.args.port, title = 'HPLC Data Explorer', reload=False)
        

_str2func = {
    'plot-hplc': plot_hplc,
    'explore-hplc': explore_hplc
}


def main(sys_args: List[str] = None):
    args_paser = argparse.ArgumentParser()
    subparsers = args_paser.add_subparsers(title='subcommands', dest='sub_command')
    plot_hplc_args = plot_hplc.make_args(subparsers.add_parser('plot-hplc', description='plot hplc spectrum'))
    explore_hplc_args = explore_hplc.make_args(subparsers.add_parser('explore-hplc', description='explore hplc spectrum data'))

    excute_command(args_paser, sys_args, _str2func)

if __name__ == "__main__":
    # dev code, MUST COMMENT OUT BEFORE RELEASE
    main('explore-hplc -i data_tmp/scripts/hplc'.split())
    
    main()