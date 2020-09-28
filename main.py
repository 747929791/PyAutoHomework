# -*- coding: utf-8 -*-
import re
import os
import glob
import string
import argparse
import hashlib
import multiprocessing
from enum import Enum
from typing import List, Tuple, Dict

import xlrd
import xlwt

import docxparser
from match import match


def create_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print('create folder:', path)


def format_log(s, blank=2):
    """
    align '\t' of multiple rows
    blank: minimum space between two columns
    example:
      format_log('a\nb\tccc\td\neee\tf\tg') =
      '
        a
        b    ccc  d
        eee  f    g
      '
    """
    L = s.split('\n')
    while True:
        m = -1
        for s in L:
            if '\t' in s:
                m = max(m, s.index('\t'))
        if m == -1:
            return '\n'.join(L)
        else:
            for i in range(len(L)):
                s = L[i]
                if '\t' in s:
                    x = s.index('\t')
                    L[i] = s[:x]+' '*(blank+m-x)+s[x+1:]


class TaskType(Enum):
    match = 0
    mannal = 1


class Task:
    def __init__(self, args):
        assert(type(args) == list and all(type(s) == str for s in args))
        self.taskid = args[0]                       # 任务的唯一ID
        if len(args)==0:
            # see settings.json
            self.fromSettings()
        if len(args) >= 3:
            self.parseArgs(args[1:])
            self.answer = str(args[1])
            self.score = float(args[2])
        else:
            raise NotImplementedError
        assert(hasattr(self, 'taskid'))
        assert(hasattr(self, 'score') and type(self.score) == float)
        assert(hasattr(self, 'type'))

    def parseArgs(self,args):
        self.isregex = 'REGEX' in args          # 是否开启正则匹配模式
        self.issub = 'SUB' in args             # 是否是子问题（主问题满分自动跳过）
        self.ismannal = 'MANNAL' in args        # 是否手工阅卷
        self.isjump = 'JUMP' in args            # 是否是子问题（主问题满分自动跳过）
        if self.isjump:
            self.jumpTarget = args[1+args.index('JUMP')]

    def fromSettings(self):
        pass # TODO


def checkTaskList(tasks: List[Task]):
    taskD = dict()
    for task in tasks:
        taskD[task.taskid] = task
    assert(all(task.isjump == False or task.jumpTarget in taskD for task in tasks))


def parseAnswer(answer: str):
    """
    answer:       text of answer.docx
    return:       List[Task]
    """
    task_pattern = r'\$>:(.*?)<:\$'
    # List[Tuple[task_id,answer,score]]
    tasks = []
    for s in re.findall(task_pattern, answer):
        args = s.split('|')
        tasks.append(Task(args))
    checkTaskList(tasks)
    return tasks


def parse(user_file: str, answer: str):
    """
    user_file:    user's docx filepath
    answer:       text of answer.docx
    return:       List[Tuple[user_answer:str,List[cv2::imgs]]]
    """
    file = os.path.basename(user_file)
    suffix = os.path.splitext(file)[-1]  # .docx
    try:
        user_input, user_imgs = docxparser.process(user_file)
    except:
        log = 'Parse docx error. Your file: '+file
        score = 0.0
        return {'score': score, 'log': log}

    # find all task
    split_pattern = r'\$>:.*?<:\$'
    # parse user's answer
    template_str = ''
    task_address = []
    for s in re.split(split_pattern, answer):
        template_str += s
        task_address.append(len(template_str))
    pair = match(user_input, template_str)
    addr_mapping = dict()
    for now_addr in range(len(pair)):
        a, b = pair[now_addr]
        if b:
            addr_mapping[len(addr_mapping)] = now_addr
    addr_mapping[len(addr_mapping)] = len(pair)
    user_answer = []
    for i in task_address:
        L = pair[addr_mapping[i-1]+1:addr_mapping[i]]
        user_answer.append((''.join(a for a, b in L)).strip())
    user_answer = user_answer[:len(tasks)]


