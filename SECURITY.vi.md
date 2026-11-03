# Phân tích an toàn — Encrypted Fuzzy Delphi (v0.3)

🇬🇧 [English version](SECURITY.md)

Tài liệu này nêu rõ hệ thống tuyên bố điều gì, dựa trên những giả định nào, và **chứng minh những điều có thể chứng minh được ngay hôm nay**. Chỗ nào chỉ mới là phác thảo hoặc còn khoảng trống thì ghi rõ. Tài liệu **chưa được chuyên gia mật mã độc lập thẩm định**, rất mong nhận góp ý.

## 1. Bối cảnh và ký hiệu

| Ký hiệu | Ý nghĩa |
|---|---|
| p = 786.433 | modulo bản rõ của BFV (là số nguyên tố, đã kiểm tra) |
| L = 5 | số mức ngôn ngữ của mỗi tiêu chí |
| K | số tiêu chí |
| x ∈ Z_p^{L·K} | phiếu của một chuyên gia; x_{l,k} là mức l của tiêu chí k |
| n = 3, t = 2 | số thành viên hội đồng và ngưỡng giải mã |
| R = 3 | số lần lặp độc lập của bước kiểm phiếu |
| BB | bảng tin công khai: danh sách mọi bản mã đã nộp |
| H | SHA-256 |

Một phiếu **hợp lệ** khi và chỉ khi với mọi tiêu chí k, có đúng một mức bằng 1 và các mức còn lại bằng 0.

**Bước kiểm phiếu (v0.3).** Với bản mã phiếu Enc(x) và các số che r₁ ∈ (Z_p^*)^K, r₂ ∈ (Z_p^*)^{L·K}, máy chủ tính trên bản mã, cho từng tiêu chí k:

  s_k = Σ_l x_{l,k} − 1,  q_{l,k} = x_{l,k}(x_{l,k} − 1),  c_k = r₁ₖ·s_k + Σ_l r₂_{l,k}·q_{l,k}

Hội đồng giải mã c = (c_1,…,c_K). Phiếu được chấp nhận khi và chỉ khi c = 0 ở cả R lần lặp.

**Số che.** Với phiếu i và lần lặp j: số che = G(H(H(ct₁)‖…‖H(ct_E)) ‖ i ‖ j), chỉ được tính sau khi bảng tin đã khóa. G là một hàm mở rộng tất định (xem khoảng trống G4).

## 2. Mô hình đe dọa

| Bên | Được tin về quyền riêng tư? | Được tin về tính toàn vẹn? |
|---|---|---|
| Chuyên gia | — | **Không.** Có thể nộp bất kỳ vectơ nào, chọn sau khi xem bảng tin. *Giả định* là nộp bản mã được tạo đúng cách (xem G1). |
| Máy chủ | Không được thông đồng với hội đồng | **Không.** Có thể bỏ phiếu, sửa phiếu, tính sai; những việc này phải bị phát hiện. |
| Hội đồng | Tối đa t − 1 = 1 thành viên bị mua chuộc | Giải mã đúng (xem G3) |
| Kiểm toán viên | — | Bất kỳ ai; chỉ cần dữ liệu công khai |

Giả định về độ khó: bài toán Ring-LWE (nền an toàn của BFV); SHA-256 chống trùng mã băm và chống tìm tiền ảnh thứ hai; H được mô hình hóa như một "hàm ngẫu nhiên lý tưởng" (random oracle) cho bước Fiat–Shamir.

## 3. Bổ đề — điều kiện theo từng ô xác định đúng phiếu một-ô

**Bổ đề 1.** Với p nguyên tố và vectơ v ∈ Z_p^L: (Σ_l v_l = 1 và v_l(v_l − 1) = 0 với mọi l) ⟺ v là phiếu một-ô.

*Chứng minh.* Z_p là một trường, nên v_l(v_l − 1) = 0 suy ra v_l ∈ {0, 1}. Khi mọi phần tử đều thuộc {0, 1}, điều kiện Σ v_l = 1 (mod p) với L < p buộc có đúng một phần tử bằng 1. Chiều ngược lại là hiển nhiên. ∎

