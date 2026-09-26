#!/bin/bash
# ════════════════════════════════════════════════════════════════
# setup_vps_auto.sh - Lightning AI VPS Setup (One-time)
# Chay 1 LAN DUY NHAT sau khi tao VPS moi.
# ════════════════════════════════════════════════════════════════
set -e
export DEBIAN_FRONTEND=noninteractive

TS_BASE=/teamspace/studios/this_studio
PERSIST=$TS_BASE/.persist
# Thu muc dong bo voi may Mac de giu profile
DATA_DIR=$TS_BASE/project/document/data-lightning-vps
TAILSCALE_AUTHKEY="tskey-auth-kxKKTFzd8421CNTRL-W92nQD6QSvCAgjyTG6wSvC25shDJC7Q2"

echo "══════════════════════════════════════════"
echo " Lightning AI VPS - Full Setup (Trading)"
echo " Persistent base: $TS_BASE"
echo " Data Dir: $DATA_DIR"
echo "══════════════════════════════════════════"

# 1. TAO CAU TRUC PERSISTENT
echo "[1/10] Tao cau truc persistent..."
mkdir -p $PERSIST/{tailscale_state,venv_ai,mt5_data}
chmod -R 777 $PERSIST/mt5_data 2>/dev/null || true
mkdir -p $DATA_DIR/TradingView
mkdir -p $TS_BASE/.lightning_studio/cloak_runner $TS_BASE/.lightningstudio

# FIX CRITICAL: Ghi co Sentinel vao ~/.studiorc (Persistent)
if ! grep -q "lightning-apt-loaded" ~/.studiorc 2>/dev/null; then
    echo "sudo mkdir -p /.sentinels /home/zeus && sudo touch /.sentinels/.lightning-apt-loaded /home/zeus/.lightning-loaded 2>/dev/null" >> ~/.studiorc
fi


# 2. CAI DAT HE THONG
echo "[2/10] Cai XFCE4 + dependencies..."
# Cho apt/dpkg hoan tat - toi da 5 phut, bo qua /commands/ wrapper cua Lightning AI (hay bi zombie)
APT_WAIT=0
while pgrep -f "/usr/bin/apt-get|/usr/bin/dpkg" > /dev/null 2>&1 && [ $APT_WAIT -lt 300 ]; do
    echo "  -> Dang cho apt-get/dpkg hoan tat... (${APT_WAIT}s)"
    sleep 5
    APT_WAIT=$((APT_WAIT + 5))
done
[ $APT_WAIT -ge 300 ] && echo "  -> [CANH BAO] Cho apt qua 5 phut, tiep tuc..." || echo "  -> apt/dpkg san sang"

# FIX: Xoa dpkg interrupted truoc khi cai bat ky goi nao
echo "  -> Kiem tra va fix dpkg interrupted..."
sudo dpkg --configure -a 2>/dev/null || true
sudo apt-get install -f -y -qq 2>/dev/null || true
echo "  -> dpkg san sang"

sudo apt-get update -qq

# Chi cai XFCE4 neu chua co (tranh cai lai mat thoi gian)
if ! dpkg -l xfce4 >/dev/null 2>&1; then
    echo "  -> Cai XFCE4 desktop..."
    sudo apt-get install -y -qq \
        xfce4 xfce4-goodies xorg dbus-x11 \
        x11-xserver-utils xinit \
        xfce4-terminal fonts-noto-cjk \
        --no-install-recommends || true
else
    echo "  -> XFCE4 da co san, bo qua."
fi

sudo apt-get install -y -qq \
    libgbm1 libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 xvfb curl wget neovim python3-venv python3-pip rsync screen bc \
    dbus-x11 || true

sudo apt-mark auto \
    xfce4 xfce4-goodies dbus-x11 \
    libgbm1 libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 xvfb neovim python3-venv python3-pip rsync screen bc \
    tailscale tailscale-archive-keyring 2>/dev/null || true


# 3. NOMACHINE
echo "[3/10] Cai NoMachine..."
NX_DEB=$TS_BASE/nomachine.deb
if [ ! -f "$NX_DEB" ]; then
    wget -q "https://download.nomachine.com/download/9.5/Linux/nomachine_9.5.7_2_amd64.deb" -O "$NX_DEB" || true
fi
if [ ! -x "/etc/NX/nxserver" ]; then
    echo "  -> Cai dat NoMachine (timeout 120s tranh treo)..."
    sudo DEBIAN_FRONTEND=noninteractive timeout 120 dpkg -i "$NX_DEB" || true
    sudo pkill -9 -f "nxserver.bin --subscription" 2>/dev/null || true
    sudo apt-get install -f -y -qq || true
else
    echo "  -> NoMachine da co san, bo qua."
fi
sudo service dbus start || true

sudo -u zeus bash -c "mkdir -p ~/.config && echo 'startxfce4' > ~/.xinitrc" 2>/dev/null || true
sudo -u zeus bash -c "echo 'xfce4-session' > ~/.xsession" 2>/dev/null || true

if [ -f "/usr/NX/etc/node.cfg" ]; then
    sudo sed -i 's/DefaultDesktopCommand "\/etc\/X11\/Xsession gnome-session"/DefaultDesktopCommand "\/etc\/X11\/Xsession startxfce4"/g' /usr/NX/etc/node.cfg || true
fi

