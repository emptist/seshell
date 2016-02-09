#-*- coding:UTF-8 -*-

from DBMongo import *
import json


def db():
    mrl = r'mongodb://localhost:3001/meteor'
    conn = pymongo.MongoClient(mrl)
    #securities = conn.meteor.securities
    tradings = conn.meteor.tradings
    return tradings

def executeShell(liveAcc, command):
  '''
    command是一個array,裡面包括 act,code,percent,price 四要素,
    act: "buyIt", "sellIt"
    code: "150152.SZ"
    percent: 進出之比例
    price: 可以為0
  '''
  d = {"info": "{id}:{command}".format(id=liveAcc.liveId, command=command)}
  print(json.dumps(d.__str__()))

  if len(command) == 4:
      act, code, percent, price = command
      act, code, percent, price = act.strip(),code.strip(),percent.strip(),price.strip()
      # 臨時注釋下面一行,以便測試而不發生委託
      #liveAcc.__getattribute__(act)(code, float(percent), float(price), t_type=None)


  elif len(command) == 2:
      act, code = command
      value = liveAcc.__getattribute__(code)().reset_index()
      rstr = '{"name":"'+act+'","value":'+value.T.to_json()+'}'
      print(rstr)#(str.encode(rstr))
