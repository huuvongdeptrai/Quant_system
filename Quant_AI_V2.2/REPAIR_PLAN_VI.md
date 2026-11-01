# VECTRA — Kế hoạch sửa chữa và đánh giá database
Ngày: 01/11/2026
Nguồn: Quant_AI_V2.2(3).zip. Trạng thái: kế hoạch đề xuất; chưa sửa mã nguồn hay migrate dữ liệu thật.

## 1. Kết luận và phạm vi bằng chứng

Giữ SQLite cho bản desktop cục bộ. Vấn đề chính là mô hình dữ liệu, nhận diện giao dịch, kiểm soát trạng thái và các đường thực thi khác nhau; chuyển hệ quản trị không tự sửa các vấn đề đó.

Đã kiểm tra file backend/database/quant_system.db trong ZIP bằng kết nối chỉ đọc:
- Kích thước: 1.355.776 byte.
- PRAGMA integrity_check: ok.
- Journal mode: WAL; user_version: 0.
- trades: 7 bản ghi, gồm 3 OPEN và 4 CLOSED.
- 3/4 bản ghi CLOSED có close_price=0. Đây là dữ liệu bất thường, chưa đủ bằng chứng xác định nguyên nhân hoặc khẳng định PnL của chúng sai.
- account_equity: 23.435 bản ghi; system_state: 5 bản ghi.
- Chưa có index phục vụ lọc trạng thái/thời gian. Truy vấn equity theo thời gian hiện quét bảng và dùng temporary B-tree để sắp xếp.
- foreign_key_check không trả lỗi nhưng schema hiện không có foreign key, nên kết quả này không chứng minh quan hệ giao dịch đã được bảo vệ.
- Timestamp equity trùng giây không tự nó là lỗi; vấn đề là thiếu độ chính xác, sequence và phạm vi tài khoản khi cần tái dựng thứ tự.

Các kiểm thử DB thực hiện trên database tạm, không ghi vào DB gốc. Bộ test nguyên bản và terminal MT5 chưa chạy trong môi trường này vì thiếu phụ thuộc. Không khẳng định đã xác minh toàn bộ dữ liệu của broker.

## 2. Cơ sở lựa chọn giải pháp

| Nguồn chính thức/nghiên cứu | Điều tham khảo | Áp dụng cho VECTRA |
|---|---|---|
| QuantConnect LEAN — Order Events | Theo dõi thay đổi trạng thái, fill và partial fill bằng sự kiện | Tách yêu cầu đặt lệnh, order, deal và vị thế; cập nhật theo kết quả broker |
| NautilusTrader — Execution/Reconciliation | Đối soát trạng thái nội bộ với báo cáo venue lúc khởi động và trong runtime; kết quả chưa xác định không đồng nghĩa bị từ chối | Lưu UNKNOWN và khóa mở mới trong phạm vi còn bất định; không retry mù |
| MetaQuotes — Position Properties | POSITION_IDENTIFIER ổn định hơn POSITION_TICKET trong các tình huống đổi ticket; order/deal/position là các định danh khác nhau | Lưu riêng các ID, dùng identifier cho liên kết lịch sử và ticket hiện tại cho thao tác vị thế |
| SQLite — Conflict, WAL, PRAGMA, Backup | REPLACE xóa dòng xung đột; WAL có một writer; NORMAL khác FULL về durability khi mất điện | UPSERT có điều kiện, transaction ngắn, writer được quản lý, backup nhất quán |
| QuantConnect — Fill Models | Mô hình fill phụ thuộc loại lệnh, giá/khối lượng, spread và slippage | Sửa gap-through-stop, fill ở thời điểm có thể thực thi và partial fills; hiệu chỉnh riêng cho CFD MT5 |
| Bailey, Borwein, López de Prado, Zhu — PBO | Lựa chọn từ nhiều cấu hình có thể tạo overfitting; holdout đơn thuần không loại mọi thiên lệch lựa chọn | Ghi lại các thử nghiệm, giữ test tách biệt, không chọn lại ngưỡng bằng test |
| López de Prado — Triple Barrier / Purging & Embargo | Nhãn có khoảng thời gian sống; overlap cần được xử lý | Lưu label_start/label_end; purge theo thời điểm nhãn kết thúc; định nghĩa embargo đúng theo cách chia mẫu |