sudo /etc/NX/nxserver --startup || sudo /usr/NX/bin/nxserver --restart || true

# 4. DAT MAT KHAU
echo "[4/10] Dat mat khau cho $USER va zeus..."
if ! id zeus >/dev/null 2>&1; then
    sudo useradd -m -s /bin/bash zeus 2>/dev/null || true
    sudo usermod -aG sudo zeus 2>/dev/null || true
fi
echo "zeus:202004"  | sudo chpasswd || true
echo "$USER:202004" | sudo chpasswd || true
echo "root:202004"  | sudo chpasswd || true


# 5. CAI NVM & NODE.JS (Persistent - can cho CloakBrowser & tradingview-mcp)
echo "[5/10] Cai NVM & Node.js..."
# Dung $HOME/.nvm (chuan) thay vi $TS_BASE/.nvm
export NVM_DIR="$HOME/.nvm"
if [ ! -d "$NVM_DIR" ]; then
    echo "  -> Dang cai NVM..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash || true
fi
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if ! nvm ls 22 > /dev/null 2>&1; then
    echo "  -> Cai Node.js v22..."
    nvm install 22 || true
fi
nvm use 22 || true

# Symlink node/npm vao /usr/local/bin (tranh mat PATH sau restart)
sudo ln -sf "$NVM_DIR/versions/node/$(nvm current)/bin/node" /usr/local/bin/node 2>/dev/null || true
sudo ln -sf "$NVM_DIR/versions/node/$(nvm current)/bin/npm" /usr/local/bin/npm 2>/dev/null || true

echo "  -> Node: $(node --version 2>/dev/null) | npm: $(npm --version 2>/dev/null)"

# Cai tradingview-mcp neu da co
if [ -d "$TS_BASE/project/tradingview-mcp" ]; then
    echo "  -> npm install tradingview-mcp..."
    cd $TS_BASE/project/tradingview-mcp && npm install --silent && cd $TS_BASE
fi

# Cai Python venv + dependencies cho KLTN_TradingAgents neu da co
if [ -d "$TS_BASE/project/KLTN_TradingAgents" ] && [ ! -f "$TS_BASE/project/KLTN_TradingAgents/venv/bin/python" ]; then
    echo "  -> Tao Python venv cho KLTN_TradingAgents..."
    cd $TS_BASE/project/KLTN_TradingAgents
    python3 -m venv venv
    ./venv/bin/pip install --quiet --upgrade pip
    [ -f requirements.txt ] && ./venv/bin/pip install --quiet -r requirements.txt
    echo "  -> KLTN_TradingAgents venv da san sang"
    cd $TS_BASE
fi

# Cai dependencies cho mt5-mcp (host-side)
if [ -d "$TS_BASE/project/mt5-mcp" ]; then
    echo "  -> Cai dat dependencies cho mt5-mcp..."
    cd $TS_BASE/project/mt5-mcp
    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
        export PATH="$HOME/.cargo/bin:$PATH"
    fi
    uv sync || echo "  -> [CANH BAO] mt5-mcp uv sync that bai, kiem tra lai sau"
    cd $TS_BASE
fi


# 6. CLOAKBROWSER + CLOAK RUNNER (TAO DAY DU run_cloak.sh & start_cloakbrowser.js)
echo "[6/10] Cai CloakBrowser & tao Cloak Runner..."
npm install -g cloakbrowser http-server || true

# Tao cloak_runner voi day du files
mkdir -p $TS_BASE/.lightning_studio/cloak_runner
cd $TS_BASE/.lightning_studio/cloak_runner

# npm init neu chua co package.json
if [ ! -f "package.json" ]; then
    npm init -y > /dev/null
fi
npm install cloakbrowser playwright-core -q || true

# Tao start_cloakbrowser.js
cat > $TS_BASE/.lightning_studio/cloak_runner/start_cloakbrowser.js << 'EOF'
(async () => {
    try {
        const cloakbrowser = await import('cloakbrowser');
        console.log("Khoi dong CloakBrowser...");
        const browser = await (cloakbrowser.default || cloakbrowser).launch({
            headless: true,
            args: [
                '--remote-debugging-port=58456',
                '--remote-debugging-address=0.0.0.0',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--headless'
            ]
        });
        console.log("Headless CloakBrowser is running on port 58456.");
        setInterval(() => {}, 100000); // Giu process chay
    } catch (err) {
        console.error("Loi khoi dong CloakBrowser:", err);
        process.exit(1);
    }
})();
EOF

# Tao run_cloak.sh wrapper - tu detect node path, KHONG phu thuoc PATH
cat > $TS_BASE/.lightning_studio/cloak_runner/run_cloak.sh << 'RUNEOF'
#!/bin/bash
# run_cloak.sh - Wrapper khoi dong CloakBrowser voi node path tu detect
# Khong dung 'node' truc tiep vi PATH co the bi mat sau restart
NODE_BIN=$(ls /system/conda/node/nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)
if [ -z "$NODE_BIN" ]; then
    NODE_BIN=$(ls $HOME/.nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)
fi
if [ -z "$NODE_BIN" ]; then
    NODE_BIN=$(which node 2>/dev/null || echo '')
fi
if [ -z "$NODE_BIN" ]; then
    echo "[LOI] Khong tim thay node binary!"
    exit 1
