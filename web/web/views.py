import os

from django.http import HttpResponse, Http404

LOG_DIR = '../log'


def md5log(request, md5):
    try:
        file = open(os.path.join(LOG_DIR, md5), "rb")
    except IOError:
        raise Http404("Log not found")
    else:
        file_data = file.read()
        file.close()
        response_body = '<html><head><meta http-equiv="content-type" content="txt/html; charset=utf-8" /><title>Homework</title></head><body><pre>' + \
            file_data.decode("utf-8") + '</pre></body></html>'
        return HttpResponse(response_body)
