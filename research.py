"""Auditable deterministic research signals. No live execution or financial advice."""
import math
import statistics

MIN_BARS = 60

def ema(values, n):
    a = 2 / (n + 1)
    out = values[0]
    for value in values[1:]: out += a * (value - out)
    return out

def validate(rows, now=None):
    errors = []
    if len(rows) < MIN_BARS: errors.append('حداقل ۶۰ کندل لازم است')
    previous = None
    for r in rows:
        try:
            t = int(r['time']); o, h, l, c, v = [float(r[k]) for k in ('open','high','low','close','volume')]
            if not all(math.isfinite(x) for x in (o,h,l,c,v)) or min(o,h,l,c) <= 0 or v < 0 or h < max(o,l,c) or l > min(o,h,c): errors.append('داده قیمت یا حجم نامعتبر است'); break
            if previous is not None and t - previous != 3600: errors.append('فاصله یا ترتیب کندل‌ها نامعتبر است'); break
            previous = t
        except (KeyError, TypeError, ValueError, OverflowError): errors.append('قالب کندل نامعتبر است'); break
    if rows and now is not None and (now - rows[-1]['time'] > 3*3600 or rows[-1]['time'] + 3600 > now): errors.append('آخرین کندل قدیمی یا ناتمام است')
    return errors

def indicators(rows):
    c=[r['close'] for r in rows]; p=c[-1]; vols=[r['volume'] for r in rows]
    changes=[c[i]-c[i-1] for i in range(-14,0)]; gain=sum(max(x,0) for x in changes)/14; loss=sum(max(-x,0) for x in changes)/14
    rsi=50 if gain == loss == 0 else (100 if loss == 0 else 100-100/(1+gain/loss))
    fast=ema(c[-60:],12); slow=ema(c[-60:],26)
    atr=sum(max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-rows[i-1]['close']),abs(rows[i]['low']-rows[i-1]['close'])) for i in range(-14,0))/14
    mean=statistics.mean(c[-20:]); sd=statistics.pstdev(c[-20:]); avgvol=statistics.mean(vols[-21:-1]); volratio=vols[-1]/avgvol if avgvol else 0
    return {'price':p,'change':(p/c[-25]-1)*100,'rsi':rsi,'ema12':fast,'ema26':slow,'atr':atr,'mean20':mean,'sd20':sd,'volume_ratio':volratio,'return5':(p/c[-6]-1)*100,'high20':max(r['high'] for r in rows[-21:-1]),'low20':min(r['low'] for r in rows[-21:-1])}

