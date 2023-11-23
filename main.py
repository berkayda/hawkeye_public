import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import requests
import config
import os
import time
from datetime import datetime, timezone, timedelta


def telegram_bot_sendtext(bot_message, id):
    bot_token = config.telegram_bot_token
    bot_chatID = id
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={str(bot_chatID)}&parse_mode=Markdown&text={bot_message}"
    try:
        response = requests.get(url)
    except Exception as e:
        print("Error occurred:", e)


def telegram_bot_sendphoto(photo_path, id):
    bot_token = config.telegram_bot_token
    bot_chatID = id
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    with open(photo_path, 'rb') as photo:
        files = {'photo': photo}
        data = {'chat_id' : bot_chatID}
        try:
            response = requests.post(url, files=files, data=data)
        except Exception as e:
            print("Error occurred:", e)
            telegram_bot_sendtext(f"*telegram_bot_sendphoto ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


def download_data(ticker, period, start, end):
    try:
        return yf.download(tickers=ticker, period=period, start=start, end=end)
    except Exception as e:
        print(f"download_data ERROR: \n\n {e}")
        telegram_bot_sendtext(f"*download_data ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


def calculate_features(data):
    try:
        n_times = 1.5 
        bars_back = 4
        length = 200
        divisor = 3.6

        data['range'] = data['High'] - data['Low']
        data['rangeAvg'] = data['range'].rolling(window=length).mean()

        HV_ma = 20
        data['durchschnitt'] = data['Volume'].rolling(window=HV_ma).mean()
        data['volumeA'] = data['Volume'].rolling(window=length).mean()

        data['high1'] = data['High'].shift(1)
        data['low1'] = data['Low'].shift(1)
        data['mid1'] = (data['High'] + data['Low']) / 2

        data['u1'] = data['mid1'] + (data['high1'] - data['low1']) / divisor
        data['d1'] = data['mid1'] - (data['high1'] - data['low1']) / divisor

        data['r_enabled1'] = ((data['range'] > data['rangeAvg']) & (data['Close'] < data['d1']) & (data['Volume'] > data['volumeA'])).astype(int)
        data['r_enabled2'] = (data['Close'] < data['mid1']).astype(int)
        data['r_enabled'] = (data['r_enabled1'] | data['r_enabled2']).astype(int)

        data['g_enabled1'] = (data['Close'] > data['mid1']).astype(int)
        data['g_enabled2'] = ((data['range'] > data['rangeAvg']) & (data['Close'] > data['u1']) & (data['Volume'] > data['volumeA'])).astype(int)
        data['g_enabled3'] = ((data['High'] > data['high1']) & (data['range'] < data['rangeAvg'] / 1.5) & (data['Volume'] < data['volumeA'])).astype(int)
        data['g_enabled4'] = ((data['Low'] < data['low1']) & (data['range'] < data['rangeAvg'] / 1.5) & (data['Volume'] > data['volumeA'])).astype(int)
        data['g_enabled'] = (data['g_enabled1'] | data['g_enabled2'] | data['g_enabled3'] | data['g_enabled4']).astype(int)

        data['gr_enabled1'] = ((data['range'] > data['rangeAvg']) & (data['Close'] > data['d1']) & (data['Close'] < data['u1']) & (data['Volume'] > data['volumeA']) & (data['Volume'] < data['volumeA'] * 1.5) & (data['Volume'] > data['durchschnitt'])).astype(int)
        data['gr_enabled2'] = ((data['range'] < data['rangeAvg'] / 1.5) & (data['Volume'] < data['volumeA'] / 1.5)).astype(int)
        data['gr_enabled3'] = ((data['Close'] > data['d1']) & (data['Close'] < data['u1'])).astype(int)
        data['gr_enabled'] = (data['gr_enabled1'] | data['gr_enabled2'] | data['gr_enabled3']).astype(int)

        data['V_color'] = np.where(data['gr_enabled'] == 1, '#696b70',
                         np.where(data['g_enabled'] == 1, '#026b07',
                         np.where(data['r_enabled'] == 1, '#d81515', '#0000FF')))

        data['volalert2'] = (data['Volume'] > ma_func(data['Volume'], bars_back, "SMA") * n_times).astype(int)
    except Exception as e:
        print(f"download_data ERROR: \n\n {e}")
        telegram_bot_sendtext(f"*calculate_features ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


def ma_func(x, length, ma_type="SMA"):
    try:
        if ma_type == "WMA":
            return x.rolling(window=length).apply(lambda x: np.average(x, weights=np.arange(1, length + 1)), raw=True)
        elif ma_type == "SMA":
            return x.rolling(window=length).mean()
        else:
            return x.ewm(span=length, adjust=False).mean()
    except Exception as e:
        print(f"download_data ERROR: \n\n {e}")
        telegram_bot_sendtext(f"*ma_func ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


def detect_spike_signals(data):
    try:
        alert_rows = data[data['volalert2'] == 1]
        if not alert_rows.empty:
            row = alert_rows.iloc[-1]
            spike_signal_date = row.name
            utc_now = datetime.now(timezone.utc)
            one_day_ago = utc_now - timedelta(days=1)
            print(spike_signal_date.date())
            if spike_signal_date.date() == utc_now.date() or spike_signal_date.date() == one_day_ago.date():
                telegram_bot_sendtext(f"_Spike Volume signal for_ *{config.ticker} ({config.period})* \n_Spike Signal Date: {spike_signal_date.strftime('%d-%m-%Y')}_", config.telegram_chat_id_ME)
    except Exception as e:
        print(f"download_data ERROR: \n\n {e}")
        telegram_bot_sendtext(f"*detect_spike_signals ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


def plot_and_save_fig(data):
    try:
        fig, ax1 = plt.subplots(figsize=(14,7))
        ax1.plot(data.index, data['Close'], color='black')
        ax2 = ax1.twinx()
        ax2.bar(data.index, data['Volume'], color=data['V_color'])
        ax2.plot(data.index, data['durchschnitt'], color='orange', linewidth=2)

        spike_times = data.index[data['volalert2'] == 1]
        spike_prices = data.loc[data['volalert2'] == 1, 'Close']
        ax1.scatter(spike_times, spike_prices, color='purple', zorder=10)

        plt.title(f'{config.ticker} Price and Volume')
        plt.savefig('my_figure.jpeg')
        plt.show()
        plt.close(fig) 
        time.sleep(5)
        if os.path.exists('my_figure.jpeg'):
            telegram_bot_sendphoto('my_figure.jpeg', config.telegram_chat_id_ME)
    except Exception as e:
        print(f"download_data ERROR: \n\n {e}")
        telegram_bot_sendtext(f"*plot_and_save_fig ERROR:* \n\n _{e}_", config.telegram_chat_id_ME)


data = download_data(config.ticker, config.period, config.start, config.end)
calculate_features(data)
detect_spike_signals(data)
plot_and_save_fig(data)
if os.path.exists('my_figure.jpeg'):
    os.remove('my_figure.jpeg')

while True:
    try:
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
        try:
            if current_time.hour == 0 and current_time.minute == 20:
                plot_and_save_fig(data)
                if os.path.exists('my_figure.jpeg'):
                    os.remove('my_figure.jpeg')
        except Exception as e:
            print(f"Hawkeye zaman şartında hata oluştu: \n\n {e}")
            telegram_bot_sendtext(f"_(Hawkeye)_ *time condition error: * \n\n _{e}_", config.telegram_chat_id_ME)
            time.sleep(55)
    except Exception as e:
        print(f"error (line 163): \n\n {e}")
        telegram_bot_sendtext(f"_(Hawkeye)_ *error (line 164): * \n\n _{e}_", config.telegram_chat_id_ME)
