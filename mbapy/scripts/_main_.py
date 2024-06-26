'''
Date: 2024-01-08 21:31:52
LastEditors: BHM-Bob 2262029386@qq.com
LastEditTime: 2024-04-21 18:45:32
FilePath: \BA_PY\mbapy\scripts\_main_.py
Description: 
'''
import importlib
import os
import sys

os.environ['MBAPY_FAST_LOAD'] = 'True'
os.environ['MBAPY_AUTO_IMPORT_TORCH'] = 'False'

from mbapy.base import get_storage_path
from mbapy.file import opts_file

scripts_info = opts_file(get_storage_path('mbapy-cli-scripts-list.json'), way = 'json')


def print_scripts_list():
    for idx, script in enumerate(scripts_info):
        print(f'scripts {idx:3d}: {script}')
        print(scripts_info[script]['brief'])
        print('-'*100)

def print_scripts_info():
    for idx, script in enumerate(scripts_info):
        print(f'scripts {idx:3d}: {script}')
        print(scripts_info[script]['brief'])
        print(scripts_info[script]['detailed'])
        print('-'*100)
        
def exec_scripts():
    import mbapy
    
    # NOTE: DO NOT use exec
    # check and exec scripts
    script = importlib.import_module(f'.{sys.argv[1]}', 'mbapy.scripts')
    script.main(sys.argv[2:])
    
def main():    
    if len(sys.argv) == 1:
        import mbapy
        print('mbapy python package command-line tools')
        print('mbapy version: ', mbapy.__version__, ', build: ', mbapy.__build__)
        print('mbapy author: ', mbapy.__author__, ', email: ', mbapy.__author_email__)
        print('mbapy url: ', mbapy.__url__, ', license: ', mbapy.__license__)
    elif len(sys.argv) == 2:
        if sys.argv[1] in ['-l', '--list']:
            print_scripts_list()
        elif sys.argv[1] in ['-i', '--info']:
            print_scripts_info()
        elif sys.argv[1] in ['-h', '--help']:
            help_info = """
            usage-1: mbapy-cli [-h] [-l | -i]
            options:
            -h, --help  show this help message and exit
            -l, --list  print scripts list
            -i, --info  print scripts info
            
            usage-2: mbapy-cli [sub-scripts-name] [args] [-h]
            options:
            sub-scripts-name  name of scripts in mbapy.scripts
            args  args for sub-scripts
            -h, --help  show this help message and exit
            """
            print(help_info)
        elif sys.argv[1] in scripts_info:
            # exec scripts only no arg
            exec_scripts()
    else:
        if sys.argv[1] in scripts_info:
            # exec scripts
            exec_scripts()
        else:
            print(f'mbapy-cli: unkown scripts: {sys.argv[1]} and args: ', end='')
            [print(f' {arg}', end='') for arg in sys.argv[1:]]
            print('\n, skip')
            
    # print a '\n' in the end
    print('')
            

if __name__ == '__main__':
    main()