**Nhận xét (lỗ hổng của v0.1–v0.2).** Bước kiểm cũ chỉ đòi hỏi Σ_l v_l(v_l − 1) = 0, tức một phương trình duy nhất. Kết hợp với Σ v_l = 1, nó tương đương với Σ v_l² = 1, và phương trình này có nghiệm không phải một-ô trên Z_p. Ví dụ v = (2, b, c, 0, 0) với b + c = −1, bc = 2, tồn tại khi p = 786.433 (b = 336.448, c = 449.984). Bổ đề 1 giải thích vì sao kiểm tra **từng ô** sẽ vá được lỗ hổng này.

## 4. Định lý 1 — bước kiểm phiếu là đúng đắn

**Định lý 1.** Cho x là một phiếu không hợp lệ, và các số che có phân bố đều trên Z_p^*, độc lập với x. Khi đó

  Pr[x được chấp nhận] ≤ (p − 1)^{−R}.

*Chứng minh.* Theo Bổ đề 1, có một tiêu chí k mà s_k ≠ 0 hoặc có một q_{l,k} ≠ 0. Khi đó c_k là một biểu thức tuyến tính theo các số che (r₁ₖ, r₂_{1,k}, …, r₂_{L,k}) với ít nhất một hệ số khác 0, gọi số che đó là r*. Cố định mọi số che khác. Đẳng thức c_k = 0 chỉ đúng với tối đa một giá trị của r*; vì r* phân bố đều trên p − 1 giá trị, Pr[c_k = 0] ≤ 1/(p − 1). R lần lặp dùng các số che độc lập, nên xác suất cả R lần đều chấp nhận là ≤ (p − 1)^{−R}. ∎

**Tính đầy đủ.** Phiếu hợp lệ cho s = 0 và q = 0, nên c = 0 ở mọi lần lặp (với giả định BFV giải mã đúng, xem G7).

**Kiểm chứng thực nghiệm** (`tests/soundness_simulation.py`, mô phỏng bản rõ, 400.000 phiếu gian ngẫu nhiên):

| p | R | Tỷ lệ lọt đo được | Cận (p − 1)^{−R} |
|---|---|---|---|
| 101 | 1 | 1,01 × 10⁻² | 1,00 × 10⁻² |
| 101 | 2 | 1,10 × 10⁻⁴ | 1,00 × 10⁻⁴ |
| 13 | 3 | 4,68 × 10⁻⁴ | 5,79 × 10⁻⁴ |

Dòng R = 2 cao hơn cận một chút (đo được 44 lần lọt so với kỳ vọng 40, độ lệch chuẩn khoảng 6,3), nằm trong sai số lấy mẫu.

**Hệ quả 1 (chống thử đi thử lại).** Số che phụ thuộc toàn bộ bảng tin, kể cả bản mã của chính kẻ tấn công. Khi mô hình hóa H như hàm ngẫu nhiên lý tưởng, một chuyên gia thử Q bản mã khác nhau trước khi nộp sẽ thành công với xác suất không quá

  Q · (p − 1)^{−R} + (một lượng không đáng kể).

Với p = 786.433 và R = 3, (p − 1)^{−3} ≈ 2,06 × 10⁻¹⁸ ≈ 2^{−58,8}. Kẻ tấn công thử Q = 2^{30} lần (mỗi lần phải mã hóa lại) có xác suất thành công khoảng 2^{−28,8}. Muốn biên an toàn mạnh hơn, R = 5 cho khoảng 2^{−97,9} mỗi lần thử (xem G5).

## 5. Định lý 2 — kiểm chứng được trước máy chủ gian lận

Mỗi chuyên gia giữ biên nhận h_i = H(ct_i). Máy chủ công bố BB, danh sách phiếu được chấp nhận, mã băm của các bản mã kiểm phiếu, các giá trị kiểm phiếu đã giải mã, và mã băm của từng bản mã kết quả gộp.

**Định lý 2.** Với giả định hội đồng giải mã đúng, kiểm toán viên phát hiện được các hành vi sau, trừ khi có trùng mã băm SHA-256 (xác suất không đáng kể):