def evaluate(rows, now=None):
    errors=validate(rows,now)
    if errors: return {'valid':False,'errors':errors,'action':'NO_SIGNAL','agents':[]}
    x=indicators(rows); p=x['price']; atrpct=x['atr']/p*100
    def agent(name,role,status,detail,vote=0): return {'name':name,'role':role,'status':status,'detail':detail,'vote':vote}
    trend=1 if x['ema12']>x['ema26'] else -1 if x['ema12']<x['ema26'] else 0
    momentum=1 if 50<x['rsi']<70 else -1 if x['rsi']<40 or x['rsi']>=75 else 0
    breakout=1 if p>x['high20'] else -1 if p<x['low20'] else 0
    meanvote=1 if p<x['mean20']-2*x['sd20'] else -1 if p>x['mean20']+2*x['sd20'] else 0
    volumevote=(1 if x['return5']>0 else -1) if x['volume_ratio']>1.2 else 0
    pricevote=1 if x['return5']>1 else -1 if x['return5'] < -1 else 0
    agents=[
      agent('Trend architect','روند EMA','صعودی' if trend==1 else 'نزولی' if trend==-1 else 'خنثی',f"EMA12 {x['ema12']:.2f} / EMA26 {x['ema26']:.2f}",trend),
      agent('Momentum analyst','مومنتوم RSI','مثبت' if momentum==1 else 'منفی' if momentum==-1 else 'خنثی',f"RSI14 {x['rsi']:.1f}",momentum),
      agent('Volatility guard','نوسان ATR','بالا' if atrpct>3 else 'عادی',f'ATR / price {atrpct:.2f}%'),
      agent('Breakout watcher','شکست محدوده','شکست بالا' if breakout==1 else 'شکست پایین' if breakout==-1 else 'داخل محدوده',f"20H {x['low20']:.2f} – {x['high20']:.2f}",breakout),
      agent('Mean reversion','بازگشت به میانگین','انحراف بالا' if meanvote else 'عادی',f"SMA20 {x['mean20']:.2f} / σ {x['sd20']:.2f}",meanvote),
      agent('Volume analyst','حجم نسبی','بالا' if x['volume_ratio']>1.2 else 'عادی',f"Volume ratio {x['volume_ratio']:.2f}x",volumevote),
      agent('Price action','بازده کوتاه‌مدت','مثبت' if pricevote==1 else 'منفی' if pricevote==-1 else 'خنثی',f"Return 5H {x['return5']:+.2f}%",pricevote),
      agent('Market regime','وضعیت بازار','رونددار' if abs(x['ema12']-x['ema26'])/p>.005 else 'خنثی','فاصله نسبی EMAها'),
      agent('Risk manager','کنترل ریسک','رد' if atrpct>3 else 'پذیرش مشروط','فیلتر نوسان؛ اندازه موقعیت محاسبه نمی‌شود'),
      agent('Data quality','کیفیت داده','تأیید','ترتیب، پیوستگی، قیمت، حجم و تازگی در صورت دسترسی'),
      agent('Cost analyst','هزینه اجرا','فرضی','هزینه واقعی برای سیگنال محاسبه نمی‌شود'),
      agent('Liquidity analyst','نقدشوندگی','ناموجود','دفتر سفارش و اسپرد واقعی دریافت نمی‌شود'),
      agent('Derivatives analyst','مشتقات','ناموجود','فاندینگ، لیکوییدیشن و بهره باز دریافت نمی‌شود'),
      agent('News & sentiment','اخبار و احساسات','ناموجود','هیچ منبع خبری یا احساساتی متصل نیست'),
      agent('Grok strategist','تحلیل زبانی اختیاری','غیرفعال','غیرفعال؛ در این نسخه به مدل متصل نیست')]
    votes=sum(a['vote'] for a in agents); positives=sum(a['vote']>0 for a in agents); negatives=sum(a['vote']<0 for a in agents)
    action='WATCH_LONG' if positives>=3 and votes>=3 and atrpct<=3 else 'AVOID' if negatives>=3 and votes<=-3 else 'NO_SIGNAL'
    stop=max(0,p-2*x['atr']); target=p+3*x['atr']
    return {'valid':True,'errors':[],'action':action,'votes':votes,'positive':positives,'negative':negatives,'agents':agents,'indicators':x,'stop_reference':stop,'target_reference':target,'limitations':['صرفاً پژوهشی؛ هیچ تضمین یا احتمال موفقیتی وجود ندارد','داده‌های دفتر سفارش، اخبار و مشتقات در دسترس نیستند','حد ضرر و هدف فقط سطح محاسباتی‌اند و سفارش محافظ ثبت نمی‌شود']}

def backtest(rows, fee=.001, slip=.0005):
    errors=validate(rows)
    if errors: raise ValueError('؛ '.join(errors))
    if len(rows)<100: raise ValueError('حداقل ۱۰۰ کندل برای بک‌تست لازم است')
    cash=10000.; units=0.; entry=0.; trades=[]; curve=[]; pending=None; peak=cash; maxdd=0.
    # Decisions at a completed close are filled only at the next candle open.
    for i in range(MIN_BARS, len(rows)):
        bar=rows[i]
        if pending=='buy' and units==0:
            fill=bar['open']*(1+slip); budget=min(cash,1000.); units=budget/(fill*(1+fee)); entry=units*fill*(1+fee); cash-=entry
        elif pending=='sell' and units>0:
            fill=bar['open']*(1-slip); proceeds=units*fill*(1-fee); cash+=proceeds; trades.append({'entry_cost':entry,'exit_value':proceeds,'pnl':proceeds-entry}); units=0.; entry=0.
        pending=None
        equity=cash+units*bar['close']; peak=max(peak,equity); maxdd=max(maxdd,(peak-equity)/peak); curve.append(equity)
        if i<len(rows)-1:
            result=evaluate(rows[:i+1]); action=result['action']
            if units==0 and action=='WATCH_LONG': pending='buy'
            elif units>0 and action!='WATCH_LONG': pending='sell'
    # Open inventory is marked to market, not counted as a closed trade.
    total=(curve[-1]/10000-1)*100; wins=sum(t['pnl']>0 for t in trades)
    return {'initial_equity':10000,'final_equity':curve[-1],'return_pct':total,'max_drawdown_pct':maxdd*100,'closed_trades':len(trades),'win_rate_pct':wins/len(trades)*100 if trades else None,'open_position':units>0,'fee_per_side':fee,'slippage_per_side':slip,'bars':len(rows),'trades':trades[-20:],'warning':'نتیجه نمونه تاریخی است؛ شامل اسپرد پویا، نقدشوندگی، سفارش ناقص و مالیات نیست. معاملات باز با قیمت پایانی ارزش‌گذاری شده‌اند.'}
