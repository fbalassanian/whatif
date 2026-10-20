#!/usr/bin/env python3
"""
Baja los datos que usa Ojalá y los deja como JSON estáticos en data/.

Para cada activo de scripts/config.json, desde Yahoo Finance (yfinance):
  - "m": precio de cierre del último día de cada mes, en USD, ajustado
         solo por splits (no por dividendos).
  - "d": dividendos por acción pagados en cada mes (fecha ex-dividendo),
         también ajustados por splits. Vacío si el activo no paga.

Con esas dos series la página calcula la inversión con o sin reinversión
de dividendos.

Uso:
    python scripts/fetch_data.py              # baja todo
    python scripts/fetch_data.py --only BTC SPY
    python scripts/fetch_data.py --fake       # datos simulados, sin internet (para probar)

Si un activo falla, se conserva el archivo que ya había y queda marcado
como "stale" en data/manifest.json. El sitio sigue funcionando con el dato anterior.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import random
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS_DIR = DATA / "assets"
CONFIG = pathlib.Path(__file__).resolve().parent / "config.json"
YAHOO_PAUSE_S = 1.5          # pausa entre activos para no gatillar el límite de Yahoo
YAHOO_RETRIES = 3


# ---------------------------------------------------------------- utilidades
def log(msg: str) -> None:
    print(msg, flush=True)


def write_json(path: pathlib.Path, obj) -> None:
    """Escritura atómica: si el proceso se corta, no queda un archivo a medias."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def month_key(d) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def clean_prices(series: list[list], name: str) -> list[list]:
    """Ordena, se queda con el último valor de cada mes y descarta valores no positivos."""
    by_month: dict[str, float] = {}
    for m, v in series:
        if v is None or not math.isfinite(v) or v <= 0:
            continue
        by_month[m] = float(v)
    out = [[m, round(by_month[m], 6)] for m in sorted(by_month)]
    if len(out) < 2:
        raise ValueError(f"{name}: menos de 2 meses de datos")
    for (m0, v0), (m1, v1) in zip(out, out[1:]):
        ratio = v1 / v0
        if ratio > 20 or ratio < 1 / 20:
            log(f"  ⚠ {name}: salto raro entre {m0} y {m1} (×{ratio:.1f}). Revisalo.")
    return out


def clean_dividends(series: list[list], prices: list[list], name: str) -> list[list]:
    """Suma por mes, descarta montos no positivos y meses sin precio."""
    with_price = {m for m, _ in prices}
    price_at = dict(prices)
    by_month: dict[str, float] = {}
    for m, v in series:
        if v is None or not math.isfinite(v) or v <= 0 or m not in with_price:
            continue
        by_month[m] = by_month.get(m, 0.0) + float(v)
    out = [[m, round(by_month[m], 6)] for m in sorted(by_month)]
    for m, v in out:
        if v / price_at[m] > 0.25:
            log(f"  ⚠ {name}: dividendo de {v} en {m} es más del 25% del precio. Revisalo.")
    return out


# ---------------------------------------------------------------- fuente real
def fetch_yahoo(symbol: str) -> tuple[list[list], list[list], str]:
    """Historia diaria completa en una sola consulta; se agrupa por mes acá.
    El mes en curso queda con el último cierre disponible, y "asof" es la fecha de ese cierre."""
    import yfinance as yf

    last = None
    for attempt in range(YAHOO_RETRIES):
        try:
            df = yf.Ticker(symbol).history(period="max", interval="1d",
                                           auto_adjust=False, actions=True)
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"Yahoo no respondió: {last}")

    if df is None or df.empty or "Close" not in df:
        return [], [], ""
    valid = df["Close"].dropna()
    asof = valid.index[-1].strftime("%Y-%m-%d") if len(valid) else ""
    months = [month_key(i) for i in df.index]
    df = df.assign(_m=months)
    g = df.groupby("_m", sort=True)
    close = g["Close"].last()                       # último cierre válido del mes
    prices = [[k, float(v)] for k, v in close.dropna().items()]
    divs = []
    if "Dividends" in df:
        divs = [[k, float(v)] for k, v in g["Dividends"].sum().items() if v and v > 0]
    return prices, divs, asof


# ---------------------------------------------------------------- fuente simulada (--fake)
def fake_yahoo(symbol: str) -> tuple[list[list], list[list], str]:
    rnd = random.Random(symbol)
    crypto = symbol.endswith("-USD")
    y, m = (2014, 9) if crypto else (2005, 1)
    drift, vol = (0.03, 0.20) if crypto else (0.007, 0.06)
    pays = not crypto and rnd.random() < 0.7          # ~70% de las acciones pagan
    yield_q = rnd.uniform(0.003, 0.008)                # dividendo trimestral como % del precio
    today = dt.date.today()
    prices, divs, p = [], [], 100.0
    while (y, m) <= (today.year, today.month):
        k = f"{y:04d}-{m:02d}"
        prices.append([k, p])
        if pays and m in (3, 6, 9, 12):
            divs.append([k, p * yield_q])
        p *= math.exp(rnd.gauss(drift, vol))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return prices, divs, today.isoformat()


# ---------------------------------------------------------------- armado
def existing_entry(path: pathlib.Path, entry: dict) -> dict | None:
    """Entrada de manifest para un activo que no se actualizó en esta corrida."""
    if not path.exists():
        return None
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        return {**entry, "div": bool(old.get("d")), "first": old["m"][0][0], "last": old["m"][-1][0],
                "asof": old.get("asof", "")}
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fake", action="store_true", help="usar datos simulados (sin internet)")
    ap.add_argument("--only", nargs="*", help="ids de config.json a actualizar")
    args = ap.parse_args()

    get = fake_yahoo if args.fake else fetch_yahoo
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))["assets"]
    wanted = set(args.only or [])
    errors = 0
    manifest_assets = []

    for i, a in enumerate(cfg):
        path = ASSETS_DIR / f"{a['id']}.json"
        entry = {k: a[k] for k in ("id", "name", "group")}
        if wanted and a["id"] not in wanted:
            old = existing_entry(path, entry)
            if old:
                manifest_assets.append(old)
            continue
        try:
            raw_p, raw_d, asof = get(a["yahoo"])
            prices = clean_prices(raw_p, a["id"])
            divs = clean_dividends(raw_d, prices, a["id"])
            write_json(path, {**entry,
                              "source": f"Yahoo Finance ({a['yahoo']}): cierre mensual en USD ajustado por splits; dividendos por acción",
                              "asof": asof, "m": prices, "d": divs})
            manifest_assets.append({**entry, "div": bool(divs), "first": prices[0][0], "last": prices[-1][0], "asof": asof})
            log(f"✓ {a['id']:6} {prices[0][0]}→{asof} ({len(prices)} meses, {len(divs)} con dividendos)")
        except Exception as e:  # noqa: BLE001
            errors += 1
            old = existing_entry(path, entry)
            if old:
                log(f"✗ {a['id']}: {e} (se conserva el archivo anterior)")
                manifest_assets.append({**old, "stale": True})
            else:
                log(f"✗ {a['id']}: {e} (se omite)")
        if not args.fake and i < len(cfg) - 1:
            time.sleep(YAHOO_PAUSE_S)

    write_json(DATA / "manifest.json", {
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fake": bool(args.fake),
        "assets": manifest_assets,
    })
    log(f"Listo: {len(manifest_assets)} activos, {errors} errores.")
    # Falla solo si no quedó nada usable, así el workflow no se pone en rojo por un activo suelto.
    return 0 if manifest_assets else 1


if __name__ == "__main__":
    sys.exit(main())