Đây là lựa chọn thiết kế cho phạm vi VECTRA, không phải tuyên bố sao chép toàn bộ kiến trúc hay đã đạt chuẩn của các nền tảng trên. Không cần thêm Kafka, microservice hoặc PostgreSQL để sửa bản desktop.

## 3. Lỗi và thiếu sót database

| ID | Mức ưu tiên | Bằng chứng | Sửa chữa |
|---|---|---|---|
| DB-01 | P0 | record_open_trade dùng INSERT OR REPLACE. Test: CLOSED được ghi mở lại -> OPEN, pnl=0, close_price=0, close_time rỗng | Chuyển sang thao tác idempotent có điều kiện; sự kiện OPEN cũ không được ghi đè trạng thái cuối |
| DB-02 | P0 | trades không có account/server; system_state và account_equity cũng thiếu phạm vi tài khoản đầy đủ | accounts(server, login) và account_id ở mọi dữ liệu liên quan; không tự gán lịch sử cũ cho tài khoản hiện tại |
| DB-03 | P0 | Lưu result.order thành ticket rồi dùng chung cho vị thế/lịch sử; schema không có order_id, deal_id, position_identifier riêng | Tách ID; đối soát bằng định danh chính thức; hỗ trợ ticket thay đổi, netting và hedging theo phạm vi được công bố |
| DB-04 | P0 | Không có intent bền vững trước broker call và không có giao dịch SQL gom cập nhật event/order/position | Lưu intent + reservation trước gửi; sự kiện broker và projection cập nhật cùng transaction |
| DB-05 | P1 | update_trade_volume và record_close_trade trả True dù ticket không tồn tại | Kiểm tra rowcount/trạng thái/version, phân biệt APPLIED, ALREADY_APPLIED, NOT_FOUND, CONFLICT, STORAGE_ERROR |
| DB-06 | P1 | Partial close chỉ ghi đè volume còn lại, không có bảng deals | Lưu từng deal duy nhất; giữ original_volume và current_volume; PnL gồm phí mở/đóng, swap, fee |
| DB-07 | P1 | Test cho phép volume=-1; schema không CHECK trạng thái/khối lượng | Validation tại service + CHECK/NOT NULL/UNIQUE/FK đúng ngữ nghĩa; tiền/giá không nhận NaN/Infinity |
| DB-08 | P1 | Singleton có thể bị đổi db_path bởi lần khởi tạo khác; test tham chiếu cũ chuyển sang DB mới | Repository/service gắn bất biến với đường dẫn; inject dependency; không sửa đường dẫn ngầm |
| DB-09 | P1 | Thời gian local mặc định lẫn thời gian UTC từ recovery; chưa có sequence event | event_time_utc_ms, received_time_utc_ms, sequence nội bộ; quy định trading_day/timezone riêng |
| DB-10 | P1/P2 | user_version=0, chưa có migration framework/index theo truy vấn; ghi telemetry dùng chung đường truy cập | Migration có version/checksum; index theo truy vấn; telemetry batch/retention; đo lock latency |
| DB-11 | P1 | Code dùng WAL + synchronous=NORMAL | Chọn FULL cho journal giao dịch cần bền vững trước mất điện, đo ảnh hưởng; không gọi NORMAL là nguyên nhân hỏng file |
| DB-12 | P1 | 3 CLOSED có giá đóng 0 | Đưa vào danh sách cần đối soát, tìm deal từ đúng tài khoản; thiếu bằng chứng thì giữ UNRESOLVED, không điền giả |

Không suy ra SQLite bị hỏng từ close_price=0. integrity_check đánh giá cấu trúc file, không xác nhận tính đúng nghiệp vụ. WAL/NORMAL vẫn giữ tính nhất quán nhưng có thể mất transaction mới commit sau mất điện/OS crash; đây là quyết định durability cần được công bố.

## 4. Schema đích đề xuất

| Bảng | Vai trò / ràng buộc chủ đạo |
|---|---|
| accounts | UNIQUE(server, login), currency, margin_mode |
| order_intents | client_order_id duy nhất theo account; signal identity, strategy/config/model version, desired action, risk snapshot, trạng thái |
| broker_orders | UNIQUE(account_id, broker_order_ticket); requested/filled/remaining volume, status, liên kết intent |
| broker_deals | UNIQUE(account_id, broker_deal_ticket); order ticket, position_identifier, entry/type, price, volume, profit/commission/swap/fee, thời gian |
| positions | UNIQUE(account_id, position_identifier); current_position_ticket, current_volume, average price, SL/TP, owner, version; initial risk theo setup/leg |
| execution_events | Event append-only, sequence, broker reference, payload, event/received time; xử lý lại không cộng fill hai lần |
| risk_state | Phạm vi account + ngày giao dịch + chính sách; halt, baseline, reservation, config version |
| equity_snapshots | account_id, UTC ms, balance/equity/margin, sequence; index(account_id, timestamp) |
| schema_migrations | Version, checksum, thời gian áp dụng |

Bảng trades cũ giữ dạng legacy hoặc view tương thích trong thời gian chuyển đổi; không xóa ngay. Index cụ thể tạo theo truy vấn thực tế: positions(account_id,status,symbol), orders(account_id,status), deals(account_id,position_identifier,time), equity(account_id,time). Bật foreign_keys trên mỗi connection có sử dụng schema mới.

Giá và tiền phải có chính sách precision theo instrument/currency. Không coi việc dùng REAL tự nó chứng minh lỗi; giữ raw broker payload và chuẩn hóa số dùng cho đối soát theo quy tắc rõ ràng. Dữ liệu chưa biết dùng NULL/UNRESOLVED, không mặc định 0 như dữ liệu đã xác minh.

Netting có thể gộp nhiều nguồn giao dịch trên một symbol; magic của một position không đủ chứng minh toàn bộ exposure thuộc một strategy. Bản đầu nên công bố chỉ hỗ trợ hedging hoặc độc quyền symbol/tài khoản cho bot; nếu cho phép giao dịch hỗn hợp trên netting cần ledger phân bổ theo deal/leg và các kiểm thử riêng.

## 5. Kế hoạch triển khai theo phụ thuộc

### Giai đoạn 0 — Bảo toàn và chốt hợp đồng hành vi
- Backup bằng SQLite Backup API; kiểm tra bản backup và khả năng restore.
- Lưu hash ZIP/code/data/config/model, giữ dữ liệu cũ chỉ đọc.
- Viết đặc tả Full/Semi/Manual, Stop/Flatten, quyền sở hữu vị thế, trading day, data-unavailable và UNKNOWN.
- Lưu các ca lỗi tái hiện thành regression tests trước khi sửa; không sửa test để hợp thức hóa bug.
Nghiệm thu: có thể tái hiện lỗi trên môi trường giả lập và restore bản sao; không yêu cầu kết nối tài khoản thật.

### Giai đoạn 1 — Chặn các hành vi mở lệnh sai
- Mọi đường GUI, worker, manual approval và headless đi qua TradingCommandService; GUI chỉ phát command/hiển thị.
- FULL: tự thực thi; SEMI: đề xuất có expiry + token duyệt một lần; MANUAL: chỉ thực thi hành động người dùng yêu cầu.
- Stop khóa tiếp nhận lệnh mới trước; Flatten khóa admission, xử lý/cancel lệnh đang bay, thanh lý rồi đối soát. Tác vụ giảm rủi ro tiếp tục khi khóa entry.
- Từ chối zero/negative/nonfinite lot. Mất account/position/tick data phải chặn entry mới trong phạm vi cần dữ liệu đó.
- Bổ sung lock/reservation trước dispatch; kiểm tra lại halt và generation token ngay trước gửi.
Nghiệm thu: bot dừng hoặc bị halt không mở lệnh từ bất kỳ đường nào; SEMI không tự gửi; lot=0 không thành min lot.

### Giai đoạn 2 — Migration database và sổ giao dịch
- Loại REPLACE trên lịch sử; cố định DB path; kiểm tra kết quả ghi.
- Migrate theo schema đích, FK/unique/check và transaction.
- Chuyển legacy vào vùng chưa xác minh account nếu thiếu mapping; đối soát 3 bản ghi giá đóng 0 bằng lịch sử broker khi có nguồn hợp lệ.
- Lưu intent/reservation bền vững trước broker call. Không giữ transaction SQL trong lúc chờ mạng.
Nghiệm thu: replay không đổi CLOSED thành OPEN; account A không ảnh hưởng B; ticket không có không báo APPLIED; migration/rollback/restore được thử trên bản sao.

### Giai đoạn 3 — Execution state machine và reconciliation
- Phân biệt local validation failure, definitive broker rejection, filled/partial và UNKNOWN.
- Requote/price-change: chỉ thử lại sau kiểm tra lại quote, SL và risk; None/connection/unknown: đối soát trước, không gửi lại mù.
- Có client ID nội bộ, broker IDs, durable event journal; comment chỉ là dấu hỗ trợ, không giả định broker bảo toàn hoặc đảm bảo exactly-once.
- Lấy volume/price/deal thực tế; startup recovery và runtime reconciliation có watermark/lookback chồng lặp, dedup theo deal ID.
- Khi DB ghi thất bại sau broker fill: giữ unresolved, chặn entry liên quan, phục hồi bằng broker history; không coi lệnh bị rollback ở broker.
Nghiệm thu: crash trước/sau từng bước không tạo thêm exposure; partial fill và sự kiện lặp cập nhật đúng volume, phí, PnL.

### Giai đoạn 4 — Risk và quản lý vị thế
- Hoàn tất quote/stop-level/tick-size trước sizing; tính lại lot khi thay đổi SL; floor theo step và hậu kiểm loss + chi phí dự kiến.
- Kiểm tra margin bằng broker API; phân biệt risk budget dự kiến với lỗ thực có thể vượt do gap/slippage.
- Mọi đường áp dụng capacity, spread, daily halt, ownership theo chính sách đã chốt.
- Lưu initial risk; trailing/BE chọn mức bảo vệ tốt hơn, không nới SL ngoài chính sách.
- Pre-news defense chỉ đánh dấu phần đã thành công; persist từng bước partial close/BE để restart không chốt lặp.
- Friday close hoạt động khi entry bị halt và chỉ tác động vị thế được phép.
Nghiệm thu: SL bị nới thì lot giảm hoặc lệnh bị từ chối; không sửa/đóng vị thế ngoài phạm vi; lỗi broker không bị báo là phòng thủ thành công.

### Giai đoạn 5 — Dữ liệu, gate và model
- Chọn một hợp đồng timestamp UTC và kiểm chứng bằng sample thật của MT5 wrapper; không trừ offset hai lần.
- Dùng nến đóng, dedup theo candle/setup, giữ nguyên broker symbol để không làm mất suffix/case.
- Hợp nhất enum gate; lỗi ML khác với chủ động không dùng ML; tối thiểu warmup đúng EMA50 và các đặc trưng khác.
- GUI truyền đúng strategy_id. Dùng một feature pipeline cho research/live, version hóa cả công thức và warmup.
- Metadata model ghi threshold, train range, feature schema, hash/config; script export không đổi 0.38 thành 0.36 ngầm.
- Sửa stale macro cache, xóa rõ các trường trạng thái None và trả snapshot không sửa được ngoài lock.
Nghiệm thu: cùng dữ liệu và config tạo cùng feature/signal ở research/live; 40 nến không được biến lỗi ML thành xác suất 1.0.

### Giai đoạn 6 — Backtest và ML
- Dùng cùng strategy contract, risk và lifecycle với execution adapter giả lập.
- Fill tại thời điểm có thể thực thi sau tín hiệu; gap-through-stop theo giá khả dụng và slippage; nến chạm hai barrier dùng quy tắc bảo thủ được công bố.
- Equity mark-to-market theo bid/ask khả dụng hoặc mô hình spread đã công bố, gồm phí; báo balance curve riêng.
- Xử lý vị thế cuối dữ liệu; nếu nhãn Triple Barrier H=20 là đặc tả thì triển khai time barrier và lưu label_end.
- Chạy chiến lược sau lọc với equity/sizing riêng, đồng thời báo khảo sát trên cùng danh sách tín hiệu như một phép phân tích khác.
- Purge bằng thời điểm label_end so với thời điểm fit/predict. Embargo áp dụng đúng cấu trúc fold; walk-forward chỉ dùng quá khứ cần purge nhãn chưa kết thúc và mô tả gap bổ sung nếu dùng, không nhầm với embargo sau test trong K-fold.
- Tuning chỉ trên validation; khóa config/threshold trước test. Nếu test cũ đã bị dùng để ra quyết định, chỉ coi tái chạy là tái đánh giá lịch sử và cần dữ liệu chưa quan sát/forward test để xác nhận mới.
- Sharpe/Sortino trên chuỗi return theo lịch phù hợp, không nhân sqrt(252) cho chuỗi lợi nhuận từng lệnh.
Nghiệm thu: test gap/MTM/timeout/final-open-position qua; pipeline tái lập được từ data snapshot; không cam kết giữ nguyên các số hiệu suất cũ.

