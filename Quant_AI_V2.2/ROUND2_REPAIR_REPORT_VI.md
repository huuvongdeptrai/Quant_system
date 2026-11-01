# VECTRA — Bản sửa lần 2 và kiểm chứng

Ngày 01/11/2026. Đầu vào: `VECTRA_repaired_2026-11-01(1).zip`.

Bản này sửa các nhánh logic tương ứng F01–F14 của báo cáo kiểm tra độc lập. Đây là bản bàn giao mã nguồn để tiếp tục kiểm chứng trên MT5 demo. Không gửi lệnh thật, không kết nối tài khoản người dùng và không tuyên bố đã hết mọi lỗi.

## Thay đổi theo từng phát hiện

| Mã | Hành vi sau sửa |
|---|---|
| F01 | Sửa pending qua `TradingCommandService`. Giữ SL/TP khi không truyền, chặn gỡ bảo vệ, kiểm tra tick size/geometry và risk/margin. Thay entry hoặc tăng loss budget phải qua admission; halt chỉ cho phép thay bảo vệ không tăng rủi ro. Có marker bền trước RPC và đối soát amendment chưa rõ kết quả. |
| F02 | FULL chuyển WAIT/BLOCKED khi ML ném exception; xác minh kiểu metadata/symbol/feature columns. Model hỏng không trở thành Standard Mode. |
| F03 | Intent chưa rõ kết quả giữ một suất capacity toàn tài khoản; khử trùng reservation theo symbol đã thấy trên broker để không cộng lại cùng reservation. Khóa admission vẫn là khóa trong một process. |
| F04 | Circuit breaker reset equity/date/streak/halt trong bộ nhớ theo cặp server/login rồi nạp state đúng scope DB. |
| F05 | Đối soát nối order ID/deals/position ID; dựng lại cả OPEN lẫn vòng đời đã đóng giữa hai poll. Chỉ giải phóng khi lịch sử đủ chứng cứ; phục hồi initial SL/strategy/order ID và holding policy đã lưu trong intent. Amendment chưa rõ vẫn giữ khóa. |
| F06 | Entry tự động mới lưu policy H=20 và timeframe. PositionGuard đếm nến broker hoàn tất, không đếm giờ lịch qua cuối tuần; time exit hoạt động cùng vòng quản lý vị thế, kể cả khi CB chặn entry. Lưu marker trước close để không gửi lặp khi mất phản hồi. |
| F07 | Close trả filled/remaining volume và position_closed. Yêu cầu đóng hết nhưng khớp một phần trả partial, cập nhật DB theo account; không báo đã flat. PLACED ở close vẫn UNKNOWN. |
| F08 | Ghép history bằng position identifier và đọc đúng order_type; ngăn dòng DB trùng cùng vị thế broker và sửa SELL bị mặc định BUY. |
| F09 | Calendar exception đặt valid=False; lỗi không bị biến thành lịch trống hợp lệ sau một lần tải thành công. |
| F10 | Phục hồi trạng thái partial/BE trước điều kiện chia lot; retry BE độc lập ngay cả khi volume còn lot tối thiểu. Bộ nhớ defense cũng reset khi đổi tài khoản. |
| F11 | Market PLACED là accepted/UNKNOWN, giữ order ID và reservation, chờ đối soát; không ghi REJECTED. Có test nhận diện order dù comment bị broker thay. |
| F12 | Pending dùng ORDER_FILLING_RETURN riêng với market. |
| F13 | Admission đọc session/timeframe/gate hiện tại; parse checkbox session từ settings khi không có runtime. Hot reload settings dùng chung admission lock; kiểm tra lại mode trước gửi. |
| F14 | Pipeline nghiên cứu mới mô phỏng lại tín hiệu, lot, cash và MTM cho từng portfolio sau lọc. Validation 2023–2024 chọn ngưỡng rồi ghi manifest khóa; test 2025–2026 chỉ chạy base và ngưỡng đã khóa. Model yearly chỉ dùng nhãn quá khứ, purge theo thời điểm nhãn đã biết và gap 5 nến broker ở ranh giới. |

## Kiểm thử

Kết quả cuối: **385 đạt, 6 bỏ qua, 0 lỗi assertion còn lại**, tổng 391 test trong 53 module. Lượt đầy đủ đầu có 1 timeout ở stress test 1.000 chu kỳ + tracemalloc. Chạy lại riêng, giữ nguyên mã và timeout 25 giây, đạt 2/2 test trong 20,01 giây. Log đầu và log rerun đều được giữ, không che lần timeout. Thêm 32 test so với bộ 359 test trong bản đầu vào.

Xem `verification_round2/summary.json` và XML/log từng module để biết kết quả cuối. Bộ kiểm thử chạy mỗi module một tiến trình Qt riêng, sử dụng MT5 stub và nguồn dữ liệu mạng bị chặn theo fixture offline. Bộ test mới là assertion cho hành vi an toàn, thay cho các assertion chẩn đoán lỗi của lần rà trước.

