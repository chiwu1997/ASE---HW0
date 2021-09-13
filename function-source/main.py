def main(request):
  import requests
  import gspread
  from oauth2client.service_account import ServiceAccountCredentials
  import talib
  import numpy as np
  import logging
  from binance.client import Client

  # Log
  logging.basicConfig(filename = "log.txt", format = '%(asctime)s %(message)s', filemode = 'w')
  logger = logging.getLogger(__name__)
  logger.setLevel(logging.INFO)

  # Binance Account Connection
  api_key = "XXXXXXXXXXXXXXXXXXXXX"
  api_secret = "XXXXXXXXXXXXXXXXXXXXX"
  client = Client(api_key, api_secret)

  # Line Notification
  def lineNotifyMessage(token, msg):
    headers = {
        "Authorization": "Bearer " + token, 
        "Content-Type" : "application/x-www-form-urlencoded"
    }
    payload = {'message': msg}
    r = requests.post("https://notify-api.line.me/api/notify", headers = headers, params = payload)
    return r.status_code

  token = 'rdueHVuo0GJbi2cEuGXJGcpsoU7dSe0N4PMEkIga3fs'
  pair = 'BTCUSDT'
  close_price_trace = np.array([])
  ma_long = 76
  ma_short = 39
  UP = 1
  DOWN = 2
  sheet_name = "MA"

  # Google sheet
  auth_json_path = 'crypto.json'
  gss_scopes = ['https://spreadsheets.google.com/feeds']
  credentials = ServiceAccountCredentials.from_json_keyfile_name(auth_json_path,gss_scopes)
  gss_client = gspread.authorize(credentials)
  sheet = gss_client.open_by_key("1YwI5N0soTRxi2GWslBEeYc0YiMpCZw7Q9NrFKY6aQ90").worksheet(sheet_name)

  # get price
  klines = client.get_historical_klines(pair, Client.KLINE_INTERVAL_1HOUR, "4 day ago UTC")
  for i in klines:
    close_price_trace = np.append(close_price_trace,float(i[1]))

  # MA Cross
  def get_current_ma_cross():
      s_ma = talib.SMA(close_price_trace, ma_short)[-1]
      l_ma = talib.SMA(close_price_trace, ma_long)[-1]
      message = "(Short, Long) = ({}, {})".format(str(round(s_ma, 1)), str(round(l_ma, 1)))
      logger.info(message)
      
      if s_ma > l_ma:
          return UP
      return DOWN

  cur_cross = get_current_ma_cross()
  strategy_start_status = int(sheet.acell('D2').value)

  # Main Function
  if strategy_start_status == False:
      message = "MA Cross Strategy Begins!"
      logger.info(message)
      sheet.update_acell('A2', cur_cross)
      sheet.update_acell('D2', 1)
      return
  
  last_cross_status = int(sheet.acell('A2').value)
  target_amount = float(client.futures_position_information(symbol=pair)[0]["positionAmt"])  # 部位數量

  # Golden Cross
  if cur_cross == UP and last_cross_status == DOWN and target_amount <= 0:           
    close_price = int(close_price_trace[-1])
    if target_amount < 0:
      message = "MA Golden Cross -> buy two units"
      signal = "reverse_short_to_long"
    if target_amount == 0:
      message = "MA Golden Cross -> buy one unit"
      signal = "long_entry"
    
    logger.info(message)
    sheet.update_acell('A2', cur_cross)   # last_cross_status
    lineNotifyMessage(token, "\n" + message)
    
    my_data = {
      "id": "aa919b86-17c7-4777-b189-c54d6a44bc1b",
      "action": "{}".format(signal),
      "stop_loss_exact_price": str(close_price - 1000),
      "take_profit_exact_price": str(close_price + 2500)
    }
    order = requests.post('https://mudrex.com/api/v1/signals', json = my_data)

  # Death Cross
  elif cur_cross == DOWN and last_cross_status == UP and target_amount >= 0:
    close_price = int(close_price_trace[-1])
    if target_amount > 0:
      message = "MA Death Cross -> sell two units"
      signal = "reverse_long_to_short"
    if target_amount == 0:
      message = "MA Death Cross -> sell one units"
      signal = "short_entry"
    
    logger.info(message)
    sheet.update_acell('A2', cur_cross)   # last_cross_status
    lineNotifyMessage(token, "\n" + message)
  
    my_data = {
      "id": "aa919b86-17c7-4777-b189-c54d6a44bc1b",
      "action": "{}".format(signal),
      "stop_loss_exact_price": str(close_price + 1000),
      "take_profit_exact_price": str(close_price - 2500)
    }
    order = requests.post('https://mudrex.com/api/v1/signals', json = my_data)

  else:
    message = "MA No Cross"
    logger.info(message)