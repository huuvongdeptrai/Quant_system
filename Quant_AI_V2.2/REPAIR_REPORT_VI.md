# VECTRA — Bản sửa và biên bản kiểm thử

Ngày: 01/11/2026. Nguồn: `Quant_AI_V2.2(3).zip`. Đây là bản sửa để tiếp tục kiểm chứng trên demo; chưa xác nhận vận hành live.

## Các thay đổi đã thực hiện

| Nhóm | Hành vi sau sửa |
|---|---|
| Luồng mở lệnh | GUI Full-auto chỉ hiển thị; worker và các đường market/pending đi qua `TradingCommandService`. Auto cần worker đang chạy và đúng Full-auto; Semi cần phê duyệt. Stop/khóa khẩn cấp được kiểm tra trước gửi. Phê duyệt đề xuất hết hạn bị chặn. |
| Rủi ro | Lot 0/âm/NaN/Inf và ngân sách dưới lot tối thiểu không được nâng lên để gửi. Floor theo volume step; chuẩn hóa stop trước tính lot, hậu kiểm broker loss/margin, tính phần deviation dự kiến. Giá chuyển bất lợi sau sizing bị từ chối để tính lại. Gate chỉ giảm sizing một lần. |
| Kết quả broker | Không tự gửi lại khi mất phản hồi/timeout/kết nối không rõ. Intent được ghi bền trước RPC; trạng thái chưa rõ giữ khóa theo symbol qua restart. Partial fill dùng giá, volume, position identifier thực tế; không đoán order ticket là position ticket. |
| Database | Schema v2, WAL + synchronous FULL; transaction ngắn. Scope theo server/login, khóa giao dịch theo account/ticket. Replay open không ghi đè lịch sử CLOSED. Có order intents, broker deals khử trùng và execution events. Cập nhật không tìm thấy hàng trả thất bại. Migration có backup và giữ bảng cũ. |
| Recovery | API None khác tài khoản trống. Đóng sổ cần exit deal thật, gồm các khoản phí trong PnL. Đổi position ticket được đối chiếu identifier. Recovery cần xác minh account; vị thế mồ côi không được lấy SL đang trailing làm SL ban đầu. |
| Quản lý vị thế | Trailing/BE giữ mức SL bảo vệ tốt hơn. Phòng vệ tin dùng initial SL đã lưu; ghi trạng thái từng bước và không chốt lại khi kết quả partial close chưa rõ. Friday close giới hạn lệnh bot, hoạt động cả khi entry bị circuit breaker khóa. |
| Dữ liệu/gate | Tín hiệu dùng nến đóng; MT5 timestamp giữ UTC. Sửa VWAP/phương sai trọng số theo phiên UTC. Snapshot trạng thái được sao chép; None có thể xóa trạng thái. Macro stale không được dùng để tự động duyệt entry. Lỗi model/thiếu warmup không biến thành xác suất 1. |
| ML/research | Dùng chung builder feature có version; threshold export thống nhất 0.38; bổ sung purge theo thời điểm kết thúc giao dịch tại ranh giới năm trong các script walk-forward đã sửa. Model thiếu metadata đúng feature version bị chặn. |
| Backtest | Canonical event engine chỉ thấy quá khứ, fill sau tín hiệu; gap xuyên SL theo giá mở khả dụng và slippage, nến chạm hai barrier xử lý SL trước. Có H=20, thanh lý cuối dữ liệu, MTM equity và phí. Fast screening được sửa tương ứng nhưng vẫn là xấp xỉ theo tín hiệu vector hóa. Sharpe theo lịch; không annualize theo số lệnh. |
| Khác | Watchdog dừng có thể đánh thức ngay; headless không ghi đè timeframe đã lưu khi không truyền tùy chọn. AST guard được mô tả đúng là linter cho code tin cậy. Bổ sung dependencies và bộ chạy test offline. |