def scoring(user_file: str, answer: str):
    """
    user_file:    user's docx filepath
    answer:       text of answer.docx
    return:       Dict:{'score':float,'log':str}
    """
    file = os.path.basename(user_file)
    suffix = file.split('.')[-1]
    try:
        user_input, user_imgs = docxparser.process(user_file)
    except:
        log = 'Parse docx error. Your file: '+file
        score = 0.0
        return {'score': score, 'log': log}

    # find all task
    task_pattern = r'\$(.*?)\|(.*?)\|(.*?)\$'
    split_pattern = r'\$.*?\|.*?\|.*?\$'
    # List[Tuple[task_id,answer,score]]
    tasks = re.findall(task_pattern, answer)
    tasks = [(str(task_id), str(answer), float(score))
             for task_id, answer, score in tasks]
    # parse user's answer
    template_str = ''
    task_address = []
    for s in re.split(split_pattern, answer):
        template_str += s
        task_address.append(len(template_str))
    pair = match(user_input, template_str)
    addr_mapping = dict()
    for now_addr in range(len(pair)):
        a, b = pair[now_addr]
        if b:
            addr_mapping[len(addr_mapping)] = now_addr
    addr_mapping[len(addr_mapping)] = len(pair)
    user_answer = []
    for i in task_address:
        L = pair[addr_mapping[i-1]+1:addr_mapping[i]]
        user_answer.append((''.join(a for a, b in L)).strip())
    user_answer = user_answer[:len(tasks)]

    # now user_answer[i]:str <-> tasks[i]:Tuple[task_id,answerStr,score]
    sum_score = 0.0
    log = 'This report is generated by the automatic marking program\n'
    for uanswer, (task_id, answer, score) in zip(user_answer, tasks):
        if uanswer.lower() == answer.lower():
            sum_score += float(score)
            result_symbol = '√'+f'  +{score}'
        else:
            result_symbol = '×'
        #log += f'  Task:{task_id}\tAnswer:"{answer}"\tYour_Answer:"{uanswer}"\t{result_symbol}\n'
        log += f'  Task:{task_id}\tYour_Answer:"{uanswer}"\t{result_symbol}\n'
    log += f'Total Score: {sum_score}\n'
    log = format_log(log)
    print(file, sum_score)
    return {'score': sum_score, 'log': log}


if __name__ == "__main__":
    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--workdir', type=str,
                        required=True, help='working folder path.')
    args = parser.parse_args()
    # pre-work
    root = os.path.abspath(args.workdir)
    data_path = os.path.join(root, 'data')
    xls_path = os.path.join(root, 'template.xls')
    answer_path = os.path.join(root, 'answer.docx')
    result_path = os.path.join(root, 'result')
    assert(os.path.exists(root))
    assert(os.path.exists(data_path))
    assert(os.path.exists(xls_path))
    assert(os.path.exists(answer_path))
    answer, answer_imgs = docxparser.process(answer_path)
    user_files = glob.glob(os.path.join(data_path, '*.*'))
    workbook = xlrd.open_workbook(xls_path)
    assert(len(workbook.sheets()) == 1)
    print('answer.docx:', repr(answer[:100]) +
          ('' if len(answer) < 100 else '......'))
    print('Find', len(user_files), 'files in student folder.')
    D = dict()
    for s in user_files:
        suffix = s.split('.')[-1]
        D[suffix] = D.get(suffix, 0)+1
    D = sorted([(k, v) for k, v in D.items()], key=lambda x: -x[1])
    print('\n'.join([f'\t.{k}:{v}' for k, v in D]))
    studentID = [os.path.basename(s).split('_')[0] for s in user_files]
    hasIllegalFile = False
    for i in range(len(studentID)):
        if len(studentID[i]) != 10 or any(c not in string.digits for c in studentID[i]):
            print('Illegal file:', os.path.basename(user_files[i]))
            hasIllegalFile = True
    if hasIllegalFile:
        print('Has illegal file, mandatory termination.')
        quit()
    log_path = os.path.join(result_path, 'log')
    create_folder(result_path)
    create_folder(log_path)
    begin = input('Press Y to be continue: ')
    if begin.lower() == 'y':
        result = []  # Store the final result: [{'score':float,'log':str},...]
        # Step 1: Parse user document and get the content of each task
        print('Step 1: Sequence Alignment')
        with multiprocessing.Pool(16) as p:
            step1_result = p.starmap(parse, [(user_files[i], answer)
                                             for i in range(len(user_files))])

        # Step 2: Scoring
        for i in range(len(step1_result)):
            data = step1_result[i]
            if type(data) == dict and 'score' in data:
                # parse user.docx error, record directly.
                result.append(data)
            else:
                result.append(scoring(data))

        # write result to result.xls
        rsheet = workbook.sheet_by_index(0)
        wbk = xlwt.Workbook()
        wsheet = wbk.add_sheet(rsheet.name, cell_overwrite_ok=True)
        for i in range(rsheet.nrows):
            for j in range(rsheet.ncols):
                wsheet.write(i, j, rsheet.cell(i, j).value)
        for i in range(rsheet.nrows):
            id = rsheet.cell(i, 1).value
            if id in studentID:
                D = result[studentID.index(id)]
                wsheet.write(i, 4, D['score'])
                if len(D['log']) < 500:
                    wsheet.write(i, 5, D['log'])
                else:
                    # Since the log is usually very large, the log will be written to the file
                    m = hashlib.md5()
                    m.update(str.encode(D['log']))
                    log_name = m.hexdigest()
                    with open(os.path.join(log_path, log_name), 'wb') as w:
                        w.write(str.encode(D['log'], encoding='utf-8'))
                    wsheet.write(
                        i, 5, 'The scoring details are here: '+args.server+log_name)
        wbk.save(os.path.join(result_path, 'result.xls'))
