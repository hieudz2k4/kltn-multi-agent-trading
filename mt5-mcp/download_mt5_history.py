#!/usr/bin/env python3
"""
Tải toàn bộ dữ liệu lịch sử từ MT5 theo format chuẩn của Kronos.
Format Kronos: timestamps,open,close,high,low,volume,amount

Chạy trên VPS:
  /home/zeus/miniconda3/envs/cloudspace/bin/python download_mt5_history.py
"""

import siliconmetatrader5 as _mt5_module
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import time

# ===================== CẤU HÌNH =====================
SYMBOL     = "DXY"               # Symbol cần tải
OUTPUT_DIR = Path("/teamspace/studios/this_studio/kronos_data/DXY")

# Tất cả timeframe cần tải: (tên_file, hằng_số_mt5)
# Các timeframe sẽ được khởi tạo trong main()
TIMEFRAMES = []

# Tải theo từng chunk để tránh OOM (số nến mỗi lần)
CHUNK_SIZE = 50000
# =====================================================

def init_mt5():
    mt5 = _mt5_module.MetaTrader5(host="localhost", port=8001)
    ok = mt5.initialize()
    if not ok:
        raise RuntimeError("❌ Không thể kết nối MT5. Kiểm tra Docker container siliconmt5.")
    acc = mt5.account_info()
    print(f"✅ Kết nối MT5 thành công | Account: {acc.login} | Server: {acc.server}")
    return mt5

def to_kronos_df(rates) -> pd.DataFrame:
    """Chuyển dữ liệu MT5 sang format Kronos."""
    df = pd.DataFrame(rates)
    df = df.rename(columns={
        "time":        "timestamps",
        "tick_volume": "volume",
    })
    # amount = giá trung bình × volume (ước tính dollar volume)
    df["amount"] = ((df["open"] + df["close"]) / 2) * df["volume"]
    # Chỉ giữ các cột Kronos, đúng thứ tự
    df = df[["timestamps", "open", "close", "high", "low", "volume", "amount"]]
    df["timestamps"] = df["timestamps"].astype("int64")
    return df

def download_all(mt5, symbol: str, tf_name: str, tf_value: int, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{symbol}_{tf_name}_kronos.csv"

    print(f"\n📥 Đang tải {symbol} [{tf_name}]...")

    # Bật symbol nếu chưa có trong Market Watch
    mt5.symbol_select(symbol, True)

    all_dfs = []
    pos = 0

    while True:
        rates = mt5.copy_rates_from_pos(symbol, tf_value, pos, CHUNK_SIZE)
        if rates is None or len(rates) == 0:
            break

        chunk_df = to_kronos_df(rates)
        all_dfs.append(chunk_df)

        fetched = len(rates)
        oldest = datetime.fromtimestamp(rates[0][0], tz=timezone.utc).strftime("%Y-%m-%d")
        newest = datetime.fromtimestamp(rates[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"   Chunk {pos:>7} → {pos + fetched:>7} bars | {oldest} → {newest}")

        if fetched < CHUNK_SIZE:
            # Đã hết dữ liệu
            break

        pos += fetched
        time.sleep(0.2)  # Tránh rate-limit

    if not all_dfs:
        print(f"   ⚠️  Không có dữ liệu cho {symbol} [{tf_name}]")
        return

    # Ghép tất cả chunks, xoá trùng, sắp xếp theo thời gian
    final_df = pd.concat(all_dfs).drop_duplicates("timestamps").sort_values("timestamps")
    final_df.to_csv(out_file, index=False)

    size_mb = out_file.stat().st_size / 1024 / 1024
    t_start = datetime.fromtimestamp(final_df["timestamps"].min(), tz=timezone.utc).strftime("%Y-%m-%d")
    t_end   = datetime.fromtimestamp(final_df["timestamps"].max(), tz=timezone.utc).strftime("%Y-%m-%d")

    print(f"   ✅ Saved: {out_file.name} | {len(final_df):,} rows | {t_start} → {t_end} | {size_mb:.2f} MB")

def main():
    print("=" * 60)
    print(f"  MT5 → Kronos Data Downloader")
    print(f"  Symbol: {SYMBOL}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    mt5 = init_mt5()

    # Khởi tạo hằng số timeframe từ instance mt5
    TIMEFRAMES = [
        ("M1",  mt5.TIMEFRAME_M1),
        ("M5",  mt5.TIMEFRAME_M5),
        ("M15", mt5.TIMEFRAME_M15),
        ("M30", mt5.TIMEFRAME_M30),
        ("H1",  mt5.TIMEFRAME_H1),
        ("H4",  mt5.TIMEFRAME_H4),
        ("D1",  mt5.TIMEFRAME_D1),
        ("W1",  mt5.TIMEFRAME_W1),
    ]

    # Kiểm tra symbol có tồn tại không
    info = mt5.symbol_info(SYMBOL)
    if info is None:
        print(f"❌ Symbol '{SYMBOL}' không tồn tại trên sàn này!")
        return

    print(f"\n📊 Symbol info: {info.name} | Digits: {info.digits} | Spread: {info.spread}")

    for tf_name, tf_value in TIMEFRAMES:
        try:
            download_all(mt5, SYMBOL, tf_name, tf_value, OUTPUT_DIR)
        except Exception as e:
            print(f"   ❌ Lỗi tải {tf_name}: {e}")

    print("\n" + "=" * 60)
    print("✅ Hoàn tất! Danh sách file đã tạo:")
    for f in sorted(OUTPUT_DIR.glob("*.csv")):
        size = f.stat().st_size / 1024 / 1024
        rows = sum(1 for _ in open(f)) - 1
        print(f"   {f.name:<35} {rows:>10,} rows  {size:>6.2f} MB")

if __name__ == "__main__":
    main()
