import json
import time
import sys
import os
import random
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from core.mt5_safe import mt5
from core.ai.decision_gate import DecisionGate
from openai import OpenAI

# ----------------- CONFIGURATION -----------------
TOTAL_SAMPLES = 1000
SYMBOLS = ['XAUUSD', 'EURUSD'] # Giới hạn 2 cặp
MODEL_NAME = 'gemma-4-26b-a4b-it'
# -------------------------------------------------

gemini_key = os.environ.get('GEMINI_API_KEY')
if not gemini_key:
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('GEMINI_API_KEY'):
                    gemini_key = line.split('=')[1].strip().strip('"').strip("'")
                    break

if not gemini_key:
    print("LOI: Can GEMINI_API_KEY")
    exit(1)

client = OpenAI(
    api_key=gemini_key,
    base_url='https://generativelanguage.googleapis.com/v1beta/openai/'
)

DYNAMIC_CONTEXTS = [
    "Thanh khoản thị trường bình thường.",
    "Thanh khoản thấp, thị trường di chuyển chậm.",
    "Chuẩn bị công bố tin tức mạnh (High Impact News).",
    "Thị trường vừa trải qua một đợt quét thanh khoản (Liquidity Sweep).",
    "Phiên Á, độ biến động cực thấp.",
    "Phiên Mỹ, dòng tiền tổ chức đang hoạt động mạnh."
]

def build_system_prompt():
    return "Bạn là một AI Trading Quant xuất sắc. Giải thích TẠI SAO quyết định giao dịch được đưa ra dựa trên dữ liệu. Trả lời 100% bằng TIẾNG VIỆT, ngắn gọn, phân tích trực diện rủi ro. Viết logic 4 bước vào thẻ <thought>. Cuối cùng trả về chuỗi JSON thô, KHÔNG dùng thẻ markdown."

def generate_sample(symbol, date_str, curriculum_type):
    gate = DecisionGate()
    
    price_info = gate._get_price_position(symbol)
    htf_bias = gate._get_htf_bias(symbol)
    macro_bias = gate._get_macro_bias()
    
    if not price_info:
        price_info = {'position': 'MIDDLE', 'price': 100, 'resistance': 110, 'support': 90}
        
    ict_signal = random.choice(['BUY', 'SELL'])
    market_context = random.choice(DYNAMIC_CONTEXTS)
    
    # NORMALIZATION (Chuan hoa gia)
    price = price_info['price']
    res = price_info['resistance']
    sup = price_info['support']
    
    dist_to_res = ((res - price) / price) * 100 if price != 0 else 0
    dist_to_sup = ((price - sup) / price) * 100 if price != 0 else 0
    
    # --- CURRICULUM LOGIC ---
    if curriculum_type == 'TECH_ONLY':
        macro_bias = "Không có dữ liệu Vĩ mô"
    elif curriculum_type == 'MACRO_ONLY':
        htf_bias = "Không xác định"
        price_info['position'] = "UNKNOWN"
        ict_signal = "NONE"
    
    gate_eval = gate.evaluate(symbol, ict_signal)
    final_decision = gate_eval['decision']
    python_reason = gate_eval['reason']
    
    if curriculum_type == 'MACRO_ONLY':
        if 'BULLISH' in macro_bias.upper(): final_decision = 'BUY'
        elif 'BEARISH' in macro_bias.upper(): final_decision = 'SELL'
        else: final_decision = 'WAIT'
        python_reason = f"Đánh giá hoàn toàn dựa trên vĩ mô: {macro_bias}"
    elif curriculum_type == 'TECH_ONLY':
        if final_decision != 'WAIT':
            python_reason = f"Đánh giá hoàn toàn dựa trên kỹ thuật. Tín hiệu: {ict_signal}, HTF: {htf_bias}, Giá: {price_info['position']}"

    user_input = f"### BỐI CẢNH (Context):\n"
    user_input += f"- Tài sản: {symbol} ({date_str})\n"
    user_input += f"- Môi trường giao dịch: {market_context}\n"
    user_input += f"- Vĩ mô: {macro_bias}\n"
    user_input += f"- Khung thời gian lớn (D1+H4): {htf_bias}\n"
    
    if price_info['position'] != "UNKNOWN":
        user_input += f"- Vị trí giá: {price_info['position']} (Cách Kháng cự: {dist_to_res:.2f}%, Cách Hỗ trợ: {dist_to_sup:.2f}%)\n"
    else:
        user_input += f"- Vị trí giá: KHÔNG XÁC ĐỊNH\n"
        
    user_input += f"- Tín hiệu ngắn hạn (M15): {ict_signal}\n\n"
    
    user_input += f"### YÊU CẦU:\n"
    user_input += f"Quyết định chốt: **{final_decision}**.\n"
    user_input += f"Lý do cốt lõi: {python_reason}\n\n"
    user_input += f"Viết biện luận 4 bước (tiếng Việt) vào thẻ <thought> BẢO VỆ quyết định '{final_decision}'. Tránh lặp văn, tập trung vào quản trị rủi ro dựa trên 'Môi trường giao dịch' và 'Vị trí giá'. Sau đó in JSON:\n"
    user_input += '{\n  "decision": "' + final_decision + '",\n  "reason": "<Lý do chuyên nghiệp>",\n  "wait_for": "<Điền nếu WAIT>"\n}'
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{'role': 'user', 'content': user_input}],
            temperature=0.4
        )
        assistant_reply = response.choices[0].message.content.strip()
        
        if assistant_reply.startswith('```json'):
            assistant_reply = assistant_reply.replace('```json', '', 1).strip()
        if assistant_reply.endswith('```'):
            assistant_reply = assistant_reply[:-3].strip()
            
        return {
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": assistant_reply}
            ]
        }
    except Exception as e:
        print(f"Loi API: {e}")
        return None

if __name__ == '__main__':
    if not mt5.initialize():
        print("Khong ket noi MT5. Fallback data.")
        
    out_file = "gemma_quant_dataset.jsonl"
    
    print(f"Thu thap {TOTAL_SAMPLES} mau bang {MODEL_NAME} (Curriculum + Normalization)...")
    
    success_count = 0
    with open(out_file, 'a', encoding='utf-8') as f:
        for i in range(TOTAL_SAMPLES):
            sym = random.choice(SYMBOLS)
            rand_val = random.random()
            if rand_val < 0.3:
                curr_type = 'TECH_ONLY'
            elif rand_val < 0.6:
                curr_type = 'MACRO_ONLY'
            else:
                curr_type = 'MIXED'
                
            print(f"Data #{i+1}/{TOTAL_SAMPLES} cho {sym} ({curr_type})...")
            sample = generate_sample(sym, datetime.now().strftime('%Y-%m-%d'), curr_type)
            
            if sample:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
                success_count += 1
            
            time.sleep(2.1)
                
    print(f"Xong! Luu {success_count} mau vao {out_file}")
