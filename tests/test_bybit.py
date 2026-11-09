import unittest
from unittest.mock import patch
from bybit_public import BybitPublic

class BybitTests(unittest.TestCase):
 def test_markets_candles_and_metrics(self):
  adapter=BybitPublic(['BTC/USDT:USDT'])
  def api(path,params):
   if path=='instruments-info': return {'list':[{'contractType':'LinearPerpetual','settleCoin':'USDT','status':'Trading'}]}
   if path=='kline': return {'list':[['7200000','101','103','100','102','4','0'],['3600000','100','102','99','101','3','0']]}
   return {'list':[{'fundingRate':'0.0001','openInterest':'123'}]}
  with patch.object(adapter,'api',side_effect=api):
   self.assertTrue(adapter.load_markets()['BTC/USDT:USDT']['swap'])
   self.assertEqual(adapter.fetch_ohlcv('BTC/USDT:USDT')[0],[3600000,100.,102.,99.,101.,3.])
   self.assertEqual(adapter.fetch_funding_rate('BTC/USDT:USDT')['fundingRate'],.0001)
   self.assertEqual(adapter.fetch_open_interest('BTC/USDT:USDT')['openInterestAmount'],123)
 def test_rejects_invalid_symbol(self):
  with self.assertRaises(ValueError): BybitPublic.native('../bad')

if __name__=='__main__': unittest.main()
