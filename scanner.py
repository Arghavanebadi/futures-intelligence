"""Background scanner for public USDT-margined perpetual data, no order execution."""
import copy, os, threading, time
import research

class FuturesScanner:
 def __init__(self, factory=None):
  self.factory=factory; self.lock=threading.RLock(); self.stop_event=threading.Event(); self.thread=None
  self.exchange_id=os.getenv('EXCHANGE_ID','bybit'); self.symbols=[s.strip() for s in os.getenv('FUTURES_SYMBOLS','BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT').split(',') if s.strip()][:20]
  try: self.interval=max(60,int(os.getenv('SCAN_INTERVAL_SECONDS','300')))
  except ValueError: self.interval=300
  self.data={'status':'starting','exchange':self.exchange_id,'last_scan':None,'next_scan':None,'results':[],'errors':[],'selected':None,'scope':'USDT perpetual swaps'}
 def client(self):
  if self.factory: return self.factory()
  if self.exchange_id=='bybit':
   from bybit_public import BybitPublic
   return BybitPublic(self.symbols)
  try: import ccxt
  except ImportError: raise ValueError('برای این صرافی باید کتابخانه CCXT نصب شود') from None
  if self.exchange_id not in ccxt.exchanges: raise ValueError('صرافی در CCXT پشتیبانی نمی‌شود')
  return getattr(ccxt,self.exchange_id)({'enableRateLimit':True,'timeout':15000,'options':{'defaultType':'swap'}})
 def get(self):
  with self.lock:
   result=copy.deepcopy(self.data)
  # Never present stale results as actionable.
  if result['last_scan'] and time.time()-result['last_scan']>max(2*self.interval,900):
   result['status']='stale'; result['selected']=None; result['results']=[]
  return result
 def run_once(self):
  now=time.time(); results=[]; errors=[]
  try:
   ex=self.client(); markets=ex.load_markets()
   for symbol in self.symbols:
    try:
     market=markets.get(symbol)
     if not market or not market.get('swap') or not market.get('linear') or market.get('settle')!='USDT' or market.get('active') is False: raise ValueError('قرارداد دائمی خطی USDT فعال نیست')
     raw=ex.fetch_ohlcv(symbol,'1h',limit=120)
     rows=[{'time':int(r[0]/1000),'open':r[1],'high':r[2],'low':r[3],'close':r[4],'volume':r[5]} for r in raw if r[0]/1000+3600<=now]
     analysis=research.evaluate(rows,now=now)
     if not analysis['valid']: raise ValueError('; '.join(analysis['errors']))
     indicators=analysis['indicators']; p=indicators['price']; atr=indicators['atr']; direction='LONG' if analysis['action']=='WATCH_LONG' else 'SHORT' if analysis['action']=='AVOID' else 'WAIT'
     # Direction is a research label, not an order or a performance guarantee.
     data={'symbol':symbol,'direction':direction,'votes':analysis['votes'],'positive':analysis['positive'],'negative':analysis['negative'],'price':p,'stop':p-2*atr if direction=='LONG' else p+2*atr if direction=='SHORT' else None,'target':p+3*atr if direction=='LONG' else max(0,p-3*atr) if direction=='SHORT' else None,'atr':atr,'rsi':indicators['rsi'],'last_candle':rows[-1]['time'],'agents':analysis['agents'],'funding_rate':None,'open_interest':None,'missing':[]}
     for capability,method,field,key in [('fetchFundingRate','fetch_funding_rate','fundingRate','funding_rate'),('fetchOpenInterest','fetch_open_interest','openInterestAmount','open_interest')]:
      if ex.has.get(capability):
       try:
        value=getattr(ex,method)(symbol).get(field)
        if isinstance(value,(int,float)) and __import__('math').isfinite(value): data[key]=value
        else: data['missing'].append(key)
       except Exception: data['missing'].append(key)
      else: data['missing'].append(key)
     data['missing']+=['order_book','news','whale_attribution']
     results.append(data)
    except Exception as e: errors.append({'symbol':symbol,'error':str(e)[:200]})
   candidates=[r for r in results if r['direction']!='WAIT']
   selected=max(candidates,key=lambda x:abs(x['votes'])) if candidates else None
   state={'status':'running' if results else 'error','exchange':self.exchange_id,'last_scan':time.time(),'next_scan':time.time()+self.interval,'results':results,'errors':errors,'selected':selected,'scope':'USDT perpetual swaps'}
  except Exception as e:
   state={'status':'error','exchange':self.exchange_id,'last_scan':None,'next_scan':time.time()+self.interval,'results':[],'errors':[{'symbol':'*','error':str(e)[:200]}],'selected':None,'scope':'USDT perpetual swaps'}
  with self.lock: self.data=state
  return state
 def loop(self):
  while not self.stop_event.is_set():
   self.run_once(); self.stop_event.wait(self.interval)
 def start(self):
  if not self.thread or not self.thread.is_alive():
   self.thread=threading.Thread(target=self.loop,name='futures-scanner',daemon=True); self.thread.start()
 def stop(self): self.stop_event.set()
