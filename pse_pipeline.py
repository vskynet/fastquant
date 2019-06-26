#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 25 19:48:03 2019

@author: enzoampil
"""

import requests
from datetime import datetime
import pandas as pd
from string import digits
import lxml.html as LH


stock_table = pd.DataFrame(
        columns=[
        'Company Name', 'Stock Symbol', 'Sector', 'Subsector', 'Listing Date',
        'company_id', 'security_id'
        ]
)

for p in range(1,7):
    print(str(p)+' out of '+str(7-1)+' pages', end='\r')

    r = requests.post(url = 'http://edge.pse.com.ph/companyDirectory/search.ax', data = {'pageNo':p})
    table = LH.fromstring(r.text)
    page_df = (pd.concat([pd.read_html(r.text)[0], 
               pd.DataFrame({'attr':table.xpath('//tr/td/a/@onclick')[::2]})], 
              axis=1)
     .assign(company_id = lambda x: x['attr'].apply(lambda s: s[s.index('(')+2:s.index(',')-1]))
     .assign(security_id = lambda x: x['attr'].apply(lambda s: s[s.index(',')+2:s.index(')')-1]))
     .drop(['attr'], axis=1)
    )
    
    stock_table = stock_table.append(page_df)
    stock_table.to_csv('stock_table.csv', index=False)
    
def date_to_epoch(date):
    return int(datetime.strptime(date, '%Y-%m-%d').timestamp())

def remove_digits(string):
    remove_digits = str.maketrans('', '', digits)
    res = string.translate(remove_digits)
    return res
    
def get_disclosures_json(symbol, from_date, to_date):
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://www.investagrams.com/Stock/PSE:JFC',
        'Origin': 'https://www.investagrams.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        'Content-Type': 'text/plain; charset=utf-8',
    }
    from_date_epoch = date_to_epoch(from_date)
    to_date_epoch = date_to_epoch(to_date)
    params = (
        ('symbol', 'PSE:{}'.format(symbol)),
        ('from', from_date_epoch),
        ('to', to_date_epoch),
        ('resolution', 'D'), # Setting D (daily) by default
    )
    
    response = requests.post('https://webapi.investagrams.com/InvestaApi/TradingViewChart/timescale_marks', headers=headers, params=params)
    results = response.json()
    return results

def disclosures_json_to_df(disclosures):
    disclosure_dfs = {}
    for disc in ['D', 'E']:
        filtered_examples = [ex for ex in disclosures if ex['label'] == disc]
        additional_feats_df = pd.DataFrame([dict([tuple(item.split(':')) for item in ex['tooltip'] if ':' in item]) for ex in filtered_examples])
        main_df = pd.DataFrame(filtered_examples)[['id', 'time', 'color', 'label']]
        combined = pd.concat([main_df, additional_feats_df], axis=1)
        combined['time'] = pd.to_datetime(combined.time, unit='s')
        if 'Total Revenue' in combined.columns.values:
            combined['Revenue Unit'] = combined['Total Revenue'].apply(lambda x: remove_digits(x).replace('.', ''))
            combined['Total Revenue'] = combined['Total Revenue'].str.replace('B', '').str.replace('M', '').astype(float)
            # Net income is followed by a parenthesis which corresponds to that quarter's YoY growth
            combined['NI Unit'] = combined['Net Income'].apply(lambda x: remove_digits(x).replace('.', ''))
            combined['Net Income Amount'] = combined['Net Income'].str.replace('B', '').str.replace('M', '').apply(lambda x: x.split()[0]).astype(float)
            combined['Net Income YoY Growth (%)'] = combined['Net Income'].apply(lambda x:str(x).replace('(', '').replace(')', '').replace('%', '').split()[1])
        disclosure_dfs[disc] = combined
    return disclosure_dfs

def get_disclosures_df(symbol, from_date, to_date):
    disclosures = get_disclosures_json(symbol, from_date, to_date)
    disclosures_dfs = disclosures_json_to_df(disclosures)
    return disclosures_dfs

def get_pse_data(symbol, start_date, end_date, stock_table=stock_table, disclosures=False):

    data = {'cmpy_id': stock_table['company_id'][stock_table['Stock Symbol'] == symbol].values[0], 
            'security_id': stock_table['security_id'][stock_table['Stock Symbol'] == symbol].values[0], 
            'startDate': datetime.strptime(start_date, '%Y-%m-%d').strftime('%m-%d-%Y'), 
            'endDate': datetime.strptime(end_date, '%Y-%m-%d').strftime('%m-%d-%Y')}

    r = requests.post(url = "http://edge.pse.com.ph/common/DisclosureCht.ax", json = data)
    df = pd.DataFrame(r.json()['chartData']).set_index('CHART_DATE')
    df.index = pd.to_datetime(df.index)
    if disclosures:
        disclosures = get_disclosures_df(symbol, start_date, end_date)
        return df, disclosures
    return df

def get_company_disclosures(symbol, from_date, to_date):
    cookies = {
        'BIGipServerPOOL_EDGE': '1427584378.20480.0000',
        'JSESSIONID': 'oAO1PNOZzGBoxIqtxy-32mVx.server-ep',
    }
    
    headers = {
        'Origin': 'http://edge.pse.com.ph',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'en-PH,en-US;q=0.9,en;q=0.8',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': '*/*',
        'Referer': 'http://edge.pse.com.ph/announcements/form.do',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive',
    }
    
    data = {
      'companyId': '',
      'keyword': symbol,
      'tmplNm': '',
      'fromDate': from_date,
      'toDate': to_date
    }
    
    response = requests.post('http://edge.pse.com.ph/announcements/search.ax', headers=headers, cookies=cookies, data=data)
    return response

if __name__ == '__main__':
    SYMBOL = 'JFC'
    DATE_START = '2010-01-01'
    DATE_END = '2019-01-01'
    print('Testing', SYMBOL, 'from', DATE_START, 'to', DATE_END, '...')
    df_dict = get_disclosures_df(SYMBOL, DATE_START, DATE_END)
    dfd = df_dict['D']
    dfe = df_dict['E']
    print(dfd.head())
    print(dfe.head())