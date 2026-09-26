#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# check_vps_trading_status.sh - Kiểm tra toàn diện hệ thống VPS Trading
# Bao gồm: Static Dependencies + Runtime Services + Sockets/Ports
# ══════════════════════════════════════════════════════════════════

echo "═══════════════════════════════════════════════════════════"
echo " KIỂM TRA HỆ THỐNG GIAO DỊCH LIGHTNING AI VPS - $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"

# Helper kiểm tra TCP Socket bằng Python
check_port() {
    local host="$1"
    local port="$2"
    python3 -c "import socket; s = socket.socket(); s.settimeout(2); exit(0 if s.connect_ex(('$host', int($port))) == 0 else 1)" 2>/dev/null
}

# 1. DISPLAY SERVER & NOMACHINE
echo -e "\n[1] Màn hình ảo & NoMachine:"
if pgrep -f "Xvfb :0" >/dev/null 2>&1; then
    echo "  ✅ Display Server: Xvfb :0 đang chạy (PID: $(pgrep -f 'Xvfb :0' | tr '\n' ' '))"
else
    echo "  ❌ Display Server: Xvfb :0 CHƯA chạy."
fi

if command -v /usr/NX/bin/nxserver >/dev/null 2>&1; then
    NX_STATUS=$(/usr/NX/bin/nxserver --status 2>/dev/null | grep -i "server" | head -1)
    echo "  ✅ NoMachine Server đã cài đặt: ${NX_STATUS:-Hoạt động}"
else
    echo "  ❌ NoMachine chưa được cài đặt."
fi

# 2. GOOGLE CHROME & CLOAKBROWSER
echo -e "\n[2] Google Chrome & CloakBrowser:"
if command -v google-chrome >/dev/null 2>&1; then
    echo "  ✅ Google Chrome binary: $(google-chrome --version)"
else
    echo "  ❌ Google Chrome chưa được cài đặt."
fi

if [ -L ~/.config/google-chrome ]; then
    TARGET=$(readlink ~/.config/google-chrome)
    if [[ "$TARGET" == *"data-lightning-vps/chrome"* ]]; then
        echo "  ✅ Profile Chrome symlink: Đã liên kết tới $TARGET"
    else
        echo "  ⚠️  Profile Chrome symlink: Trỏ tới $TARGET"
    fi
else
    echo "  ❌ Profile Chrome: Chưa cấu hình symlink đồng bộ."
fi

if pgrep -f "cloak_visible_profile" >/dev/null 2>&1 || pgrep -f "cloakbrowser" >/dev/null 2>&1; then
    echo "  ✅ CloakBrowser Runtime: Tiến trình đang chạy ngầm."
else
    echo "  ℹ️  CloakBrowser Runtime: Chưa có tiến trình chạy ngầm."
fi

# 3. TRADINGVIEW DESKTOP & CDP PORT 9222
echo -e "\n[3] TradingView Desktop & CDP Debugger (Port 9222):"
if command -v tradingview >/dev/null 2>&1; then
    echo "  ✅ TradingView binary: $(which tradingview)"
else
    echo "  ❌ TradingView binary chưa có trong PATH."
fi

if [ -L ~/.config/TradingView ]; then
    TARGET=$(readlink ~/.config/TradingView)
    if [[ "$TARGET" == *"data-lightning-vps/TradingView"* ]]; then
        echo "  ✅ Profile TradingView symlink: Đã liên kết tới $TARGET"
    else
        echo "  ⚠️  Profile TradingView symlink: Trỏ tới $TARGET"
    fi
else
    echo "  ❌ Profile TradingView: Chưa cấu hình symlink đồng bộ."
fi

if pgrep -f "[Tt]rading[Vv]iew" >/dev/null 2>&1; then
    echo "  ✅ Tiến trình TradingView: Đang chạy (PID: $(pgrep -f '[Tt]rading[Vv]iew' | tr '\n' ' '))"
else
    echo "  ❌ Tiến trình TradingView: CHƯA chạy."
fi

