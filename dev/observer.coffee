###說明:
  此為實時控制機器人.
    實時交易中有兩個並行流程:
    1. 用選定策略針對選定品種實時跟蹤,發出買賣信號(event),由相關賬戶執行操作
    2. 各賬戶根據各品種成本實時跟蹤持倉狀況,作最終保本性止損
    3. 根據賬戶總體資產變動,確定若干條砍倉保本線,到線根據比例砍倉

    1 簡單一刀切砍倉,容易,先做
    2 確定總比例,根據不同品種自身狀況,分別決定. 後做
###
util = require 'util'
dbconnected = require('../api.mongodb.meteor/collection')
券商接口 = require '../api.order.py/sesocket'#'sesocket'
#券商接口 = require '../seshell/lib/sebroker'
策略機器人 = require '../sys.trading/robot'
{ticks} = require 'sedata'
{account} = require '../config'
資產賬戶 = require account
券商接口.賬戶 = new 資產賬戶

dbconnected (err, db)->
  secs = db.collection "securities"
  secs.find().toArray (err,doc)->
    codes = (sec.SecurityCode for sec in doc)
    機器人 = new 策略機器人(codes)

    兩小時 = 2*60*60*1000
    間隔 = 5*1000
    開市時間 = 3*10*1000  #兩小時 #15000 #兩小時

    券商接口.就緒 (err,data)->
      if err then throw(err)
      util.log('已接通券商..')
      跟蹤行情 = ->
        # ticks 券商接口.賬戶.可用.join(','), (行情)->
        ticks 機器人.codes.join(','), (行情)->
          if 行情
            機器人.應對 行情, (指令)->
              # 機器人不管具體賬戶情況,根據行情發出指令,券商接口過濾指令
              if 指令
                券商接口.賬戶.操作指令 指令, (obj)->
                  if obj
                    # 經過過濾的指令可能跟原來不一樣,所以需要這樣寫
                    指令 = "#{obj.操作},#{obj.代碼},#{obj.比重},#{obj.價位}"
                    券商接口.發出指令 指令, ->

        ###
          盡量簡化,將來不用Python接口時,這些代碼也不用改,只需取前半部分
          系統內部用的是前半部分,英文部分是針對Python接口的
        ###
        券商接口.提取資料 '最新持倉,getPosition'
        券商接口.提取資料 '可撤單,getWOrders'

      interval = setInterval 跟蹤行情, 間隔

      結束 = ->
        util.log '收盤了'
        clearInterval interval
        券商接口.destroy()

      timeout = setTimeout 結束, 開市時間
    db.close()
