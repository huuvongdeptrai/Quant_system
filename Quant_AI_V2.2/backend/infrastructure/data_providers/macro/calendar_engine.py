import requests
import datetime
import re
from loguru import logger


class CalendarEngine:
    def __init__(self):
        self.url = "https://economic-calendar.tradingview.com/events"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        }

    @staticmethod
    def classify_impact(raw_importance: int, title: str, country: str = "") -> int:
        """
        ĐÁNH GIÁ CHÍNH XÁC TẦM QUAN TRỌNG CỦA TIN TỨC VĨ MÔ (INSTITUTIONAL TIERING):
        - Tier 0 (0): Low Impact (Tin xám / vàng) - Khảo sát vùng, chỉ số thứ cấp, đấu thầu, ngày nghỉ.
                      -> KHÔNG BAO GIỜ dừng bot giao dịch.
        - Tier 1 (1): Medium Impact (Tin cam) - Báo cáo kinh tế thứ cấp (Doanh số bán lẻ, Nhà ở, Khảo sát niềm tin).
                      -> Hiển thị thông tin trực quan, không dừng bot.
        - Tier 2 (2): High Impact (Tin đỏ - Siêu bão vĩ mô) - CPI, Core PCE, NFP, Quyết định Lãi suất, FOMC, ISM, Phát biểu Thống đốc tối cao.
                      -> KÍCH HOẠT DỪNG GIAO DỊCH (Trading Halt) và Cơ chế phòng vệ vị thế trước tin.
        """
        title_upper = title.strip().upper()

        # 1. BẢO VỆ CHỐNG BÁO ĐỘNG GIẢ (NEGATIVE FILTERS / DEMOTIONS)
        # Khảo sát chi nhánh địa phương của Fed (Regional Fed: NY, Dallas, Philly, Kansas, Richmond, v.v.)
        regional_fed_patterns = [
            r'\bNY FED\b', r'\bNEW YORK FED\b', r'\bPHILLY FED\b', r'\bPHILADELPHIA FED\b',
            r'\bDALLAS FED\b', r'\bRICHMOND FED\b', r'\bKANSAS FED\b', r'\bCHICAGO FED\b',
            r'\bCLEVELAND FED\b', r'\bATLANTA FED\b', r'\bST\.? LOUIS FED\b', r'\bMINNEAPOLIS FED\b',
            r'\bSAN FRANCISCO FED\b'
        ]
        if any(re.search(rf, title_upper) for rf in regional_fed_patterns):
            return 0  # Low impact tuyệt đối

        # Các chỉ số và hoạt động thứ cấp không đủ sức gây biến động bão
        demote_to_low = [
            'SERVICES ACTIVITY', 'MANUFACTURING ACTIVITY', 'BUSINESS OUTLOOK',
            'SURVEY', 'MORTGAGE', 'WEEKLY', 'REDBOOK',
            'CRUDE OIL INVENTORIES', 'EIA', 'API', 'NATURAL GAS',
            'AUCTION', 'HOLIDAY', 'CAR REGISTRATIONS'
        ]
        if any(kw in title_upper for kw in demote_to_low):
            return 0

        # Dữ liệu nhà ở và cấp phép thứ cấp (không gây bão thị trường tiền tệ) hạ về Medium
        housing_data = [
            'EXISTING HOME SALES', 'NEW HOME SALES', 'BUILDING PERMITS', 'HOUSING STARTS', 'HOME SALES'
        ]
        if any(kw in title_upper for kw in housing_data):
            return 1

        # 2. ĐỊNH DANH SIÊU SỰ KIỆN TIER-1 (POSITIVE RED RULES)
        tier1_macro = [
            r'\bINTEREST RATE\b', r'\bRATE DECISION\b', r'\bRATE STATEMENT\b',
            r'\bFOMC STATEMENT\b', r'\bFOMC PRESS CONFERENCE\b', r'\bFOMC MEETING\b',
            r'\bFOMC ECONOMIC PROJECTIONS\b',
            r'\bECB MONETARY POLICY\b', r'\bECB PRESS CONFERENCE\b',
            r'\bBOE BANK RATE\b', r'\bBOE MONETARY POLICY\b',
            r'\bBOJ MONETARY POLICY\b',
            r'\bCPI\b', r'\bCORE CPI\b', r'\bPCE PRICE INDEX\b', r'\bCORE PCE\b', r'\bINFLATION RATE\b',
            r'\bNON-?FARM\b', r'\bNFP\b',
            r'\bGDP\b', r'\bGROSS DOMESTIC PRODUCT\b',
            r'\bISM MANUFACTURING\b', r'\bISM SERVICES\b'
        ]
        if any(re.search(p, title_upper) for p in tier1_macro):
            return 2

        # Phát biểu của Người đứng đầu NHTW tối cao (Chủ tịch / Thống đốc)
        top_leaders = [
            r'\bPOWELL\b', r'\bFED CHAIR\b',
            r'\bLAGARDE\b', r'\bECB PRESIDENT\b',
            r'\bBAILEY\b', r'\bBOE GOV\b',
            r'\bUEDA\b', r'\bBOJ GOV\b'
        ]
        if any(re.search(p, title_upper) for p in top_leaders):
            return 2

        # 3. BASELINE THEO XẾP HẠNG THỰC TẾ CỦA NHÀ CUNG CẤP (TRADINGVIEW)
        if raw_importance == 1:
            return 2
        elif raw_importance == 0:
            return 1
        else:
            return 0

    def fetch_events(self):
        # Lấy sự kiện chuẩn 1 Tuần (Từ Thứ 2 đến Chủ nhật của tuần hiện tại)
        now = datetime.datetime.now(datetime.timezone.utc)

        # Tìm Thứ 2 (Monday) của tuần này
        monday = now - datetime.timedelta(days=now.weekday())
        start_dt = monday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Tìm Chủ nhật (Sunday) của tuần này
        sunday = start_dt + datetime.timedelta(days=6)
        end_dt = sunday.replace(hour=23, minute=59, second=59, microsecond=0)

        start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_date = end_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        params = {
            "from": start_date,
            "to": end_date,
            "countries": "US,EU,GB,JP,AU,CA,CH,NZ",
        }

        try:
            res = requests.get(
                self.url, params=params, headers=self.headers, timeout=10
            )
            if res.status_code == 200:
                data = res.json()
                events = data.get("result", [])

                # MERGE VỚI DỮ LIỆU TELEGRAM LOCAL DB
                import json
                from pathlib import Path

                tele_db_path = (
                    Path(__file__).resolve().parents[3] / "data" / "local_calendar.json"
                )
                if tele_db_path.exists():
                    try:
                        with open(tele_db_path, "r", encoding="utf-8") as f:
                            tele_events = json.load(f)
                        events.extend(tele_events)
                        events.sort(key=lambda x: x.get("date", ""), reverse=True)
                    except Exception:
                        pass

                processed_events = []
                for e in events:
                    date_str = e.get("date", start_date)
                    try:
                        dt_utc = datetime.datetime.strptime(
                            date_str, "%Y-%m-%dT%H:%M:%S.000Z"
                        ).replace(tzinfo=datetime.timezone.utc)
                    except Exception:
                        try:
                            dt_utc = datetime.datetime.fromisoformat(
                                date_str.replace("Z", "+00:00")
                            )
                            if dt_utc.tzinfo is None:
                                dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
                        except Exception:
                            dt_utc = datetime.datetime.now(datetime.timezone.utc)

                    # Giờ hiển thị VN (UTC+7) trên giao diện người dùng
                    dt_vn = dt_utc.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
                    time_str = dt_vn.strftime("%d/%m %H:%M")

                    raw_imp = e.get("importance", -1)
                    title = e.get("title", "")
                    country = e.get("country", "")

                    # Đánh giá tầm quan trọng chính xác khoa học
                    imp = self.classify_impact(raw_imp, title, country)

                    processed_events.append(
                        {
                            "time": time_str,
                            "sort_key": dt_utc.timestamp(),  # Chuẩn UTC epoch timestamp (giây tuyệt đối)
                            "country": country,
                            "title": title,
                            "impact": imp,
                            "actual": str(e.get("actual", "")),
                            "forecast": str(e.get("forecast", "")),
                            "previous": str(e.get("previous", "")),
                        }
                    )

                processed_events.sort(key=lambda x: x["sort_key"])
                return processed_events
            else:
                return []
        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []
