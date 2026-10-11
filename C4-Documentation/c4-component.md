# C4 Model — Level 3: Component Architecture (Kiến trúc Thành phần Multi-Agent)

## 1. Tổng quan Kiến trúc Thành phần (Component Overview)
`multi-agent-core` là trái tim của hệ thống, tổ chức theo mô hình **Đa Tác tử Đối kháng (Adversarial Multi-Agent Governance)**. Trong mô hình này, các Agent tìm kiếm cơ hội kiếm lời (Signal Generators) hoàn toàn độc lập và chịu sự giám sát tối cao của Agent bảo vệ vốn (Risk Gatekeeper) — Agent duy nhất có quyền phủ quyết (**VETO**) trước khi bất kỳ lệnh nào được gửi tới sàn.

## 2. Sơ đồ Thành phần Tương tác (Interactive Component Diagram)
Sơ đồ tương tác chuẩn HTML/SVG đã được biên dịch thành công qua `archify`:
- 🔗 **File Sơ đồ Tương tác**: [c4-component.html](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/c4-component.html) *(Mở trực tiếp trên trình duyệt để zoom, pan, đổi dark/light theme và export SVG/PNG)*.

```mermaid
C4Component
  title Component Diagram: Multi-Agent Trading Core

  Container_Boundary(core, "Multi-Agent Trading Core") {
    
    Boundary(b1, "Nhánh 1: Cross-Sectional Ranking Portfolio (Allocation)") {
      Component(csr_data, "Asset Data Collector", "Python Asyncio", "Quét nến M15/H1/H4 của rổ 30-50 tài sản từ MT5")
      Component(csr_ranker, "Factor Scoring Engine", "NumPy / Pandas", "Tính điểm Momentum ROC, RSI, ATR và xếp hạng")
      Component(csr_alloc, "Portfolio Allocator", "Optimizer", "Lựa chọn Top 10 Long + Top 10 Short, tỷ trọng 5%/vị thế")
    }

    Boundary(b2, "Nhánh 2: Multi-Asset Opportunistic SMC (Entry Method)") {
      Component(smc_bias, "HTF Bias Analyzer", "Trend Engine", "Xác định xu hướng lớn trên H4/D1 làm khung định hướng")
      Component(smc_struct, "Market Structure Agent", "Geometry Analyzer", "Nhận diện phá vỡ cấu trúc BOS và đảo chiều CHoCH trên M15/H1")
      Component(smc_poi, "POI & Liquidity Detector", "Smart Money Module", "Xác định Order Block, Fair Value Gap và quét thanh khoản")
      Component(smc_sizer, "SMC Position Sizer", "Formula Engine", "Tính Lot Size theo 1R = 1.0% Equity và kiểm tra R:R >= 2.0")
    }

    Boundary(b_gov, "Tầng Quản trị Đối kháng & An toàn (Adversarial Governance)") {
      Component(risk_gatekeeper, "Risk Gatekeeper Agent", "Policy Evaluator", "Nắm quyền VETO tối cao (Lọc Swap, Spread, Exposure, R:R)")
      Component(circuit_breaker, "Circuit Breaker Engine", "System Monitor", "Theo dõi Drawdown ngày (-3%) và ngắt toàn bộ hệ thống")
      Component(order_router, "Execution Dispatcher", "RPyC Client", "Chuyển tiếp các lệnh đã được phê duyệt sang MT5 Bridge")
    }
  }

  Rel(csr_data, csr_ranker, "Dữ liệu OHLCV")
  Rel(csr_ranker, csr_alloc, "Bảng điểm xếp hạng")
  Rel(csr_alloc, risk_gatekeeper, "Đề xuất rổ 20 mã tái cân bằng")

  Rel(smc_bias, smc_struct, "Khung định hướng HTF")
  Rel(smc_struct, smc_poi, "Cấu trúc đỉnh/đáy BOS")
  Rel(smc_poi, smc_sizer, "Vùng Entry & SL kỹ thuật")
  Rel(smc_sizer, risk_gatekeeper, "Đề xuất Setup SMC (Entry/SL/TP)")

  Rel(circuit_breaker, risk_gatekeeper, "Tín hiệu ngắt mạch khẩn cấp", "Alert")
  Rel(risk_gatekeeper, order_router, "Lệnh đã qua kiểm duyệt", "Approved Intent")
```