1. **Bỏ hoặc sửa phiếu:** một biên nhận h_i không xuất hiện trong các H(ct) với ct ∈ BB.
2. **Kết luận kiểm phiếu sai:** bước kiểm phiếu là hàm tất định của (ct_i, số che), và số che là hàm tất định của BB. Kiểm toán viên tính lại từng bản mã kiểm phiếu và so mã băm. Một phiếu bị tuyên bố là gian nhưng giá trị kiểm đã giải mã bằng 0 (hoặc được tuyên bố hợp lệ nhưng giá trị kiểm khác 0) là một mâu thuẫn.
3. **Gộp sai:** phép gộp là hàm tất định, công khai, của BB và danh sách phiếu được chấp nhận, không dùng dữ liệu bí mật nào. Kiểm toán viên tính lại và so mã băm.

*Chứng minh.* (1) Sửa ct_i thành ct′ ≠ ct_i mà vẫn có H(ct′) = h_i đòi hỏi tìm được tiền ảnh thứ hai. (2)–(3) Phép tính lại của kiểm toán viên tạo ra đúng bản mã mà máy chủ trung thực sẽ tạo, vì mọi phép toán đều tất định (đã xác minh thực nghiệm: mã băm tính lại khớp từng byte). Máy chủ công bố một bản mã khác có cùng mã băm là đã tìm được trùng mã băm. ∎

**Chưa bao phủ:** bước xáo trộn độ lệch dùng số ngẫu nhiên của máy chủ, là biện pháp bảo vệ riêng tư chứ không phải bước kiểm chứng được; và kết quả giải mã của hội đồng được tin tưởng (G3).

## 6. Giữ kín phiếu — phác thảo chứng minh và khoảng trống

**Tuyên bố.** Một kẻ tấn công mua chuộc tối đa một thành viên hội đồng và quan sát mọi dữ liệu công khai sẽ không biết gì về các phiếu hợp lệ trung thực ngoài phần rò rỉ

  𝓛 = (trung bình mờ và điểm giải mờ chung; một bit hợp lệ/không hợp lệ cho mỗi phiếu; tập hợp các độ lệch đồng thuận, nếu máy chủ không thông đồng; nội dung của các phiếu gian).

**Phác thảo.**
1. **Các mảnh Shamir.** Với t = 2, mỗi thành viên giữ một mảnh của phần khóa của từng thành viên khác; một mảnh Shamir đơn lẻ hoàn toàn độc lập với bí mật. Phần khóa mà thành viên bị mua chuộc thấy được có thể mô phỏng được.
2. **Các bản mã.** Lập luận "thay thế từng bước": thay bản mã của mỗi chuyên gia trung thực bằng bản mã của số 0. Mỗi bước không phân biệt được nhờ tính an toàn IND-CPA của BFV với khóa công khai chung, tức nhờ độ khó của Ring-LWE.
3. **Mảnh giải mã.** Bộ mô phỏng phải tạo ra mảnh giải mã của các thành viên trung thực khi chỉ biết kết quả bản rõ. Đây là **lập luận phủ nhiễu tiêu chuẩn**: mảnh giải mã phải mang nhiễu mới đủ lớn để che đi thành phần nhiễu phụ thuộc vào khóa bí mật.

**Khoảng trống G2: bước 3 không đứng vững với cài đặt mặc định.** Chế độ `MultipartyMode` mặc định của OpenFHE là `FIXED_NOISE_MULTIPARTY`, **không phủ nhiễu**. Khi không phủ nhiễu, qua nhiều lần giải mã, các mảnh giải mã có thể làm lộ thông tin về phần khóa, và lập luận mô phỏng không còn đúng. OpenFHE có sẵn chế độ `NOISE_FLOODING_MULTIPARTY`. Chi phí đo được (`delphi/08_noise_flooding_check.py`, 20 × 30, hai lần chạy):

