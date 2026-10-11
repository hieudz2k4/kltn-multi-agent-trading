# ĐẶC TẢ YÊU CẦU HỆ THỐNG GIAO DỊCH ĐA TÁC TỬ ĐỊNH LƯỢNG
## (Quantitative Multi-Agent Trading System — Requirements Specification)

- **Đề tài**: Hệ thống giao dịch đa tác tử (Multi-Agent) tự động tích hợp 02 hướng tiếp cận: (1) Rổ danh mục định lượng trung lập thị trường (Cross-Sectional Ranking Portfolio) và (2) Giao dịch cơ hội đa tài sản theo cấu trúc SMC (Multi-Asset Opportunistic SMC Trading).
- **Mã tài liệu**: `SPEC-KLTN-MULTI-AGENT-01`
- **Phiên bản**: `1.1.0`
- **Trạng thái**: `APPROVED`
- **Tác giả / Chủ sở hữu**: KLTN Multi-Agent Trading Team

---

## 1. TỔNG QUAN & MỤC TIÊU CỐT LÕI (CORE GOALS & OBJECTIVES)

### 1.1. Mục tiêu tối thượng (Profit-First Objective)
Hệ thống được thiết kế với mục tiêu cao nhất là **sinh lời thực tế và bền vững** trên thị trường tài chính thông qua việc khai thác biên độ chênh lệch hiệu suất (Alpha Spread) giữa nhóm tài sản mạnh nhất và nhóm tài sản yếu nhất, kết hợp khai thác các điểm vào lệnh bất đối xứng (Asymmetric R:R) từ cấu trúc dòng tiền lớn (Smart Money):
- **Kỳ vọng Lợi nhuận (Expected Return)**: Tỷ suất sinh lời dương ổn định qua các chu kỳ thị trường (Bull, Bear, Sideway).
- **Profit Factor**: Đạt $\ge 1.5$ trên dữ liệu kiểm thử thực nghiệm.
- **Sharpe Ratio**: Đạt $\ge 1.2$ (lợi nhuận vượt trội so với mức độ biến động rủi ro gánh chịu).

### 1.2. Mục tiêu Học thuật của Khóa luận (Thesis Evaluation Objective)
Chứng minh tính khả thi và hiệu quả của kiến trúc **Hệ thống Đa Tác tử (Multi-Agent System)** trong việc tự động hóa giao dịch tài chính theo 02 nhánh chiến lược độc lập:
1. **Tự động hóa Chiến lược Định lượng (Nhánh 1 - CSR Portfolio)**: Agent tự động tính điểm xếp hạng đa nhân tố, phân bổ vốn Dollar-Neutral, tái cân bằng định kỳ và kiểm soát độ phơi nhiễm ròng (Net Exposure ≤ 5%).
2. **Tự động hóa Phân tích Cấu trúc Giá (Nhánh 2 - Opportunistic SMC)**: Agent tự động nhận diện cấu trúc BOS/CHoCH, phát hiện POI (Order Block, FVG, Liquidity Sweep) và thực thi lệnh khi đủ điều kiện $R:R \ge 1:2.0$ — không cần can thiệp thủ công.
3. **Cơ chế Phân tách Quyền lực (Adversarial Governance)**: Tách biệt Agent tìm kiếm cơ hội (Signal Agent) và Agent bảo vệ vốn (Risk Gatekeeper có quyền **VETO**), đảm bảo kiểm soát rủi ro hoàn toàn độc lập với quyết định giao dịch.
4. **Khả năng Vận hành Liên tục 24/7**: Hệ thống hoạt động không ngừng trên Lightning AI Studio, xử lý đồng thời đa tài sản mà không phụ thuộc vào thao tác thủ công.

---

## 2. ĐẶC TẢ HAI (02) NHÁNH CHIẾN LƯỢC GIAO DỊCH (TRADING STRATEGY SPECIFICATION)