fi
cd /teamspace/studios/this_studio/.lightning_studio/cloak_runner
exec "$NODE_BIN" start_cloakbrowser.js
RUNEOF
chmod +x $TS_BASE/.lightning_studio/cloak_runner/run_cloak.sh
echo "  -> Da tao run_cloak.sh + start_cloakbrowser.js!"

# Build cloak-mcp neu co
CLOAK_MCP_DIR="$TS_BASE/project/cloak-mcp"
if [ -d "$CLOAK_MCP_DIR" ]; then
    echo "  -> Build Cloak MCP..."
    cd "$CLOAK_MCP_DIR"
    npm install -q || true
    npm run build || true
    cd $TS_BASE
fi

cd $TS_BASE


# 7. TRADINGVIEW + SYMLINK USERDATA -> LOCAL
echo "[7/10] Cai TradingView Desktop..."
TV_DEB=$TS_BASE/tradingview.deb
if [ ! -f "$TV_DEB" ]; then
    cd $TS_BASE
    wget -O - https://tvd-packages.tradingview.com/keyring.gpg \
        | sudo tee /usr/share/keyrings/tradingview-desktop-archive-keyring.gpg > /dev/null
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/tradingview-desktop-archive-keyring.gpg] \
https://tvd-packages.tradingview.com/ubuntu/stable jammy multiverse" \
        | sudo tee /etc/apt/sources.list.d/tradingview-desktop.list > /dev/null
    sudo apt-get update -qq || true
    sudo apt-get download tradingview || true
    cp tradingview_*.deb "$TV_DEB" 2>/dev/null || true
fi
if [ -f "$TV_DEB" ]; then
    sudo dpkg -i "$TV_DEB" || sudo apt-get install -f -y || true
    sudo chown root:root /opt/TradingView/chrome-sandbox 2>/dev/null || true
    sudo chmod 4755 /opt/TradingView/chrome-sandbox 2>/dev/null || true
fi
mkdir -p ~/.config/TradingView-local
echo "  -> TradingView se chay tren local SSD va dong bo voi $DATA_DIR/TradingView"

# Tao shortcut Desktop
mkdir -p ~/Desktop
cat > ~/Desktop/TradingView_MCP.desktop << 'EOF'
[Desktop Entry]
Name=TradingView (MCP Debug 9222)
Exec=/opt/TradingView/tradingview --remote-debugging-port=9222 --no-sandbox
Type=Application
Icon=tradingview
Terminal=false
EOF
chmod +x ~/Desktop/TradingView_MCP.desktop
gio set ~/Desktop/TradingView_MCP.desktop metadata::trusted true 2>/dev/null || true


# 8. TAILSCALE
echo "[8/10] Cai Tailscale..."
if ! command -v tailscale >/dev/null 2>&1; then
    # FIX: Dung apt thay vi install.sh de tranh dpkg interrupted
    sudo dpkg --configure -a 2>/dev/null || true
    sudo apt-get install -f -y -qq 2>/dev/null || true
    # Thu apt truoc (nhanh hon, khong can curl)
    if sudo apt-get install -y tailscale tailscale-archive-keyring 2>/dev/null; then
        echo "  -> Tailscale cai qua apt OK"
    else
        echo "  -> Apt that bai, thu install.sh..."
        curl -fsSL https://tailscale.com/install.sh | sh || true
    fi
fi
# FIX: Verify binary thuc su ton tai sau khi cai
if ! command -v tailscale >/dev/null 2>&1; then
    echo "  -> [LOI] Tailscale binary khong ton tai sau khi cai! Thu cai lai lan 2..."
    sudo dpkg --configure -a 2>/dev/null || true
    curl -fsSL https://tailscale.com/install.sh | sh
fi
echo "  -> Tailscale version: $(tailscale version 2>/dev/null | head -1 || echo 'CHUA CAI DUOC')"
# Fix: them hostname vao /etc/hosts tranh loi 'sudo: unable to resolve host'
HOSTNAME_NOW=$(hostname)
if ! grep -q "$HOSTNAME_NOW" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 $HOSTNAME_NOW" | sudo tee -a /etc/hosts > /dev/null
fi
# Chay Tailscale userspace mode (tranh conflict routing table voi Lightning AI)
sudo tailscaled --tun=userspace-networking --statedir=$PERSIST/tailscale_state > /dev/null 2>&1 &
sleep 3
sudo tailscale up \
    --hostname="lightning-ai-${LIGHTNING_STUDIO_NAME:-$(hostname)}" \
    --auth-key=$TAILSCALE_AUTHKEY \
    --operator=$USER \
    --accept-dns=false \
    --accept-routes=false \
    --netfilter-mode=off 2>/dev/null && \
    echo "  -> Tailscale IP: $(tailscale ip -4 2>/dev/null)" || \
    echo "  -> [CANH BAO] Tailscale can auth thu cong: sudo tailscale up"
# Dam bao DNS van dung 8.8.8.8 sau khi tailscale up
if ! grep -q "8.8.8.8" /etc/resolv.conf 2>/dev/null; then
    printf 'nameserver 8.8.8.8\nnameserver 8.8.4.4\n' | sudo tee /etc/resolv.conf > /dev/null
fi