## Kết quả kiểm thử

Kết quả cuối: **353 đạt, 6 bỏ qua, 0 thất bại / 0 lỗi**, tổng 359 test trong 51 module; tất cả tiến trình test kết thúc bình thường. Có 38 test hồi quy mới. Sau bổ sung kiểm tra ghi state bền vững, đã chạy lại riêng 5 module database/risk/recovery liên quan; lượt tích hợp bổ sung đạt 61 test.

6 test bỏ qua: 1 test cần MT5/broker thật, 5 test cần system tray trong desktop session. Compile các module backend/frontend/test/headless thành công; một số script nghiên cứu cũ có SyntaxWarning về chuỗi escape. Chi tiết từng module và lý do skip nằm trong XML/log kèm theo.

Lệnh tái chạy toàn bộ bộ test offline:

```bash
python -m pip install -r requirements-dev.txt
python tools/run_offline_tests.py --output verification
```

Bộ chạy tách từng module thành tiến trình riêng để quản lý vòng đời QApplication. Có giới hạn thời gian và coi exit code bất thường/native crash là thất bại, kể cả khi các assertion đã qua. `VECTRA_OFFLINE_TESTS=1` thay MT5 bằng stub không thể giao dịch và chặn nguồn dữ liệu mạng trong tests; không thay broker adapter sản xuất.

Lần chạy toàn bộ trong một tiến trình bằng `pytest tests/` trên môi trường Linux/offscreen đã có native crash ở vòng đời Qt. Vì vậy không báo rằng cách chạy một tiến trình này đã đạt. Chứng cứ hoàn tất được lấy từ bộ chạy từng module; cần kiểm tra lại GUI desktop thật trên Windows.

Các test cũ được cập nhật ở những hợp đồng thay đổi có chủ đích: không round lot lên, không retry mù, GUI Full-auto không tự dispatch, MT5 timestamp UTC, model cũ cần retrain. Các assertion yêu cầu chiến lược có lãi/Sharpe cao trên dữ liệu ngẫu nhiên được thay bằng đối chiếu accounting, MTM drawdown và công thức chỉ số; không dùng kỳ vọng lợi nhuận để chứng nhận phần mềm đúng. Fixture ownership/history/account được bổ sung dữ liệu broker nhất quán.

Kiểm thử hồi quy mới bao gồm lot không hợp lệ, loss budget sau đổi stop, adverse quote, auto mode/Stop/halt, intent đồng thời và restart, partial fill, account/ticket trùng, migration, replay CLOSED, mất dữ liệu API, phí/PnL của partial exits, gap, H20, cuối dữ liệu, feature/gate lỗi, macro stale, immutable snapshots, BE retry, partial close không rõ và phê duyệt hết hạn. Xem `tests/test_repair_regressions.py`.

## Kiểm chứng database gốc

Đã thử migration trên bản sao của DB trong ZIP:

- `integrity_check = ok`, `user_version = 2`, backup trước migration tồn tại.
- Giữ đủ 7 giao dịch và 23.435 snapshot equity; bảng legacy giữ nguyên.
- Sau chuyển đổi: 3 OPEN, 1 CLOSED, 3 UNRESOLVED. Ba hàng CLOSED cũ có close_price bằng 0 được giữ để đối soát, không tạo giá/PnL broker giả.
- Dữ liệu cũ mang scope `legacy`; không tự gán vào account mới khi không có bằng chứng.
- File DB và cấu hình gốc trong gói bàn giao được giữ nguyên byte. Schema mới được áp dụng khi chương trình khởi tạo DB; file `.pre_v2.bak` được tạo trước migration.
- SHA256 DB gốc: `f4186aa973abd5eaaac1a29b4582cee35da39abd0cbd92b2cb19bcc42957ef83`.

## Phần còn phải làm / giới hạn

