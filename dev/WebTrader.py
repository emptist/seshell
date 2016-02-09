#-*- coding:UTF-8 -*-
from time import sleep
from HTSocket import HTSocket
import pandas as pd
import tushare as ts
import SocketTrader as st
import ShellTrader as sht
#from numba import jit
import pymongo
#import json

import logging
logging.basicConfig(level=logging.INFO, filename='.pyTrader.log', filemode='w')
logging.captureWarnings(True)

'''
模仿windPy的功能, 包裹HTSocket.py, 或來自第三方其他證券公司web api,
主要提供多賬戶同時使用的便利, 保持與windPy接口一致
'''


class WebTrader(object):
    '''主要實現以下功能'''
    def  __init__(self):
        ''' doesn't work
        self.api_name = api_name
        self.account = account
        self.password = password
        self.isOn = False
        '''
        #self.logon_object = logon_object


#mrl = r'mongodb://192.168.1.101:3001/meteor'
mrl = r'mongodb://localhost:3001/meteor'


# 華泰證券
class HTTrader(WebTrader):
    """
    我是一個(logon後)已經登錄的華泰證券交易端,可接受買賣查詢等委託,接口與萬得保持一致,以便同時使用.
    """
    def __init__(self, bname, account, encrypted_password, \
        service_password=None, api_name='htweb', limitAmnt=100000, mrl=mrl):
        super(HTTrader, self).__init__()

        self.limitAmnt = limitAmnt # 單筆操作數量有限制
        self.bname = bname
        self.api_name = api_name
        self.account = account
        self.liveId = self.api_name + self.account

        self.password = encrypted_password
        self.encrypted_password = encrypted_password
        self.service_password = service_password
        self.isOn = False
        self.stockAccounts = {}

        self.api_class = HTSocket
        self.api_func = lambda : self.api_class(self.account, \
            self.encrypted_password, self.service_password)
        self.api = self.api_func()

        self.dormb = 6.4778
        self.hkrmb = 0.8386
        self.rmbdo = 1/self.dormb
        self.rmbhk = 1/self.hkrmb

        '''
            連接Meteor 數據庫
        '''
        self.mrl = mrl
        try:
            self.conn = pymongo.MongoClient(self.mrl)
            self.securities = self.conn.meteor.securities
            self.tradings = self.conn.meteor.tradings
            self.funds = self.conn.meteor.funds
        except Exception as e:
            print('WebTrader init:')
            print(e)

    def db_find(self, db, something={}):
        return pd.DataFrame(list(db.find({})))

    def db_upsert_one(self, db, upfilter, update):
        # return db.update_one(upfilter, update, upsert=True)
        try:
            return db.update(upfilter, update, upsert=True)
        except Exception as e:
            print('WebTrader db_upsert_one:')
            print(e)

    def db_insert(self, db, something):
        try:
            return db.insert(something)
        except Exception as e:
            print('WebTrader db_insert:')
            print(e)

    def db_insert_df(self, db, df):
        try:
            newdict = df.T.to_dict()
            for idx in newdict:
                db.insert(newdict[idx])
            return self
        except Exception as e:
            print('WebTrader db_insert_df:')
            print(e)


    def recordAccounts(self, items):
        for item in items:
            self.stockAccounts[item['exchange_type']] = item
            #print(self.stockAccounts)

    def money(self, code):
        '''
            '0', 人民幣, '1', 美元, '2', 港幣
        '''
        if code[:2] == '90':
            mt = '1'
        elif code[:2] == '20':
            mt = '2'
        else:
            mt = '0'
        cptl = self.getCapital()
        _AvailableFund = cptl.ix[mt,'AvailableFund']
        _TotalAsset = cptl.ix[mt,'TotalAsset']
        _ratio = cptl.ix[mt,'rmb_value'] / cptl.ix[mt, 'rmb_total']
        return _TotalAsset, _AvailableFund, _ratio

    def getExCount(self, code):
        if code[:2] == '15' or code[:2] == '16' or code[:2] == '00':
            return '2', self.stockAccounts['2']['stock_account']
        elif code[:2] == '50' or code[:2] == '51' or code[:2] == '60':
            return '1', self.stockAccounts['1']['stock_account']
        elif code[:2] == '90':
            return 'D', self.stockAccounts['D']['stock_account']
        elif code[:2] == '20':
            return 'H', self.stockAccounts['H']['stock_account']
        else:
            raise Exception('stock_account not ready for code: '+code)

    def logon(self, t=4):
        if self.isOn:
            print('{bname} {account} : 登錄成功'.format(bname= self.bname, account= self.account))
            return self
        elif t < 0:
            raise Exception('{bname} {account} : 登錄失敗'.format(bname= self.bname, account= self.account))
        else:
            '''
            登錄使用新的 HTSocket object
            '''
            self.api = self.api_func()
            #sleep(3)
            print('嘗試登錄,剩餘次數: {n}'.format(n=t-1))
            '''
            以下一行如果登錄成功,會設置 self.isOn = True
            '''
            self.autolog()
            #self.manulog()
            return self.logon(t-1)

    def reLogon(self):
        self.isOn = False
        sleep(3)
        return self.logon(8)

    def postLogon(self):
        self.isOn = True
        ks = self.api._HTSocket__trade_keys
        self.recordAccounts(ks['item'])
        self.logonId = ks['uid']
        print('{"api":"ready"}')

    def autolog(self):
        try:
            while True:
                if self.api.try_auto_login() and self.api._get_position() and\
                    self.api._get_balance:
                    self.postLogon()
                    return self
                sleep(3)
        except Exception as e:
            print('WebTrader autolog')
            print(e)

    def manulog(self):
        try:
            self.api.prepare_login()
            self.api.show_verify_code()
            vericode = input("input verify code: ")
            self.api.enter_verify_code(vericode)
            sleep(5)
            if self.api.login():
                self.postLogon()
                self.api.prepare_trade()
            return self
        except Exception as e:
            print('WebTrader manulog')
            print(e)

    def _getCapital(self, t=3):
        if self.api._get_balance():
            return pd.DataFrame.from_dict(self.api.capital).T.set_index('money_type')
            '''
            return pd.DataFrame.from_dict({0: self.api.balance}).T
            '''
        else:
            if t < 0:
                self.reLogon()
                return self._getCapital()
            else:
                sleep(2)
                return self._getCapital(t-1)

    def _getPosition(self, t=5):
        '''
        取得持仓信息
        '''
        p = {}
        if self.api._get_position():
            p = self.api.stock_position
        if p:
            pdata = pd.DataFrame.from_dict(p)
            return pdata
        else:
            if t < 0:
                self.reLogon()
                return self._getPosition()
            else:
                sleep(2)
                return self._getPosition(t-1)

    def getCapital(self):
        '''
        取得信息,更名与万德一致
        '''
        rndict = {
            'money_type': 'money_type',  # '0',
            'money_name': 'money_name',  # '人民币',
            'market_value': 'market_value',  # 100000.0,     股票市值
            'fetch_balance': 'fetch_balance',  #? '0',         可取
            'enable_balance': 'AvailableFund',  # 100000.0,   可用资金
            'asset_balance': 'TotalAsset', # 10000.0,     总资产
            'current_balance': 'current_balance' # '0'
        }
        jkc = self._getCapital().rename(columns=rndict)
        jkc.loc[jkc.money_name == '人民币','rmb_value']=jkc.TotalAsset
        '''
            不一定有b股賬戶
        '''
        try:
            jkc.loc[jkc.money_name == '美元','rmb_value']=jkc.TotalAsset*self.dormb
            jkc.loc[jkc.money_name == '港币','rmb_value']=jkc.TotalAsset*self.hkrmb
        except Exception as e:
            jkc.dropna()
            print('WebTrader getCapital 無外匯而已')
            print(e)

        jkc.loc[:,'rmb_total'] = jkc.rmb_value.sum()
        jkc.loc[:,'acc_id'] = self.liveId

        try:
            self.db_insert_df(self.funds, jkc)
        except Exception as e:
            print('WebTrader getCapital db_insert_df: ')
            print(e)

        return jkc


    def getPosition(self):
        '''
        取得信息,更名与万德一致
        '''
        rndict = {
            'enable_amount': 'SecurityAvail',
            'stock_name': 'SecurityName',
            'last_price': 'LastPrice',
            'income_balance': 'Profit',
            'market_value': 'HoldingValue', # 10253.4,     # 市值
            'keep_cost_price': 'keep_cost_price',  # 102.534,  # 保本价格
            'av_buy_price': 'av_buy_price',  #?
            'hand_flag': 'hand_flag',  # ?
            'current_amount': 'SecurityAmount',  #?   # 股票数量
            'stock_code': 'SecurityCode',      # 股票代码
            'cost_price': 'CostPrice',       # 成本价
            'exchange_type': 'exchange_type',
            'av_income_balance': 'av_income_balance',  # ?
            'exchange_name': 'exchange_name',  # '上海Ａ',
            'stock_account': 'stock_account'   # 'A111111111'
        }
        pdata = self._getPosition()
        pos = pdata.rename(columns=rndict)
        cpt = self.getCapital()

        try:
            '''
                有些沒有B股賬戶,有時賬戶無持倉
            '''

            pos.loc[(pos.exchange_type=='1')|(pos.exchange_type=='2'),'extra']=\
                pos.HoldingValue/cpt.loc['0','TotalAsset']\
                - max(0.005, (1 / (1+pos.loc[(pos.exchange_type=='1')|\
                (pos.exchange_type=='2'),'Profit'].size)))
            pos.loc[pos.exchange_type=='D','extra']=pos.HoldingValue/cpt.loc['1','TotalAsset']\
                - max(0.005, (1 / (1+pos.loc[pos.exchange_type=='D','Profit'].size)))
            pos.loc[pos.exchange_type=='H','extra']=pos.HoldingValue/cpt.loc['2','TotalAsset']\
                - max(0.005, (1 / (1+pos.loc[pos.exchange_type=='H','Profit'].size)))
        except Exception as e:
            pos.dropna()
            print('WebTrader getPosition: 空賬戶而已,並非出錯')
            print(e)

        return pos

    # @jit
    def briefPosition(self):
        tmp = self.getPosition()
        pos = tmp[:]
        # pos = pos[pos.SecurityAvail > 100] # 少於等於1手就不動他了
        # pos = pos[['SecurityCode' ,  'SecurityName', 'Profit', 'TradingCost','CostPrice', 'LastPrice']]
        selected = ['SecurityCode' ,  'SecurityName', 'Profit', 'SecurityAmount',\
            'LastPrice', 'CostPrice', 'HoldingValue', 'SecurityAvail', 'extra']  # ,'keep_cost_price','CostPrice']
        pos = pos[selected]
        '''
            標的品種不賣完
        '''
        pos = pos[pos.HoldingValue > 0]
        pos.loc[:,'PerItemProfit'] = (tmp.Profit / (tmp.HoldingValue - tmp.Profit)) * 100
        pos.loc[:,'MaxPrice'] = tmp.LastPrice
        pos.loc[:,'MinPrice'] = tmp.LastPrice
        pos['stimes'] = 0  # sell times
        pos['btimes'] = 0  # buy times
        #pos['Fixed'] = pos.SecurityName.str.contains('A') & pos.SecurityCode.str.match(r'^(1|5)')
        #return pos.set_index(['SecurityCode', 'SecurityName', 'Fixed'])  # .sort_index()
        return pos.set_index(['SecurityCode', 'SecurityName'])  # .sort_index()

    def simplePosition(self):
        simp = self.getPosition()[:][['SecurityCode','Profit','LastPrice', 'CostPrice', 'HoldingValue', 'SecurityAvail', 'extra']
]
        return simp.set_index('SecurityCode')

    def availableSecurity(self, code):
        '''
            這部份需要改寫,應該一次性提供所有 sellAll 中提到的品種 可用和全部數量 ###
        '''
        dfa = self.getPosition()
        if code in dfa.SecurityCode.values:
            info = dfa[dfa.SecurityCode == code]
            return info.SecurityAmount.values[0], info.SecurityAvail.values[0]
        else:
            return 0

    def getTrade(self, t=3):
        if self.api._get_today_trade():
            return pd.DataFrame.from_dict(self.api.trade_list)
        else:
            if t < 0:
                self.reLogon()
                return self.getTrade()
            else:
                sleep(2)
                return self.getTrade(t-1)

    def _getOrderInfo(self, t=3):
        if self.api._get_today_entrust():
            return pd.DataFrame.from_dict(self.api.entrust_list)
        else:
            if t < 0:
                self.reLogon()
                return self._getOrderInfo()
            else:
                sleep(2)
                return self._getOrderInfo(t-1)

    def getOrderInfo(self):
        rndict ={
            'entrust_price': 'entrust_price',  # 102.533,     委托价格
            'stock_account': 'stock_account',  # 'A1111111',  股东账户
            'entrust_time': 'entrust_time',  # '110849',     委托时间
            'entrust_amount': 'OrderVolume',  # 100.0,      委托数量
            'stock_name': 'SecurityName',  # '银华日利',
            'status_name': 'status_name',  # '已成',
            'exchange_type': 'exchange_type',  # '1',
            'prop_name': 'prop_name',  # '买卖',
            'bs_name': 'bs_name',  # '买入',
            'entrust_status': 'entrust_status',  # '8',        8为已成,9为废单,6为已撤,2为已报
            'entrust_no': 'entrust_no',  # '24410',        委托号
            'business_price': 'business_price',  # 102.533,
            'business_amount': 'TradedVolume',  # 100.0,
            'entrust_prop': 'entrust_prop',  # '0',
            'stock_code': 'SecurityCode',  # '511880',       股票代码
            'entrust_bs': 'entrust_bs',  # '1',            1为买入,2为卖出
            'exchange_name': 'exchange_name',  # '上海Ａ'
        }
        pdata = self._getOrderInfo()
        return pdata.rename(columns=rndict)

    # 當日委託
    def briefOrderInfo(self):
        oinfo = self.getOrderInfo()
        _cols_ = ['SecurityCode','SecurityName','business_price',\
            'OrderVolume','TradedVolume','entrust_bs']
        rndict = {
            'SecurityCode': '碼',
            'SecurityName': '名',
            'entrust_bs': '類',
            'business_price': '價',
            'OrderVolume': '申',
            'TradedVolume': '成'
        }
        try:
            return (oinfo[_cols_]).rename(columns=rndict)  # ,'CancelVolume']]
        except:
            return oinfo

    def getWOrders(self, t=3):
        if self.api._get_cancel_list():
            return pd.DataFrame.from_dict(self.api.cancel_list)
        else:
            if t < 0:
                self.reLogon()
                return self.getWOrders()
            else:
                sleep(2)
                return self.getWOrders(t-1)

    # 限價買入
    #限价委托，price: 2.00 amt: 100
    # @jit
    def buyAt(self, code, price=0, amount=0):
        '''
        Buy code at price and amount, expecting those as args

        > w.torder("150001.SZ","Buy","2.00","100","OrderType=LMT;LogonId=2")
        > buyAt("150153.SZ", "2.001","10000")

        '''
        if code == '150022':
            return 0
        if amount == 0:
            return 0  # return something?
        if amount > self.limitAmnt:
            amt = amount - self.limitAmnt
            self.buyAt(code, price=price, amount=amt//100*100)
            return self.buyAt(code, price=price, amount=self.limitAmnt)

        if price == 0: # 如果報價為零,採用本方最優價格BOP,對方為BOC,現價為ITC,鑒於將來以分級A為主,用現價
            # dfOrder = wdf(w.torder(code, "Buy", "0", amount, "OrderType=ITC;LogonId={0}".format(self.logonId)))
            pass
        else:
            typ, accnt = self.getExCount(code)
            info = self.api._buy(typ, accnt, code, amount=amount, price=price)
            return info
        # info = self.getOrderInfo()
        # return info  # info[(info['SecurityCode'] == code) & (info['bs_name'] =='买入')][-1:]   # 再選取相應的項目

    # @jit
    def buyIt(self, code, percent, price=0, t_type=None):
        '''
        Get Amnt and ask price and buy percentage of all
        '''
        #print("批量買入:" + code)

        if percent < 0:
            return 0

        if price == 0:
            # askPrice = quote126(code).ask1[code[:-3]] + 0.002
            askPrice = float(ts.get_realtime_quotes(code).ask[0])
        else:
            askPrice = price

        cp_tot, cp_ava,cp_ratio = self.money(code)
        rs = 0
        try:
            # fund = capit.AvailableFund * percent  # <-- 剩餘模式
            percent = percent / cp_ratio
            fund = min(cp_tot * percent, cp_ava) # <-- 等額模式
            '''if fund < 500:
                print('{code}: 剩餘資金較少,避免零碎小單累計手續費成本,故暫時不買'.format(code= code))
                return 0
            '''
            amnt =  fund // (askPrice*100)
            autoAmnt = amnt * 100
            if autoAmnt < 100:
                print('{'+'"info":"{code}: 資金{percent}%剩餘{fund}不夠{askPrice}買({autoAmnt})"'.format\
                    (code= code, percent=percent*100,fund=fund, askPrice=askPrice, autoAmnt=autoAmnt)+'}')
                # print(capit) # 深圳b股經常報資金餘額不足,看有無問題
                return 0
            if t_type == 'itc':  # 如果採用對方限價
                rs = self.buyAt(code, price=0, amount=autoAmnt)
            else:
                rs = self.buyAt(code, price=askPrice, amount=autoAmnt)

            # print("批量買入{code} {autoAmnt}股, 報價:{price}".format(code=code, autoAmnt=autoAmnt, price=askPrice))
            self.db_insert(self.tradings, {'acc_id':self.liveId, '代碼': code, '報價': askPrice, '比重': percent,'數量': autoAmnt, '操作': '買入'})
            return rs #return getOrderInfo(fidBroker)

        except Exception as e:
            #dfCancel()
            print('WebTrader buyAt:')
            print(e)

    # @jit
    def sellAt(self, code, price=0, amount=0):
        '''
        Sell code at price orderId by LogonID accept order id as args

        > w.torder("150001.SZ","Sell","2.00","100","OrderType=LMT;LogonId=2")
        > sellAt("150153.SZ", "2.001","10000")

        '''
        if amount == 0:
            return 0 # something?
        if amount > self.limitAmnt:
            am = amount - self.limitAmnt
            self.sellAt(code, price=price, amount=self.limitAmnt)
            return self.sellAt(code, price=price, amount=am//100*100)

        if price == 0: #如果報價為零,採用ITC, 當前價格,剩餘撤單
            pass
            #dfOrder = wdf(w.torder(code, "Sell", "0", amount, "OrderType=ITC;LogonId={0}".format(self.logonId)))
        else:
            typ, accnt = self.getExCount(code)
            info = self.api._sell(typ, accnt, code, amount, price)

        # info = self.getOrderInfo()
        return info  # info[(info['SecurityCode'] == code) & (info['bs_name'] =='卖出')][-1:]   # 再選取相應的項目

    # @jit
    def sellIt(self, code, percent=0, price=0, t_type=None, am=0, av=0):
        '''
        Get Amnt and ask price and sell percentage of all
        '''
        if  percent <= 0:
            return 0

        if av == 0:
            amount, avamnt = self.availableSecurity(code)
        else:
            amount = am
            avamnt = av

        # 取100之倍數 ceil(autoAmnt(code,fidBroker) * percent)
        if amount < 100 and percent < 1: # 少於100股就不賣了
            print('{'+'"info":"{code}可用證券{x}, 少於100股"'.format(code=code, x=amount)+'}')
            return 0

        autoAmnt = min(avamnt, (amount * percent // 100 * 100))

        if 101 > autoAmnt > -1:
            autoAmnt = 100

        # 若未制定賣出價格則自動決定,否則根據制定價格提交
        try:
            if price == 0:
                #dfq = quote126(code)
                #bidp = dfq.bid1[code[:-3]]
                bidp = float(ts.get_realtime_quotes(code).b1_p[0])
                bidv = float(ts.get_realtime_quotes(code).b1_v[0])

                if bidv > autoAmnt/100:
                    bidprice = bidp
                else:
                    # 未解決
                    bidprice = bidp  # bidp - 0.001 # bug here! 股票委託價格只能兩位數!基金只能3位數!
            else:
                bidprice = price

            #print(self.briefOrderInfo().tail(3))#.to_string())
            '''
            由於經常出現賣不出情況,故降低賣出價位, 最好是採用買一價位,有空時改寫.總之確保賣出
            '''

            if t_type == 'itc': #如果採用對方限價
                result = self.sellAt(code, price=0, amount=autoAmnt)
            else:
                result = self.sellAt(code, price=bidprice, amount=autoAmnt)

            self.db_insert(self.tradings, {'acc_id':self.liveId,'代碼': code, \
                '報價': price, '比重': percent,'數量': autoAmnt, '操作': '賣出'})
            return result

        except Exception as e:
            #dfCancel()
            print('WebTrader sellAt:')
            print(e)


    # 批量買賣需要研究用dataframe怎麼設計
    def buyAll(self, df, percent=0.02):
        # 臨時先使用 buyIt,以後再改為直接批量出售
        #print(pd.datetime.now())
        for i in df.index:
            ix = df.ix[i]
            if 'B' in ix.SecurityName \
                and (ix.SecurityCode[0] == '5' or ix.SecurityCode[0] == '1') \
                and ix.LastPrice < 0.55:
                print('{"info":"規避b級基金下折風險故不回購."}')
                continue

            if percent == 0:
                p = -ix.extra  # 買入情形是補充不足,故原來為負數
            else:
                p = min(percent, -ix.extra)  # 避免超買

            self.buyIt(ix.SecurityCode, percent=p, price=ix.LastPrice)

        #print(pd.datetime.now())
        #print(self.briefOrderInfo().tail(len(df)+1))#.to_string())

    def sellAll(self, df, percent=0.618):
        # 臨時先使用 sellIt,以後再改為直接批量出售
        for i in df.index:
            ix = df.ix[i]
            if percent == 0:
                p = ix.extra
            else:
                p = percent
            # 此處更合理的比重應為資產百分比折算股數
            self.sellIt(ix.SecurityCode, percent=p, price=ix.LastPrice,\
                am=ix.SecurityAmount,av=ix.SecurityAvail)
        #print(pd.datetime.now())
        #print(self.briefOrderInfo().tail(len(df)+1))#.to_string())

    def cancelIt(self, orderId):
        entrust_no = orderId
        return self.api._cancel(entrust_no)

    def cancelAll(self, orderIds):
        pass

    '''
        for python-shell

    '''
    def shellTrade(self, line):
        '''
        接收操作指令,分解執行

        '''
        try:
            #for line in cstr.split('\r'):
            command = line.split(',')
            sht.executeShell(self, command)

        except Exception as e:
            d = '{'+'"err":"WebTrader shellTrade:{e}"'.format(e=e)+'}'
            print(d)
            raise e


    '''
    Socket Trading
    可以使用SocketBroker作為服務器,接收任何語言的client連接,實現操作
    '''

    def socketTrade(self, conn, cstr):
        '''
        接收socket獲得的String,解析為操作指令,分解執行
        conn 只是偶爾使用, 如發回某些提示信息等等
        '''
        try:
          #print(cstr)

          for line in cstr.split('\r'):
              command = line.split(',')
              self.executeIt(conn, command)
          # conn.sendall(str.encode(cstr))

        except Exception as e:
          print('WebTrader socketTrade:')
          print(e)

    def executeIt(self, conn, command):
        '''
        command是一個array,裡面包括 act,code,percent,price 四要素,
        act: "buyIt", "sellIt"
        code: "150152.SZ"
        percent: 進出之比例
        price: 可以為0
        '''
        return st.executeIt(self, conn, command)

# 國金證券佣金寶
class GJTrader(WebTrader):
    """docstring for YJBroker"""
    def __init__(self,  account, password, api_name='Gjzq'):
        super(GJTrader, self).__init__()

        '''
        # 若用他人庫則:
        from GJAPI import GJAPI
        # 否則在此直接定義,參照華泰證券 HTTrader
        '''
