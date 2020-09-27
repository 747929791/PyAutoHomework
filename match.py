# -*- coding: utf-8 -*-
import re
import time

from numba import jit
import numpy as np

@jit(nopython=True)
def DP(A, B):
    w = [3, -1]
    a, b = (-2, -1)
    n, m = len(A), len(B)
    dp = [[0 for j in range(m+1)] for i in range(n+1)]
    ord = [[(-1, -1) for j in range(m+1)]
           for i in range(n+1)]
    for i in range(1, n+1):
        dp[i][0] = a+b*i
        ord[i][0] = (0, 0)
    gu = [(-1,-1) for i in range(m+1)]
    for i in range(1, m+1):
        dp[0][i] = a+b*i
        ord[0][i] = (0, 0)
        gu[i] = (dp[0][i], 0)
    for i in range(1, n+1):
        # print(i,n+1)
        gv = (dp[i][0], 0)
        for j in range(1, m+1):
            o = (w[1]+dp[i-1][j-1] if A[i-1] != B[j-1] else w[0]+dp[i-1][j-1],
                 gu[j][0]+a+b*i, gv[0]+a+b*j)
            dp[i][j] = max(o)
            ord[i][j] = ((i-1, j-1), (gu[j][1], j),
                         (i, gv[1]))[o.index(dp[i][j])]
            if dp[i][j]-b*i > gu[j][0]:
                gu[j] = (dp[i][j]-b*i, i)
            if dp[i][j]-b*j > gv[0]:
                gv = (dp[i][j]-b*j, j)
    match = []
    x, y = n, m
    while(x > 0 and y > 0):
        nx, ny = ord[x][y]
        if nx == x-1 and ny == y-1:
            match.append((A[x-1], B[y-1]))
        elif nx == x:
            for i in range(y, ny, -1):
                match.append(('', B[i-1]))
        else:
            for i in range(x, nx, -1):
                match.append((A[i-1], ''))
        x, y = nx, ny
    match.reverse()
    ans = dp[n][m]
    return ans, match


def match(A,B,name1 = 'str1',name2 = 'str2'):
    ans, match = DP(A, B)
    result = str(ans)
    # out = open('./match.txt', 'w')
    # step = 60  # format print
    # for index in range(0, len(match), step):
    #     s1 = ''.join(c[0] for c in match[index:index+step])
    #     s2 = ''.join(c[1] for c in match[index:index+step])
    #     out.write(name1+'% 8d' % index+' :  '+s1+'\n')
    #     out.write(name2+'% 8d' % index+' :  '+s2+'\n\n')
    # out.close()
    # print('result :', result)
    return match
