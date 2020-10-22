# -*- coding: utf-8 -*-


def task9(text: str):
    try:
        r = int(text)
        if r > 0 and r % 2 == 0:
            return {'score': 5.0, 'log': '√'}
        else:
            return {'score': 0.0, 'log': '×'}
    except Exception as e:
        return {'score': 0.0, 'log': str(e)}


tasks = {
    '9': task9
}


def run(taskid: str, input: str, task: object):
    # main function of the spj module
    assert(taskid in tasks)
    func = tasks[taskid]
    result = func(input)
    assert('score' in result and 'log' in result)
    return result
