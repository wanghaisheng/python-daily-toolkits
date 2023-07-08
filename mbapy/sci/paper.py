'''
Date: 2023-07-07 20:51:46
LastEditors: BHM-Bob 2262029386@qq.com
LastEditTime: 2023-07-09 00:24:57
FilePath: \BA_PY\mbapy\sci\paper.py
Description: 
'''
import os, re

import rispy
from scihub_cn.scihub import SciHub
import PyPDF2

if __name__ == '__main__':
    # dev mode
    from mbapy.base import put_err
    from mbapy.file import replace_invalid_path_chr, convert_pdf_to_txt
else:
    # release mode
    from ..base import put_err
    from ..file import replace_invalid_path_chr, convert_pdf_to_txt

scihub = SciHub()

def parse_ris(ris_path:str, fill_none_doi:str = None):
    if not os.path.isfile(ris_path):
        return put_err(f'{ris_path} does not exist.', None)
    with open('./data_tmp/savedrecs.ris', 'r', encoding='utf-8') as bibliography_file:
        ris = rispy.load(bibliography_file)
        if fill_none_doi is not None:
            for r in ris:
                if 'doi' not in r:
                    r['doi'] = fill_none_doi
        return ris
            
def download_by_scihub(doi: str, dir: str, file_full_name:str = None, use_title_as_name: bool = True, valid_path_chr:str = '_'):
    """
    Download a paper from Sci-Hub using its DOI.
    if file_full_name is None, use the paper's title as the file name, if not, use the paper's DOI as the file name.

    Args:
        doi (str): The DOI (Digital Object Identifier) of the paper.
        dir (str): The directory where the downloaded file will be saved.
        file_full_name (str, optional): The name of the downloaded file, include the file extension(.pdf). Defaults to None.
        use_title_as_name (bool, optional): Whether to use the paper's title as the file name. Defaults to True.
        valid_path_chr (str, optional): The character used to replace invalid characters in the file name. Defaults to '_'.

    Returns:
        dict or None: If successful, returns a dictionary containing information about the downloaded paper. If unsuccessful, returns None.
    """
    try:
        res, paper_info = scihub.fetch({'doi':doi})
    except:
        return put_err(f'Maybe DOI: {doi:s} does not exist. scihub fetch error', None)
    if file_full_name is not None:
        file_name = file_full_name
    else:
        file_name = (paper_info.title if use_title_as_name else doi) + '.pdf'
    file_name = replace_invalid_path_chr(file_name, valid_path_chr)

    if type(res) == dict and 'err' in res:        
        return put_err(res['err'])
    if not res:
        return None
    scihub._save(res.content, os.path.join(dir, file_name))
    return paper_info
    
def _parse_section_bookmarks(*bookmarks):
    """
        Parse a list of bookmarks and return a flattened list of all bookmarks.

        Args:
            *bookmarks (List[Any]): A variable number of bookmark lists.

        Returns:
            List[Any]: A flattened list of all bookmarks.
    """
    ret = []
    for bookmark in bookmarks:
        if isinstance(bookmark, list):
            ret = ret + _parse_section_bookmarks(*bookmark)
        else:
            ret.append(bookmark)
    return ret

def has_sci_bookmarks(pdf_path:str = None, pdf_obj = None, section_names:list[str]=[]):
    """
    Checks if a PDF document has bookmarks for scientific sections.

    Parameters:
        pdf_obj: The PDF object(Being opened!). Defaults to None.
        pdf_path (str): The path to the PDF document. Defaults to None.
        section_names (list[str]): A list of section names to check for bookmarks. Defaults to an empty list.

    Returns:
        list[str] or bool: list of section names if the PDF has bookmarks, False otherwise.
    """
    def _get_outlines(pdf_obj):
        if hasattr(pdf_obj, 'outline') and pdf_obj.outline:
            return pdf_obj.outline
        else:
            return []
    # check parameters
    if pdf_path is None and pdf_obj is None:
        return put_err('pdf_path or pdf_obj is None', None)
    # get outlines
    if pdf_obj is not None:
        outlines = _get_outlines(pdf_obj)
    elif pdf_path is not None and os.path.isfile(pdf_path):
        with open(pdf_path, 'rb') as file:
            pdf_obj = PyPDF2.PdfReader(file)
            outlines = _get_outlines(pdf_obj)
    # check for valid bookmarks, get flat section list
    if len(outlines) == 0:
        return False
    else:
        outlines = _parse_section_bookmarks(*outlines)
    # set default section names
    if not section_names:
        section_names = ['Abstract', 'Introduction', 'Materials', 'Methods',
                         'Results', 'Discussion', 'References']
    # check whether any of the section names is in the outlines
    for outline in outlines:
        for section_name in section_names:
            pattern = r'\b{}\b'.format(re.escape(section_name))
            if re.search(pattern, outline.title, re.IGNORECASE):
                return outlines
    return False

