---
name: trendline-mtf
description: Kẻ trendline tự động bằng Pine Script trên các khung D1, H4, H1. Dùng ta.pivothigh/pivotlow built-in của TradingView để phát hiện pivot chính xác. Dùng khi user muốn kẻ trendline, phân tích xu hướng, hoặc phân tích đa khung.
---

# Kẻ Trendline Tự Động — Pine Script (Auto Trendline MTF)

Thay vì phân tích thủ công, skill này deploy một **Pine Script indicator** sử dụng engine pivot detection native của TradingView — chính xác 100%, không phụ thuộc vào AI tính toán.

---

## CÁCH HOẠT ĐỘNG

Script dùng `ta.pivothigh(high, 3, 3)` và `ta.pivotlow(low, 3, 3)` của TradingView để:
1. Tự động tìm 2 pivot high/low gần nhất trên chart hiện tại
2. Kẻ trendline qua 2 điểm đó
3. Kéo dài đường sang phải (`extend.right`) để chiếu về tương lai

---

## BƯỚC 1: Đọc Source Code

Đọc file Pine Script từ đường dẫn:
```
/Users/macbook/Desktop/document/technology_project/project/tradingview-mcp/scripts/trendline_auto.pine
```

---

## BƯỚC 2: Deploy lên từng khung thời gian

### D1 — Xu hướng chính
```
chart_set_timeframe("D")
```
Sau đó inject và compile script:
```
pine_set_source(source: <nội dung file trendline_auto.pine>)
pine_smart_compile()
pine_get_errors()
```
Nếu compile thành công → chụp ảnh:
```
capture_screenshot(region: "chart")
```

### H4 — Xu hướng trung hạn
```
chart_set_timeframe("240")
```
Deploy lại script (script tự thích nghi với timeframe hiện tại):
```
pine_set_source(source: <nội dung file trendline_auto.pine>)
pine_smart_compile()
capture_screenshot(region: "chart")
```

### H1 — Điểm vào lệnh
```
chart_set_timeframe("60")
pine_set_source(source: <nội dung file trendline_auto.pine>)
pine_smart_compile()
capture_screenshot(region: "chart")
```

---

## BƯỚC 3: Đọc kết quả từ ảnh

Sau mỗi khung, phân tích screenshot để xác định:
- Trendline tăng (xanh dương) đang ở vùng giá nào
- Trendline giảm (đỏ) đang ở vùng giá nào
- Giá hiện tại đang tiếp cận trendline nào

---

## BƯỚC 4: Báo cáo tổng hợp

```
═══════════════════════════════════════
📊 PHÂN TÍCH TRENDLINE AUTO MTF
Symbol: [SYMBOL]  |  Thời điểm: [DATE]
═══════════════════════════════════════

📅 D1 — XU HƯỚNG CHÍNH
  Trendline tăng: [Vùng giá hiện tại của đường]
  Trendline giảm: [Vùng giá hiện tại của đường]
  Bias: [BULLISH / BEARISH / NEUTRAL]

⏱ H4 — XU HƯỚNG TRUNG HẠN
  Trendline tăng: [Vùng giá]
  Trendline giảm: [Vùng giá]
  Cùng chiều D1? [Có / Không]

⚡ H1 — ĐIỂM VÀO LỆNH
  Trendline tăng: [Vùng giá]
  Confluence Zone: [Vùng giá giao nhau với H4/D1]

🎯 KẾT LUẬN
  Bias tổng: [BULLISH / BEARISH / NEUTRAL]
  Vùng hỗ trợ trendline gần nhất: [Giá]
  Vùng kháng cự trendline gần nhất: [Giá]
  Invalidation: [Trendline bị phá khi giá close dưới/trên X]
═══════════════════════════════════════
```

---

## TÙY CHỈNH SCRIPT (nếu user yêu cầu)

Các parameter có thể thay đổi trong file `trendline_auto.pine`:

| Parameter | Mặc định | Ý nghĩa |
|-----------|----------|---------|
| `pivot_left` | 3 | Số nến bên trái xác nhận pivot |
| `pivot_right` | 3 | Số nến bên phải xác nhận pivot |
| `use_wick` | true | True = dùng High/Low (wick), False = dùng Close |
| `extend_right` | true | Kéo dài sang phải |
| `bull_color` | #2196F3 | Màu trendline tăng |
| `bear_color` | #F44336 | Màu trendline giảm |

Tăng `pivot_left/right` (ví dụ 5) = pivot lớn hơn, ít nhiễu hơn, phù hợp D1.
Giảm xuống 2 = pivot nhỏ hơn, nhiều hơn, phù hợp H1.

---

## LƯU Ý

- Script chỉ kẻ **1 trendline tăng** (nối 2 pivot low gần nhất) và **1 trendline giảm** (nối 2 pivot high gần nhất) tại bất kỳ thời điểm nào.
- Khi chuyển timeframe, deploy lại script để recalculate trên dữ liệu mới.
- Các dấu tam giác nhỏ trên chart là các điểm pivot đã được detect.
- Trendline sẽ tự cập nhật khi có nến mới (real-time).