# 9. CAI DOCKER + PULL MT5 IMAGE
echo "[9/10] Cai Docker + Pull MT5 image..."
if ! command -v docker >/dev/null 2>&1; then
    echo "  -> Cai dat Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh || true
    sudo sh get-docker.sh || true
    rm -f get-docker.sh
    sudo apt-get install -y -qq docker-compose-plugin docker-compose || true
    sudo systemctl enable docker || true
    sudo systemctl start docker || true
    sudo usermod -aG docker $USER || true
fi
# Pull image MT5 (chi 1 lan, duoc cache tren persistent disk)
sudo docker pull gmag11/metatrader5_vnc:latest || true
echo "  -> MT5 Docker image san sang (port 8001 rpyc | 5900 VNC)"


# 10. TAO on_start.sh (Sieu toc - SSD Local + GPU + Skip Cache)
echo "[10/10] Tao on_start.sh (Khoi dong <30s)..."
cat > $TS_BASE/.lightning_studio/on_start.sh << 'ONSTART'
#!/bin/bash
# ════════════════════════════════════════════════════════════════
# on_start.sh - Trading VPS Auto-Start
# Tu dong chay khi VPS boot - phuc hoi toan bo moi truong
# ════════════════════════════════════════════════════════════════
TS_BASE=/teamspace/studios/this_studio
DATA_DIR=$TS_BASE/project/document/data-lightning-vps
LOG=$TS_BASE/.lightning_studio/on_start.log
START_TIME=$(date +%s)

# Thu muc Local SSD de chay TradingView nhanh hon
LOCAL_TV=~/.config/TradingView-local

# Ham dong bo sieu toc (loai bo Cache rac)
sync_fast() {
    src=$1; dest=$2
    if [ -d "$src" ]; then
        rsync -a --delete \
            --exclude='Cache*' --exclude='Code Cache' \
            --exclude='GPUCache' --exclude='Service Worker/CacheStorage' \
            "$src/" "$dest/"
    fi
}

log()   { echo "[$(date '+%H:%M:%S')] $*" | tee -a $LOG; }
timer() { echo "[$(date '+%H:%M:%S')] OK $* ($(( $(date +%s) - START_TIME ))s)" | tee -a $LOG; }

echo "==========================================" > $LOG
log "BAT DAU KHOI DONG (SUPER FAST MODE)"

# Tao co Sentinel de studio-setup khong loop cho
sudo mkdir -p /.sentinels /home/zeus
sudo touch /.sentinels/.lightning-apt-loaded /home/zeus/.lightning-loaded 2>/dev/null || true

# 1. Dong bo TradingView tu O mang -> SSD Local (chi mat ~1s do skip Cache)
mkdir -p "$LOCAL_TV" "$DATA_DIR/TradingView"
sync_fast "$DATA_DIR/TradingView" "$LOCAL_TV"

# Link vao SSD Local
mkdir -p ~/.config /tmp/cloakbrowser-local
rm -rf ~/.config/TradingView
ln -sf "$LOCAL_TV" ~/.config/TradingView

# Dong bo CloakBrowser Chromium sang SSD Local (cho khoi dong sieu toc <1s)
# Dung wildcard tranh bi hong khi CloakBrowser update version
CLOAK_BIN_DIR=$(ls -d "$TS_BASE/.cloakbrowser/chromium-"* 2>/dev/null | head -1)
if [ -n "$CLOAK_BIN_DIR" ] && [ -d "$CLOAK_BIN_DIR" ]; then
    rsync -a "$CLOAK_BIN_DIR/" /tmp/cloakbrowser-local/ 2>/dev/null || true
fi
timer "Dong bo SSD Local (Super Fast) xong"

# 2. Khoi chay tien trinh dong bo nguoc ngam (5 phut/lan)
pkill -f "sleep 300" || true
(
    while true; do
        sleep 300
        mkdir -p "$DATA_DIR/TradingView"
        sync_fast "$LOCAL_TV" "$DATA_DIR/TradingView"
    done
) &
log "Da bat tu dong sao luu ngam (skip Cache)"

# 3. Kiem tra & phuc hoi phan mem he thong neu VPS bi reset root
log "Kiem tra & phuc hoi phan mem he thong..."
export DEBIAN_FRONTEND=noninteractive

