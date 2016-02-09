#-*- coding:UTF-8 -*-
import json
from WebTrader import *
from WebTraderBook import *


'''
examples
from WebPyAcc import *

myWebTrader = WebTraderBook()
jk = myWebTrader.logonWith(ht_main)
'''
def __htcfg(name):
    with open('.{config}'.format(config=name), 'r') as f:
        config = json.loads(f.read().replace(r'\n', ''))
    #print('登錄券商....')
    return HTTrader('華泰證券',config['account'], config['password'], config['service_password'])

def ht_other():
    return __htcfg('ht_other')

def ht_main():
    return __htcfg('ht_main')
    
def webAccount(func):
    webTraderBook = WebTraderBook()
    try:
        acc = webTraderBook.logonWith(func)
    except Exception as e:
        raise e

def webAccounts(functions):
    myWebTraders = []
    webTraderBook = WebTraderBook()
    #先登錄賬戶並停頓5秒待其完成. 如此則即便重現連接,也還是同一個myWebTrader,其記憶不丟失
    for func in functions:
        try:
            acc = webTraderBook.logonWith(func)
            myWebTraders.append(acc)
            # print('已經登錄{acnt}'.format(acnt=acc.account))
        except Exception as e:
            print('WebPyAcc webAccounts: ')
            print(e)
    return myWebTraders