def get_sci_bookmarks_from_pdf(pdf_path:str = None, pdf_obj = None, section_names:list[str]=[]):
    # check parameters
    if pdf_path is None and pdf_obj is None:
        return put_err('pdf_path or pdf_obj is None', None)
    # set default section names
    if not section_names:
        section_names = ['Abstract', 'Introduction', 'Materials', 'Methods',
                         'Results', 'Discussion', 'References']
    # get pdf full txt
    if pdf_obj is not None:
        # extract text from pdf obj
        content = '\n'.join([page.extract_text() for page in pdf_obj.pages])
    elif pdf_path is not None and os.path.isfile(pdf_path):
        # get text from pdf file
        content = convert_pdf_to_txt(pdf_path)
    # get section titles
    ret = []
    for section in section_names:
        if content.find(section) != -1:
            ret.append(section)
    return ret
    
def get_section_bookmarks(pdf_path:str = None, pdf_obj = None):
    """
    Returns a list of titles of bookmark sections in a PDF.

    Parameters:
    - pdf_path (str): The path to the PDF file. Defaults to None.
    - pdf_obj: The PDF object(Being opened!). Defaults to None.

    Returns:
    - list: A list of titles of bookmark sections in the PDF. Returns None if there are no bookmark sections or if the PDF file does not exist.
    """
    def worker(pdf_obj):
        sections = has_sci_bookmarks(None, pdf_obj)
        if not sections:
            # do not has inner bookmarks, just parse from text
            return get_sci_bookmarks_from_pdf(None, pdf_obj)
        # has inner bookmarks, parse from outline
        return [section.title for section in sections]
    # check path
    if not os.path.isfile(pdf_path):
        return put_err(f'{pdf_path:s} does not exist', None)
    # get section titles
    if pdf_obj is None:
        with open(pdf_path, 'rb') as file:
            pdf_obj = PyPDF2.PdfReader(file)
            return worker(pdf_obj)
    else:
        return worker(pdf_obj)
    
def get_english_part_of_bookmarks(bookmarks:list[str]):
    if bookmarks is None:
        return put_err('bookmarks is None', None)
    english_bookmarks = []
    for bookmark in bookmarks:
        match = re.search(r'[a-zA-Z]+[a-zA-Z\s\S]+', bookmark)
        english_bookmarks.append(match.group(0).strip() if match else bookmark)
    return english_bookmarks

def get_section_from_paper(paper:str, key:str,
                           keys:list[str] = ['Title', 'Authors', 'Abstract', 'Keywords',
                                             'Introduction', 'Materials & Methods',
                                             'Results', 'Discussion', 'References']):
    """
    extract section of a science paper by key
    
    Parameters:
        paper (str): a science paper.
        key (str): one of the sections in the paper.
            can be 'Title', 'Authors', 'Abstract', 'Keywords', 'Introduction', 'Materials & Methods', 'Results', 'Discussion', 'References'
        keys (list[str], optional): a list of keys to extract. Defaults to ['Title', 'Authors', 'Abstract', 'Keywords', 'Introduction', 'Materials & Methods', 'Results', 'Discussion', 'References'].
    """
    # 构建正则表达式模式，使用re.IGNORECASE标志进行不区分大小写的匹配
    if paper is None or key is None:
        return put_err('paper or key is None', None)
    # TODO : sometimes may fail
    pattern = r'\b{}\b.*?(?=\b{})'.format(key, keys[keys.index(key)+1] if key != keys[-1] else '$')
    # 使用正则表达式匹配内容
    match = re.search(pattern, paper, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0)
    else:
        return put_err(f'key "{key}" not found in paper', '')

def format_paper_from_txt(content:str,
                          struct:list[str] = ['Title', 'Authors', 'Abstract', 'Keywords',
                                              'Introduction', 'Materials & Methods',
                                              'Results', 'Discussion', 'References']):
    content = content.replace('\n', '')
    struction = {}
    for key in struct:
        struction[key] = ''

if __name__ == '__main__':
    # dev code
    from mbapy.base import rand_choose
    from mbapy.file import convert_pdf_to_txt
    
    # RIS parse
    ris = parse_ris('./data_tmp/savedrecs.ris', '')
    print(f'sum papers: {len(ris)}')
    ris = rand_choose(ris)
    print(f'title: {ris["title"]}, doi: {ris["doi"]}')
    
    # download
    download_by_scihub(ris["doi"], './data_tmp/', file_full_name = f'{ris["title"]:s}.pdf')
    
    # extract section
    pdf_path = replace_invalid_path_chr("./data_tmp/{:s}.pdf".format(ris["title"]))
    sections = get_english_part_of_bookmarks(get_section_bookmarks(pdf_path))
    paper, section = convert_pdf_to_txt(pdf_path), rand_choose(sections, 0)
    print(sections, section, get_section_from_paper(paper, section, keys=sections))