### 2.0. Phân định Bản chất: Chiến lược Quản lý Danh mục vs. Phương pháp Vào lệnh
Hệ thống phân định rõ hai tầng độc lập về bản chất:
- **Tầng Chiến lược Danh mục (Portfolio Allocation Strategy — "WHAT to hold")**:
  - Tiêu biểu là **Cross-Sectional Ranking**: quyết định việc phân bổ tỷ trọng vốn vào rổ tài sản dựa trên sức mạnh tương đối. Hệ thống luôn duy trì vị thế đồng thời ($10 \text{ Long} + 10 \text{ Short}$) và tái cân bằng định kỳ theo lịch trình cố định ($4H / Daily$) để giữ trạng thái trung lập rủi ro thị trường (Market-Neutral).
- **Tầng Phương pháp Khai thác Cơ hội & Điểm vào lệnh (Execution / Entry Method — "WHERE/WHEN to enter")**:
  - Tiêu biểu là **Smart Money Concepts (SMC)**: là phương pháp phân tích cấu trúc giá và hành vi thanh khoản nhằm xác định điểm vào lệnh tối ưu.
  - Khi **không** sử dụng cơ chế xếp hạng rổ danh mục, nhánh này thuộc nhóm **Chiến lược Giao dịch Cơ hội Đa Tài sản theo Hướng (Multi-Asset Opportunistic Directional Trading)**:
    - Hoạt động hoàn toàn theo sự kiện (Event-driven), không bị ép buộc mở lệnh theo chu kỳ.
    - Tài khoản có thể duy trì $0$ vị thế (100% Cash) khi thị trường không có tín hiệu sạch.
    - Chỉ giải ngân vốn khi xuất hiện setup thỏa mãn biên độ rủi ro/lợi nhuận $R:R \ge 1:2.0$.

### 2.1. Nhánh Chiến lược 1: Rổ Danh mục Định lượng Trung lập Thị trường (Cross-Sectional Ranking Portfolio)
- **Bản chất**: Chiến lược Phân bổ Danh mục Định lượng (Quantitative Portfolio Allocation Strategy).
- **Vũ trụ tài sản (Universe)**: $N = 30 \text{ đến } 50$ mã tài sản thanh khoản cao trên MT5.
- **Cơ chế Xếp hạng Đa Nhân tố (Multi-Factor Scoring)**:
  - Tính điểm tổng hợp: Momentum ROC ($M15, H1, H4$), RSI, Trend EMA, và biên độ dao động ATR.
  - **Top 10 Long**: 10 mã mạnh nhất thị trường ➔ Mua (BUY).
  - **Top 10 Short**: 10 mã yếu nhất thị trường ➔ Bán khống (SELL).
- **Phân bổ vốn Dollar-Neutral**: Mỗi mã chiếm cố định $5.0\%$ vốn ($1/20$). Giữ $|\text{Net Exposure}| \le 5\%$.
- **Thoát lệnh & Tái cân bằng**:
  - Tái cân bằng theo chu kỳ (Định kỳ $4H$ hoặc $Daily\text{ }00:00\text{ UTC}$).
  - Cắt lỗ cực đại từng mã: $-8.0\%$.
  - Portfolio Circuit Breaker: $-3.0\%$ tổng tài khoản.

### 2.2. Nhánh Chiến lược 2: Giao dịch Cơ hội Đa Tài sản theo Phương pháp SMC (Multi-Asset Opportunistic SMC Trading)
- **Bản chất**: Chiến lược Giao dịch Cơ hội theo Sự kiện (Event-Driven Opportunistic Trading) sử dụng phương pháp vào lệnh theo cấu trúc Smart Money Concepts.
- **Vũ trụ tài sản giám sát (Multi-Asset Watchlist)**: Giám sát đa tài sản có biến động và thanh khoản tốt nhất (ví dụ: `XAUUSD`, `EURUSD`, `GBPUSD`, `BTCUSDT`, `US100`).
- **Đặc tính vị thế**: Vị thế linh hoạt theo cơ hội ($0 \text{ đến } 5$ lệnh đồng thời), không ép buộc duy trì số lượng lệnh cố định.
- **Logic Phân tích Cấu trúc Giá & Phương pháp SMC**:
  1. **Định hình Cấu trúc Thị trường (Market Structure)**:
     - Xác định xu hướng khung lớn (HTF: $H4, D1$) làm thiên hướng chủ đạo (Bias).
     - Phát hiện các điểm phá vỡ cấu trúc **BOS** (Break of Structure) và đảo chiều xu hướng **CHoCH** (Change of Character) trên khung vào lệnh (LTF: $M15, H1$).
  2. **Xác định Vùng Quan tâm (POI - Points of Interest)**:
     - Nhận diện các Khối lệnh tổ chức (**Order Block - OB**).
     - Nhận diện các Vùng mất cân bằng giá (**Fair Value Gap - FVG**).
     - Nhận diện các pha quét thanh khoản đỉnh/đáy (**Liquidity Sweeps / Inducement**).
  3. **Tích hợp Dữ liệu Đồ họa TradingView Desktop (qua CDP Port 9222)**:
     - Đọc các mức giá kháng cự/hỗ trợ, nhãn dán (labels), hộp vùng giá (boxes) và bảng dữ liệu vẽ từ Pine Script trên biểu đồ.
     - Đọc tín hiệu xác nhận động lượng từ RSI, Bollinger Bands và nến đảo chiều (Pinbar, Engulfing).
