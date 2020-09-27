import os
import csv
import datetime
import random

import asyncio
from enum import Enum

import requests
from bs4 import BeautifulSoup


class Travian:
    class PageUrl(Enum):
        login = 'login.php'
        dorf = 'dorf1.php'
        bid = 'hero.php?t=4'

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
        print("開始登入")
        res = self.session.get(f'{self.travian}/{self.PageUrl.login.value}')
        soup = BeautifulSoup(res.text, 'html.parser')
        login_num = soup.find('input', attrs={'name': 'login'}).attrs['value']
        post_data = {'name': self.username, 'password': self.password, 's1': 'Login',
                     'w': '1440:900', 'login': login_num}
        self.session.post(f'{self.travian}/{self.PageUrl.login.value}', data=post_data)
        await asyncio.sleep(5)
        self.session.get(f'{self.travian}/{self.PageUrl.dorf.value}')

    async def go_bid_page(self) -> BeautifulSoup:
        print("跳轉至出價頁面")
        res = self.session.get(f'{self.travian}/{self.PageUrl.bid.value}')
        return BeautifulSoup(res.text, 'html.parser')

    async def fetch_bid_price(self):
        print("獲取出價價格")
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
            created_at = str(datetime.datetime.now())
            bid_result.append({'time': time, 'amount': amount, 'name': name,
                               'bids': bids, 'silver': silver, 'silver_unit': silver_unit,
                               'created_at': created_at})
            print(f'時間:{time}, 數量:{amount}, 產品:{name}, 單價:{silver_unit}, 取得時間:{created_at}')
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

    async def save_bid_to_csv(self):
        print("紀錄出價啟動")
        if not os.path.exists('bid.csv'):
            print('找不到bid.csv，建立新檔案')
            with open('bid.csv', 'w') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.bid_csv_header)
                writer.writeheader()
        while True:
            bid_result = await self.fetch_bid_price()
            min_time = 0
            with open('bid.csv', 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.bid_csv_header)
                for bid in bid_result:
                    if bid['time'] <= 30:
                        print(f"紀錄資料:{bid}")
                        writer.writerow(bid)
                    else:
                        min_time = bid['time'] - 15
                        break
            min_time = max(min_time, 15)
            wait_time = min(random.randint(120, 300), min_time)
            print(f'waiting... {wait_time} seconds')
            await asyncio.sleep(wait_time)


if __name__ == "__main__":
    t = Travian(username=os.environ['T_USER'], password=os.environ['T_PASS'])
    asyncio.run(t.save_bid_to_csv())