# Kiểm tra Socket CDP 9222
CDP_RES=$(curl -s --connect-timeout 2 http://127.0.0.1:9222/json/version 2>/dev/null)
if [ -n "$CDP_RES" ]; then
    BROWSER_INFO=$(echo "$CDP_RES" | grep -o '"Browser": "[^"]*"' | cut -d'"' -f4)
    WS_URL=$(echo "$CDP_RES" | grep -o '"webSocketDebuggerUrl": "[^"]*"' | cut -d'"' -f4)
    echo "  ✅ CDP Port 9222 Socket: ĐANG PHẢN HỒI"
    echo "     - Browser: ${BROWSER_INFO:-Unknown}"
    echo "     - WebSocket: ${WS_URL:-Available}"
else
    echo "  ❌ CDP Port 9222 Socket: KHÔNG phản hồi (Chưa bật --remote-debugging-port=9222 hoặc ứng dụng chưa mở)."
fi

# 4. DOCKER & METATRADER 5 CONTAINER (RPyC Port 8001 & Web VNC Port 3000)
echo -e "\n[4] Docker & MetaTrader 5 Container (RPyC 8001 / Web VNC 3000):"
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1; then
        echo "  ✅ Docker Daemon: Đang hoạt động bình thường."
    else
        echo "  ❌ Docker Daemon: Cài đặt nhưng daemon chưa chạy."
    fi
else
    echo "  ❌ Docker chưa được cài đặt."
fi

# Kiểm tra Container MT5
DOCKER_CMD="docker"
sudo -n docker ps >/dev/null 2>&1 && DOCKER_CMD="sudo docker"
if $DOCKER_CMD ps --format '{{.Names}}' 2>/dev/null | grep -q "mt5-container"; then
    CONTAINER_STATUS=$($DOCKER_CMD inspect --format='{{.State.Status}}' mt5-container 2>/dev/null)
    echo "  ✅ Container mt5-container: Đang hoạt động (Status: $CONTAINER_STATUS)"
else
    echo "  ❌ Container mt5-container: CHƯA chạy."
fi

# Kiểm tra RPyC Socket Port 8001
if check_port "127.0.0.1" 8001; then
    echo "  ✅ MT5 RPyC Socket (Port 8001): ĐANG LẮNG NGHE (Sẵn sàng phục vụ AI Agent)"
else
    echo "  ❌ MT5 RPyC Socket (Port 8001): KHÔNG phản hồi kết nối."
fi

# Kiểm tra Web VNC Socket Port 3000
if check_port "127.0.0.1" 3000; then
    echo "  ✅ MT5 Web VNC (Port 3000): ĐANG LẮNG NGHE (noVNC sẵn sàng)"
else
    echo "  ❌ MT5 Web VNC (Port 3000): Không phản hồi."
fi

# 5. TAILSCALE MESH VPN (Userspace Networking)
echo -e "\n[5] Tailscale Mesh VPN (Userspace Networking):"
if command -v tailscale >/dev/null 2>&1; then
    TS_VER=$(tailscale --version 2>/dev/null | head -n 1)
    echo "  ✅ Tailscale binary: $TS_VER"
    TS_IP=$(tailscale ip -4 2>/dev/null)
    if [ -n "$TS_IP" ]; then
        echo "  ✅ Tailscale IP nội bộ: $TS_IP"
    else
        echo "  ❌ Tailscale: Chưa có IP hoặc chưa kết nối tunnel."
    fi
else
    echo "  ❌ Tailscale chưa được cài đặt."
fi

# 6. MÃ NGUỒN & MÔI TRƯỜNG PYTHON/NODE.JS
echo -e "\n[6] Mã nguồn dự án & Dependencies:"
PROJECT_DIR="${TS_BASE:-/teamspace/studios/this_studio}/project"
[ ! -d "$PROJECT_DIR" ] && PROJECT_DIR="$HOME/project"

for dir_name in "mt5-mcp" "tradingview-mcp" "Kronos" "KLTN_TradingAgents"; do
    if [ -d "$PROJECT_DIR/$dir_name" ]; then
        echo "  ✅ Thư mục $dir_name: Tồn tại ($PROJECT_DIR/$dir_name)"
    else
        echo "  ⚠️  Thư mục $dir_name: Chưa tìm thấy tại $PROJECT_DIR"
    fi
done

# 7. TRADINGVIEW-MCP & NODE.JS BRIDGE RUNTIME
echo -e "\n[7] tradingview-mcp & Node.js Bridge Runtime:"
TV_MCP_DIR="$PROJECT_DIR/tradingview-mcp"
NVM_DIR_PATH="${TS_BASE:-/teamspace/studios/this_studio}/.nvm"
[ ! -d "$NVM_DIR_PATH" ] && NVM_DIR_PATH="$HOME/.nvm"

if [ -d "$NVM_DIR_PATH" ]; then
    NODE_VER=$(ls "$NVM_DIR_PATH/versions/node/" 2>/dev/null | sort -V | tail -1)
    if [ -n "$NODE_VER" ]; then
        NODE_BIN="$NVM_DIR_PATH/versions/node/$NODE_VER/bin/node"
        echo "  ✅ Node.js binary: $("$NODE_BIN" --version 2>/dev/null) ($NODE_BIN)"
    else
        NODE_BIN=$(command -v node 2>/dev/null)
        echo "  ℹ️  Dùng Node.js hệ thống: ${NODE_BIN:-Chưa có}"
    fi
else
    NODE_BIN=$(command -v node 2>/dev/null)
    echo "  ℹ️  Dùng Node.js hệ thống: ${NODE_BIN:-Chưa có}"
fi

if [ -d "$TV_MCP_DIR/node_modules/@modelcontextprotocol" ]; then
    echo "  ✅ Package @modelcontextprotocol/sdk: Đã cài đặt"
else
    echo "  ❌ Package @modelcontextprotocol/sdk: CHƯA cài đặt (Chạy 'cd $TV_MCP_DIR && npm install')"
fi

# Test trực tiếp bridge bằng Node nếu có binary và cổng 9222 mở
if [ -x "$NODE_BIN" ] && [ -n "$CDP_RES" ]; then
    echo "  🔍 Đang thực hiện kiểm tra ping CDP Bridge qua Node.js..."
    BRIDGE_TEST=$("$NODE_BIN" -e "
    const http = require('http');
    const req = http.get('http://127.0.0.1:9222/json/version', { timeout: 2000 }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => {
            try {
                const json = JSON.parse(body);
                console.log('SUCCESS:' + (json.Browser || 'OK'));
            } catch(e) {
                console.log('ERROR:ParseFailed');
            }
        });
    });
    req.on('error', err => console.log('ERROR:' + err.message));
    req.on('timeout', () => { req.destroy(); console.log('ERROR:Timeout'); });
    " 2>/dev/null)

    if [[ "$BRIDGE_TEST" == SUCCESS:* ]]; then
        echo "  🎉 TradingView MCP Bridge: KẾT NỐI THÀNH CÔNG (${BRIDGE_TEST#SUCCESS:})"
    else
        echo "  ⚠️  TradingView MCP Bridge: Thất bại (${BRIDGE_TEST:-Không có phản hồi})"
    fi
fi

echo -e "\n═══════════════════════════════════════════════════════════"
echo " HOÀN TẤT KIỂM TRA DỊCH VỤ TRADING"
echo "═══════════════════════════════════════════════════════════"
