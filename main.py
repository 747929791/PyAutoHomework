# -*- coding: utf-8 -*-
import re
import os
import sys
import json
import glob
import string
import argparse
import hashlib
import pickle
import multiprocessing
from typing import List, Tuple, Dict
import unicodedata

import xlrd
import xlwt
import numpy as np
import cv2

import docxparser
from match import match


def wide_chars(s):
    return sum(unicodedata.east_asian_width(x) == 'W' for x in s)


def width(s):
    return len(s) + wide_chars(s)


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
                idx = s.index('\t')
                m = max(m, width(s[:idx]))
        if m == -1:
            return '\n'.join(L)
        else:
            for i in range(len(L)):
                s = L[i]
                if '\t' in s:
                    x = s.index('\t')
                    w = width(s[:x])
                    L[i] = s[:x]+' '*(blank+m-w)+s[x+1:]


def shorten_log(s: str, length=20):
    if len(s) > length:
        mid = length//2-1
        s = s[:mid]+'...'+s[-(length-mid-3):]
    return s


wrong_answer_statistics = []  # (userid,taskid,user_input)
score_statistics = []  # (userid,taskid,score)


class Task:
    def __init__(self, args: List[str], settings: Dict):
        assert(type(args) == list and all(type(s) == str for s in args))
        self.taskid = args[0]                       # 任务的唯一ID
        self.settings = settings
        if len(args) == 1:
            # see settings.json
            self.fromSettings(settings)
        elif len(args) >= 3:
            self.parseArgs(args[1:])
            self.answer = str(args[1])
            self.score = float(args[2])
        else:
            raise NotImplementedError
        assert(hasattr(self, 'taskid'))
        assert(hasattr(self, 'score') and type(self.score) == float)

    def parseArgs(self, args):
        self.isregex = 'REGEX' in args          # 是否开启正则匹配模式
        self.issub = 'SUB' in args              # 是否是子问题（主问题满分自动跳过）
        self.ismannal = 'MANNAL' in args        # 是否手工阅卷
        self.isnocomment = 'NOCOMMENT' in args  # 手工阅卷时是否需要写评语(出现在log里)
        self.isjump = 'JUMP' in args            # 是否是子问题（主问题满分自动跳过）
        self.islowercase = 'LOWERCASE' in args
        self.isprogram = 'PROGRAM' in args
        if self.isjump:
            self.jumpTarget = args[1+args.index('JUMP')]

    def fromSettings(self, settings):
        assert('tasks' in settings)
        assert(self.taskid in settings['tasks'])
        setting = settings['tasks'][self.taskid]
        self.score = float(setting['score'])
        self.answer = setting.get('answer', '')
        self.parseArgs(setting.get('args', []))

    def run(self, userfile: str, userid: str, result_path: str, text: str, imgs: List[np.ndarray], user_input: List, tasks: List) -> Tuple[Dict]:
        """
        return {'score':float,'log':str}
        """
        origin_text = text
        result = dict()
        self.userid = userid

        def gen_result_line(score: float, log: str = None):
            log_text = shorten_log(repr(origin_text))
            if score == self.score:
                result_symbol = '√'+f'  +{self.score}'
            elif score > 0:
                result_symbol = '×'+f'  +{score}'
            else:
                result_symbol = '×'
            ret = dict()
            ret['score'] = score
            ret['log'] = f'Task:{self.taskid}\tYour_Answer:{log_text}\t{result_symbol}'
            if log != None:
                assert(type(log) == str)
                ret['log'] += '\n    '.join(['']+log.split('\n'))
            return ret
        if self.ismannal:
            # 人工阅卷
            task_key = userid+'-'+self.taskid
            cache_path = os.path.join(result_path, 'mannal.json')
            cache = json.load(open(cache_path, 'r')) if os.path.exists(
                cache_path) else {}
            if task_key in cache:
                result = cache[task_key]
            else:
                print('-'*40+'\n'+userid +
                      f'\nTask:{self.taskid} ({self.score})\n')
                print(text)
                if len(imgs) > 0:
                    for i in range(len(imgs)):
                        cv2.imshow('img'+str(i), imgs[i])
                    cv2.waitKey(10)
                while True:
                    score = input(
                        'Input score (press "O" to open the docx file):')
                    if score.lower() == 'o':
                        command = self.settings.get(
                            'openFileCommand').replace('{path}', os.path.abspath(userfile))
                        os.system(command)
                        continue
                    if re.match(r'^\d+(\.\d+)?$', score):
                        score = float(score)
                        if score > self.score:
                            print('  Too much score!')
                        else:
                            break
                    else:
                        print('  Format error!')
                result = gen_result_line(score)
                if len(imgs) > 0:
                    cv2.destroyAllWindows()
                cache[task_key] = result
                json.dump(cache, open(cache_path, 'w'))
        else:
            # 自动阅卷
            if self.islowercase:
                text = text.lower()
            # 程序阅卷
            if self.isprogram:
                spj_result = spj.run(self.taskid, input=text, task=self)
                score = spj_result['score']
                log = spj_result.get('log', None) or None
                result = gen_result_line(score, log)
            else:
                # 匹配阅卷
                def match(answer, text):
                    if self.isregex:
                        return bool(re.match('^'+answer+'$', text))
                    else:
                        return answer == text

                def check(item, text):
                    # return score
                    if type(item) == str:
                        return self.score if match(item, text) else 0.0
                    elif type(item) == dict:
                        return item['score'] if match(item['answer'], text) else 0.0
                    elif type(item) == list:
                        for answer in item:
                            r = check(answer, text)
                            if r > 0.0:
                                return r
                        return 0.0
                    else:
                        raise NotImplementedError
                score = check(self.answer, text)
                result = gen_result_line(score)
        assert('score' in result and 'log' in result)
        if result['score'] < self.score:
            wrong_answer_statistics.append((userid, self.taskid, origin_text))
        score_statistics.append((userid, self.taskid, result['score']))
        if self.isjump and result['score'] < self.score:
            for i, task in enumerate(tasks):
                if task.taskid == self.jumpTarget:
                    print(result['log'], '. JUMP to : {{task.taskid}}.')
                    text, imgs = user_input[i]
                    return task.run(userfile, userid, result_path, text, imgs, user_input, tasks)
        return result

    def __str__(self):
        s = f'{self.taskid}:\t'
        s += 'MANNAL' if self.ismannal else 'AUTO'
        if self.isjump:
            s += ' JUMP:'+self.jumpTarget
        if self.islowercase:
            s += ' LOWERCASE'
        if self.isregex:
            s += ' REGEX'
        if self.issub:
            s += ' SUB'
        if self.isnocomment:
            s += ' NOCOMMENT'
        if self.isprogram:
            s += ' PROGRAM'
        s += '\tScore:'+str(self.score)
        s += '\tAnswer:'+str(self.answer)
        return s