if ! command -v tailscale >/dev/null 2>&1 || [ ! -f /usr/NX/bin/nxserver ] || ! command -v docker >/dev/null 2>&1; then
    log "He thong bi reset root, dang cho apt/dpkg hoan tat..."
    APT_WAIT=0
    while pgrep -f "/usr/bin/apt-get|/usr/bin/dpkg" > /dev/null 2>&1 && [ $APT_WAIT -lt 300 ]; do
        sleep 5
        APT_WAIT=$((APT_WAIT + 5))
    done

    # FIX: Luon chay dpkg --configure -a truoc de tranh dpkg interrupted lam silent fail
    log "-> Fix dpkg interrupted neu co..."
    sudo dpkg --configure -a >> $LOG 2>&1 || true
    sudo apt-get install -f -y -qq >> $LOG 2>&1 || true

    log "-> Phuc hoi phan mem dang bat dau..."
    sudo apt-get update -qq >> $LOG 2>&1
    if ! dpkg -l xfce4 >/dev/null 2>&1; then
        sudo apt-get install -y -qq xfce4 xfce4-goodies dbus-x11 >> $LOG 2>&1 || true
    fi
    sudo apt-get install -y -qq \
        libgbm1 libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxfixes3 libxrandr2 xvfb curl wget neovim rsync bc screen \
        dbus-x11 \
        >> $LOG 2>&1 || true

    # Cai Docker
    log "Cai dat Docker cho MetaTrader 5 container..."
    curl -fsSL https://get.docker.com -o get-docker.sh >> $LOG 2>&1
    sudo sh get-docker.sh >> $LOG 2>&1
    rm -f get-docker.sh
    sudo systemctl enable docker >> $LOG 2>&1 || true
    sudo systemctl start docker >> $LOG 2>&1 || true
    sudo usermod -aG docker $USER >> $LOG 2>&1 || true

    # Cai TradingView
    log "Cai dat TradingView..."
    TV_DEB="$TS_BASE/tradingview.deb"
    if [ ! -f "$TV_DEB" ]; then
        wget -q https://tvd-packages.tradingview.com/ubuntu/stable/jammy/tradingview_1.0.0_amd64.deb -O "$TV_DEB" || true
    fi
    if [ -f "$TV_DEB" ]; then
        sudo dpkg -i "$TV_DEB" >> $LOG 2>&1 || sudo apt-get install -f -y >> $LOG 2>&1
        sudo chown root:root /opt/TradingView/chrome-sandbox 2>/dev/null || true
        sudo chmod 4755 /opt/TradingView/chrome-sandbox 2>/dev/null || true
    fi

    # Cai NoMachine (voi timeout tranh treo)
    log "Cai dat NoMachine (timeout 90s)..."
    if [ ! -x "/etc/NX/nxserver" ] && [ -f "$TS_BASE/nomachine.deb" ]; then
        sudo DEBIAN_FRONTEND=noninteractive timeout 90 dpkg -i "$TS_BASE/nomachine.deb" >> $LOG 2>&1 || true
        sudo pkill -9 -f "nxserver.bin --subscription" 2>/dev/null || true
    fi

    # Tao shortcut CloakBrowser tren Desktop
    mkdir -p ~/Desktop
    cat > ~/Desktop/CloakBrowser.desktop << 'EOF'
[Desktop Entry]
Name=CloakBrowser
Exec=/teamspace/studios/this_studio/.lightning_studio/cloak_runner/open_cloak.sh
Type=Application
Icon=web-browser
Terminal=false
EOF
    chmod +x ~/Desktop/CloakBrowser.desktop 2>/dev/null || true
    gio set ~/Desktop/CloakBrowser.desktop metadata::trusted true 2>/dev/null || true

    # Cai Tailscale neu chua co
    # FIX: Dung apt truoc (tranh dpkg interrupted tu curl | sh), sau do verify binary
    if ! command -v tailscale >/dev/null 2>&1; then
        log "Cai dat Tailscale qua apt..."
        # Them repo tailscale neu chua co
        if ! apt-cache show tailscale >/dev/null 2>&1; then
            curl -fsSL https://tailscale.com/install.sh | sh >> $LOG 2>&1
        else
            sudo dpkg --configure -a >> $LOG 2>&1 || true
            sudo apt-get install -y tailscale tailscale-archive-keyring >> $LOG 2>&1
        fi
    fi
    # FIX: Verify tailscale binary thuc su ton tai - neu khong thi cai lai bang install.sh
    if ! command -v tailscale >/dev/null 2>&1; then
        log "[LOI] Tailscale binary khong ton tai! Thu cai lai bang install.sh..."
        curl -fsSL https://tailscale.com/install.sh | sh >> $LOG 2>&1 || true
    fi
    command -v tailscale >/dev/null 2>&1 && \
        log "Tailscale da cai: $(tailscale version 2>/dev/null | head -1)" || \
        log "[CANH BAO] Tailscale van chua cai duoc!"

    # Khoi dong Tailscale userspace mode
    (
        sleep 5
        sudo tailscaled --tun=userspace-networking --statedir=$TS_BASE/.persist/tailscale_state >/dev/null 2>&1 &
        sleep 3
        sudo tailscale up \
            --hostname="lightning-ai-$(hostname)" \
            --auth-key=tskey-auth-kxKKTFzd8421CNTRL-W92nQD6QSvCAgjyTG6wSvC25shDJC7Q2 \
            --operator=$USER \
            --accept-dns=false \
            --accept-routes=false \
            --netfilter-mode=off >>/dev/null 2>&1 || true
        log "[Tailscale Phuc Hoi] IP: $(tailscale ip -4 2>/dev/null || echo 'dang ket noi')"
    ) &

fi

# 4. Dam bao Xvfb :0 & XFCE4 Desktop luon luon khoi dong truoc moi app
log "Kiem tra & khoi dong Xvfb + XFCE4 Desktop..."
if ! ls /tmp/.X11-unix/X0 2>/dev/null; then
    Xvfb :0 -screen 0 1920x1080x24 +extension RANDR >/dev/null 2>&1 &
    sleep 2
fi

if ! pgrep -f "xfce4-session" >/dev/null 2>&1; then
    DISPLAY=:0 nohup startxfce4 >/tmp/xfce.log 2>&1 &
    sleep 3
    log "XFCE4 desktop da khoi dong tren DISPLAY :0"
fi

