import yfinance as yf
import datetime
import requests

import time

_MACRO_CACHE = {'report': None, 'timestamp': 0}

class MacroRegimeEngine:
    def __init__(self):
        self.VIX_RISK_OFF_THRESHOLD = 20.0
        self.tv_url = "https://economic-calendar.tradingview.com/events"
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Origin': 'https://www.tradingview.com',
            'Referer': 'https://www.tradingview.com/'
        }
    
    def _fetch_tv_historical(self, days_back=30):
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(days=days_back)
        params = {
            'from': start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            'to': now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            'countries': 'US'
        }
        try:
            res = requests.get(self.tv_url, params=params, headers=self.headers, timeout=5)
            if res.status_code == 200:
                return res.json().get('result', [])
        except:
            pass
        return []

    def get_market_state(self):
        try:
            vix_hist = yf.Ticker('^VIX').history(period='5d')['Close']
            dxy_hist = yf.Ticker('DX-Y.NYB').history(period='5d')['Close']
            
            if vix_hist.empty or dxy_hist.empty:
                return {'state': 'UNKNOWN', 'vix': 0, 'dxy': 0, 'reason': 'No data'}
                
            vix_current = vix_hist.iloc[-1]
            dxy_current = dxy_hist.iloc[-1]
            dxy_prev = dxy_hist.iloc[0]
            dxy_trend = 'UP' if dxy_current > dxy_prev else 'DOWN'
            
            state = 'Risk-Off' if vix_current >= self.VIX_RISK_OFF_THRESHOLD else 'Risk-On'
                
            return {
                'state': state,
                'vix': round(vix_current, 2),
                'dxy': round(dxy_current, 2),
                'dxy_trend': dxy_trend,
                'reason': f"VIX = {vix_current:.2f}. DXY xu huong {dxy_trend}."
            }
        except Exception as e:
            return {'state': 'UNKNOWN', 'vix': 0, 'dxy': 0, 'reason': str(e)}

    def get_monetary_state(self):
        try:
            tnx_hist = yf.Ticker('^TNX').history(period='5d')['Close']
            if tnx_hist.empty:
                return {'state': 'UNKNOWN', 'us10y': 0, 'reason': 'No data'}
            
            tnx_current = tnx_hist.iloc[-1]
            tnx_prev = tnx_hist.iloc[0]
            delta = tnx_current - tnx_prev
            
            if delta > 0.1: state = 'Hawkish (That chat)'
            elif delta < -0.1: state = 'Dovish (Noi long)'
            else: state = 'Neutral (Di ngang)'
                
            return {
                'state': state,
                'us10y': round(tnx_current, 3),
                'delta_5d': round(delta, 3),
                'reason': f"US10Y = {tnx_current:.3f}%, delta 5d = {delta:.3f}%"
            }
        except Exception as e:
            return {'state': 'UNKNOWN', 'us10y': 0, 'reason': str(e)}

    def get_economic_state(self):
        events = self._fetch_tv_historical(45)
        nfp_score = 0  # +1 tot, -1 xau
        pmi_score = 0
        unemp_score = 0
        
        for e in events:
            title = e.get('title', '').upper()
            actual = e.get('actual')
            forecast = e.get('forecast')
            if actual is None or forecast is None or actual == '' or forecast == '':
                continue
                
            try:
                act_val = float(actual)
                for_val = float(forecast)
            except:
                continue
                
            if 'NON FARM PAYROLLS' in title or 'NONFARM PAYROLLS' in title:
                nfp_score = 1 if act_val > for_val else -1
            elif 'PMI' in title and ('MANUFACTURING' in title or 'SERVICES' in title):
                pmi_score = 1 if act_val > 50 else -1
            elif 'UNEMPLOYMENT RATE' in title:
                unemp_score = 1 if act_val < for_val else -1  # That nghiep giam la tot

        total = nfp_score + pmi_score + unemp_score
        
        if total >= 1: state = 'Growth (Tang truong)'
        elif total <= -1: state = 'Recession (Suy thoai)'
        else: state = 'Recovery (Phuc hoi/Di ngang)'
        
        return {
            'state': state,
            'reason': f"Scoring - NFP:{nfp_score}, PMI:{pmi_score}, Unemp:{unemp_score}"
        }

    def generate_macro_report(self):
        return {
            'Market': self.get_market_state(),
            'Monetary': self.get_monetary_state(),
            'Economic': self.get_economic_state()
        }