def checkTaskList(tasks: List[Task]):
    taskD = dict()
    for task in tasks:
        taskD[task.taskid] = task
    assert(all(task.isjump == False or task.jumpTarget in taskD for task in tasks))


def parseAnswer(answer: str, settings: Dict):
    """
    answer:       text of answer.docx
    return:       List[Task]
    """
    task_pattern = r'\$:>(.*?)<:\$'
    # List[Tuple[task_id,answer,score]]
    tasks = []
    for s in re.findall(task_pattern, answer):
        args = s.split('|')
        tasks.append(Task(args, settings))
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
    split_pattern = r'\$:>.*?<:\$'
    # parse user's answer
    template_str = ''
    task_address = []
    for s in re.split(split_pattern, answer):
        template_str += s
        task_address.append(len(template_str))
    task_address.pop()
    L = user_input.split(docxparser.graphic_token)
    if len(L) != len(user_imgs)+1:
        print(f'Warning. {user_file} image number mismatch. imgs:' +
              str(len(user_imgs))+' tokens:'+str(len(L)-1)+'')
    user_input = ''
    for i in range(len(L)):
        user_input += L[i]
        if i < len(user_imgs):
            user_input += f'<docximg:{i}>'
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
        text = (''.join(a for a, b in L)).strip()
        imgs = [user_imgs[int(i)]
                for i in re.findall(r'<docximg:(\d+)>', text)]
        text = re.sub(r'<docximg:(\d+)>', '{img}', text)
        user_answer.append((text, imgs))
    print('step1:', user_file)
    return user_answer


def scoring(userfile: str, userid: str, result_path: str, user_input: Tuple[str, List[np.ndarray]], tasks: List[Task]):
    """
    return:       Dict:{'score':float,'log':str}
    """
    print('='*40)
    print('UserID:', userid)
    sum_score = 0.0
    log = os.path.basename(userfile)+'\n'
    log += 'This report is generated by the automatic marking program\n'
    for (text, imgs), task in zip(user_input, tasks):
        if not task.issub:
            result = task.run(userfile, userid, result_path, text,
                              imgs, user_input, tasks)
            log += '  '+result['log']+'\n'
            sum_score += result['score']
    log += f'Total Score: {sum_score}\n'
    log = format_log(log)
    print(userid, sum_score)
    print(log)
    return {'score': sum_score, 'log': log}