- **Quy tắc Quản lý Vốn theo R-Multiple ($1R = 1.0\%$ Equity)**:
  - Rủi ro cố định: $1.0\%$ tài khoản trên mỗi lệnh setup SMC.
  - Công thức tính Lot Size tự động:
    $$\text{Lot Size} = \frac{\text{Equity} \times 1\%}{\text{Khoảng cách từ Entry đến SL (pips)} \times \text{Giá trị 1 Pip}}$$
  - **Tỷ lệ R:R tối thiểu bắt buộc**: $1 : 2.0$ (TP phải đạt tối thiểu gấp đôi khoảng cách SL; SL đặt an toàn sau đỉnh/đáy của Order Block).
- **Cơ chế Thoát lệnh & Trailing Stop**:
  - Chạm giá TP hoặc SL kỹ thuật.
  - Dời Stop Loss về hòa vốn (Breakeven - BE) khi giá đi đúng hướng đạt mức $+1.0R$.
  - Đóng lệnh từng phần (Partial Close 50%) khi chạm vùng cản tiếp theo và thả trôi 50% còn lại theo trend.

### 2.3. Chế độ Vận hành Hệ thống (System Operation Modes)
- **Mode A (Pure Cross-Sectional Ranking Portfolio)**: Chỉ chạy rổ danh mục Long-Short tái cân bằng định kỳ theo lịch trình cố định.
- **Mode B (Pure Multi-Asset Opportunistic SMC)**: Chỉ quét và bắn các setup SMC đạt chuẩn R:R $\ge 1:2.0$ (tối ưu hóa điểm vào lệnh, vị thế linh hoạt theo sự kiện).
- **Mode C (Hybrid Portfolio)**: Phân bổ vốn 50% cho rổ danh mục trung lập (tạo dòng tiền ổn định, Beta = 0) và 50% cho nhánh săn setup cơ hội SMC (tối ưu hóa đột biến lợi nhuận từ Alpha cao).

---

## 3. QUẢN TRỊ RỦI RO ĐỊNH LƯỢNG CHUẨN MT5 (QUANTITATIVE RISK RULES)

| Quy tắc | Phạm vi Áp dụng | Thông số Ngưỡng | Hành vi khi Vi phạm |
| :--- | :--- | :--- | :--- |
| **Net Market Exposure** | Nhánh 1 (CSR Portfolio) | $|\sum w_{\text{Long}} - \sum w_{\text{Short}}| \le 5\%$ | **VETO**: Ép cân đối lại tỷ trọng Long/Short |
| **Tỷ trọng mỗi vị thế** | Nhánh 1 (CSR Portfolio) | Cố định $5.0\%$ vốn ($1/20$) | Tự động chuẩn hóa lại Lot Size |
| **Bộ lọc Phí SWAP MT5** | Nhánh 1 (CSR Portfolio) | $\text{Swap}_{\text{direction}} \ge \text{Ngưỡng cho phép}$ | **VETO**: Loại bỏ mã có phí qua đêm âm nặng |
| **Bộ lọc Giãn Spread** | Toàn hệ thống | $\text{Spread} \le 1.5 \times \text{Avg Spread}$ | **VETO**: Hoãn mở vị thế mã đó |
| **Giới hạn Tương quan** | Nhánh 1 (CSR Portfolio) | $r_{ij} < 0.85$ và $\le 2$ mã cùng ngành | **VETO**: Chọn mã xếp hạng liền kề |
| **Rủi ro mỗi Setup (1R)** | Nhánh 2 (Opportunistic SMC) | Cố định $1.0\%$ Equity / Trade | Tự động tính Lot Size theo khoảng cách SL pips |
| **Tỷ lệ Reward/Risk (R:R)** | Nhánh 2 (Opportunistic SMC) | $\text{R:R} \ge 1 : 2.0$ | **VETO**: Từ chối vào lệnh nếu TP < 2 * SL |
| **Catastrophic SL** | Nhánh 1 (CSR Portfolio) | $-8.0\%$ giá trị vị thế | **Tự động đóng vị thế khẩn cấp** |
| **Max Daily Drawdown** | Toàn hệ thống (Global) | $-3.0\%$ tổng tài khoản | **CIRCUIT BREAKER**: Đóng toàn bộ vị thế, ngắt bot |
| **Chuỗi thua liên tiếp** | Toàn hệ thống (Global) | 3 chu kỳ/lệnh thua liên tiếp | **Cooldown**: Tạm dừng giao dịch 24 giờ |

