#!/usr/bin/env python3
"""
Arma scripts/config.json: la lista de activos que baja fetch_data.py.

  - ETFs: una lista fija de ~100 de los más usados (abajo): índices, sectores, países, bonos, materias primas.
  - Acciones EE.UU.: las del S&P 500 y el Nasdaq-100, desde las tablas de Wikipedia.
  - Argentina (ADRs): una lista fija de empresas argentinas que cotizan en EE.UU.
  - Cripto: las 100 más grandes por capitalización según CoinGecko, sin stablecoins
    ni versiones "envueltas" o "en staking" de otras monedas.

Cada símbolo se valida contra Yahoo Finance; los que no tienen precios se descartan.
Corre una vez por mes en GitHub Actions (workflow "Actualizar lista de activos").

Uso:
    python scripts/build_universe.py
"""
from __future__ import annotations

import datetime as dt
import io
import json
import pathlib
import re
import sys
import time
import urllib.request

CONFIG = pathlib.Path(__file__).resolve().parent / "config.json"
UA = "Mozilla/5.0 (compatible; ojala-universe/1.0; +https://github.com/fbalassanian/whatif)"
N_CRYPTO = 100

ETFS = [
    # índices de EE.UU.
    ("SPY", "S&P 500 (SPDR)"), ("VOO", "S&P 500 (Vanguard)"), ("IVV", "S&P 500 (iShares)"), ("SPLG", "S&P 500 (SPDR Portfolio)"),
    ("RSP", "S&P 500 equiponderado"), ("QQQ", "Nasdaq 100 (Invesco)"), ("QQQM", "Nasdaq 100 (Invesco, mini)"),
    ("DIA", "Dow Jones"), ("IWM", "Russell 2000"), ("VTI", "Mercado total EE.UU."), ("MDY", "S&P MidCap 400"),
    ("IJH", "S&P MidCap 400 (iShares)"), ("IJR", "S&P SmallCap 600"), ("VUG", "Crecimiento EE.UU. (Vanguard)"),
    ("VTV", "Valor EE.UU. (Vanguard)"), ("IWF", "Russell 1000 Crecimiento"), ("IWD", "Russell 1000 Valor"),
    ("MTUM", "Momentum EE.UU."), ("USMV", "Baja volatilidad EE.UU."),
    # dividendos
    ("SCHD", "Dividendos EE.UU. (Schwab)"), ("VIG", "Dividendos crecientes (Vanguard)"), ("VYM", "Alto dividendo (Vanguard)"),
    ("DGRO", "Crecimiento de dividendos (iShares)"), ("HDV", "Alto dividendo (iShares)"), ("NOBL", "Aristócratas del dividendo"),
    ("JEPI", "Ingreso premium S&P 500 (JPMorgan)"), ("JEPQ", "Ingreso premium Nasdaq (JPMorgan)"),
    # sectores
    ("XLK", "Sector tecnología"), ("XLF", "Sector financiero"), ("XLE", "Sector energía"), ("XLV", "Sector salud"),
    ("XLY", "Sector consumo discrecional"), ("XLP", "Sector consumo básico"), ("XLI", "Sector industrial"),
    ("XLU", "Sector servicios públicos"), ("XLB", "Sector materiales"), ("XLRE", "Sector inmobiliario"),
    ("XLC", "Sector comunicaciones"), ("VGT", "Tecnología (Vanguard)"), ("SMH", "Semiconductores (VanEck)"),
    ("SOXX", "Semiconductores (iShares)"), ("IBB", "Biotecnología (iShares)"), ("XBI", "Biotecnología (SPDR)"),
    ("KRE", "Bancos regionales"), ("ITA", "Aeroespacial y defensa"), ("XHB", "Construcción de viviendas"), ("JETS", "Aerolíneas"),
    # temáticos
    ("ARKK", "Innovación (ARK)"), ("ICLN", "Energía limpia"), ("TAN", "Energía solar"), ("LIT", "Litio y baterías"),
    ("URA", "Uranio"), ("BOTZ", "Robótica e IA"), ("CIBR", "Ciberseguridad"), ("IGV", "Software"),
    # cripto en ETF
    ("IBIT", "Bitcoin (iShares)"), ("FBTC", "Bitcoin (Fidelity)"), ("ETHA", "Ethereum (iShares)"),
    # países y regiones
    ("ARGT", "Argentina (Global X)"), ("EWZ", "Brasil"), ("ILF", "Latinoamérica 40"), ("EWW", "México"), ("ECH", "Chile"),
    ("FXI", "China grandes empresas"), ("MCHI", "China (MSCI)"), ("KWEB", "Internet China"), ("EWJ", "Japón"),
    ("INDA", "India"), ("EWY", "Corea del Sur"), ("EWT", "Taiwán"), ("EWG", "Alemania"), ("EWU", "Reino Unido"),
    ("EZU", "Eurozona"), ("VGK", "Europa (Vanguard)"), ("EEM", "Emergentes (iShares)"), ("VWO", "Emergentes (Vanguard)"),
    ("IEMG", "Emergentes Core (iShares)"), ("EFA", "Desarrollados ex EE.UU. (iShares)"), ("VEA", "Desarrollados ex EE.UU. (Vanguard)"),
    ("VXUS", "Mundo ex EE.UU. (Vanguard)"), ("ACWI", "Mundo (iShares)"), ("VT", "Mundo (Vanguard)"),
    # bonos
    ("BIL", "Letras del Tesoro 1-3 meses"), ("SGOV", "Letras del Tesoro 0-3 meses"), ("SHY", "Tesoro 1-3 años"),
    ("IEF", "Tesoro 7-10 años"), ("TLT", "Tesoro 20+ años"), ("TIP", "Tesoro ajustado por inflación"),
    ("BND", "Bonos EE.UU. total (Vanguard)"), ("AGG", "Bonos EE.UU. total (iShares)"), ("LQD", "Bonos corporativos grado inversión"),
    ("HYG", "Bonos high yield"), ("EMB", "Bonos emergentes en dólares"),
    # materias primas
    ("GLD", "Oro (SPDR)"), ("IAU", "Oro (iShares)"), ("SLV", "Plata"), ("GDX", "Mineras de oro"), ("GDXJ", "Mineras de oro junior"),
    ("COPX", "Mineras de cobre"), ("USO", "Petróleo"), ("UNG", "Gas natural"), ("DBC", "Materias primas (canasta)"),
    # apalancados más usados
    ("TQQQ", "Nasdaq 100 x3"), ("SQQQ", "Nasdaq 100 x3 inverso"), ("SPXL", "S&P 500 x3"), ("SOXL", "Semiconductores x3"),
]
ADRS = [
    ("GGAL", "Grupo Galicia"), ("BMA", "Banco Macro"), ("BBAR", "BBVA Argentina"), ("SUPV", "Supervielle"),
    ("YPF", "YPF"), ("PAM", "Pampa Energía"), ("CEPU", "Central Puerto"), ("TGS", "Transportadora Gas del Sur"),
    ("EDN", "Edenor"), ("TEO", "Telecom Argentina"), ("LOMA", "Loma Negra"), ("CRESY", "Cresud"),
    ("IRS", "IRSA"), ("VIST", "Vista Energy"), ("MELI", "MercadoLibre"), ("GLOB", "Globant"),
    ("DESP", "Despegar"), ("BIOX", "Bioceres"), ("CAAP", "Corporación América"), ("AGRO", "Adecoagro"),
]
# monedas atadas al dólar u otros activos, y versiones envueltas / en staking: no tienen sentido acá
SKIP_CRYPTO = re.compile(r"usd|eur|wrapped|staked|bridged|restak|liquid|tether gold|pax gold|\bbuidl\b|binance-peg", re.I)
# stablecoins sin "usd" en el nombre y monedas respaldadas por oro o plata
SKIP_SYMBOLS = {"DAI", "USDS", "GHO", "FRAX", "LUSD", "CRVUSD", "EURC", "XAUT", "PAXG", "KAU", "KAG", "BUIDL", "USDTB", "USYC", "STABLE"}
NAME_SUFFIX = re.compile(r",?\s+(Inc\.?|Incorporated|Corporation|Corp\.?|Company|Co\.?|plc|N\.V\.|S\.A\.|Ltd\.?|Limited|Holdings?|Group)$", re.I)