| Chế độ | N | Mỗi người gửi | Tổng thời gian | Đúng |
|---|---|---|---|---|
| FIXED_NOISE (mặc định, dùng trong v0.3) | 8.192 | 385 KB | 8,9–10,3 s | ✓ |
| NOISE_FLOODING | 16.384 | 1.281 KB | 32,5–41,2 s | ✓ |

**Khuyến nghị: dùng `NOISE_FLOODING_MULTIPARTY` khi triển khai thật.** Cho tới khi đó, tuyên bố về giữ kín phiếu cần được hiểu là *có điều kiện: phải bật phủ nhiễu*.

**Các rò rỉ khác.**
- **Phiếu gian.** Khi số che công khai, giá trị kiểm là hàm công khai của các ẩn số nhỏ; hội đồng có thể thử hết để suy ra nội dung phiếu gian. Phiếu hợp lệ luôn giải mã ra 0 nên không lộ gì.
- **Khôi phục khóa.** Khi vắng một thành viên, những người có mặt khôi phục phần khóa của người vắng (OpenFHE `RecoverSharedKey`). Phần khóa đó sau đó bị lộ cho người thực hiện khôi phục. **Dùng khóa mới cho mỗi đợt lấy ý kiến.**
- **Xáo trộn** chỉ che được độ lệch nào thuộc về ai khi máy chủ không thông đồng với hội đồng.

## 7. Các khoảng trống còn mở

| # | Khoảng trống | Hậu quả | Hướng giải quyết |
|---|---|---|---|
| G1 | Bản mã chế tạo sai cấu trúc | Chuyên gia có thể nộp thứ không phải bản mã được tạo đúng | Chứng minh không tiết lộ (ZK) rằng bản mã tạo đúng, ví dụ Greco (IACR ePrint 2024/594); có thể chứng minh luôn phiếu là một-ô và thay thế bước kiểm phiếu |
| G2 | Mặc định không phủ nhiễu | Bước 3 của chứng minh giữ kín phiếu không đứng vững | Bật `NOISE_FLOODING_MULTIPARTY` (đã đo ở trên) |
| G3 | Không có chứng minh rằng mảnh giải mã đúng | Thành viên bị mua chuộc có thể làm sai kết quả | Giải mã kiểm chứng được / chứng minh ZK cho mảnh giải mã |
| G4 | Hàm sinh số che dùng NumPy PCG64 khởi tạo từ SHA-256 | Không phải bộ sinh số ngẫu nhiên mật mã; Định lý 1 giả định số che phân bố đều | Sinh số che bằng SHAKE-256 hoặc HKDF |
| G5 | Biên chống thử lại phụ thuộc R và p | Khoảng 2^{−58,8} mỗi lần thử khi R = 3 | R = 5 (khoảng 2^{−97,9}) hoặc modulo bản rõ lớn hơn |
| G6 | Khôi phục khóa làm lộ một phần khóa | Giảm an toàn ở các đợt sau | Khóa mới cho mỗi đợt |
| G7 | Tính đúng của BFV dựa vào cách OpenFHE chọn tham số | Mới xác minh bằng thực nghiệm | Phân tích nhiễu hình thức |
| G8 | Mức an toàn | Mặc định của OpenFHE (128 bit cổ điển), chưa kiểm tra độc lập | Rà soát tham số tường minh |
| G9 | Chưa có chứng minh ghép nối (ví dụ UC) | Các chứng minh trên tách theo từng tính chất | Mô hình hình thức cho toàn bộ giao thức |
| G10 | Siêu dữ liệu, thời gian, kênh kề | Ngoài phạm vi | Gia cố khi triển khai |

## 8. Tóm tắt

- **Đã chứng minh:** bước kiểm phiếu là đúng đắn (Định lý 1, kèm cận chống thử lại) và kiểm chứng được trước máy chủ gian lận (Định lý 2), dưới các giả định tiêu chuẩn và với điều kiện hội đồng giải mã đúng.
- **Đã phác thảo, có điều kiện:** giữ kín phiếu, **đòi hỏi bật phủ nhiễu** (G2).
- **Còn mở:** bản mã chế tạo sai (G1) và giải mã kiểm chứng được (G3) là hai khoảng trống quan trọng nhất.