- `tests/test_review_findings.py`: các đường admission, amendment/halt, timeout/PLACED, capacity, đổi account, khôi phục pending, partial close, statistics, BE, calendar và time exit.
- `tests/test_walk_forward_replay.py`: sizing/cash sau lọc, MTM, purge/gap theo nến, thời điểm nhãn đã biết, hợp đồng OHLC M15 và fit bằng LightGBM thật.
- Một lần chạy toàn workflow bằng 2.000 nến tổng hợp và chiến lược fixture đã hoàn tất: harvest → train yearly bằng LightGBM → chọn ngưỡng trên validation → ghi manifest → hai portfolio test độc lập. Đây chỉ là kiểm tra chức năng; không phải dữ liệu thị trường hoặc bằng chứng lợi nhuận.
- Fixture partial-close cũ được bổ sung account và actual filled volume để kiểm tra đúng scope; giữ nguyên assertion volume còn lại.

Lệnh kiểm thử lại:

```bash
python -m pip install -r requirements-dev.txt
python tools/run_offline_tests.py --output verification_round2_new
```

Lệnh trên không kết nối MT5 thật. GUI desktop trên Windows cần được kiểm chứng riêng.

## Nghiên cứu/model: phần đã làm và phần chưa có dữ liệu

`research/run_expanding_walk_forward.py` và `research/reproduce_canonical_walk_forward.py` hiện dùng cùng `research/walk_forward_pipeline.py`.

```bash
python research/run_expanding_walk_forward.py --data completed_XAUUSD_M15.csv --output research/verified_walk_forward
```

Nguồn cần các cột time/open/high/low/close/tick_volume, thứ tự UTC tăng, nến M15 đã đóng. Có thể dùng `--mt5` thay `--data` trên máy đã cài MT5; tùy chọn này là yêu cầu lấy dữ liệu tường minh. Không tự lấy dữ liệu broker khi không yêu cầu.

Chỉ sau khi pipeline có dữ liệu thật và validation thành công mới export deployment model:

```bash
python research/export_trained_wyckoff_model.py --data completed_XAUUSD_M15.csv --output research/verified_walk_forward
```

Lệnh export ghi model và metadata mới tại storage/models, nên cần giữ bản cũ trước khi chạy. Model deployment fit sau evaluation được tách khỏi các model dùng để dự báo OOS. Ngưỡng có thể khác 0.38 sau khi sửa engine; tuyệt đối không chọn theo kết quả test. Nếu không ngưỡng validation nào đạt cap DD 10%, pipeline dừng thay vì chọn bằng OOS.

**Không retrain model trong gói này:** ZIP có cache equity/trade results nhưng thiếu OHLC gốc để tái chạy nghiên cứu thực. Model cũ thiếu feature version mới vẫn được giữ và bị gate chặn. Không gắn metadata mới vào trọng số cũ, không thay model bằng model train trên nến tổng hợp. Các biểu đồ/số liệu lịch sử có sẵn chưa được tái xác nhận sau sửa engine.

Gap 5 nến trong script là khoảng cách ở ranh giới training quá khứ/test tương lai; không mô tả nó thành khoảng embargo sau từng giao dịch. Nếu luận văn định nghĩa một quy tắc khác, cần đối chiếu và tái lập riêng trước khi công bố kết quả.

## Database và tương thích vận hành

Schema v2 được giữ; execution policy được lưu trong system_state theo account và position identifier, có transaction khi gắn vào trade. Database gốc trong ZIP không bị sửa, migration/backup cũ vẫn hoạt động khi khởi tạo. Không sửa ba hàng legacy thiếu giá đóng khi chưa có chứng cứ broker.

H=20 chỉ tự áp dụng cho vị thế tự động có policy bền đã lưu; không tự gắn quy tắc mới vào lệnh tay hoặc legacy chưa rõ nguồn. Time exit là tác vụ của worker, không phải lệnh thời gian chạy tại broker: khi worker dừng/offline sẽ được đánh giá lại sau khởi động, không bảo đảm đóng đúng thời điểm khi máy tắt.

Outcome UNKNOWN giữ khóa và có thể cần đối soát thủ công nếu broker không cung cấp đủ nhận diện/lịch sử. Không cam kết exactly-once với MT5. Chưa kiểm chứng nhiều process cùng tài khoản, netting/reversal phức tạp, disk full/power loss hay mọi biến thể broker. Chi phí và gap/slippage thực có thể khác giả định nghiên cứu.

## Cách dùng gói

Giải nén vào thư mục mới, không ghi đè bản đang vận hành. Đọc báo cáo này trước khi bật auto. Dùng MT5 demo để kiểm tra login/reconnect/đổi account, Start/Stop, Full/Semi/Manual, pending/modify/cancel, partial fills, emergency halt và restart.

`ROUND2_CHANGES.diff` và `verification_round2/changed_files.json` ghi các thay đổi so với ZIP đầu vào. Tài liệu `REPAIR_REPORT_VI.md` và `verification/` có sẵn thuộc vòng sửa trước; kết quả vòng này nằm ở `verification_round2/`.

## Cơ sở tham chiếu

- MetaQuotes: [Order Properties](https://www.mql5.com/en/docs/constants/tradingconstants/orderproperties), [Position Properties](https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties), [Return Codes](https://www.mql5.com/en/docs/constants/errorswarnings/enum_trade_return_codes).
- NautilusTrader: [Execution Reconciliation](https://nautilustrader.io/docs/latest/concepts/execution/reconciliation/).
- QuantConnect LEAN: [Order Events](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-events).

Đây là áp dụng nguyên tắc trạng thái/đối soát vào VECTRA, không phải tuyên bố đạt toàn bộ đặc tính của các hệ thống tham chiếu.