---

## 4. YÊU CẦU PHI CHỨC NĂNG & HẠ TẦNG (TECHNICAL INTERFACES)

1. **TradingView CDP Interface**:
   - Giao thức: Chrome DevTools Protocol qua HTTP/WebSocket `http://127.0.0.1:9222`.
   - Chức năng: Đọc indicator values, Pine labels, lines, tables và nến OHLCV.
2. **MetaTrader 5 Docker Interface**:
   - Giao thức: RPyC Socket `tcp://127.0.0.1:8001` hoặc FastMCP Server.
   - Chức năng: Đọc `account_info()`, `symbol_info()`, `positions_get()`, `order_send()`.
3. **Môi trường Hạ tầng & Runtime (Infrastructure Environment)**:
   - **Nền tảng chính**: **Lightning AI Studio** (Cloud Ubuntu Linux Container).
   - **Hiển thị Ảo & Remote Desktop**: Server hiển thị ảo `Xvfb :0` kết hợp NoMachine / Web VNC (Port 4000 / 3000) phục vụ chạy giao diện đồ họa headless.
   - **Lưu trữ Bền vững (Data Persistence)**: Sử dụng cơ chế Symlink liên kết dữ liệu cấu hình (`TradingView`, `Chrome`, `MT5 data`) vào ổ lưu trữ gắn ngoài `data-lightning-vps/` để bảo toàn trạng thái đăng nhập khi Studio sleep/wake.
   - **Ngôn ngữ & Môi trường thực thi**: Python 3.11+ quản lý qua `uv`.

---

## 5. TIÊU CHUẨN THỰC NGHIỆM ĐÁNH GIÁ KLTN (EXPERIMENTAL EVALUATION)

Để bảo vệ thành công Khóa luận tốt nghiệp, hệ thống phải hoàn thành các thực nghiệm định lượng sau:

1. **Backtest Lịch sử (Historical Backtesting)**:
   - Dữ liệu: 1 - 2 năm dữ liệu lịch sử nến M15/H1/H4 trên MT5.
   - Thực nghiệm độc lập từng nhánh:
     - **Nhánh 1 (CSR Portfolio)**: Đo lường hiệu suất rổ danh mục Long/Short tái cân bằng định kỳ.
     - **Nhánh 2 (Opportunistic SMC)**: Đo lường hiệu suất các setup SMC khai thác cơ hội theo sự kiện.
2. **Hệ thống Chỉ số Đo lường Bắt buộc**:
   - **Tỷ suất sinh lời ròng (Net Cumulative Return)**.
   - **Tỷ lệ Sharpe & Sortino**: Đo lường chất lượng lợi nhuận trên biến động rủi ro.
   - **Maximum Drawdown (MDD)**: Đánh giá khả năng kiểm soát sụt giảm tài khoản.
   - **Expectancy ($E$)**: Kỳ vọng lợi nhuận trung bình mỗi lệnh/chu kỳ tái cân bằng.
   - **Tỷ lệ can thiệp của Risk Manager**: Thống kê số lần Risk Manager kích hoạt VETO thành công.
