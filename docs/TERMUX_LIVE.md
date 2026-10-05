# Termux live mode

This runs beside the existing Termux services as a separate foreground process. It does not control, restart, stop, start, enable, disable, delete, or modify any legacy service.

It reads public market data only. No API keys, exchange accounts, orders, or withdrawals are used.

## Install

```bash
clear
cd ~
git clone https://github.com/kia269749-bit/market-intelligence-core.git
cd market-intelligence-core
```

## Run

```bash
clear
cd ~/market-intelligence-core
PYTHONUNBUFFERED=1 python -m mi_core.cli live --exchanges binance,coinbase,kraken,okx --symbols BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,ADAUSDT,AVAXUSDT,LINKUSDT,TRXUSDT --interval 20
```

Press Ctrl+C to stop the foreground monitor.

Output contains a real timestamp, median price, observed range, cross-exchange spread, source count, and warnings.

Default polling is 20 seconds to keep phone/network load modest. Increase the interval for lower load.
