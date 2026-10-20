"""Prueba temporal de fuentes de precios cripto (se borra después)."""
import json, urllib.request, traceback
out = {}
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 portfolito-probe", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())
def probe(name, fn):
    try: out[name] = fn()
    except Exception as e: out[name] = "ERROR " + repr(e)[:300]
def cc(sym):
    d = get(f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={sym}&tsym=USD&allData=true")
    rows = [x for x in d.get("Data", {}).get("Data", []) if x.get("close")]
    return {"resp": d.get("Response"), "msg": d.get("Message"), "n": len(rows), "first": rows[0] if rows else None, "last": rows[-1] if rows else None}
for s in ["BTC", "HYPE", "SUI", "ETH"]:
    probe(f"cryptocompare_{s}", lambda s=s: cc(s))
def cm(a):
    d = get(f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={a}&metrics=PriceUSD&frequency=1d&page_size=3")
    return d.get("data", [])[:3]
for a in ["btc", "hype", "sui"]:
    probe(f"coinmetrics_{a}", lambda a=a: cm(a))
probe("coinmetrics_catalog_n", lambda: len(get("https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics?metrics=PriceUSD&page_size=10000").get("data", [])))
def cg(id_):
    d = get(f"https://api.coingecko.com/api/v3/coins/{id_}/market_chart?vs_currency=usd&days=max&interval=daily")
    p = d.get("prices", [])
    return {"n": len(p), "first": p[0] if p else None, "err": d.get("error") or d.get("status")}
probe("coingecko_bitcoin_max", lambda: cg("bitcoin"))
probe("coingecko_hyperliquid_max", lambda: cg("hyperliquid"))
def top():
    d = get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=40&page=1")
    return [f"{c['market_cap_rank']} {c['id']} {c['symbol']} {c['current_price']}" for c in d]
probe("coingecko_top40", top)
def paprika():
    d = get("https://api.coinpaprika.com/v1/tickers/btc-bitcoin/historical?start=2010-07-01&interval=30d&limit=5")
    return d[:3] if isinstance(d, list) else d
probe("coinpaprika_btc", paprika)
def yahoo():
    import yfinance as yf
    r = {}
    for s in ["HYPE-USD", "HYPE32196-USD", "SUI-USD", "SUI20947-USD"]:
        try:
            h = yf.Ticker(s).history(period="1mo"); r[s] = None if h.empty else float(h["Close"].iloc[-1])
        except Exception as e: r[s] = repr(e)[:100]
    r["search_hyperliquid"] = [(q.get("symbol"), q.get("shortname")) for q in yf.Search("Hyperliquid USD", max_results=10).quotes]
    r["search_sui"] = [(q.get("symbol"), q.get("shortname")) for q in yf.Search("Sui USD", max_results=10).quotes]
    return r
probe("yahoo", yahoo)
json.dump(out, open("probe.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:4000])
