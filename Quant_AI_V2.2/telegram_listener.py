import os
import re
import json
import asyncio
from pathlib import Path
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from telethon import TelegramClient, events
from loguru import logger

# Load environment variables
load_dotenv()
API_ID = os.getenv("TELE_API_ID")
API_HASH = os.getenv("TELE_API_HASH")
TARGET_CHAT = os.getenv("TELE_TARGET_CHAT", "") 

PROJECT_ROOT = Path(__file__).parent.absolute()

if not API_ID or not API_HASH:
    logger.error("Vui lòng thêm TELE_API_ID và TELE_API_HASH vào file .env")
    exit(1)

client = TelegramClient('quant_session', int(API_ID), API_HASH)

def parse_telegram_message(text: str):
    actual_match = re.search(r'Thực tế:\s*([-\d\.]+)', text)
    forecast_match = re.search(r'Kỳ vọng:\s*([-\d\.]+)', text)
    prev_match = re.search(r'Trước đó:\s*([-\d\.]+)', text)
    
    return {
        'actual': actual_match.group(1) if actual_match else None,
        'forecast': forecast_match.group(1) if forecast_match else None,
        'previous': prev_match.group(1) if prev_match else None
    }

def match_event_by_numbers(tele_data: dict, xml_path: str):
    if not tele_data['forecast'] or not tele_data['previous']:
        return None
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for event in root.findall('event'):
            impact = event.find('impact').text
            if impact != 'High': continue
            
            xml_forecast = event.find('forecast').text or ""
            xml_prev = event.find('previous').text or ""
            
            def clean_num(s):
                match = re.search(r'([-\d\.]+)', s.replace(',', ''))
                return match.group(1) if match else None
                
            c_xml_for = clean_num(xml_forecast)
            c_xml_prev = clean_num(xml_prev)
            
            if c_xml_for == tele_data['forecast'] and c_xml_prev == tele_data['previous']:
                return event.find('title').text
        return None
    except Exception as e:
        logger.error(f"XML Match Error: {e}")
        return None

@client.on(events.NewMessage(chats=TARGET_CHAT if TARGET_CHAT else None))
async def handler(event):
    text = event.message.message
    if not text or "Thực tế:" not in text:
        return
        
    logger.info("Nhận được tin nhắn kinh tế mới. Đang xử lý...")
    data = parse_telegram_message(text)
    
    if data['actual'] and data['forecast']:
        xml_file = PROJECT_ROOT / "data" / "ff_calendar.xml"
        matched_title = match_event_by_numbers(data, xml_file)
        
        if matched_title:
            logger.success(f"Khớp thành công tin: {matched_title} | Actual: {data['actual']}")
            
            actuals_file = PROJECT_ROOT / "data" / "news_actual.json"
            actuals_dict = {}
            if actuals_file.exists():
                try:
                    with open(actuals_file, "r", encoding="utf-8") as f:
                        actuals_dict = json.load(f)
                except: pass
            
            actuals_dict[matched_title] = data['actual']
            with open(actuals_file, "w", encoding="utf-8") as f:
                json.dump(actuals_dict, f, indent=4)
                
            cache_file = PROJECT_ROOT / "data" / "macro_cache.json"
            if cache_file.exists():
                try: os.remove(cache_file)
                except: pass
                
            cfg_path = PROJECT_ROOT / "config" / "config.json"
            if cfg_path.exists():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as cfg_f:
                        cfg_data = json.load(cfg_f)
                    if "system" not in cfg_data: cfg_data["system"] = {}
                    cfg_data["system"]["force_macro_sync"] = True
                    with open(cfg_path, "w", encoding="utf-8") as cfg_f:
                        json.dump(cfg_data, cfg_f, indent=4)
                except: pass
                
            logger.info("Đã bắn tín hiệu Force Sync. Lõi AI đang được kích nổ!")
        else:
            logger.warning(f"Không thể khớp tin nhắn với Lịch kinh tế: {data}")

async def main():
    logger.info("Khởi động Lõi Nghe Lén Telegram...")
    await client.start()
    logger.success("Đã kết nối Telegram thành công! Đang chờ tin tức nổ...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