def load_spj(work_dir: str):
    # load special judge program
    path = os.path.join(work_dir, 'program/spj.py')
    if os.path.exists(path) and 'spj' not in sys.modules:
        import importlib.util
        spec = importlib.util.spec_from_file_location("spj", path)
        global spj
        spj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(spj)
        assert(callable(spj.run))


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
    settings_path = os.path.join(root, 'settings.json')
    assert(os.path.exists(root))
    assert(os.path.exists(data_path))
    assert(os.path.exists(xls_path))
    assert(os.path.exists(answer_path))
    assert(os.path.exists(settings_path))
    load_spj(root)
    answer, answer_imgs = docxparser.process(answer_path)
    settings = json.load(open(settings_path, 'r', encoding="utf-8"))
    tasks = parseAnswer(answer, settings)
    print(format_log('Tasks:\n'+'\n'.join('  '+str(t) for t in tasks)))
    user_files = glob.glob(os.path.join(data_path, '*.*'))
    workbook = xlrd.open_workbook(xls_path)
    assert(len(workbook.sheets()) == 1)
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
    begin = input('Press Y to be continue: ')
    if begin.lower() == 'y':
        create_folder(result_path)
        create_folder(log_path)
        result = []  # Store the final result: [{'score':float,'log':str},...]
        # Step 1: Parse user document and get the content of each task
        print('Step 1: Sequence Alignment')
        step1_cache = os.path.join(result_path, 'parse.cache')
        if os.path.exists(step1_cache):
            step1_result = pickle.load(open(step1_cache, 'rb'))
        else:
            with multiprocessing.Pool(16) as p:
                step1_result = p.starmap(parse, [(user_files[i], answer)
                                                 for i in range(len(user_files))])
            assert(all(len(r) == len(tasks) or (type(r) == dict and 'score' in r)
                       for r in step1_result))
            pickle.dump(step1_result, open(step1_cache, 'wb'))
        print('Step1 over,', len(step1_result), 'files are aligned.')

        # Step 2: Scoring
        for i in range(len(step1_result)):
            data = step1_result[i]
            if type(data) == dict and 'score' in data:
                # parse user.docx error, record directly.
                result.append(data)
            else:
                userid = os.path.splitext(os.path.basename(user_files[i]))[0]
                print('='*5, 'Scoring:', userid,
                      f'{i}/{len(step1_result)}', '='*5)
                result.append(
                    scoring(user_files[i], userid, result_path, data, tasks))

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
                # Since the log is usually very large, the log will be written to the file
                m = hashlib.md5()
                m.update(str.encode(D['log']))
                md5 = m.hexdigest()
                with open(os.path.join(log_path, md5), 'wb') as w:
                    w.write(str.encode(D['log'], encoding='utf-8'))
                wsheet.write(
                    i, 5, settings.get('longTermLog', '').replace('{md5}', md5))
        wbk.save(os.path.join(result_path, 'result.xls'))
        # statistics
        w = open(os.path.join(result_path, 'statistics.txt'), 'w')
        w.write('Average Score:'+str(sum(score for uid, tid,
                                         score in score_statistics)/len(user_files))+'\n')
        wrong_list = []
        for task in tasks:
            L = [(uid, text) for uid, tid,
                 text in wrong_answer_statistics if tid == task.taskid]
            D = dict()
            for uid, text in L:
                studentID = os.path.basename(uid).split('_')[0]
                if text not in D:
                    D[text] = []
                D[text].append(studentID)
            L = [(k, v) for k, v in D.items()]
            L = sorted(L, key=lambda x: -len(x[1]))
            wrong_list.append(L)
        w.write('Wrong Case:\n')
        for i in range(len(tasks)):
            if len(wrong_list[i]) > 0:
                w.write('  Task:'+str(tasks[i].taskid)+'\n')
                for text, userids in wrong_list[i]:
                    w.write(f"    {repr(text)}:\t"+str(len(userids))+'\n')
        w.write('Details Wrong Case:\n')
        w.write('Wrong Case:\n')
        for i in range(len(tasks)):
            if len(wrong_list[i]) > 0:
                w.write('  Task:'+str(tasks[i].taskid)+'\n')
                for text, userids in wrong_list[i]:
                    w.write(f"    {repr(text)}:\t"+str(userids)+'\n')
        w.close()
