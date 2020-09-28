import os
import csv
import datetime
import random

import asyncio
from enum import Enum
import urllib.parse as urlparse
from urllib.parse import parse_qs

import requests
from bs4 import BeautifulSoup


class Travian:
    class PageUrl(Enum):
        login = 'login.php'
        dorf = 'dorf1.php'
        bid = 'hero.php?t=4'

    AutoBidList = {'Cage': 170, 'Ointment': 35, 'Small Bandage': 12}

    def __init__(self, username, password):
        self.username = username
        self.password = password
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'}
        self.session = requests.Session()
        self.session.headers.update(header)
        self.travian = 'https://tse.asia.travian.com'
        self.bid_csv_header = ('time', 'amount', 'name', 'bids', 'silver', 'silver_unit', 'created_at')

    async def login(self):
        print("開始登入...")
        res = self.session.get(f'{self.travian}/{self.PageUrl.login.value}')
        soup = BeautifulSoup(res.text, 'html.parser')
        login_num = soup.find('input', attrs={'name': 'login'}).attrs['value']
        post_data = {'name': self.username, 'password': self.password, 's1': 'Login',
                     'w': '1440:900', 'login': login_num}
        self.session.post(f'{self.travian}/{self.PageUrl.login.value}', data=post_data)
        await asyncio.sleep(5)
        self.session.get(f'{self.travian}/{self.PageUrl.dorf.value}')

    async def go_bid_page(self) -> BeautifulSoup:
        print("跳轉至出價頁面...")
        res = self.session.get(f'{self.travian}/{self.PageUrl.bid.value}')
        return BeautifulSoup(res.text, 'html.parser')

    async def fetch_bid_price(self):
        print("獲取出價價格...")
        soup = await self.get_page(f'{self.travian}/{self.PageUrl.bid.value}&reload=auto')
        bid_table = soup.find('table')
        bid_tbody = bid_table.find('tbody')
        bid_trs = bid_tbody.find_all('tr')
        bid_result = []
        for bid_tr in bid_trs:
            amount, name = bid_tr.find(class_='name').text.strip().split('\u202c×\u202c')
            amount = int(amount.replace('\u202d\u202d', '').strip())
            name = name.strip()
            bids = int(bid_tr.find(class_='bids').text.strip())
            silver = int(bid_tr.find(class_='silver').text.strip())
            silver_unit = silver / amount
            time = int(bid_tr.find(class_='timer').attrs['value'])
            created_at = str(datetime.datetime.now()).split('.')[0]
            bid_a = bid_tr.find('a', class_='bidButton')
            bid_url = None
            if bid_a is not None:
                bid_url = f'{self.travian}{bid_a.attrs["href"]}'
            bid_result.append({'time': time, 'amount': amount, 'name': name,
                               'bids': bids, 'silver': silver, 'silver_unit': silver_unit,
                               'created_at': created_at, 'bid_url': bid_url})
        return bid_result

    async def get_page(self, url) -> BeautifulSoup:
        res = self.session.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        while soup.find('div', class_='innerLoginBox') is not None:
            print("嘗試重新登入...")
            await self.login()
            await asyncio.sleep(3)
            res = self.session.get(url)
            soup = BeautifulSoup(res.text, 'html.parser')
        return soup

    async def auto_bid(self, bids):
        print('判斷是否自動出價...')
        for bid in bids:
            if bid['name'] in self.AutoBidList:
                name = bid['name']
                silver_unit = bid['silver_unit']
                max_silver_unit = self.AutoBidList[name]
                amount = bid['amount']
                bid_silver = max_silver_unit * amount
                bid_url = bid['bid_url']
                time = bid['time']
            else:
                continue

            if silver_unit < max_silver_unit and bid_url and time <= 600:
                print(f"開始出價: {bid['name']} 嘗試價格為: {bid_silver}...")
                soup = await self.get_page(bid['bid_url'])
                submit_bit = soup.find('div', class_='submitBid')
                if submit_bit:
                    try:
                        bid_a = soup.find('a', class_='bidButton')
                        z_href = bid_a.attrs['href']
                        z = parse_qs(urlparse.urlparse(z_href).query)['z'][0]
                        a = parse_qs(urlparse.urlparse(bid_url).query)['a'][0]
                        post_data = {'page': 1, 'filter': '', 'action': 'but', 'z': z, 'a': a,
                                     'maxBid': bid_silver}
                        self.session.post(f'{self.travian}/hero.php?t=4', data=post_data)
                    except Exception as e:
                        print(f"出價失敗: {e}")
                else:
                    print("找不到出價提交")

    async def save_bid_to_csv(self, auto_bid=False):
        print("紀錄出價啟動...")
        if not os.path.exists('bid.csv'):
            print('找不到bid.csv，建立新檔案')
            with open('bid.csv', 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.bid_csv_header)
                writer.writeheader()
        while True:
            bid_result = await self.fetch_bid_price()
            _auto_bid_task = None
            if auto_bid:
                _auto_bid_task = asyncio.create_task(self.auto_bid(bid_result))
            min_time = 0
            with open('bid.csv', 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.bid_csv_header)
                for bid in bid_result:
                    if bid['time'] <= 30:
                        print(f"紀錄資料:{bid}")
                        writer.writerow({k: v for k, v in bid.items() if k in self.bid_csv_header})
                    else:
                        min_time = bid['time'] - 15
                        break
            min_time = max(min_time, 15)
            wait_time = min(random.randint(120, 300), min_time)
            print(f'waiting... {wait_time} seconds')
            await asyncio.sleep(wait_time)
            if _auto_bid_task:
                await _auto_bid_task


if __name__ == "__main__":
    t = Travian(username=os.environ['T_USER'], password=os.environ['T_PASS'])
    asyncio.run(t.save_bid_to_csv(auto_bid=True))
