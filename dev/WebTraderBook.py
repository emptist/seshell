# -*- coding:UTF-8 -*-

from WebTrader import *
from time import sleep

import logging
logging.basicConfig(level=logging.INFO, filename='.pyTrader.log', filemode='w')
logging.captureWarnings(True)

'''
主要提供多賬戶同時使用的便利, 保持與windPy接口一致

若一個class只有 __init__ 和 一個 method, 那麼這實際是一個 function而非class.
但此處似乎將來還可以增加其他的批量執行多賬戶操作的methods,所以先保留
'''


class WebTraderBook(object):
    '''
        存放 WebTrader(s) 而已
        一家證券公司的已登錄賬戶. 同一個賬戶只有一個活動個體. 此法支持多賬戶同時操作
    '''
    def __init__(self, accounts=[]):
        '''
            用法:
                每人可有多個資金賬戶.在配置文件中設定.目前配置文件單列,將來合併為大表.
                每一個資金賬戶對應唯一的券商,此資金賬號登陸后,本法記錄入一個array;
                每一個因此而有一個id號即序號.association中含賬號->登陸之後的broker
                如此則與wind平台取得一致
        '''
        self.accounts = accounts  # 各個賬戶的array,為webAccount instance


    def logonAll(self, t=8):
        '''
        self.accounts 批量登錄若干賬戶.根據賬戶配置文件名稱,登錄各自賬戶(webLogon)
        '''
        for account in self.accounts:
            if account.isOn:
                pass  # doing nothing
            else:
                account.logon(t)
        return self

    def logonWith(self, accGenerator, t=8):
        '''
        單獨使用,初始化之後,隨時增加登錄單個賬戶
        '''
        acc = accGenerator()
        if acc not in self.accounts:
            if not acc.isOn:
                try:
                    acc.logon(t)
                except Exception as e:
                    print(e)
                self.accounts.append(acc)
                return acc
        else:
            if acc.isOn:
                return acc
            else:
                acc.logon(t)
                return acc
