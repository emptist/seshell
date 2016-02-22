Pysh = require 'python-shell'
### 券商接口
基本功能:
  提取資料:回報賬戶等資料
  發出指令:發出操作指令

說明:
  邏輯上,券商接口跟賬戶是綁定的.故此處賬戶跟接口並用.
  但是賬戶主要功能應獨立於接口,故賬戶另外設module.以便可以對接所有接口

  通過該券商接口登錄之後,在開市期間,
    1 對賬戶進行實時監控
    2 連接可為多用戶服務的策略交易機器人(含止盈止損機器人)
  應對行情和賬戶變動,進行實時交易.

Server要求如下:
  json: 發回來的資料須符合: {name:'資料名',value:資料內容},其中,資料名等同client所發申請
  賬戶登錄成功: 須print {"api":"ready"}
Path
  如果Python文件不隨npm發佈,則默認是在當前工作路徑(不定的),可以用相對路徑來引用
  如果Python文件跟隨此包發佈,則須設置路徑
  setup a default "scriptPath"
    PythonShell.defaultOptions = { scriptPath: '../scripts' };
  或個別設置,如以下代碼所示,注意,該script再引用其他script,會在正確的路徑中引用,不須設置
###


options =
  mode:'json'
  pythonOptions:['-u']
  #scriptPath: __dirname

# 出現接口問題時,可重新運行
券商接口 = new Pysh 'psbroker.py', options

券商接口.準備就緒 = false
券商接口.就緒 = (回執)->
  #等待登錄成功信息
  until 券商接口.準備就緒
    回執(null, null)

券商接口.on 'message', (jso)->
  obj = jso
  if obj.hasOwnProperty 'api'
    if obj.api is 'ready'
      券商接口.準備就緒 = true
  else if obj.hasOwnProperty 'name'
    券商接口.賬戶[obj.name] obj.value, (指令)->
      if 指令 then 券商接口.發出指令(指令)

券商接口.destroy = ->
  券商接口.end (err)->
    throw err if err
    console.info 'done.'

# 盡量簡化了
券商接口.提取資料 = (指令)->
  券商接口.發出指令(指令, ->)

券商接口.發出指令 = (指令, 回執)->
  券商接口.send {command:指令} # 換行 = '\r';指令+換行
  util.log 指令
  回執?() #沒啥用?


module.exports = 券商接口

###
util = require 'util'
{Socket} = require 'net'
# TODO: 糾正引用文件位置方法
{端口,主機} = require './config'

券商接口 = new Socket()

券商接口.on 'close',()->
  util.log 'socket closed'
###
###

  券商接口收到任何資料,都交給所屬賬戶來處理,
  因為服務於多用戶的策略機器人不需要這些資料

  將來新版本各種券商接口也都這樣處理

###
###
券商接口.on 'data', (data)->
  obj = JSON.parse data
  if obj.hasOwnProperty 'name'
    券商接口.賬戶[obj.name] obj.value, (指令)->
      if 指令 then 券商接口.發出指令(指令)
###
