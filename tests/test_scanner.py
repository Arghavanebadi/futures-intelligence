import copy, math, time, unittest
from unittest.mock import patch
import research
from scanner import FuturesScanner

def sample():
 now=int(time.time()//3600)*3600
 rows=[]
 for i in range(120):
  price=100+i*.2+math.sin(i)*.1
  rows.append({'time':now-(120-i)*3600,'open':price-.1,'high':price+.3,'low':price-.3,'close':price,'volume':100+i})
 return rows
class FakeExchange:
 has={'fetchFundingRate':True,'fetchOpenInterest':True}
 def load_markets(self): return {'BTC/USDT:USDT':{'swap':True,'linear':True,'settle':'USDT','active':True}}
 def fetch_ohlcv(self,*args,**kwargs): return [[r['time']*1000,r['open'],r['high'],r['low'],r['close'],r['volume']] for r in sample()]
 def fetch_funding_rate(self,s): return {'fundingRate':.0001}
 def fetch_open_interest(self,s): return {'openInterestAmount':42}
class Tests(unittest.TestCase):
 def test_roles_and_data_validation(self):
  rows=sample();result=research.evaluate(rows,now=time.time());self.assertTrue(result['valid']);self.assertEqual(len(result['agents']),15)
  rows[-1]['close']=float('nan');self.assertFalse(research.evaluate(rows)['valid'])
 def test_gap_and_stale(self):
  rows=sample();rows[-1]['time']-=3600;self.assertFalse(research.evaluate(rows)['valid'])
  self.assertFalse(research.evaluate(sample(),now=time.time()+86400)['valid'])
 def test_scanner_contract_filter_and_metrics(self):
  scan=FuturesScanner(factory=FakeExchange);scan.symbols=['BTC/USDT:USDT','BAD/USDT:USDT'];result=scan.run_once()
  self.assertEqual(result['status'],'running');self.assertEqual(len(result['results']),1);self.assertEqual(len(result['errors']),1);self.assertEqual(result['results'][0]['funding_rate'],.0001);self.assertEqual(result['results'][0]['open_interest'],42)
 def test_scanner_stale_clears_selection(self):
  scan=FuturesScanner(factory=FakeExchange);scan.data.update(status='running',last_scan=time.time()-3600,selected={'symbol':'BTC'})
  self.assertEqual(scan.get()['status'],'stale');self.assertIsNone(scan.get()['selected'])
 def test_provider_failure_never_produces_signal(self):
  def fail(): raise RuntimeError('unavailable')
  scan=FuturesScanner(factory=fail);r=scan.run_once();self.assertEqual(r['status'],'error');self.assertIsNone(r['selected'])
  state=scan.get();self.assertEqual(len(state['agents']),15);self.assertTrue(all(a['status']=='بدون داده' for a in state['agents']));self.assertTrue(any(e['level']=='error' for e in state['activity']))
 def test_progress_and_agent_results(self):
  scan=FuturesScanner(factory=FakeExchange);scan.symbols=['BTC/USDT:USDT'];scan.run_once();state=scan.get()
  self.assertEqual(state['progress']['completed'],1);self.assertEqual(len(state['agents']),15)
  self.assertEqual(next(a for a in state['agents'] if a['name']=='Derivatives analyst')['status'],'داده جزئی')
 def test_incomplete_candle_is_not_used(self):
  rows=sample(); now=time.time(); rows[-1]['time']=int(now//3600)*3600
  self.assertFalse(research.evaluate(rows,now=now)['valid'])
 def test_backtest_next_open(self):
  rows=sample(); calls=[]
  def signal(history): calls.append(len(history));return {'action':'WATCH_LONG' if len(history)==61 else 'NO_SIGNAL'}
  with patch('research.evaluate',side_effect=signal): result=research.backtest(rows)
  self.assertEqual(calls[0],61);self.assertEqual(result['closed_trades'],1)
if __name__=='__main__':unittest.main()
