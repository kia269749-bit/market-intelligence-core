#!/data/data/com.termux/files/usr/bin/bash
clear
set -e
cd "$HOME/market-intelligence-core"
PYTHONUNBUFFERED=1 python -m mi_core.cli live --exchanges binance,coinbase,kraken,okx --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,TRXUSDT --interval 20