1. **Model Wyckoff đi kèm là model cũ, thiếu feature version mới nên bị chặn khi dùng gate có ML.** Không gắn metadata mới vào trọng số cũ để giả định tương thích. Cần dataset OHLC cố định, retrain, validation rồi export model v2. Giữ file model cũ làm chứng cứ; hiệu suất và biểu đồ luận văn cũ chưa được tái xác nhận.
2. Chưa có MT5 Windows/demo để kiểm tra real fills, requote, suffix symbol, netting/hedging, đổi account lúc đang quản lý lệnh, reconnect và broker có sửa/loại comment. Chưa gửi lệnh thật hoặc kết nối tài khoản người dùng trong đợt sửa.
3. Đối soát intent chỉ tự giải phóng khi có bằng chứng broker. Nếu broker loại comment và không liên kết được ID, intent tiếp tục bị khóa để kiểm tra thủ công. Không cam kết exactly-once từ MT5; không tự kết luận không có lịch sử là bị từ chối.
4. Cần fault injection đầy đĩa, mất điện đúng thời điểm, DB lock kéo dài và đo tải trên máy mục tiêu. SQLite vẫn chỉ có một writer mỗi thời điểm; chưa thay thành kiến trúc writer service/event store đầy đủ trong kế hoạch. Admission lock trong tiến trình không chứng minh capacity an toàn khi chạy nhiều instance bot đồng thời.
5. Chi phí commission dự kiến chưa có biểu phí broker tổng quát trong live admission. Risk budget đã xét stop/deviation dự kiến nhưng lỗ thực có thể vượt do phí, gap và slippage. Backtest vẫn dùng giả định contract multiplier/spread, cần hiệu chỉnh theo broker/tick thật.
6. Force Defense hiện dùng cơ chế phòng vệ trước tin; chưa thiết kế lại thành chức năng phòng vệ vô điều kiện mọi thời điểm. AST linter không phải sandbox OS; chưa cô lập code không tin cậy.
7. Cần kiểm tra luồng desktop bằng thao tác thật (login/demo, đổi account, Start/Stop, Full/Semi/Manual, pending/cancel/modify, kill switch, restart), forward test và dữ liệu ngoài mẫu trước khi cân nhắc live. Kết quả offline không phải xác nhận lợi nhuận hay toàn bộ lỗi đã hết.

## Cách dùng bản bàn giao

Giải nén vào thư mục riêng, lưu bản gốc trước khi dùng. Đọc phần giới hạn model trước khi bật auto. Thử migration trên bản sao database, đối soát scope legacy với broker rồi kiểm tra tài khoản demo Windows. Không chạy hai instance cùng account để coi bộ test này là bảo đảm capacity liên tiến trình.

Trong thư mục `verification/`: báo cáo số lượng, XML JUnit, log từng module, kiểm chứng migration, danh sách file thay đổi và patch để review. Các báo cáo nghiên cứu có sẵn trong project được giữ làm tài liệu lịch sử, chưa cập nhật số hiệu suất sau sửa.

## Cơ sở tham khảo đã dùng trong kế hoạch

- QuantConnect LEAN: [Order Events](https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-events), [Trade Fill Models](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts).
- NautilusTrader: [Execution Reconciliation](https://nautilustrader.io/docs/latest/concepts/execution/reconciliation/).
- MetaQuotes: [Position Properties](https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties).
- SQLite: [ON CONFLICT](https://www.sqlite.org/lang_conflict.html), [PRAGMA](https://www.sqlite.org/pragma.html), [Backup API](https://www.sqlite.org/backup.html).
- Bailey, Borwein, López de Prado, Zhu: [The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
- López de Prado: [Triple Barrier / Purging](https://www.quantresearch.org/Innovations.htm).

Đây là áp dụng nguyên tắc thiết kế từ các nguồn trên vào VECTRA, không phải tuyên bố đã sao chép hoặc đạt toàn bộ đặc tính của các hệ thống tham chiếu.
