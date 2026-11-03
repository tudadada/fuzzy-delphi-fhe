# Delphi mờ trên dữ liệu mã hóa đồng cấu (Encrypted Fuzzy Delphi)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23928557.svg)](https://doi.org/10.5281/zenodo.23928557)

Lấy ý kiến chuyên gia bằng **số mờ tam giác** theo phương pháp **Delphi mờ**, trong đó **không ai đọc được phiếu của từng người** — kể cả máy chủ và người tổ chức. Chỉ kết quả chung được giải mã, và chỉ khi **đủ số thành viên hội đồng** (2 trên 3) cùng đồng ý. Bất kỳ ai cũng **tính lại và kiểm chứng** được phép gộp của máy chủ. Phiếu gian bị phát hiện và loại bỏ mà không lộ nội dung.

> **Trạng thái:** bản chứng minh khái niệm (proof of concept), phiên bản v0.3. Dữ liệu giả lập, chưa được chuyên gia mật mã thẩm định, chưa thử với hội đồng thật. Rất mong nhận góp ý và chỉ ra lỗ hổng.

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
| **Hội đồng (3 người)** | Mỗi người giữ một mảnh khóa. **Chỉ cần 2 trên 3** là giải mã được kết quả (v0.2; v0.1 cần đủ cả 3). Một người tự giải mã chỉ thu được dữ liệu vô nghĩa. |
| **Kiểm toán viên (bất kỳ ai)** | Tính lại phép gộp từ các bản mã đã công bố, rồi so với kết quả máy chủ công bố. |

**Chống phiếu gian:** chuyên gia gửi phiếu dạng "chọn 1 trong 5 ô" (0/1). Trên bản mã, máy chủ kiểm tra (1) tổng các ô bằng 1 và (2) mỗi ô thỏa x(x−1) = 0. Kết quả được nhân với số ngẫu nhiên: phiếu hợp lệ giải mã ra 0, phiếu gian ra số ngẫu nhiên — hội đồng biết phiếu nào gian nhưng không biết nội dung. Vì máy chủ tự đổi ô sang số mờ, điều kiện a ≤ b ≤ c luôn được bảo đảm.

Quy tắc Delphi mờ dùng theo Chen (2000) và Cheng & Lin (2002): đồng thuận khi khoảng cách d ≤ 0,2 với tỷ lệ ≥ 75% chuyên gia; giữ tiêu chí khi điểm giải mờ ≥ 0,5.

> ⚠️ **Thông báo bảo mật (v0.1–v0.2):** bước kiểm tra phiếu hợp lệ trong `03`, `04` và `05` **có lỗ hổng**. Nó cộng gộp x(x−1) của 5 mức trước khi che ngẫu nhiên, nên một phiếu không phải một-ô như (2, b, c, 0, 0) với b + c = −1 và bc = 2 (mod p) vẫn lọt qua. Khi thử, phiếu này làm trung bình mờ sai hơn 1.000 lần trên thang 0–1. **Đã sửa ở v0.3 (`07_public_validity.py`). Không dùng các phiên bản cũ.**

## Điểm mới trong v0.3 (`delphi/07_public_validity.py`)

1. **Vá lỗ hổng kiểm phiếu.** Giá trị x(x−1) của **từng ô** được che bằng một số ngẫu nhiên riêng *trước khi* cộng, nên mọi ô đều phải là 0 hoặc 1.
2. **Kiểm phiếu kiểm chứng công khai được (Fiat–Shamir).** Số che không còn là bí mật do máy chủ chọn. Chúng được sinh từ mã băm SHA-256 của toàn bộ bảng tin, **chỉ sau khi mọi phiếu đã được khóa**. Ai cũng tính lại được bước kiểm phiếu; kẻ gian không thể biết trước số che.
3. **Chống "thử đi thử lại".** Với p ≈ 786.433, một lần kiểm có xác suất bị lừa khoảng 1/786.433, và người nộp cuối có thể mã hóa lại hàng triệu lần cho tới khi trúng. Bước kiểm được lặp **3 lần với 3 bộ số che độc lập**, đưa xác suất này xuống khoảng 10⁻¹⁸.

| Phép thử (20 × 30 và 50 × 100, giải mã 2/3) | Kết quả |
|---|---|
| Kiểm tra cũ (v0.2): phiếu không phải một-ô lọt qua | **Có — lỗ hổng được xác nhận** |
| v0.3 bắt cả 3 phiếu gian (gồm phiếu khai thác lỗ hổng) | ✓ |
| Không báo nhầm | ✓ |
| Kiểm toán viên tính lại bước kiểm phiếu, mã băm khớp | ✓ |
| Máy chủ vu oan một phiếu hợp lệ (sửa lời tuyên bố) | bị bắt ✓ |
| Máy chủ tráo bản mã kiểm tra của phiếu khác vào | bị bắt ✓ |
| Kẻ gian **biết trước số che** chế được phiếu lọt qua | có — vì vậy số che phải sinh từ bảng tin đã khóa |
| Cùng phiếu chế đó, khi số che sinh từ bảng tin | bị bắt ✓ |
| Kết quả gộp khớp bản rõ | ✓ |