# Phuc hoi npm tradingview-mcp neu bi mat
if [ -d "$TS_BASE/project/tradingview-mcp" ] && [ ! -d "$TS_BASE/project/tradingview-mcp/node_modules" ]; then
    log "Cai lai npm install cho tradingview-mcp..."
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    cd $TS_BASE/project/tradingview-mcp && npm install --silent >> $LOG 2>&1 && cd $TS_BASE
    log "tradingview-mcp npm install xong"
fi

# Phuc hoi Python venv cho KLTN_TradingAgents
if [ -d "$TS_BASE/project/KLTN_TradingAgents" ] && [ ! -f "$TS_BASE/project/KLTN_TradingAgents/venv/bin/python" ]; then
    log "Khoi tao Python venv cho KLTN_TradingAgents..."
    cd $TS_BASE/project/KLTN_TradingAgents
    python3 -m venv venv
    ./venv/bin/pip install --quiet --upgrade pip >> $LOG 2>&1
    [ -f requirements.txt ] && ./venv/bin/pip install --quiet -r requirements.txt >> $LOG 2>&1
    cd $TS_BASE
    log "KLTN_TradingAgents venv da san sang"
fi

# 4. Khoi dong NoMachine (chi start neu chua chay, KHONG restart tranh drop SSH)
if [ -f /usr/NX/etc/node.cfg ]; then
    sudo sed -i 's/DefaultDesktopCommand "\/etc\/X11\/Xsession gnome-session"/DefaultDesktopCommand "\/etc\/X11\/Xsession startxfce4"/g' /usr/NX/etc/node.cfg 2>/dev/null || true
fi
if [ -x "/usr/NX/bin/nxserver" ]; then
    NX_STATUS=$(sudo timeout 10 /etc/NX/nxserver --status 2>/dev/null | head -1 || echo 'unknown')
    log "NoMachine status: $NX_STATUS"
    pgrep -x nxserver >/dev/null 2>&1 || sudo /usr/NX/bin/nxserver --start >> $LOG 2>&1 || true
else
    log "[CANH BAO] NoMachine chua cai hoac bi mat sau restart"
fi

# Mat khau cho $USER va zeus
if ! id zeus >/dev/null 2>&1; then
    sudo useradd -m -s /bin/bash zeus 2>/dev/null || true
    sudo usermod -aG sudo zeus 2>/dev/null || true
fi
echo "zeus:202004"  | sudo chpasswd 2>/dev/null || true
echo "$USER:202004" | sudo chpasswd 2>/dev/null || true
timer "He thong san sang"

# 5. Fix hostname & DNS
HOSTNAME_NOW=$(hostname)
if ! grep -q "$HOSTNAME_NOW" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 $HOSTNAME_NOW" | sudo tee -a /etc/hosts >> $LOG
fi
if ! grep -q "8.8.8.8" /etc/resolv.conf 2>/dev/null; then
    printf 'nameserver 8.8.8.8\nnameserver 8.8.4.4\n' | sudo tee /etc/resolv.conf >> $LOG
    log "[DNS] Da phuc hoi DNS ve 8.8.8.8"
fi

# 6. Khoi dong Tailscale userspace mode (KHONG anh huong SSH gateway)
(
    sleep 30
    sudo tailscaled --tun=userspace-networking --statedir=$TS_BASE/.persist/tailscale_state >/dev/null 2>&1 &
    sleep 3
    sudo tailscale up \
        --hostname="lightning-ai-$(hostname)" \
        --auth-key=tskey-auth-kxKKTFzd8421CNTRL-W92nQD6QSvCAgjyTG6wSvC25shDJC7Q2 \
        --operator=$USER \
        --accept-dns=false \
        --accept-routes=false \
        --netfilter-mode=off >>/dev/null 2>&1 || true
    log "[Tailscale] Da ket noi: $(tailscale ip -4 2>/dev/null || echo 'dang ket noi...')"
) &

