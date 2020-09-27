# coding:utf-8
import os
import socket
import re

from multiprocessing import Process

# 设置静态文件根目录
HTML_ROOT_DIR = "./log/"


def handle_client(client_socket):
    """
    处理客户端请求
    """
    # 获取客户端请求数据
    request_data = client_socket.recv(1024)
    print("request data:", request_data)
    request_lines = request_data.splitlines()
    # 解析请求报文
    request_start_line = request_lines[0]
    # 提取用户请求的文件名
    file_name = re.match(r"\w+ +(/[^ ]*) ", request_start_line.decode("utf-8")).group(1)
    print('filename:',file_name)
    if "/" == file_name:
        file_name = "/index.html"

    md5 = file_name[1:]
    if len(md5)!=32 or not md5.isalnum():
        response_start_line = "HTTP/1.1 404 Not Found\r\n"
        response_headers = "Server: My server\r\n"
        response_body = "The file is not found!"
    else:
        # 打开文件，读取内容
        try:
            file = open(os.path.join(HTML_ROOT_DIR,md5), "rb")
        except IOError:
            response_start_line = "HTTP/1.1 404 Not Found\r\n"
            response_headers = "Server: My server\r\n"
            response_body = "The file is not found!"
        else:
            file_data = file.read()
            file.close()

            # 构造响应数据
            response_start_line = "HTTP/1.1 200 OK\r\n"
            response_headers = "Computer Science Foundation Homework Server\r\n"
            response_body = '<html><head><meta http-equiv="content-type" content="txt/html; charset=utf-8" /><title>Homework</title></head><body><pre>'+file_data.decode("utf-8")+ '</pre></body></html>'

    response = response_start_line + response_headers + "\r\n" + response_body
    print("response data:", response)

    # 向客户端返回响应数据
    client_socket.send(bytes(response, "utf-8"))

    # 关闭客户端连接
    client_socket.close()


if __name__ == "__main__":
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("", 8083))
    server_socket.listen(128)

    while True:
        client_socket, client_address = server_socket.accept()
        print("[%s, %s]用户连接上了" % client_address)
        handle_client_process = Process(target=handle_client, args=(client_socket,))
        handle_client_process.start()
        client_socket.close()