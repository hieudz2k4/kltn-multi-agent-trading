# BỘ TÀI LIỆU KIẾN TRÚC HỆ THỐNG C4 MODEL
## (Multi-Agent Quantitative Trading System Architecture Documentation)

Bộ tài liệu kiến trúc này được xây dựng theo chuẩn **C4 Model** (Context, Container, Component, Code), tích hợp sơ đồ tương tác đồ họa cao cấp được sinh bởi **`archify`** (HTML/SVG standalone, dark/light theme, trace motion) phục vụ thuyết minh Khóa luận tốt nghiệp.

---

## 1. Cấu trúc Tài liệu 4 Tầng C4

| Tầng C4 | Tài liệu Đặc tả | Sơ đồ Tương tác Độc lập (`archify`) | Trọng tâm Thuyết minh |
| :--- | :--- | :--- | :--- |
| **Level 1: System Context** | [c4-context.md](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/c4-context.md) | [c4-context.html](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/c4-context.html) | Ngữ cảnh tương tác giữa Trader, Multi-Agent Core, TradingView CDP và MT5 Broker |
| **Level 2: Container** | [c4-container.md](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/c4-container.md) | [c4-container.html](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/c4-container.html) | Môi trường Lightning AI Studio: Python Core, Node.js CDP, FastMCP Bridge, Display Xvfb |
| **Level 3: Component** | [c4-component.md](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/c4-component.md) | [c4-component.html](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/c4-component.html) | Cấu trúc nội bộ 2 nhánh (CSR Allocation + Opportunistic SMC) & Risk Gatekeeper (VETO) |
| **Level 4: Code / Lifecycle** | [c4-code.md](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/c4-code.md) | [c4-lifecycle.html](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/c4-lifecycle.html) | State Machine vòng đời lệnh từ sinh tín hiệu, kiểm duyệt VETO, dời SL hòa vốn đến chốt lời |

---

## 2. Hợp đồng Giao tiếp & Data Schemas
- **Tập tin định nghĩa Pydantic Models**: [schemas.py](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/contracts/schemas.py)
  - `SignalPayload`: Cấu trúc dữ liệu tín hiệu từ Agent chiến lược.
  - `RiskVerdict`: Kết quả phán quyết phủ quyết (VETO) của Risk Gatekeeper.
  - `OrderExecutionIntent`: Lệnh đã được phê duyệt gửi xuống MT5.
  - `CircuitBreakerState`: Trạng thái ngắt mạch an toàn của tài khoản.

---

## 3. Hướng dẫn Mở & Trích xuất Sơ đồ cho Khóa luận
1. **Xem trực tiếp**: Click chuột phải vào bất kỳ file `.html` trong thư mục [diagrams/](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/C4-Documentation/diagrams/) và chọn *Open with Live Server* hoặc mở bằng trình duyệt (Chrome, Safari).
2. **Xuất ảnh báo cáo**: Trên góc phải của giao diện trình duyệt Archify có sẵn nút **Export SVG / PNG** để tải hình ảnh vector độ nét cao chèn trực tiếp vào báo cáo thuyết minh và slide trình chiếu.