# 7. Bat TradingView + MetaTrader 5 (background)
(
    sleep 5
    # TradingView Desktop
    pkill -f "[Tt]rading[Vv]iew" 2>/dev/null || true
    sleep 2
    TV_APP=""
    for loc in "/opt/TradingView/tradingview" "/opt/TradingView/TradingView" \
               "$HOME/.local/share/TradingView/TradingView" "/usr/bin/tradingview"; do
        if [ -f "$loc" ] && [ -x "$loc" ]; then TV_APP="$loc"; break; fi
    done
    if [ -n "$TV_APP" ]; then
        DISP_NAME=":0"
        DISPLAY=$DISP_NAME "$TV_APP" --remote-debugging-port=9222 --no-sandbox > /tmp/tradingview.log 2>&1 &
        log "TradingView da bat tai $TV_APP tren DISPLAY $DISP_NAME (PID: $!)"
    else
        log "[CANH BAO] Khong tim thay TradingView app"
    fi

    # CloakBrowser GUI (Pre-start ngam de bat tuc thi 0s)
    if [ -x "/tmp/cloakbrowser-local/chrome" ]; then
        DISPLAY=:0 /tmp/cloakbrowser-local/chrome --no-sandbox --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage --no-first-run --no-default-browser-check --disable-component-update --user-data-dir=/tmp/cloak_visible_profile https://www.google.com > /tmp/cloakbrowser_gui.log 2>&1 &
        log "CloakBrowser GUI da pre-start ngam tren DISPLAY :0 (PID: $!)"
    fi

    # MetaTrader 5 Docker container
    if command -v docker >/dev/null 2>&1; then
        log "Cho Docker daemon san sang..."
        DOCKER_WAIT=0
        until sudo docker info >/dev/null 2>&1 || [ $DOCKER_WAIT -ge 60 ]; do
            sleep 3
            DOCKER_WAIT=$((DOCKER_WAIT + 3))
        done

        if sudo docker info >/dev/null 2>&1; then
            if ! sudo docker image inspect gmag11/metatrader5_vnc:latest >/dev/null 2>&1; then
                log "Image MT5 chua co, dang pull..."
                sudo docker pull gmag11/metatrader5_vnc:latest >> /tmp/mt5docker.log 2>&1 || true
            fi
            if sudo docker image inspect gmag11/metatrader5_vnc:latest >/dev/null 2>&1; then
                log "Bat MetaTrader 5 Docker container..."
                # Fix phan quyen cho container user abc (UID 911) tranh loi 'not owned by you' cua Wine
                sudo mkdir -p "$PERSIST/mt5_data"
                sudo chown -R 911:911 "$PERSIST/mt5_data" 2>/dev/null || true
                sudo chmod -R 777 "$PERSIST/mt5_data" 2>/dev/null || true
                sudo docker rm -f mt5-container 2>/dev/null || true
                sudo docker run -d \
                    --name mt5-container \
                    --restart unless-stopped \
                    -p 3000:3000 \
                    -p 3001:3001 \
                    -p 8001:8001 \
                    -p 5900:5900 \
                    -e WINEPREFIX=/config/.wine \
                    -v "$TS_BASE/.persist/mt5_data:/config" \
                    gmag11/metatrader5_vnc:latest >> /tmp/mt5docker.log 2>&1
                log "Cho Wine + Python 3.9 san sang trong container (max 5 phut)..."
                PYCHECK=0
                while [ $PYCHECK -lt 60 ]; do
                    if sudo docker exec -u abc -e WINEPREFIX=/config/.wine mt5-container \
                        wine 'C:/Program Files (x86)/Python39-32/python.exe' --version \
                        >> /tmp/mt5docker.log 2>&1; then
                        log "  -> Python 3.9 san sang! Cai rpyc==5.2.3 + mt5linux==1.0.3..."
                        sudo docker exec -u abc -e WINEPREFIX=/config/.wine mt5-container \
                            wine 'C:/Program Files (x86)/Python39-32/python.exe' \
                            -m pip install 'numpy<2.0.0' 'rpyc==5.2.3' 'mt5linux==1.0.3' \
                            >> /tmp/mt5docker.log 2>&1 || true
                        log "  -> Khoi dong MT5 RPyC server tai port 8001..."
                        sudo docker exec -d -u abc -e DISPLAY=:1 -e WINEPREFIX=/config/.wine mt5-container \
                            wine 'C:/Program Files (x86)/Python39-32/python.exe' \
                            -c "import rpyc; from rpyc.utils.server import ThreadedServer; ThreadedServer(rpyc.SlaveService, port=8001, hostname='0.0.0.0').start()" || true
                        log "MetaTrader 5 Docker da khoi dong (port 8001 rpyc | 5900 VNC)"
                        break
                    fi
                    PYCHECK=$((PYCHECK + 1))
                    [ $((PYCHECK % 12)) -eq 0 ] && log "  -> Dang cho Wine/Python... (${PYCHECK}x5s kinh qua)"
                    sleep 5
                done
                [ $PYCHECK -ge 60 ] && log "[CANH BAO] Python chua san sang sau 5 phut - container se tu xu ly"
            else
                log "[CANH BAO] Khong pull duoc image MT5, kiem tra ket noi mang"
            fi
        else
            log "[CANH BAO] Docker daemon khong phan hoi sau 60s, bo qua MT5"
        fi
    else
        log "[CANH BAO] Docker chua cai, bo qua MT5"
    fi
) &

# 8. CloakBrowser headless (CDP port 58456) & Cloak MCP
log "Kiem tra & khoi dong CloakBrowser / Cloak MCP..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Tu detect node binary (tranh mat PATH sau restart)
NODE_BIN=$(ls /system/conda/node/nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)
[ -z "$NODE_BIN" ] && NODE_BIN=$(ls "$NVM_DIR/versions/node/"*/bin/node 2>/dev/null | sort -V | tail -1)
[ -z "$NODE_BIN" ] && NODE_BIN=$(command -v node 2>/dev/null || echo '')

