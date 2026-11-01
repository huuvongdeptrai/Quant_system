import sys
from pathlib import Path

path = Path("Kho_Do_An/Quant_AI_V2.2/docs/thesis/chuong_3_thiet_ke_he_thong.md")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = "Việc bổ sung mô phỏng hoa hồng và trượt giá nhằm giảm thiểu thiên kiến lạc quan từ giả định khớp lệnh hoàn hảo không ma sát."
replacement = (
    "Việc bổ sung mô phỏng hoa hồng và trượt giá nhằm giảm thiểu thiên kiến lạc quan từ giả định khớp lệnh hoàn hảo không ma sát. "
    "*Lưu ý phương pháp luận về thiết lập thực nghiệm chuẩn mực:* Mô hình phân phối chuẩn cắt cụt ngẫu nhiên được hỗ trợ trực tiếp trong giao diện Tab Backtest phục vụ khảo sát Monte Carlo; "
    "trong khi đó, toàn bộ các thực nghiệm kiểm chứng chính thức ngoài mẫu Walk-Forward tại Chương 4 được cấu hình theo kịch bản kiểm thử áp lực định chế với mức trượt giá cố định thận trọng là "
    "20.0 points ($0.20$ USD/oz, tương đương $20.0$ USD/lot) trọn gói cho mỗi chu kỳ giao dịch vòng tròn Round-Trip, kết hợp phí hoa hồng $7.0$ USD/lot để bảo đảm tính tất định và khả năng tái lập độc lập."
)

if target in text:
    text = text.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("Successfully updated Chapter 3 line 452!")
else:
    print("Target not found in Chapter 3!")