Thời gian kiểm phiếu (lặp 3 lần): 4,2 giây với 20 × 30, 10,5 giây với 50 × 100.

**Đánh đổi:** khi số che công khai, hội đồng có thể suy ra nội dung của phiếu **gian** (các giá trị nhỏ nên thử hết được). Phiếu hợp lệ không lộ gì, vì kết quả kiểm tra của nó luôn bằng 0. Ai gian lận thì mất quyền giữ kín phiếu.

## Điểm mới trong v0.2 (`delphi/05_verifiable_tofn.py`)

Các thay đổi theo góp ý đánh giá độc lập:

1. **Giải mã ngưỡng 2 trên 3** thay cho 3 trên 3. Khi khởi tạo, mỗi thành viên chia mảnh khóa của mình cho những người còn lại theo phương pháp Shamir (OpenFHE `ShareKeys` / `RecoverSharedKey`). Nếu vắng một người, hai người còn lại khôi phục phần của người vắng rồi giải mã.
2. **Kiểm chứng công khai, chống máy chủ gian lận.** Mỗi chuyên gia giữ một biên nhận (mã băm SHA-256 bản mã của mình). Máy chủ công bố toàn bộ phiếu lên một bảng tin. Vì phép gộp là tất định và không dùng bí mật nào, **bất kỳ ai cũng tính lại được** và so với kết quả máy chủ công bố. Cách này bắt được máy chủ **bỏ phiếu** (biên nhận của một chuyên gia không có trên bảng tin) hoặc **tính sai** (tính lại không khớp).
3. **Xáo trộn độ lệch.** Máy chủ hoán vị ngẫu nhiên danh sách độ lệch của các chuyên gia trước khi giải mã. Hội đồng thấy được phân bố độ lệch nhưng không gắn được độ lệch nào với chuyên gia nào (với điều kiện máy chủ không thông đồng với hội đồng).

| Chuyên gia × Tiêu chí | Người vắng | Gửi đi | Tổng thời gian | Bắt phiếu gian | Chính xác | Kiểm toán khớp | Bắt bỏ phiếu | Bắt tính sai |
|---|---|---|---|---|---|---|---|---|
| 20 × 30 | số 3 | 385 KB | 3,6 s | ✓ | ✓ | ✓ | ✓ | ✓ |
| 20 × 30 | số 1 | 385 KB | 3,1 s | ✓ | ✓ | ✓ | ✓ | ✓ |
| 50 × 100 | số 2 | 385 KB | 7,5 s | ✓ | ✓ | ✓ | ✓ | ✓ |
| 50 × 100 | không ai | 385 KB | 6,9 s | ✓ | ✓ | ✓ | ✓ | ✓ |

Tổng thời gian gồm kiểm phiếu, gộp kết quả và mọi lần giải mã ngưỡng (kể cả khôi phục khóa cho người vắng).

**Phần chưa kiểm chứng công khai được ở v0.2:** bước kiểm tra phiếu hợp lệ dùng số che bí mật. **Đã xử lý ở v0.3.**

## So sánh với chia sẻ bí mật (`delphi/06_baseline_secret_sharing.py`)

Cùng phép tính trung bình mờ, nhưng dùng **chia sẻ bí mật cộng** qua 3 máy chủ (cách mà Prio và các hệ thống tính toán đa bên dùng):

| Chuyên gia × Tiêu chí | Chia sẻ bí mật: gửi đi | Chia sẻ bí mật: gộp | FHE (v0.2): gửi đi | FHE: tổng thời gian |
|---|---|---|---|---|
| 20 × 30 | 1,8 KB | 0,6 ms | 385 KB | 3,6 s |
| 50 × 100 | 5,9 KB | 0,6 ms | 385 KB | 7,5 s |
| 50 × 800 | 46,9 KB | 1,6 ms | 385 KB | — |

**Kết luận trung thực: riêng với trung bình mờ, chia sẻ bí mật nhẹ hơn khoảng 8–200 lần và nhanh hơn hàng nghìn lần.** Bản đối chứng *chưa* gồm bước kiểm tra phiếu hợp lệ (cần giao thức chứng minh kiểu Prio) và độ lệch đồng thuận (bình phương cần phép nhân bảo mật, ví dụ bộ ba Beaver). Vì vậy khoảng cách thật nhỏ hơn, nhưng chia sẻ bí mật vẫn thắng về chi phí.

