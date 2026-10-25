# Đặc tả Kỹ thuật: Hyperdash Data Pipeline (Option B)

- **Dự án**: `kltn-multi-agent-trading`
- **Tên tài liệu**: `HYPERDASH_DATA_PIPELINE_SPEC`
- **Mã tài liệu**: `SPEC-HYPERDASH-DATA-PIPELINE-01`
- **Kiến trúc**: Task Queue + Checkpoint Worker Architecture
- **Trạng thái**: APPROVED

---

## 1. Tổng quan & Mục tiêu

Pipeline này phục vụ mục tiêu thu thập, làm sạch và gắn nhãn tập dữ liệu giao dịch từ các Top Trader thành công trên nền tảng Hyperliquid / Hyperdash. Dữ liệu sau khi xử lý sẽ được lưu trữ dưới dạng Parquet/DuckDB để làm đầu vào huấn luyện và backtest cho hệ thống Multi-Agent Quantitative Trading (Agent SMC và Agent CSR).

### 1.1. Mục tiêu cốt lõi
1. **Discovery**: Tự động lọc và xếp hạng trader theo Size Cohort (nhóm quy mô vốn) qua `ExploreTraders` và `PnlLeaderboard`, kết hợp Screening Gate 0 cứng để chặn ví rác trước khi gọi L1 RPC.
2. **Ingestion**: Thu thập hồ sơ định lượng (`GetTrader`), trạng thái đòn bẩy (`clearinghouseState`) và lịch sử khớp lệnh (`userFills`) đầy đủ từ L1 RPC với khả năng phục hồi lỗi (fault-tolerant) và tự động resume từ checkpoint.
3. **Enrichment, Quality Gate & Labeling**: Tính toán và kiểm định bộ 7 chỉ số định lượng cốt lõi (`Max Drawdown 30D`, `Sortino 30D`, `Sharpe All-Time/90D`, `Profit Factor`, `Win Rate`, `Equity Curve R²` & `K-Ratio`, `Effective Leverage`), kèm Calmar Ratio và gắn nhãn phân loại:
   - `quality_tier`: Phân hạng chất lượng dữ liệu (`GOLD`, `PASS`, `REJECT`) theo ngưỡng lọc chuẩn tại [quantitative_trading_metrics_report.md](file:///Users/hieudz/Desktop/workspace/kltn-multi-agent-trading/reports/quantitative_trading_metrics_report.md).
   - `smoothness_tier`: Phân bậc độ mượt đường cong vốn theo `R²` và chiều dốc `β`.
   - `is_algo`: Tự động nhận diện trader sử dụng thuật toán/bot hay discretionary trader.
   - `strategy_tag`: Phân loại chiến lược (`FUNDING_CARRY`, `GRID_MARTINGALE`, `BREAKOUT_MOMENTUM`, `TREND_DISCRETIONARY`).

### 1.2. Non-goals
- Không thực hiện live copy-trade trực tiếp trên tài khoản thật.
- Không nhận diện danh tính thực tế (KYC) của địa chỉ ví.

---

## 2. Kiến trúc Hệ thống (System Architecture)

```
       ┌───────────────────────────────┐
       │   Hyperdash GraphQL API       │
       │   (api.hyperdash.com/graphql) │
       └──────────────┬────────────────┘
                      │  ExploreTraders + PnlLeaderboard
                      ▼
         ┌─────────────────────────┐
         │    Discovery Worker     │
         │  (Gate 0 Screening)     │
         └────────────┬────────────┘
                      │ Chỉ ví pass Gate 0
                      ▼
         [data/traders_discovered.json]
                      │
                      ▼
         ┌─────────────────────────┐         ┌───────────────────────────────┐
         │    Ingestion Worker     │ ◄────── │   Hyperliquid L1 RPC /info    │
         │   (Token-Bucket 5 rps)  │         │   (api.hyperliquid.xyz/info)  │
         └────────────┬────────────┘         └───────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │   data/checkpoint.json  │ ◄─── Quản lý resume & retry
         └────────────┬────────────┘
                      │
                      ▼
         [data/raw_fills/{address}.parquet]
                      │
                      ▼
         ┌─────────────────────────┐
         │ Transform & Tag Worker  │
         │ (Ratios + ML/Rule Tag)  │
         └────────────┬────────────┘
                      │
                      ▼
         [data/dataset_traders.parquet]
```

---

## 3. Nguồn Dữ liệu & Giao thức

### 3.1. Nguồn 1: Hyperdash GraphQL API
- **Endpoint**: `POST https://api.hyperdash.com/graphql`
- **Mục đích**: Thu thập danh sách leaderboard, xếp hạng PnL và copy trading.
- **Xác thực**: Public access, yêu cầu giả lập trình duyệt (Browser headers) để vượt qua Cloudflare WAF.

---

#### Query 1: Bảng xếp hạng PnL theo khung thời gian (`PnlLeaderboard`)
Dùng để quét top trader theo khung `d30` và `alltime`. Lưu ý: Query này **không trả về `sizeCohort`** — phân nhóm vốn sẽ được lấy từ `ExploreTraders` (Query 2) hoặc `GetTrader`.

```graphql
query PnlLeaderboard(
  $category: PnlLeaderboardCategory!
  $window: PnlLeaderboardWindow!
  $address: String
  $page: Int
  $pageSize: Int!
) {
  pnlLeaderboard(
    category: $category
    window: $window
    address: $address
    page: $page
    pageSize: $pageSize
  ) {
    ...LeaderboardFields
    __typename
  }
}

fragment LeaderboardFields on PnlLeaderboard {
  pagination { page pageSize totalItems totalPages __typename }
  data { ...LeaderboardEntryFields __typename }
  self { ...LeaderboardEntryFields __typename }
  __typename
}

fragment LeaderboardEntryFields on PnlLeaderboardEntry {
  rank
  address
  displayName
  label
  avatar
  twitter
  tag
  verified
  accountValue
  copyScore
  netPnl
  grossPnl
  fundingPnl
  totalFees
  volume
  tradeCount
  winningTrades
  losingTrades
  lastTradeAt
  __typename
}
```

**Variables mẫu**:
```json
{
  "category": "all",
  "window": "d30",
  "page": 1,
  "pageSize": 50,
  "address": null
}
```

> **Lưu ý**: Tham số `window` nhận giá trị: `"d1"`, `"d7"`, `"d30"`, `"ytd"`, `"alltime"` (viết thường liền nhau, không có `"d90"`). Pipeline sử dụng `"d30"` làm khung quét chính để bắt các trader đang hoạt động hiệu quả trong cấu trúc thị trường hiện tại, kết hợp `"alltime"` để không bỏ sót Lead Trader lớn.

---

#### Query 2: Danh sách Lead Trader theo Copy Score & Size Cohort (`ExploreTraders`)
Đây là query cốt lõi của luồng Discovery. Trả về `sizeCohort` và `portfolioGraph` ngay tại bước này, cho phép lọc theo nhóm vốn mà không cần gọi `GetTrader` cho từng ví.

```graphql
query ExploreTraders(
  $page: Int
  $pageSize: Int
  $timeframe: TraderTimeframe!
  $sortBy: TraderSortInput
  $filters: TraderFilterInput
) {
  exploreTraders(
    page: $page
    pageSize: $pageSize
    timeframe: $timeframe
    sortBy: $sortBy
    filters: $filters
  ) {
    pagination { page pageSize totalItems totalPages }
    data {
      address
      displayName
      label
      verified
      avatar
      twitter
      tag

      # Phân loại vốn & copytrade (alias sang copyScoreV2 theo bundle mới)
      copyScore: copyScoreV2
      perpsEquity
      pnl
      pnlCohort
      sizeCohort         # SMALL | MID | WHALE

      # Tỷ lệ thắng & Số lượng giao dịch
      winrate
      totalTrades
      totalLongTrades
      totalShortTrades
      totalWinningTrades
      totalLosingTrades

      # Chỉ số định lượng tổng quan
      sharpe
      drawdown

      # Chuỗi vốn theo thời gian
      portfolioGraph {
        timestamp
        value
      }
    }
  }
}
```

**Variables mẫu (quét chính)**:
```json
{
  "page": 1,
  "pageSize": 50,
  "timeframe": "all",
  "sortBy": { "field": "copyScoreV2", "order": "desc" },
  "filters": {}
}
```

> **Lưu ý**: Tham số `timeframe` (`TraderTimeframe` enum) nhận `"one_day"`, `"seven_days"`, `"thirty_days"`, `"all"`. Pipeline dùng `"all"` và sort theo `"copyScoreV2"` để không bỏ sót các Lead Trader lớn dài hạn và khớp với điểm Copy Score V2 trên giao diện Hyperdash hiện tại.

---

#### Query 3: Hồ sơ Định lượng Đa khung & Chuỗi vốn (`GetTrader`)
Gọi cho từng ví đã qua Gate 0. Trả về đầy đủ chỉ số `sharpe`, `sortino`, `drawdown` theo `30d/90d/AllTime`, dữ liệu winrate đa khung và mảng `portfolioGraph` phục vụ hồi quy OLS tính `R²` & `K-Ratio`.

```graphql
query GetTrader($address: String!) {
  getTrader(address: $address) {
    address
    displayName
    label
    verified
    isClaimed

    # Vốn & PnL
    perpsEquity
    pnl
    pnlCohort
    sizeCohort

    # Tỷ lệ thắng đa khung
    winrate
    winrate7d
    winrate30d
    winrateLifetime
    winrate90d
    winrate180d
    winrate365d

    # Số lượng lệnh đa khung
    totalTrades
    trades7d
    trades30d
    totalLongTrades
    totalShortTrades
    totalWinningTrades
    totalLosingTrades

    # Chỉ số định lượng (Quant Metrics)
    sharpe           # All-time Sharpe
    sharpe30d
    sharpe90d
    sharpe180d
    sharpe365d

    sortino30d
    sortino90d
    sortino180d
    sortino365d

    drawdown         # All-time Drawdown
    drawdown7d
    drawdown30d
    drawdown90d
    drawdown180d
    drawdown365d

    copyScore: copyScoreV2

    # Biểu đồ chuỗi vốn — dùng để tính R² và K-Ratio
    portfolioGraph {
      timestamp
      value
    }
  }
}
```

---

### 3.2. Nguồn 2: Hyperliquid L1 RPC Endpoint
- **Endpoint**: `POST https://api.hyperliquid.xyz/info`
- **Mục đích**: Lấy toàn bộ lịch sử khớp lệnh (`userFills`) và trạng thái ký quỹ / đòn bẩy thực tế (`clearinghouseState`) của ví cụ thể.
- **Payload 1 (`userFills`)**:
```json
{
  "type": "userFills",
  "user": "0x1234567890abcdef1234567890abcdef12345678"
}
```
- **Payload 2 (`clearinghouseState` — tính Effective Leverage)**:
```json
{
  "type": "clearinghouseState",
  "user": "0x1234567890abcdef1234567890abcdef12345678"
}
```
Trả về `marginSummary.totalNtlPos` và `marginSummary.accountValue` để tính `Effective Leverage = totalNtlPos / accountValue`.

> **Implementation Note — Effective Leverage = 0 Edge Case**: Nếu lúc chạy `ingest`, trader vừa đóng hết vị thế thì `totalNtlPos = 0` → `effective_leverage = 0.0`, đánh giá sai là "không dùng đòn bẩy". Logic trong `transform.py` phải kết hợp fallback từ `userFills`:
> ```python
> realtime_lev = total_ntl_pos / account_value  # từ clearinghouseState
> historical_max_lev = fills_df["notional"].max() / account_value  # từ userFills
> effective_leverage = max(realtime_lev, historical_max_lev)
> ```
> Nếu cả hai đều bằng 0 (ví mới, chưa có fill), gán `effective_leverage = NaN` và loại khỏi pipeline.

- **Rate Limit Policy**: Giới hạn tối đa 5 requests/giây để tránh mã lỗi HTTP 429.

---

## 4. Đặc tả Lược đồ Dữ liệu (Data Schemas)

### 4.1. Trader Discovery Schema (`TraderDiscoveryRecord`)
Schema ghi vào `data/traders_discovered.json` sau Gate 0. Tất cả trường đều map 1-1 với payload thực tế từ `PnlLeaderboard` hoặc `ExploreTraders`.

| Trường | Kiểu dữ liệu | Nguồn API | Mô tả |
| :--- | :--- | :--- | :--- |
| `address` | `str` | `PnlLeaderboard` / `ExploreTraders` | Địa chỉ ví Ethereum (0x...) |
| `rank` | `int` | `PnlLeaderboard.rank` | Thứ hạng trong bảng xếp hạng |
| `display_name` | `str` | `displayName` | Tên hiển thị của trader |
| `account_value` | `float` | `accountValue` / `perpsEquity` | Tổng giá trị tài khoản (USDC) — dùng để phân nhóm vốn |
| `size_cohort` | `str` | `sizeCohort` từ `ExploreTraders` / `GetTrader` | Phân nhóm vốn: `SMALL` ($1k-$10k), `MID` ($10k-$100k), `WHALE` (>$100k) |
| `net_pnl` | `float` | `netPnl` | Lợi nhuận ròng (USDC, đã trừ phí) |
| `gross_pnl` | `float` | `grossPnl` | Lợi nhuận gộp (USDC) |
| `funding_pnl` | `float` | `fundingPnl` | PnL đến từ Funding Fee |
| `volume` | `float` | `volume` | Tổng khối lượng giao dịch (USDC) |
| `trade_count` | `int` | `tradeCount` | Tổng số lượt giao dịch trong khung thời gian |
| `winning_trades` | `int` | `winningTrades` | Số lệnh thắng |
| `losing_trades` | `int` | `losingTrades` | Số lệnh thua |
| `copy_score` | `float` | `copyScore` | Điểm số đánh giá tổng hợp của Hyperdash (0–100) |
| `last_trade_at` | `int` | `lastTradeAt` | Unix timestamp (giây) lần giao dịch gần nhất |
| `window` | `str` | — | Khung thời gian quét (`d30`, `alltime`) |
| `discovered_at` | `int` | — | Unix timestamp (giây) lúc pipeline quét |

> **Lưu ý**: Trường `MICRO` cohort (`accountValue < $1,000`) bị loại tại Gate 0 và không xuất hiện trong file này.

> **Implementation Note — Chênh lệch trường giữa hai nguồn Discovery**:
> `PnlLeaderboard` và `ExploreTraders` trả về các tập trường khác nhau. Khi code, cần xử lý như sau:
>
> | Trường | `PnlLeaderboard` | `ExploreTraders` | Xử lý |
> | :--- | :---: | :---: | :--- |
> | `rank` | ✅ có | ❌ không có | `ExploreTraders` → gán `rank = None` |
> | `sizeCohort` | ❌ không có | ✅ có | `PnlLeaderboard` → suy từ `accountValue`: `$1k–$10k → SMALL`, `$10k–$100k → MID`, `>$100k → WHALE` |
> | `grossPnl`, `fundingPnl` | ✅ có | ❌ không có | `ExploreTraders` → gán `None` (Optional field) |
> | `lastTradeAt` | ✅ có | ❌ không có | `ExploreTraders` → dùng `portfolioGraph[-1].timestamp` làm proxy cho Gate 0 |
> | `portfolioGraph` | ❌ không có | ✅ có | `PnlLeaderboard` → bỏ qua ở Discovery, lấy tại bước `GetTrader` |

### 4.2. Raw Fills Schema (`RawFillRecord`)
Lưu trữ dạng file nén Parquet theo từng địa chỉ ví: `data/raw_fills/{address}.parquet`.
| Cột | Kiểu | Mô tả |
| :--- | :--- | :--- |
| `tid` | `int64` | Mã định danh duy nhất của lượt khớp lệnh |
| `coin` | `string` | Tên tài sản (e.g., `BTC`, `ETH`, `SOL`) |
| `side` | `string` | `B` (Buy) hoặc `A` (Ask / Sell) |
| `px` | `float64` | Mức giá khớp thực tế |
| `sz` | `float64` | Khối lượng khớp |
| `time` | `int64` | Epoch timestamp tính bằng milliseconds |
| `fee` | `float64` | Phí giao dịch phải trả (USDC) |
| `closed_pnl` | `float64` | Lợi nhuận thực nhận khi đóng lệnh (USDC) |
| `dir` | `string` | Chiều lệnh (`Open Long`, `Close Long`, `Open Short`, `Close Short`) |

### 4.3. Enriched Dataset Schema (`data/dataset_traders.parquet`)
| Cột | Kiểu | Mô tả |
| :--- | :--- | :--- |
| `address` | `string` | Địa chỉ ví trader |
| `size_cohort` | `string` | Nhóm quy mô vốn (`SMALL`, `MID`, `WHALE`) |
| `total_trades` | `int32` | Tổng số lượt khớp lệnh trong kỳ |
| `trades_30d` | `int32` | Số lượng lệnh trong 30 ngày gần nhất (đảm bảo mẫu thống kê `N >= 30`) |
| `win_rate` | `float32` | Tỷ lệ lệnh có PnL dương (`wins / total_closed_trades`) |
| `profit_factor` | `float32` | Tổng Gross Profit chia cho Tổng Gross Loss |
| `max_drawdown_30d` | `float32` | Tỷ lệ sụt giảm vốn tối đa 30 ngày gần nhất (%) |
| `max_drawdown_90d` | `float32` | Tỷ lệ sụt giảm vốn tối đa 90 ngày gần nhất (%) |
| `max_drawdown_all` | `float32` | Tỷ lệ sụt giảm vốn tối đa toàn thời gian (%) từ đường cong vốn |
| `sharpe_ratio_all` | `float32` | Tỷ số Sharpe toàn thời gian (`R_f = 0`) |
| `sharpe_ratio_90d` | `float32` | Tỷ số Sharpe khung 90 ngày |
| `sortino_ratio_30d` | `float32` | Tỷ số Sortino khung 30 ngày (chỉ phạt downside deviation) |
| `calmar_ratio` | `float32` | `Annualized Return / Max Drawdown All-Time` |
| `equity_r2` | `float32` | Hệ số xác định `R²` (0 → 1) từ hồi quy OLS tuyến tính chuỗi `portfolioGraph` (đo độ mượt đường vốn) |
| `equity_beta` | `float32` | Độ dốc `β` của đường hồi quy OLS — phải `> 0` để xác nhận xu hướng tăng |
| `k_ratio` | `float32` | Tỷ số Kestner: `β / (SE(β) × √n)` — đo độ nhất quán tốc độ tăng trưởng vốn |
| `effective_leverage` | `float32` | Đòn bẩy thực tế (`totalNtlPos / accountValue`) từ `clearinghouseState` |
| `avg_holding_sec` | `float32` | Thời gian nắm giữ vị thế trung bình (giây) |
| `funding_pnl_pct` | `float32` | % PnL đến từ `fundingPnl` so với tổng `netPnl` — đặc trưng phân loại `FUNDING_CARRY` |
| `quality_tier` | `string` | Phân hạng chất lượng: `GOLD` (Dataset Vàng), `PASS` (Chấp nhận), `REJECT` (Loại bỏ) |
| `smoothness_tier` | `string` | Phân bậc đường vốn: `SMOOTH_LINEAR` (`R²≥0.90` & `β>0`), `MODERATE` (`0.75≤R²<0.90`), `CHOPPY` (`R²<0.75` hoặc `β≤0`) |
| `is_algo` | `bool` | Cờ nhận diện giao dịch bằng thuật toán / bot |
| `strategy_tag` | `string` | Nhãn chiến lược (`FUNDING_CARRY`, `GRID_MARTINGALE`, `BREAKOUT_MOMENTUM`, `TREND_DISCRETIONARY`) |

---

## 5. Tiêu chí Lọc Chất lượng (Quality Gate) & Gắn nhãn Định lượng

### 5.0. Gate 0 — Screening tại Discovery (Bộ lọc Sơ bộ)
Áp dụng ngay sau khi nhận response từ `PnlLeaderboard` / `ExploreTraders`, **trước khi đẩy ví vào hàng đợi Ingestion**. Mục đích: loại bỏ ví rác để bảo toàn rate limit 5 rps cho L1 RPC.

| Tiêu chí | Ngưỡng cứng | Trường kiểm tra | Lý do |
| :--- | :---: | :--- | :--- |
| **Tài khoản còn hoạt động** | `lastTradeAt ≤ 7 ngày ago` | `lastTradeAt` | Loại trader đã ngừng hoạt động |
| **Vốn tối thiểu** | `accountValue ≥ $1,000` | `accountValue` / `perpsEquity` | Bỏ cohort MICRO — dữ liệu nhiễu, không đại diện |
| **Có lợi nhuận** | `netPnl > 0` | `netPnl` | Loại ví thua lỗ hoàn toàn |
| **Copy Score tối thiểu** | `copyScore ≥ 60.0` | `copyScore` | Lọc trader có profile đã được Hyperdash xác thực chất lượng (anti-rác) |

> Ví không qua Gate 0 bị ghi vào `data/rejected_screening.json` kèm lý do để audit. Chỉ ví qua Gate 0 mới được ghi vào `data/traders_discovered.json` và đẩy vào Ingestion Queue.

> **Lưu ý**: Tiêu chí `tradeCount` không còn là bộ lọc cứng tại Gate 0. Lịch sử giao dịch đủ dài được đảm bảo bởi `len(portfolioGraph) ≥ 30` tại Gate 1, vì Hyperdash backfill toàn bộ lịch sử on-chain khi index ví.

---

### 5.1. Bộ lọc Chất lượng Đường vốn — Gate 1 (Equity Curve Quality Filter)
Áp dụng tại giai đoạn Transform sau khi đã tính toán đầy đủ metrics từ `portfolioGraph`. Mục tiêu: giữ lại các ví có **đường vốn tăng trưởng ổn định, mượt mà** — đủ tin cậy để làm dữ liệu huấn luyện cho hệ thống Multi-Agent.

**Bộ lọc cứng (Hard Filters)**:

| Tiêu chí | Ngưỡng | Trường kiểm tra | Lý do |
| :--- | :---: | :--- | :--- |
| **Lịch sử ví đủ dài** | `len(portfolioGraph) ≥ 30` | `portfolioGraph` từ `GetTrader` | Cần tối thiểu 30 điểm dữ liệu để hồi quy OLS tin cậy thống kê |
| **Đường vốn tăng trưởng** | `equity_beta > 0` | OLS trên `portfolioGraph` | Loại trader thua lỗ dài hạn hoặc không có xu hướng |
| **Đường vốn mượt** | `equity_r2 ≥ 0.75` | OLS trên `portfolioGraph` | Loại ví có equity curve lên-xuống thất thường (CHOPPY) |

> **Lý do bỏ lọc cứng bằng MDD, Sharpe, Sortino, Win Rate, Leverage**: Hyperliquid L1 `userFills` chỉ trả về tối đa 2.000 fills gần nhất (không phân trang theo `type=userFills`). Với trader scalper/bot, 2.000 fills có thể chỉ bao quát vài ngày — dẫn đến `win_rate` và `profit_factor` bị méo nghiêm trọng nếu tính từ fills thô. Dữ liệu tổng hợp từ Hyperdash (Sharpe, Sortino, MDD) đã chính xác hơn, nhưng các ngưỡng cứng dễ bị vượt bởi correction ngắn hạn (ví dụ: `drawdown_90d` tăng lên 21% trong nhịp điều chỉnh 2 tuần). Equity Curve R² là chỉ số trực quan và toàn diện nhất để đo chất lượng trader.

**Quy tắc phân hạng `quality_tier`** (closed-interval):
- `GOLD`: `equity_r2 ≥ 0.90` **và** `equity_beta > 0` **và** `len(portfolioGraph) ≥ 30`
- `PASS`: `equity_r2 ≥ 0.75` **và** `equity_beta > 0` **và** `len(portfolioGraph) ≥ 30`
- `REJECT`: Không thỏa mãn bất kỳ điều kiện nào ở trên

**Các chỉ số định lượng khác** (Sharpe, Sortino, MDD, Profit Factor, Win Rate, Effective Leverage, Calmar, K-Ratio) vẫn được **tính toán đầy đủ và lưu vào `dataset_traders.parquet`** làm metadata cho downstream model/agent sử dụng — nhưng **không dùng để lọc**.

---

### 5.2. Nhận diện Thuật toán (`is_algo`)
Một trader được phân loại là `is_algo = True` khi thỏa mãn ít nhất **2 trong 3** tiêu chuẩn sau:

1. **Activity Density**: Trong chuỗi 14 ngày hoạt động, ≥ 70% các window 6 giờ liên tiếp phải có ít nhất 1 fill. Phản ánh hoạt động liên tục 24/7 của bot mà không bị ảnh hưởng bởi maintenance gap ngắn.

2. **Periodic Order Clustering (CV Rule)**: Hệ số biến thiên của khoảng thời gian giữa các lệnh thỏa mãn:
   ```
   CV(Δt) = σ(Δt) / μ(Δt) < 0.20
   ```
   hoặc ≥ 60% các khoảng `Δt` rơi vào bội số của các chu kỳ cố định `{60s, 300s, 900s, 3600s}` (Round Interval Clustering).
   > **Lý do thay `σ_Δt < 5s`**: Công thức cũ chỉ bắt được HFT bot. `CV(Δt) < 0.20` bắt được toàn bộ bot DCA, Grid, Rebalance có chu kỳ 15m–4h với phân bố lệnh đồng đều nhưng `σ` lớn.

3. **High Frequency Activity**: Tần suất giao dịch bình quân vượt quá 50 lệnh/ngày trong 14 ngày quan sát.

---

### 5.3. Phân loại Chiến lược (`strategy_tag`)
- **`FUNDING_CARRY`**:
  - Tỷ lệ giữ lệnh vắt qua mốc thanh toán funding (1 giờ hoặc 8 giờ) > 85%.
  - PnL đến chủ yếu từ `funding_fee` hoặc Delta rủi ro gần bằng 0 (Hedging).
- **`GRID_MARTINGALE`**:
  - Xuất hiện chuỗi lệnh cùng chiều với khối lượng tăng dần khi giá đi ngược hướng vị thế.
  - Khoảng cách giữa các bước giá vào lệnh đều nhau (`ΔP ≈ const`).
- **`BREAKOUT_MOMENTUM`**:
  - Thời điểm mở vị thế trùng với các cây nến có khối lượng đột biến (`Volume Spike > 2.5 × MA20`).
  - Tỷ lệ Risk/Reward cao, thời gian giữ lệnh ngắn đến trung bình (< 4 giờ).
- **`TREND_DISCRETIONARY`**:
  - Thời gian giữ lệnh dài (> 12 giờ đến nhiều ngày).
  - Phân bố giờ vào lệnh tập trung vào các phiên giao dịch chính (London/New York), có chu kỳ nghỉ ngơi tự nhiên của con người.

---

## 6. Cơ chế Quản lý Hàng đợi & Checkpoint (Task Queue & Fault Tolerance)

### 6.1. Cấu trúc `data/checkpoint.json`
```json
{
  "updated_at": "2026-10-25T11:15:00Z",
  "total_discovered": 350,
  "completed_count": 120,
  "failed_count": 2,
  "tasks": {
    "0x123...": {
      "status": "COMPLETED",
      "fills_count": 850,
      "last_updated": 1740001200
    },
    "0x456...": {
      "status": "PENDING",
      "retry_count": 0
    },
    "0x789...": {
      "status": "FAILED",
      "retry_count": 3,
      "last_error": "HTTP 429: Rate limit exceeded"
    }
  }
}
```

### 6.2. Phục hồi và Chống lỗi (Error Recovery)
- **Resume Idempotency**: Khi khởi động lại lệnh `ingest`, worker chỉ duyệt qua các địa chỉ có trạng thái `PENDING` hoặc `FAILED` với `retry_count < 3`.
- **Atomic Writing**: Ghi dữ liệu Parquet ra file tạm (`.tmp`) trước, sau khi ghi hoàn tất và kiểm tra checksum mới đổi tên thành `.parquet`.
- **Adaptive Rate Limiter**:
  - Triển khai Token Bucket giới hạn 5 req/s.
  - Khi gặp mã lỗi `429`, kích hoạt cơ chế Exponential Backoff: Chờ `2^n × 1s` (tối đa 30s) trước khi thử lại.

---

## 7. Cấu trúc Module Triển khai (`src/hyperdash_data_pipeline/`)

```
src/hyperdash_data_pipeline/
├── __init__.py
├── schemas.py           # Pydantic models & Parquet schema definitions
├── discovery.py         # Hyperdash GraphQL client (PnlLeaderboard, ExploreTraders) & Gate 0 screening
├── ingestion.py         # Hyperdash GetTrader + Hyperliquid L1 RPC client, queue & checkpoint manager
├── transform.py         # Multi-timeframe ratios (Sharpe, Sortino, MDD, PF, R², K-Ratio) & strategy tagging
└── coordinator.py       # CLI Entrypoint điều phối pipeline
```

---

## 8. CLI Interface

```bash
# Giai đoạn 1: Discovery danh sách ví (Gate 0 screening: minEquity=$1000, minCopyScore=60)
python -m src.hyperdash_data_pipeline.coordinator discover --window d30 --min-copyscore 60.0 --min-equity 1000

# Giai đoạn 2: Thu thập GetTrader profile, clearinghouseState và raw fills theo queue + checkpoint
python -m src.hyperdash_data_pipeline.coordinator ingest --workers 3 --rate-limit 5

# Giai đoạn 3: Tính toán 7 core metrics (Sharpe, Sortino, MDD, PF, R², K-Ratio, Lev), lọc Quality Gate và xuất Parquet
python -m src.hyperdash_data_pipeline.coordinator transform --min-tier PASS --output data/dataset_traders.parquet
```

---

## 9. Implementation Notes Tổng hợp

Phần này tổng hợp các edge case quan trọng cần xử lý đặc biệt khi code, được phát hiện qua phân tích schema và logic pipeline.

### 9.1. Trường Optional phân biệt theo nguồn Discovery

Khi merge ví từ `PnlLeaderboard` và `ExploreTraders`, các trường sau là **Optional** tùy nguồn:

```python
@dataclass
class TraderDiscoveryRecord:
    address: str
    copy_score: float
    account_value: float
    net_pnl: float
    trade_count: int
    last_trade_at: int          # Proxy = portfolioGraph[-1].timestamp nếu từ ExploreTraders
    window: str
    discovered_at: int
    size_cohort: str            # Suy từ account_value nếu từ PnlLeaderboard
    rank: Optional[int] = None  # None nếu từ ExploreTraders
    gross_pnl: Optional[float] = None    # None nếu từ ExploreTraders
    funding_pnl: Optional[float] = None  # None nếu từ ExploreTraders
    volume: Optional[float] = None
```

### 9.2. Hàm suy `size_cohort` từ `account_value`

Dùng khi nguồn là `PnlLeaderboard` (không trả về `sizeCohort`):

```python
def infer_size_cohort(account_value: float) -> str:
    if account_value < 1_000:
        return "MICRO"   # Sẽ bị loại tại Gate 0
    elif account_value < 10_000:
        return "SMALL"
    elif account_value < 100_000:
        return "MID"
    else:
        return "WHALE"
```

### 9.3. Effective Leverage Fallback

Xử lý trường hợp trader vừa đóng toàn bộ vị thế khi pipeline chạy:

```python
def compute_effective_leverage(
    total_ntl_pos: float,
    account_value: float,
    fills_df: pd.DataFrame,
) -> float:
    if account_value <= 0:
        return float("nan")
    realtime_lev = total_ntl_pos / account_value
    if fills_df.empty:
        return float("nan")   # Ví chưa có fill → loại khỏi pipeline
    historical_max_lev = fills_df["notional"].max() / account_value
    return max(realtime_lev, historical_max_lev)
```

### 9.4. Closed-Interval Tier Mapping

Sử dụng hàm helper sau trong `transform.py` để tránh dead-zone:

```python
def score_metric(metric: str, value: float) -> str:
    """Returns 'GOLD' | 'PASS' | 'REJECT'"""
    thresholds = {
        # (reject_max, pass_min, gold_min) — đơn vị như trong bảng Gate 1
        "trades_30d":        (30,   30,   50),    # REJECT < 30, PASS [30,50), GOLD >= 50
        "max_drawdown_30d":  (None, None, None),  # Xử lý riêng: REJECT > 20, GOLD <= 8
        "sortino_ratio_30d": (1.5,  1.5,  3.0),
        "sharpe_ratio_all":  (1.0,  1.0,  2.0),
        "profit_factor":     (1.3,  1.3,  3.0),
        "win_rate":          (0.50, 0.50, 0.80),
        "equity_r2":         (0.75, 0.75, 0.90),
        "effective_leverage":(None, None, None),  # Xử lý riêng: REJECT > 5, GOLD <= 1.5
    }
    # ... (implementation per metric)
```
