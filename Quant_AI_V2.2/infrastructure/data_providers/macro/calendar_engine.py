import requests
import datetime
from loguru import logger

class CalendarEngine:
    def __init__(self):
        self.url = "https://economic-calendar.tradingview.com/events"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Origin': 'https://www.tradingview.com',
            'Referer': 'https://www.tradingview.com/'
        }

    def fetch_events(self):
        # Lấy sự kiện chuẩn 1 Tuần (Từ Thứ 2 đến Chủ nhật của tuần hiện tại)
        now = datetime.datetime.utcnow()
        
        # Tìm Thứ 2 (Monday) của tuần này
        monday = now - datetime.timedelta(days=now.weekday())
        start_dt = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Tìm Chủ nhật (Sunday) của tuần này
        sunday = start_dt + datetime.timedelta(days=6)
        end_dt = sunday.replace(hour=23, minute=59, second=59, microsecond=0)
        
        start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_date = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        params = {
            'from': start_date,
            'to': end_date,
            'countries': 'US,EU,GB,JP,AU,CA,CH,NZ'
        }

        try:
            res = requests.get(self.url, params=params, headers=self.headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                events = data.get('result', [])
                
                processed_events = []
                for e in events:
                    dt_utc = datetime.datetime.strptime(e.get('date', start_date), "%Y-%m-%dT%H:%M:%S.000Z")
                    dt_vn = dt_utc + datetime.timedelta(hours=7)
                    
                    time_str = dt_vn.strftime("%d/%m %H:%M")
                    
                    processed_events.append({
                        'time': time_str,
                        'sort_key': dt_vn.timestamp(),
                        'country': e.get('country', ''),
                        'title': e.get('title', ''),
                        'impact': e.get('importance', 0),
                        'actual': str(e.get('actual', '')),
                        'forecast': str(e.get('forecast', '')),
                        'previous': str(e.get('previous', ''))
                    })
                
                processed_events.sort(key=lambda x: x['sort_key'])
                return processed_events
            else:
                return []
        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []
