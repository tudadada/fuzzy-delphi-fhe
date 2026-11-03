# Delphi mờ trên dữ liệu mã hóa đồng cấu (Encrypted Fuzzy Delphi)

Lấy ý kiến chuyên gia bằng **số mờ tam giác** theo phương pháp **Delphi mờ**, trong đó **không ai đọc được phiếu của từng người** — kể cả máy chủ và người tổ chức. Chỉ kết quả chung được giải mã, và chỉ khi **đủ cả hội đồng** cùng đồng ý. Phiếu gian bị phát hiện và loại bỏ mà không lộ nội dung.

> **Trạng thái:** bản chứng minh khái niệm (proof of concept). Dữ liệu giả lập, chưa được chuyên gia mật mã thẩm định, chưa thử với hội đồng thật. Rất mong nhận góp ý và chỉ ra lỗ hổng.

🇬🇧 [English version](README.md)

---

## Bài toán

Khi lấy ý kiến chuyên gia (quy hoạch, y tế, chấm thi, đánh giá dự án), người tham gia thường **nói theo số đông hoặc theo cấp trên**, hoặc ngại nói thật vì sợ lộ danh tính. Phiếu "ẩn danh" thông thường vẫn bị người tổng hợp đọc được.

Phương pháp **Delphi mờ** cho phép chuyên gia trả lời bằng thang ngôn ngữ (rất thấp → rất cao), mỗi mức ứng với một **số mờ tam giác** (a, b, c). Các phép tính cốt lõi của Delphi mờ — trung bình mờ, giải mờ theo trọng tâm, khoảng cách đồng thuận — chỉ gồm **cộng, nhân với hằng số và bình phương**. Đây đúng là nhóm phép tính mà **mã hóa đồng cấu hoàn toàn (FHE)** làm rẻ nhất.

## Hệ thống làm gì

| Vai | Việc |
|---|---|
| **Chuyên gia** | Đánh dấu 1 trong 5 mức cho từng tiêu chí. Phiếu được **mã hóa trên máy của họ** trước khi gửi. |
| **Máy chủ** | Chỉ nhận bản mã. Kiểm tra phiếu hợp lệ, đổi phiếu thành số mờ, tính trung bình mờ, điểm giải mờ và độ lệch — **toàn bộ trên bản mã**. |
| **Hội đồng (3 người)** | Mỗi người giữ một mảnh khóa. **Phải đủ cả 3** mới giải mã được kết quả. Một người tự giải mã chỉ thu được dữ liệu vô nghĩa. |

**Chống phiếu gian:** chuyên gia gửi phiếu dạng "chọn 1 trong 5 ô" (0/1). Trên bản mã, máy chủ kiểm tra (1) tổng các ô bằng 1 và (2) mỗi ô thỏa x(x−1) = 0. Kết quả được nhân với số ngẫu nhiên: phiếu hợp lệ giải mã ra 0, phiếu gian ra số ngẫu nhiên — hội đồng biết phiếu nào gian nhưng không biết nội dung. Vì máy chủ tự đổi ô sang số mờ, điều kiện a ≤ b ≤ c luôn được bảo đảm.

Quy tắc Delphi mờ dùng theo Chen (2000) và Cheng & Lin (2002): đồng thuận khi khoảng cách d ≤ 0,2 với tỷ lệ ≥ 75% chuyên gia; giữ tiêu chí khi điểm giải mờ ≥ 0,5.

## Kết quả đo (bản cuối: `delphi/04_packed_final.py`)

OpenFHE, BFV, độ sâu nhân 2, N = 8192, giải mã ngưỡng 3 bên. Một máy chủ đám mây thông thường, không GPU.

| Chuyên gia × Tiêu chí | Mỗi người gửi | Mã hóa | Kiểm phiếu | Gộp kết quả | Bắt phiếu gian | Khớp bản rõ |
|---|---|---|---|---|---|---|
| 15 × 20 | 385 KB | 6,5 ms | 0,6 s | 0,9 s | 2/2 | 100% |
| 50 × 100 | 385 KB | 6,4 ms | 2,1 s | 3,3 s | 2/2 | 100% |
| 50 × 800 | 385 KB | 9,7 ms | 2,4 s | 3,1 s | 2/2 | 100% |

- Kiểm tra lặp với 3 bộ dữ liệu khác nhau: 3/3 đạt. Không có phiếu gian thì không báo nhầm.
- Hai kiểu phiếu gian đã thử: dồn 50 phiếu vào một ô; chọn cùng lúc hai mức.
- Kết quả là **chính xác tuyệt đối** (số nguyên), không phải xấp xỉ.

### Quá trình tối ưu

| Phiên bản | Cách làm | Mỗi người gửi | Khóa tính toán | Ghi chú |
|---|---|---|---|---|
| `01_ckks_baseline.py` | CKKS số thực, khóa xoay | 836 KB | ~117 MB | xấp xỉ, máy chủ ~10 s |
| `02_bfv_integer.py` | BFV số nguyên, tách a/b/c, bỏ khóa xoay | 259 KB | ~0,4 MB | chính xác, chưa có ngưỡng, chưa chống gian |
| `03_threshold_anticheat.py` | + giải mã ngưỡng + chống phiếu gian | 1.925 KB | — | 5 bản mã/người |
| `04_packed_final.py` | Dồn 5 mức vào 1 bản mã | **385 KB** | — | bản cuối |

Đã thử nén bản mã (zlib, lzma): không giảm được (385 → 382 KB), đúng như lý thuyết vì bản mã có tính ngẫu nhiên cao.

## Giới hạn đã biết

1. **Máy chủ được giả định trung thực nhưng tò mò** (semi-honest). Máy chủ cố tình bỏ phiếu hoặc tính sai thì hệ thống chưa phát hiện được.
2. Hội đồng biết **ai nộp phiếu gian** và **mỗi người lệch khỏi số đông bao nhiêu** (không biết nội dung phiếu).
3. Giải mã ngưỡng hiện là **3 trên 3** (thiếu một người là không mở được). Chưa làm dạng t-trên-n.
4. Chưa bảo vệ trước việc chuyên gia gửi **bản mã được chế tạo sai cấu trúc** (không phải bản mã mã hóa đúng cách).
5. Dữ liệu giả lập; chưa có đánh giá bảo mật độc lập.

## Đã có ai làm chưa?

Tra cứu (tháng 11/2026) **chưa tìm thấy** công trình làm Delphi mờ trên dữ liệu mã hóa đồng cấu. Các thành phần riêng lẻ thì đã có:

- **Kiểm tra dữ liệu gửi lên hợp lệ mà không lộ nội dung** cho thống kê tổng hợp: hệ thống **Prio** (Corrigan-Gibbs & Boneh, NSDI 2017) — dùng chia sẻ bí mật thay vì FHE.
- **Cộng bảo mật nhiều bên**, bỏ phiếu điện tử: có từ lâu.
- **Giải mã ngưỡng, đóng gói SIMD**: tính năng chuẩn của OpenFHE.

Đóng góp ở đây là **ghép các thành phần trên thành một quy trình Delphi mờ hoàn chỉnh chạy được**, kèm số đo. Đây là đóng góp về ứng dụng và hệ thống, không phải kỹ thuật mật mã mới. **Nếu bạn biết công trình tương tự, xin mở issue để chỉ ra.**

## Thư mục `exploration/` — các hướng đã thử trước đó (kể cả thất bại)

Trước khi đến Delphi mờ, dự án thử áp dụng logic mờ để làm FHE nhẹ hơn trong **chấm điểm tín dụng** (dữ liệu German Credit, UCI).

| Thí nghiệm | Kết luận |
|---|---|
| `credit_01`: luật mờ 8 mức (BFV) vs số chính xác (CKKS) | Nhẹ hơn ~90% so với CKKS kèm sigmoid, nhưng chỉ ~62% so với thiết kế CKKS tối giản. Phần lớn lợi ích đến từ việc bỏ sigmoid, không phải từ "mờ". |
| `credit_02`: độ thuộc mờ tam giác vs chia mức cứng | AUC 0,767 vs 0,766 — chênh lệch nằm trong nhiễu. **Không có ích.** |
| `credit_03`: đóng gói nhiều hồ sơ vào một bản mã | Nhỏ hơn 51 lần, nhanh hơn ~220 lần, kết quả khớp 100%. Đây là kỹ thuật chuẩn (SIMD batching), **không mới**. |

Bài học: ghép "logic mờ + FHE" một cách chung chung không tạo ra gì mới. Kết quả có giá trị xuất hiện khi chọn bài toán **vốn dĩ đã dùng số mờ** (Delphi mờ).

Để chạy, tải dữ liệu vào `exploration/german.data`:
```bash
curl -L -o exploration/german.data https://raw.githubusercontent.com/selva86/datasets/master/GermanCredit.csv
```

## Cài đặt và chạy

```bash
pip install -r requirements.txt          # Python 3.12 cho OpenFHE
python delphi/04_packed_final.py          # bản cuối
python delphi/02_bfv_integer.py           # bản BFV đơn giản (TenSEAL)
```

## Minh bạch về cách làm

Ý tưởng, định hướng và các lựa chọn bài toán do **Tuda** (ceo@dottheworld.com) đưa ra. Mã nguồn được viết và chạy với sự hỗ trợ của trợ lý AI (Claude, Anthropic). Mọi số liệu trong README là kết quả chạy thật của mã trong kho này.

## Giấy phép

MIT — xem `LICENSE`.