if [ -n "$NODE_BIN" ]; then
    export PATH="$(dirname $NODE_BIN):$PATH"
    log "Su dung node tai: $NODE_BIN"

    # Cai cloakbrowser neu chua co
    if ! command -v cloakbrowser &>/dev/null; then
        log "Cai dat cloakbrowser..."
        npm install -g cloakbrowser >> $LOG 2>&1 || true
    fi

    # Build cloak-mcp neu co
    CLOAK_MCP_DIR="$TS_BASE/project/cloak-mcp"
    if [ -d "$CLOAK_MCP_DIR" ]; then
        log "Phat hien Cloak MCP, dam bao dependencies va build..."
        cd "$CLOAK_MCP_DIR"
        npm install -q >> $LOG 2>&1 || true
        npm run build >> $LOG 2>&1 || true
        cd "$TS_BASE"
    fi

    # Cai node_modules cho cloak_runner
    CLOAK_RUNNER_DIR="$TS_BASE/.lightning_studio/cloak_runner"
    if [ -d "$CLOAK_RUNNER_DIR" ]; then
        # Tao package.json neu chua co (tranh loi ENOENT)
        if [ ! -f "$CLOAK_RUNNER_DIR/package.json" ]; then
            cd "$CLOAK_RUNNER_DIR" && npm init -y > /dev/null
        fi
        cd "$CLOAK_RUNNER_DIR"
        npm install cloakbrowser playwright-core -q >> $LOG 2>&1 || true
        cd "$TS_BASE"
    fi

    # Tu dong tao lai run_cloak.sh + start_cloakbrowser.js neu bi mat
    CLOAK_RUNNER_DIR="$TS_BASE/.lightning_studio/cloak_runner"
    if [ ! -f "$CLOAK_RUNNER_DIR/run_cloak.sh" ] || [ ! -f "$CLOAK_RUNNER_DIR/start_cloakbrowser.js" ]; then
        log "Khong tim thay cloak runner files, dang tao lai..."
        mkdir -p "$CLOAK_RUNNER_DIR"
        cat > "$CLOAK_RUNNER_DIR/start_cloakbrowser.js" << 'CLOAKEOF'
(async () => {
    try {
        const cloakbrowser = await import('cloakbrowser');
        console.log('Khoi dong CloakBrowser...');
        const browser = await (cloakbrowser.default || cloakbrowser).launch({
            headless: false,
            args: [
                '--remote-debugging-port=58456',
                '--remote-debugging-address=0.0.0.0',
                '--no-sandbox',
                '--disable-dev-shm-usage'
            ]
        });
        console.log('CloakBrowser dang chay tren port 58456.');
        setInterval(() => {}, 100000);
    } catch (err) {
        console.error('Loi khoi dong CloakBrowser:', err);
        process.exit(1);
    }
})();
CLOAKEOF
        NODE_PATH_FOR_CLOAK=$(dirname $NODE_BIN)
        cat > "$CLOAK_RUNNER_DIR/run_cloak.sh" << RUNEOF
#!/bin/bash
NODE_BIN=\$(ls /system/conda/node/nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)
[ -z "\$NODE_BIN" ] && NODE_BIN=\$(ls \$HOME/.nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1)
[ -z "\$NODE_BIN" ] && NODE_BIN=\$(which node 2>/dev/null || echo '')
if [ -z "\$NODE_BIN" ]; then echo "[LOI] Khong tim thay node!"; exit 1; fi
cd $CLOAK_RUNNER_DIR
exec "\$NODE_BIN" start_cloakbrowser.js
RUNEOF
        chmod +x "$CLOAK_RUNNER_DIR/run_cloak.sh"
        log "Da tao lai run_cloak.sh + start_cloakbrowser.js"
    fi

    # Khoi dong CloakBrowser qua run_cloak.sh wrapper
    pkill -f "cloakbrowser" 2>/dev/null || true
    sleep 1
    if [ -f "$CLOAK_RUNNER_DIR/run_cloak.sh" ]; then
        screen -dmS cloak bash -c "$CLOAK_RUNNER_DIR/run_cloak.sh >> $TS_BASE/.lightning_studio/cloakbrowser.log 2>&1"
        sleep 5
        if curl -s http://localhost:58456/json/version > /dev/null 2>&1; then
            log "CloakBrowser headless SAN SANG tai port 58456"
        else
            log "[CANH BAO] CloakBrowser chua phan hoi port 58456, thu lai sau..."
        fi
    else
        log "[CANH BAO] Khong the tao run_cloak.sh!"
    fi
else
    log "[CANH BAO] Khong tim thay node binary, bo qua CloakBrowser"
fi

TOTAL=$(( $(date +%s) - START_TIME ))
log "HOAN THANH trong ${TOTAL}s"
log "=========================================="
log "  Tailscale IP : $(tailscale ip -4 2>/dev/null || echo 'chua ket noi')"
log "  TradingView  : remote-debugging-port=9222"
log "  MT5 Docker   : port 8001 (rpyc) | 5900 (VNC)"
log "  CloakBrowser : port 58456 (CDP)"
log "  NoMachine    : port 4000 | user=zeus | pass=202004"
log "=========================================="
ONSTART

mkdir -p $TS_BASE/.lightning_studio $TS_BASE/.lightningstudio
cp $TS_BASE/.lightning_studio/on_start.sh $TS_BASE/.lightningstudio/on_start.sh
chmod +x $TS_BASE/.lightning_studio/on_start.sh $TS_BASE/.lightningstudio/on_start.sh

echo "══════════════════════════════════════════"
echo " SETUP HOAN TAT!"
echo " Tailscale IP  : $(tailscale ip -4 2>/dev/null || echo 'chua ket noi')"
echo " TradingView   : remote-debugging-port=9222"
echo " CloakBrowser  : CDP port 58456"
echo " MT5 Docker    : port 8001 (rpyc) | 5900 (VNC)"
echo " NoMachine     : port 4000 | user=zeus | pass=202004"
echo " TradingView data: $DATA_DIR/TradingView"
echo " on_start.sh   : $TS_BASE/.lightning_studio/on_start.sh"
echo "══════════════════════════════════════════"
