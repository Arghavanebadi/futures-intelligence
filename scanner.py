"""Background scanner for public USDT-margined perpetual data, no order execution."""
import copy, os, threading, time
import research

ROLES = [
 ('Trend architect','روند EMA'), ('Momentum analyst','مومنتوم RSI'),
 ('Volatility guard','نوسان ATR'), ('Breakout watcher','شکست محدوده'),
 ('Mean reversion','بازگشت به میانگین'), ('Volume analyst','حجم نسبی'),
 ('Price action','بازده کوتاه‌مدت'), ('Market regime','وضعیت بازار'),
 ('Risk manager','کنترل ریسک'), ('Data quality','کیفیت داده'),
 ('Cost analyst','هزینه اجرا'), ('Liquidity analyst','نقدشوندگی'),
 ('Derivatives analyst','مشتقات'), ('News & sentiment','اخبار و احساسات'),
 ('Grok strategist','تحلیل زبانی اختیاری')]

class FuturesScanner:
 def __init__(self, factory=None):
  self.factory=factory; self.lock=threading.RLock(); self.stop_event=threading.Event(); self.thread=None
  self.exchange_id=os.getenv('EXCHANGE_ID','bybit'); self.symbols=[s.strip() for s in os.getenv('FUTURES_SYMBOLS','BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT').split(',') if s.strip()][:20]
  try: self.interval=max(60,int(os.getenv('SCAN_INTERVAL_SECONDS','300')))
  except ValueError: self.interval=300
  self.data={'status':'starting','exchange':self.exchange_id,'last_scan':None,'next_scan':None,'results':[],'errors':[],'selected':None,'scope':'USDT perpetual swaps','activity':[],'progress':{'completed':0,'total':len(self.symbols),'symbol':None},'agents':[{'name':name,'role':role,'status':'در انتظار داده','detail':'هنوز تحلیل معتبر دریافت نشده است'} for name,role in ROLES]}
 def event(self, message, level='info'):
  with self.lock:
   self.data['activity'].insert(0,{'time':time.time(),'level':level,'message':message})
   self.data['activity']=self.data['activity'][:100]
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
   for agent in result['agents']:
    agent['status']='داده قدیمی'; agent['detail']='تا دریافت داده جدید نتیجه معتبر نیست'
  return result
 def run_once(self):
  now=time.time(); results=[]; errors=[]
  with self.lock:
   self.data['status']='scanning'; self.data['progress']={'completed':0,'total':len(self.symbols),'symbol':None}
  self.event('شروع دریافت داده بازار از '+self.exchange_id)
  try:
   ex=self.client(); markets=ex.load_markets()
   for symbol in self.symbols:
    with self.lock: self.data['progress']['symbol']=symbol
    self.event('بررسی قرارداد '+symbol)
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
     derivatives=next(agent for agent in data['agents'] if agent['name']=='Derivatives analyst')
     if data['funding_rate'] is not None or data['open_interest'] is not None:
      derivatives['status']='داده جزئی'; derivatives['detail']='Funding: '+str(data['funding_rate'])+' / OI: '+str(data['open_interest'])+'؛ در رأی استفاده نمی‌شود'
     results.append(data)
     self.event(symbol+' · نتیجه '+direction)
    except Exception as e:
     error=str(e)[:200]; errors.append({'symbol':symbol,'error':error}); self.event(symbol+' · '+error,'error')
    finally:
     with self.lock: self.data['progress']['completed']+=1
   candidates=[r for r in results if r['direction']!='WAIT']
   selected=max(candidates,key=lambda x:abs(x['votes'])) if candidates else None
   state={'status':'running' if results else 'error','exchange':self.exchange_id,'last_scan':time.time(),'next_scan':time.time()+self.interval,'results':results,'errors':errors,'selected':selected,'scope':'USDT perpetual swaps'}
  except Exception as e:
   state={'status':'error','exchange':self.exchange_id,'last_scan':None,'next_scan':time.time()+self.interval,'results':[],'errors':[{'symbol':'*','error':str(e)[:200]}],'selected':None,'scope':'USDT perpetual swaps'}
   self.event('دریافت داده ناموفق بود: '+str(e)[:200],'error')
  self.event('اسکن پایان یافت؛ '+str(len(results))+' بازار بررسی شد', 'info' if results else 'error')
  with self.lock:
   self.data.update(state); self.data['progress']['symbol']=None
   display=selected if results else None
   if not display and results: display=results[0]
   if display:
    self.data['agents']=copy.deepcopy(display['agents'])
   else:
    self.data['agents']=[{'name':name,'role':role,'status':'بدون داده','detail':'تحلیل اجرا نشد؛ اتصال یا ورودی در دسترس نیست'} for name,role in ROLES]
  return state
 def loop(self):
  while not self.stop_event.is_set():
   self.run_once(); self.stop_event.wait(self.interval)
 def start(self):
  if not self.thread or not self.thread.is_alive():
   self.thread=threading.Thread(target=self.loop,name='futures-scanner',daemon=True); self.thread.start()
 def stop(self): self.stop_event.set()
