import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = 'https://push2.eastmoney.com/api/qt/'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
CST = timezone(timedelta(hours=8))

def get(path, params):
    url = BASE + path + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.load(response)
    if payload.get('rc') != 0 or not isinstance(payload.get('data'), dict):
        raise RuntimeError(f'API response invalid: {payload}')
    return payload['data']

def board(kind):
    data = get('clist/get', {'pn':1,'pz':100,'po':1,'np':1,'fltt':2,'invt':2,'fid':'f3','fs':f'm:90+t:{kind}', 'fields':'f12,f14,f2,f3,f6,f8'})
    return {'total':data.get('total'), 'top': [{'code':x.get('f12'),'name':x.get('f14'),'change_pct':x.get('f3'),'turnover_cny':x.get('f6'),'turnover_rate_pct':x.get('f8')} for x in data.get('diff',[])]}

def stock(secid):
    d=get('stock/get', {'secid':secid,'fields':'f57,f58,f43,f44,f45,f46,f47,f48,f60,f170','fltt':2,'invt':2})
    return {'code':d.get('f57'),'name':d.get('f58'),'price':d.get('f43'),'change_pct':d.get('f170'),'high':d.get('f44'),'low':d.get('f45'),'turnover_cny':d.get('f48')}

def main():
    result={'collected_at':datetime.now(CST).isoformat(), 'timezone':'Asia/Shanghai', 'source':'Eastmoney public web API (unofficial)', 'market_data_timestamp':None, 'note':'Source response has no verified exchange timestamp; data may be delayed or stale.', 'industry':board(2), 'concept':board(3), 'watchlist':[stock('0.300364'),stock('1.603533')]}
    Path('data').mkdir(exist_ok=True)
    Path('data/latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Collected',len(result['industry']['top']),'industry boards,',len(result['concept']['top']),'concept boards and',len(result['watchlist']),'stocks')

if __name__=='__main__':
    main()
