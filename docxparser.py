#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Modified copy of docx2txt

import argparse
import re
import xml.etree.ElementTree as ET
import zipfile
import os
import sys

import cv2
import numpy as np


nsmap = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

graphic_token = '^GRAPHICTOKEN$'


def process_args():
    parser = argparse.ArgumentParser(description='A pure python-based utility '
                                                 'to extract text and images '
                                                 'from docx files.')
    parser.add_argument("docx", help="path of the docx file")
    parser.add_argument('-i', '--img_dir', help='path of directory '
                                                'to extract images')

    args = parser.parse_args()

    if not os.path.exists(args.docx):
        print('File {} does not exist.'.format(args.docx))
        sys.exit(1)

    if args.img_dir is not None:
        if not os.path.exists(args.img_dir):
            try:
                os.makedirs(args.img_dir)
            except OSError:
                print("Unable to create img_dir {}".format(args.img_dir))
                sys.exit(1)
    return args


def qn(tag):
    """
    Stands for 'qualified name', a utility function to turn a namespace
    prefixed tag name into a Clark-notation qualified tag name for lxml. For
    example, ``qn('p:cSld')`` returns ``'{http://schemas.../main}cSld'``.
    Source: https://github.com/python-openxml/python-docx/
    """
    prefix, tagroot = tag.split(':')
    uri = nsmap[prefix]
    return '{{{}}}{}'.format(uri, tagroot)


def xml2text(xml):
    """
    A string representing the textual content of this run, with content
    child elements like ``<w:tab/>`` translated to their Python
    equivalent.
    Adapted from: https://github.com/python-openxml/python-docx/
    """
    text = u''
    root = ET.fromstring(xml)
    for child in root.iter():
        tagroot = child.tag.split('}')[-1]
        if child.tag == qn('w:t'):
            t_text = child.text
            text += t_text if t_text is not None else ''
        elif child.tag == qn('w:tab'):
            text += '\t'
        elif child.tag == qn('w:br'):
            text += '{br}'
        elif child.tag == qn('w:cr'):
            text += '{cr}'
        elif child.tag in (qn('w:br'), qn('w:cr')):
            text += '\n'
        elif child.tag == qn("w:p"):
            text += '\n\n'
        elif tagroot == 'graphic':
            text += graphic_token
        elif 'grid' in tagroot.lower():
            text += '{'+tagroot+'}'
        else:
            ignore = {'document', 'body', 'pPr', 'jc', 'rPr', 'rFonts', 'b', 'bCs', 'docGrid', 'sz',
                      'szCs', 'r', 'color', 'pStyle', 'numPr', 'ilvl', 'numId', 'ind', 'tbl', 'tblPr', 'tblStyle',
                      'tblW', 'tblBorders', 'left', 'right', 'gridCol', 'tblLook', 'tr', 'trPr', 'tc', 'tcPr', 'tcW', 'i', 'iCs',
                      'tblInd'}  # ,'lang','noProof','drawing','inline','extent','effectExtent','docPr','cNvGraphicFramePr',
            #'graphicFrameLocks','graphic','graphicData','pic','nvPicPr','cNvPr','cNvPicPr','blipFill'}
            suffix = text[-20:]
            if tagroot not in ignore:
                #print(child.tag)
                log = ' keys:'+repr(child.keys())+' items:' + \
                    repr(child.items())+' attrib:'+repr(child.attrib)
                #text += '{'+tagroot+(' text:'+str(child.text) if child.text else '')+(' tail:'+str(child.tail) if child.tail else '')+log+'}'
    return text


def process(docx):
    # return (text:str,imgs:List[cv2::img])
    text = u''

    # unzip the docx in memory
    zipf = zipfile.ZipFile(docx)
    filelist = zipf.namelist()

    # get header text
    # there can be 3 header files in the zip
    header_xmls = 'word/header[0-9]*.xml'
    for fname in filelist:
        if re.match(header_xmls, fname):
            text += xml2text(zipf.read(fname))

    # get main text
    doc_xml = 'word/document.xml'
    text += xml2text(zipf.read(doc_xml))

    # get footer text
    # there can be 3 footer files in the zip
    footer_xmls = 'word/footer[0-9]*.xml'
    for fname in filelist:
        if re.match(footer_xmls, fname):
            text += xml2text(zipf.read(fname))

    imgList = []
    # extract images
    for fname in filelist:
        _, extension = os.path.splitext(fname)
        if extension in [".jpg", ".jpeg", ".png", ".bmp"]:
            binary = np.frombuffer(zipf.read(fname), np.uint8)
            img = cv2.imdecode(binary, cv2.IMREAD_ANYCOLOR)
            imgid = re.findall(r'word/media/image(\d+).png',fname)
            assert(len(imgid)==1)
            imgid=imgid[0]
            imgList.append((imgid, img))
    imgList = sorted(imgList,key=lambda x:x[0])
    imgList = [img for id,img in imgList]
    zipf.close()
    return (text.strip(), imgList)


if __name__ == '__main__':
    #args = process_args()
    #text = process(args.docx, args.img_dir)
    text = process('test.docx')
    with open('test.out', 'w', encoding='utf-8') as w:
        w.write(repr(text[0]))
    #sys.stdout.write(text.encode('utf-8'))