## 3. Chi tiết Các Nhóm Agent

### 3.1. Nhóm Agent Nhánh 1: Cross-Sectional Ranking Portfolio
- **Asset Data Collector**: Định kỳ $4H$ hoặc $Daily$ tải dữ liệu nến đồng bộ của toàn bộ vũ trụ $30 - 50$ mã Forex/Crypto/Indices.
- **Factor Scoring Engine**: Áp dụng công thức chuẩn hóa điểm Z-Score:
  $$\text{Score} = w_{\text{ROC}} \cdot Z(\text{ROC}) + w_{\text{RSI}} \cdot Z(\text{RSI}) + w_{\text{Trend}} \cdot Z(\text{EMA}) - w_{\text{ATR}} \cdot Z(\text{ATR})$$
- **Portfolio Allocator**: Lựa chọn 10 mã có Score cao nhất để MUA và 10 mã có Score thấp nhất để BÁN. Mỗi mã phân bổ chính xác $5\%$ tài khoản để đảm bảo trung lập thị trường ($|\sum w_{\text{Long}} - \sum w_{\text{Short}}| \le 5\%$).

### 3.2. Nhóm Agent Nhánh 2: Multi-Asset Opportunistic SMC Trading
- **HTF Bias Analyzer**: Xác định cấu trúc đỉnh cao dần / đáy cao dần (Bullish) hoặc đỉnh thấp dần / đáy thấp dần (Bearish) trên nến H4/D1.
- **Market Structure Agent**: Tìm các điểm BOS (tiếp diễn xu hướng) và CHoCH (bắt đầu đảo chiều) trên khung thời gian vào lệnh M15.
- **POI & Liquidity Detector**: Xác định Order Block (cây nến đối màu cuối cùng trước đợt bùng nổ thanh khoản), FVG (vùng nến 3 thanh không chồng lấn) và phát hiện cú quét thanh khoản (Liquidity Sweep).
- **SMC Position Sizer**: Tính toán khối lượng giao dịch chính xác:
  $$\text{Lot Size} = \frac{\text{Equity} \times 1\%}{\text{Khoảng cách Entry đến SL} \times \text{Pip Value}}$$
  Bắt buộc $TP \ge 2 \times SL$ ($R:R \ge 1:2.0$).

### 3.3. Tầng Quản trị Đối kháng (Adversarial Governance)
- **Risk Gatekeeper Agent**:
  - Không sinh tín hiệu mà chỉ nhận đề xuất từ 2 nhánh.
  - Áp dụng các quy tắc kiểm tra nghiêm ngặt:
    1. **Swap Check**: Phí qua đêm của lệnh giữ dài có ăn mòn lợi nhuận không? (Nếu Swap âm nặng ➔ **VETO**).
    2. **Spread Check**: Spread hiện tại có lớn hơn $1.5 \times \text{Spread trung bình}$ không? (Nếu giãn spread ➔ **VETO**).
    3. **Net Exposure Check**: Tổng vị thế Long/Short có vượt quá $5\%$ chênh lệch không? (Nếu lệch ➔ **VETO / Điều chỉnh**).
    4. **R:R Check**: Lệnh SMC có đạt tối thiểu $1:2.0$ không? (Nếu thấp hơn ➔ **VETO**).
- **Circuit Breaker Engine**:
  - Giám sát Equity theo thời gian thực.
  - Nếu Drawdown trong ngày chạm $-3.0\%$ ➔ Kích hoạt ngắt mạch khẩn cấp: đóng toàn bộ vị thế đang mở và khóa hệ thống 24 giờ.