def log(msg: str) -> None:
    print(msg, flush=True)


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def wiki_table(pages: tuple[str, ...], sym_cols: tuple[str, ...], name_cols: tuple[str, ...]) -> list[tuple[str, str]]:
    """Primera tabla con columnas de símbolo y nombre (y al menos 90 filas) en alguna de las páginas.
    Los nombres de columna se comparan sin notas al pie ("Company[1]") y sin mayúsculas."""
    import pandas as pd
    base = lambda c: re.sub(r"\[.*?\]", "", str(c[-1] if isinstance(c, tuple) else c)).strip().lower()
    for page in pages:
        try:
            tables = pd.read_html(io.StringIO(get(f"https://en.wikipedia.org/wiki/{page}")))
        except Exception as e:  # noqa: BLE001
            log(f"  {page}: {e}")
            continue
        for t in tables:
            cols = {base(c): c for c in t.columns}
            sc = next((cols[k] for k in sym_cols if k in cols), None)
            nc = next((cols[k] for k in name_cols if k in cols), None)
            if sc is not None and nc is not None and len(t) >= 90:
                return [(str(a).strip(), str(b).strip()) for a, b in zip(t[sc], t[nc]) if str(a).strip() and str(a) != "nan"]
    raise RuntimeError(f"No encontré la tabla de símbolos en {', '.join(pages)}")


def clean_name(n: str) -> str:
    n = re.sub(r"\s*\(.*?\)\s*$", "", n).strip()      # "(Class A)" y similares
    for _ in range(2):
        n = NAME_SUFFIX.sub("", n).strip()
    return n or "?"