### Giai đoạn 7 — Chịu lỗi, hiệu năng và phát hành
- Một writer được quản lý; connection đọc riêng; transaction ngắn; telemetry batch/retention. Lock timeout có giới hạn và backpressure được đo trên phần cứng mục tiêu.
- Critical journal durable trước dispatch, tách telemetry nếu cần; đo p50/p95/p99, không khẳng định toàn bộ đường ghi bền vững luôn dưới 50 ms.
- Kiểm thử mất kết nối, khóa DB, đầy đĩa, restart, đổi tài khoản, partial fills, quyền sở hữu và kill switch.
- Tách pure unit tests khỏi Windows/MT5 integration tests và demo-account tests. Chạy regression suite sau mỗi giai đoạn.
- Giới hạn AST validator đúng vai trò linter; nếu chạy code không tin cậy, cô lập process với quyền hạn/time/memory/network được kiểm soát, không xem process riêng tự nó là sandbox.
Nghiệm thu: có báo cáo test thực sự đã chạy, các test chưa chạy ghi rõ; qua integration trên demo trước khi cân nhắc live.

## 6. Ma trận nghiệm thu bắt buộc

| Kịch bản | Kết quả mong muốn |
|---|---|
| Zero lot / risk bị từ chối | Không gọi broker gửi lệnh |
| Stop/CB trong lúc phân tích | Không có entry sau điểm khóa admission |
| GUI và worker cùng tín hiệu | Chỉ một intent được giữ quyền gửi |
| Broker nhận lệnh nhưng client mất phản hồi | UNKNOWN -> reconciliation; không gửi lại mù |
| Fill một phần rồi restart | Volume/commission/PnL và phần còn lại tái dựng đúng |
| Replay open/deal/event | Không reopen lịch sử, không nhân đôi exposure/PnL |
| Đổi account có ticket trùng | Không trộn dữ liệu hoặc risk state |
| DB locked/full sau broker fill | Không mất dấu unresolved; không khẳng định lệnh bị từ chối |
| Friday + breaker + lệnh tay | Tác vụ giảm rủi ro đúng phạm vi vẫn chạy |
| Gap qua SL | Không giả định khớp ở giá tốt hơn không thể thực thi |
| ML lỗi/thiếu nến | Trạng thái lỗi rõ ràng theo policy |
| Backup + migration + restore | Dữ liệu cũ bảo toàn, count/PnL đối chiếu được |

## 7. Nguồn tham khảo

1. QuantConnect LEAN — Order Events:
https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/order-events
2. NautilusTrader — Execution Reconciliation:
https://nautilustrader.io/docs/latest/concepts/execution/reconciliation/
3. NautilusTrader — Execution:
https://nautilustrader.io/docs/latest/concepts/execution/
4. MetaQuotes — Position Properties:
https://www.mql5.com/en/docs/constants/tradingconstants/positionproperties
5. SQLite — ON CONFLICT / REPLACE:
https://www.sqlite.org/lang_conflict.html
6. SQLite — PRAGMA synchronous / foreign_keys:
https://www.sqlite.org/pragma.html
7. SQLite — Appropriate Uses / one writer:
https://www.sqlite.org/whentouse.html
8. SQLite — Online Backup API:
https://www.sqlite.org/backup.html
9. QuantConnect — Trade Fill Key Concepts:
https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/key-concepts
10. QuantConnect — Equity Fill Model (tham khảo cơ chế gap; không mặc định dùng nguyên thông số cho CFD):
https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/equity-model
11. Bailey, Borwein, López de Prado, Zhu (2015), The Probability of Backtest Overfitting, bản tác giả:
https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
12. López de Prado — Innovations, Triple Barrier và Purging/Embargo:
https://www.quantresearch.org/Innovations.htm

Các nguồn trên hỗ trợ nguyên tắc thiết kế. Schema, thứ tự triển khai và tiêu chí nghiệm thu là đề xuất kỹ thuật riêng cho mã VECTRA đã kiểm tra.