| | Chia sẻ bí mật (Prio/MPC) | Thiết kế FHE này |
|---|---|---|
| Số máy chủ cần | **Từ 2–3 máy chủ không thông đồng, do các tổ chức khác nhau vận hành** | **1 máy chủ** |
| Giả định tin cậy | Các máy chủ không được thông đồng | Số thành viên hội đồng đủ ngưỡng không được thông đồng; máy chủ chỉ cần kiểm chứng được |
| Bình phương / kiểm phiếu | Cần thêm giao thức trao đổi giữa các máy chủ | Làm ngay trên một máy chủ, không cần trao đổi |
| Chi phí | **Thấp hơn nhiều** | Cao hơn (385 KB, vài giây) |
| Kiểm chứng công khai phép gộp | Không đơn giản | Có (tính lại tất định) |

**Khi nào FHE hợp lý:** khi khó tìm được nhiều tổ chức độc lập chịu vận hành các máy chủ không thông đồng. Ví dụ một hội, một liên hoan hay một hội đồng tự tổ chức đợt lấy ý kiến của mình. Khi có sẵn các bên vận hành độc lập, chia sẻ bí mật là lựa chọn kỹ thuật tốt hơn.

## Kết quả đo (v0.1: `delphi/04_packed_final.py`)

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
| `04_packed_final.py` | Dồn 5 mức vào 1 bản mã | **385 KB** | — | v0.1 |
| `05_verifiable_tofn.py` | + ngưỡng 2/3, kiểm chứng công khai, xáo trộn | **385 KB** | — | v0.2 (kiểm phiếu có lỗ hổng) |
| `07_public_validity.py` | + vá kiểm phiếu, số che công khai, lặp 3 lần | **385 KB** | — | **v0.3 (hiện tại)** |

Đã thử nén bản mã (zlib, lzma): không giảm được (385 → 382 KB), đúng như lý thuyết vì bản mã có tính ngẫu nhiên cao.

## Phân tích an toàn

Xem **[SECURITY.vi.md](SECURITY.vi.md)**: mô hình đe dọa, chứng minh bước kiểm phiếu là đúng đắn (Định lý 1, kèm cận chống thử lại) và kiểm chứng được trước máy chủ gian lận (Định lý 2), phác thảo chứng minh có điều kiện cho tính giữ kín phiếu, và danh sách các khoảng trống còn mở. **Quan trọng:** tính giữ kín phiếu đòi hỏi bật chế độ `NOISE_FLOODING_MULTIPARTY` của OpenFHE, vốn không phải mặc định (chi phí đo trong `delphi/08_noise_flooding_check.py`).

## Giới hạn đã biết

1. ~~Máy chủ bỏ phiếu hoặc tính sai thì không phát hiện được.~~ **Đã xử lý ở v0.2** bằng biên nhận và tính lại công khai; bước kiểm phiếu trở nên kiểm chứng công khai được ở **v0.3**.
2. Hội đồng biết **phiếu nộp nào là phiếu gian**. ~~Hội đồng còn biết độ lệch của từng người~~: v0.2 đã xáo trộn độ lệch, nhưng chỉ có tác dụng khi máy chủ không thông đồng với hội đồng.
3. ~~Chỉ có 3 trên 3.~~ **v0.2 hỗ trợ 2 trên 3.** Các cấu hình t-trên-n lớn hơn chưa được thử. Bất kỳ 2 thành viên nào thông đồng đều giải mã được phiếu riêng lẻ, đây là bản chất của ngưỡng 2 trên 3.
4. Chưa bảo vệ trước việc chuyên gia gửi **bản mã được chế tạo sai cấu trúc** (không phải bản mã mã hóa đúng cách). Cần chứng minh không tiết lộ (zero-knowledge) rằng bản mã được tạo đúng, đây là việc còn bỏ ngỏ.
5. Chi phí cao hơn nhiều so với chia sẻ bí mật (xem phần so sánh).
6. Dữ liệu giả lập; chưa có đánh giá bảo mật độc lập.

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
python delphi/07_public_validity.py       # phiên bản hiện tại (v0.3)
python delphi/05_verifiable_tofn.py       # v0.2
python delphi/06_baseline_secret_sharing.py   # đối chứng chia sẻ bí mật
python delphi/04_packed_final.py          # v0.1
python delphi/02_bfv_integer.py           # bản BFV đơn giản (TenSEAL)
```

## Minh bạch về cách làm

Ý tưởng, định hướng và các lựa chọn bài toán do **Tuda** (ceo@dottheworld.com) đưa ra. Mã nguồn được viết và chạy với sự hỗ trợ của trợ lý AI (Claude, Anthropic). Mọi số liệu trong README là kết quả chạy thật của mã trong kho này.

## Giấy phép

MIT — xem `LICENSE`.
