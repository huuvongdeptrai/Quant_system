import os
import re
import json
import asyncio
import redis
from telethon import TelegramClient, events
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

API_ID = os.getenv("TELE_API_ID")
API_HASH = os.getenv("TELE_API_HASH")
TARGET_CHAT = os.getenv("TELE_TARGET_CHAT", "").strip()
if not TARGET_CHAT:
    TARGET_CHAT = "@vnwallstreet"

chat_list = [c.strip() for c in TARGET_CHAT.split(",")]



if not API_ID or not API_HASH:
    logger.error("Vui lòng cấu hình TELE_API_ID và TELE_API_HASH trong file .env")
    exit(1)

# Connect to Redis
redis_host = "127.0.0.1" if not os.path.exists("/.dockerenv") else "quant_redis"
r = redis.Redis(host=redis_host, port=6379, db=0)

client = TelegramClient('quant_news_session', int(API_ID), API_HASH)

def extract_news_json(text: str) -> dict:
    text_lower = text.lower()
    
    # Từ khóa xác định tin Vĩ mô
    macro_keywords = ["cpi", "nfp", "payroll", "pmi", "gdp", "fomc", "rate", "bps", "inflation", "thực tế", "actual", "lãi suất", "thất nghiệp", "non-farm"]
    
    # Từ khóa của các quốc gia KHÔNG PHẢI MỸ (Dùng để loại trừ)
    exclude_keywords = ["anh ", " uk ", "boe", "châu âu", "ecb", "euro", "nhật", "boj", "jpy", "trung quốc", "pboc", "cny", "úc", "aud", "rba", "canada", "cad", "boc"]
    
    # Từ khóa xác nhận là MỸ (Nếu có thì chắc chắn lấy)
    us_keywords = ["mỹ", "hoa kỳ", "usd", "fed", "powell", "🇺🇸"]
    
    has_macro = any(k in text_lower for k in macro_keywords)
    has_exclude = any(k in text_lower for k in exclude_keywords)
    has_us = any(k in text_lower for k in us_keywords)
    
    if has_macro:
        # Nếu có từ khóa loại trừ (Vd: "CPI của Anh") mà KHÔNG có từ khóa Mỹ -> Bỏ qua
        if has_exclude and not has_us:
            return None
            
        return {
            "source": "TELEGRAM_LIVE",
            "raw_text": text,
            "is_high_impact": True
        }
    return None

@client.on(events.NewMessage(chats=chat_list))
async def handler(event):
    logger.info(f"Nhận được tin nhắn từ Telegram: {event.raw_text}")
    
    news_data = extract_news_json(event.raw_text)
    if news_data:
        logger.success("Phát hiện tin tức Kinh tế Thực tế (Actuals)! Đang bắn lên Event-Bus...")
        # Ghi log ra file để lưu trữ
        with open("data/news_actual.json", "w", encoding="utf-8") as f:
            json.dump({"actual": event.raw_text}, f, ensure_ascii=False)
            
        # Bắn tín hiệu qua Redis Pub/Sub
        r.publish('MACRO_NEWS', json.dumps(news_data))
        logger.info("Đã phát tín hiệu lên kênh MACRO_NEWS của Redis.")

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz

async def fetch_history_on_startup():
    logger.info("Đang đồng bộ dữ liệu Vĩ mô (Smart Sync) dựa trên Lịch kinh tế...")
    try:
        # Đọc lịch kinh tế từ XML
        xml_path = "data/ff_calendar.xml"
        if not os.path.exists(xml_path):
            logger.warning("Không tìm thấy Lịch kinh tế để đồng bộ.")
            return

        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        est_tz = pytz.timezone('US/Eastern')
        utc_tz = pytz.UTC
        now_utc = datetime.now(utc_tz)
        
        missing_events = []
        # Lọc các sự kiện quan trọng trong 30 ngày qua
        for event in root.findall('event'):
            if event.find('impact').text != 'High': continue
            
            date_str = event.find('date').text
            time_str = event.find('time').text
            
            # Bỏ qua các sự kiện All Day hoặc Tentative
            if not time_str or time_str == 'All Day' or time_str == 'Tentative':
                continue
                
            try:
                # Format: 09-02-2026 8:30am
                dt_str = f"{date_str} {time_str}"
                est_time = est_tz.localize(datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p"))
                utc_time = est_time.astimezone(utc_tz)
                
                # Nếu sự kiện đã diễn ra trong vòng 30 ngày qua
                if timedelta(hours=0) < now_utc - utc_time < timedelta(days=30):
                    title = event.find('title').text
                    missing_events.append((utc_time, title))
            except Exception:
                pass
                
        if not missing_events:
            logger.info("Không có sự kiện High Impact nào bị bỏ lỡ trong 30 ngày qua.")
            return
            
        logger.info(f"Phát hiện {len(missing_events)} sự kiện đã diễn ra. Tiến hành truy quét Telegram...")
        
        # Sắp xếp từ cũ đến mới
        missing_events.sort(key=lambda x: x[0])
        
        all_actuals = []
        for chat in chat_list:
            try:
                for ev_time, ev_title in missing_events:
                    logger.info(f"Tìm kiếm Actual cho: {ev_title} (Lúc {ev_time.strftime('%Y-%m-%d %H:%M')} UTC)")
                    # Quét mốc thời gian: Lấy 15 tin nhắn ngay sau lúc ra tin (tối đa trễ 4 tiếng)
                    search_end_time = ev_time + timedelta(hours=4)
                    found = False
                    async for msg in client.iter_messages(chat, offset_date=search_end_time, limit=20):
                        # Đảm bảo tin nhắn nằm trong khoảng từ lúc ra tin đến sau đó 4 tiếng
                        if msg.date < ev_time:
                            break # Hết tin trong khung giờ
                            
                        if msg.raw_text:
                            news_data = extract_news_json(msg.raw_text)
                            if news_data:
                                logger.success(f"-> Đã tìm thấy: {msg.raw_text[:50]}...")
                                all_actuals.append(msg.raw_text)
                                found = True
                                break
                    if not found:
                        logger.warning(f"-> Không tìm thấy tin tức trên Telegram cho mốc thời gian này.")
            except Exception as e:
                logger.error(f"Lỗi khi quét kênh {chat}: {e}")
                
        if all_actuals:
            # Gộp tất cả các Actuals tìm được và đẩy cho AI
            combined_actuals = "
---
".join(all_actuals)
            with open("data/news_actual.json", "w", encoding="utf-8") as f:
                json.dump({"actual": combined_actuals}, f, ensure_ascii=False)
            logger.success("Đã đồng bộ xong dữ liệu quá khứ. Đánh thức AI...")
            r.publish('MACRO_NEWS', json.dumps({"source": "SMART_SYNC", "raw_text": "Cập nhật hàng loạt"}))
            
    except Exception as e:
        logger.error(f"Lỗi khi Smart Sync: {e}")


async def main():
    await client.start()
    await fetch_history_on_startup()
    logger.info(f"Tele Scraper đang lắng nghe các kênh: {chat_list}...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