def yahoo_ok(symbols: list[str]) -> set[str]:
    """Símbolos que tienen precios en Yahoo (consulta en tandas)."""
    import yfinance as yf
    ok: set[str] = set()
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        df = yf.download(batch, period="1mo", interval="1d", group_by="ticker", progress=False, threads=True, auto_adjust=False)
        for s in batch:
            col = None
            for pick in (lambda: df[s]["Close"], lambda: df["Close"][s], lambda: df["Close"]):   # según la versión de yfinance
                try:
                    col = pick()
                    break
                except Exception:  # noqa: BLE001
                    continue
            if col is not None and getattr(col, "ndim", 1) == 1 and col.dropna().size:
                ok.add(s)
        time.sleep(1)
    return ok


def crypto_symbol(sym: str, name: str) -> str | None:
    """Símbolo de Yahoo para una cripto: SYM-USD, o el que devuelva la búsqueda (ej. SUI20947-USD)."""
    import yfinance as yf
    try:
        for q in yf.Search(f"{name} USD", max_results=10).quotes:
            s = q.get("symbol", "")
            if q.get("quoteType") == "CRYPTOCURRENCY" and s.endswith("-USD") and s.split("-")[0].rstrip("0123456789") == sym:
                return s
    except Exception:  # noqa: BLE001
        pass
    return None


def main() -> int:
    assets: list[dict] = []
    seen: set[str] = set()

    def add(id_: str, yahoo: str, name: str, group: str) -> None:
        if id_ in seen:
            return
        seen.add(id_)
        assets.append({"id": id_, "name": f"{name} ({id_})", "group": group, "yahoo": yahoo})

    for s, n in ETFS:
        add(s, s, re.sub(r"\s*\((.*?)\)", r" \1", n), "ETFs")   # "S&P 500 (Vanguard)" -> "S&P 500 Vanguard"
    for s, n in ADRS:
        add(s, s, n, "Argentina (ADRs)")

    sp = wiki_table(("List_of_S%26P_500_companies",), ("symbol", "ticker"), ("security", "company"))
    try:
        nq = wiki_table(("List_of_NASDAQ-100_companies", "Nasdaq-100"), ("ticker", "symbol"), ("company", "security"))
    except Exception as e:  # noqa: BLE001
        log(f"⚠ Nasdaq-100: {e}. Sigo sin esa lista.")
        nq = []
    log(f"Wikipedia: {len(sp)} del S&P 500, {len(nq)} del Nasdaq-100")
    for s, n in sp + nq:
        y = s.replace(".", "-")                         # BRK.B -> BRK-B
        add(y, y, clean_name(n), "Acciones EE.UU.")

    cg = json.loads(get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=200&page=1"))
    def is_skipped(c: dict) -> bool:
        if SKIP_CRYPTO.search(f"{c['id']} {c['name']} {c['symbol']}") or c["symbol"].upper() in SKIP_SYMBOLS:
            return True
        price = c.get("current_price") or 0
        return 0.97 <= price <= 1.03                     # vale ~1 dólar: es una stablecoin
    coins = [c for c in cg if not is_skipped(c)]
    log(f"CoinGecko: {len(cg)} monedas, {len(coins)} después de sacar stablecoins y envueltas")

    # validar acciones y ETFs contra Yahoo
    stocks = list(assets)
    ok = yahoo_ok([a["yahoo"] for a in stocks])
    dropped = [a["id"] for a in stocks if a["yahoo"] not in ok]
    assets = [a for a in stocks if a["yahoo"] in ok]
    if dropped:
        log(f"Sin datos en Yahoo, se omiten: {', '.join(dropped)}")

    # cripto: SYM-USD; si no existe, se busca el símbolo que usa Yahoo
    ok_c = yahoo_ok([f"{c['symbol'].upper()}-USD" for c in coins])
    n_c = 0
    for c in coins:
        if n_c >= N_CRYPTO:
            break
        sym = c["symbol"].upper()
        y = f"{sym}-USD"
        if y not in ok_c:
            y = crypto_symbol(sym, c["name"])
            if not y or not yahoo_ok([y]):
                log(f"  cripto sin datos en Yahoo: {c['name']} ({sym})")
                continue
        id_ = sym if sym not in seen else f"{sym}-USD"   # si choca con una acción (STX, DASH…), queda STX-USD
        if id_ in seen:
            continue
        seen.add(id_)
        assets.append({"id": id_, "name": f"{c['name']} ({sym})", "group": "Cripto", "yahoo": y})
        n_c += 1

    if len(assets) < 300:
        log(f"✗ Quedaron solo {len(assets)} activos: algo falló, no se toca config.json")
        return 1
    CONFIG.write_text(json.dumps({
        "_comment": "Generado por scripts/build_universe.py. No editar a mano: los cambios se pisan en la próxima corrida.",
        "generated": dt.date.today().isoformat(),
        "assets": assets,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    by = {}
    for a in assets:
        by[a["group"]] = by.get(a["group"], 0) + 1
    log(f"✓ config.json: {len(assets)} activos — " + ", ".join(f"{g}: {n}" for g, n in by.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
