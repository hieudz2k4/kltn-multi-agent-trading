#!/usr/bin/env node

/**
 * Whale Order Sync for TradingView
 * 
 * Script này chạy trên Máy Chính (chứa TradingView Desktop).
 * Nó sẽ gọi API trên VPS (chứa Tracker Backend) để lấy các lệnh cá voi mới nhất,
 * sau đó sử dụng CLI của tradingview-mcp để vẽ đường (horizontal line) lên chart.
 */

const { execSync } = require('child_process');
const fetch = require('node-fetch'); // Đảm bảo đã cài hoặc dùng Node 18+ native fetch
const path = require('path');

// --- CẤU HÌNH ---
// Điền IP/Domain của VPS (có chứa cổng, vd: http://1.2.3.4:3000)
const VPS_API_URL = process.env.VPS_API_URL || 'http://<VPS_IP>:3000/whale-trades';

// Đường dẫn tới thư mục tradingview-mcp (Mặc định là ở cùng repo)
const CLI_PATH = path.join(__dirname, '..', 'src', 'cli', 'index.js');
const SYNC_INTERVAL_MS = 10000; // 10 giây/lần

// Biến lưu trạng thái để tránh vẽ trùng
const drawnTradeIDs = new Set();

async function getActiveSymbol() {
    try {
        const output = execSync(`node "${CLI_PATH}" state`, { encoding: 'utf-8' });
        const state = JSON.parse(output);
        return state.symbol; // Vd: "BINANCE:BTCUSDT" hoặc "BTCUSDT"
    } catch (err) {
        console.error("Lỗi khi lấy trạng thái chart (Đảm bảo TV đang mở với port 9222):", err.message);
        return null;
    }
}

async function drawWhaleTradeOnChart(trade) {
    // Trade Format: { id, coin, side, px, sz, isKnownTrader, action, ... }
    const actionStr = trade.action ? trade.action.replace('_', ' ') :
        (trade.side.toUpperCase() === 'B' || trade.side.toUpperCase() === 'BUY' ? 'BUY' : 'SELL');

    const text = `Whale ${actionStr} (${trade.sz} @ ${trade.px})`;

    console.log(`Tiến hành vẽ lệnh lên chart: ${text}`);

    try {
        // Dùng CLI vẽ một horizontal line
        // node index.js draw shape horizontal_line --price 95000 --text "Whale LONG"
        const cmd = `node "${CLI_PATH}" draw shape horizontal_line --price ${trade.px} --text "${text}"`;
        execSync(cmd, { encoding: 'utf-8' });
    } catch (err) {
        console.error(`Lỗi khi vẽ lệnh ID ${trade.id}:`, err.message);
    }
}

async function syncLoop() {
    console.log(`[Sync] Đang kiểm tra biểu đồ hiện tại...`);
    const activeSymbol = await getActiveSymbol();
    if (!activeSymbol) return;

    console.log(`[Sync] Chart đang mở đồng: ${activeSymbol}. Gọi lên VPS lấy dữ liệu...`);

    try {
        // Chỉ lấy 20 trade gần nhất
        const response = await fetch(`${VPS_API_URL}?limit=20`);
        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
        const result = await response.json();
        const trades = result.data || [];

        // Tách base coin (Vd rút gọn "BINANCE:BTCUSDT" -> "BTC")
        const symbolClean = activeSymbol.includes(':') ? activeSymbol.split(':')[1] : activeSymbol;
        const baseCoin = symbolClean.replace(/USDT|USD|PERP|\!/g, '');

        // Lọc các lệnh của cá voi trùng với đồng coin trên chart
        const relevantTrades = trades.filter(t =>
            t.isKnownTrader &&
            (t.coin.toUpperCase() === baseCoin.toUpperCase() || activeSymbol.includes(t.coin.toUpperCase())) &&
            !drawnTradeIDs.has(t.id)
        );

        for (const trade of relevantTrades) {
            await drawWhaleTradeOnChart(trade);
            drawnTradeIDs.add(trade.id);
        }

    } catch (err) {
        console.error("[Sync] Không thể lấy dữ liệu từ VPS:", err.message);
    }
}

console.log("=== WHALE TV SYNC STARTED ===");
console.log(`VPS URL: ${VPS_API_URL}`);
console.log(`Nhấn Ctrl+C để dừng.`);

// Chạy vòng lặp
setInterval(syncLoop, SYNC_INTERVAL_MS);
syncLoop(); // Gọi lần đầu
