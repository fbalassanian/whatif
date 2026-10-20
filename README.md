# What if?

"Si en marzo de 2016 hubieras puesto USD 1.000 en Apple, ¿cuánto tendrías en tal mes?" Todo en dólares, con la opción de reinvertir dividendos, para acciones, ETFs y cripto. Se puede invertir una sola vez o todos los meses; en ese caso el rendimiento anual se muestra como TIR.

Para jugar:

- **Barra de tiempo y reproducir:** arrastrás por el recorrido o lo reproducís, y la cifra cambia mes a mes. Pasar el mouse por el gráfico muestra ese mes.
- **Carrera:** hasta 3 activos más con el mismo monto y las mismas fechas, que avanzan juntos al reproducir.
- **Sorpréndeme:** arma un escenario al azar.
- **Copiar link:** el escenario queda en el link (`#SPY~2016-01~500~m~2025-12~1~NVDA_BTC`), así quien lo abre ve lo mismo. Si la fecha final es futura, proyecta desde el último dato con el rendimiento que elijas.

Es un sitio estático: no tiene servidor ni base de datos. Un script baja los datos una vez por día y los guarda como JSON; la página los lee y hace todos los cálculos en el navegador.

## Cómo está armado

```
main (rama)     → el sitio: lo publica Netlify. Solo cambia cuando tocás el código.
data (rama)     → los datos: los escribe GitHub Actions todos los días.
                  La página los lee desde jsDelivr: cdn.jsdelivr.net/gh/USUARIO/REPO@data/
```

```
index.html                         la página (gráfico con TradingView Lightweight Charts)
netlify.toml                       config de Netlify (sin build)
scripts/fetch_data.py              baja precios y dividendos y escribe data/
scripts/config.json                lista de activos (agregá o sacá líneas acá)
.github/workflows/update-data.yml  corre el script todos los días y publica la rama data

En la rama data:
manifest.json                      activos disponibles, si pagan dividendos y fecha de actualización
assets/<ID>.json                   "m": cierre de cada mes en USD · "d": dividendos por acción de cada mes
```

**Por qué los datos van en otra rama:** en el plan gratis de Netlify cada deploy de producción cuesta 15 de los 300 créditos del mes, y si se terminan los créditos el sitio se pausa hasta el mes siguiente. Actualizar los datos en `main` todos los días serían unos 26 deploys, 390 créditos. Con los datos en la rama `data`, Netlify solo despliega cuando cambiás el código.

## Fuentes

Todo sale de Yahoo Finance (`yfinance`), en una consulta por activo:

| Dato | Detalle |
|---|---|
| Precio | Último cierre de cada mes, en USD, ajustado solo por splits |
| Dividendos | Monto por acción, sumado por mes según la fecha ex-dividendo, ajustado por splits |

Precio y dividendos van por separado a propósito: así la página puede calcular las dos variantes. Con reinversión, cada dividendo compra más acciones al cierre de ese mes. Sin reinversión, se acumula como efectivo y se suma al valor final. No se descuentan impuestos ni comisiones.

Un CEDEAR rinde en dólares lo mismo que la acción de EE.UU. que representa, así que no necesita datos propios.

## Correrlo en tu compu

```bash
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/fetch_data.py          # tarda ~1 minuto (pausa entre activos para no gatillar el límite de Yahoo)
python -m http.server 8000            # abrí http://localhost:8000
```

Sin internet podés probar con datos simulados: `python scripts/fetch_data.py --fake` (la página lo avisa arriba a la derecha).

Para actualizar solo algunos activos: `python scripts/fetch_data.py --only BTC SPY`.

En `localhost` la página busca primero la carpeta `data/` local, así probás tus datos recién bajados. Si no encuentra datos en ningún lado, usa datos de ejemplo aproximados y lo indica con un aviso.

## Publicarlo en Netlify (gratis)

1. **Subí la carpeta a un repo público de GitHub.** Tiene que ser público para que jsDelivr pueda servir los datos.
2. **Poné tu repo en `index.html`.** En la línea `<meta name="whatif-data" ...>`, reemplazá `USUARIO/REPO` por el tuyo, por ejemplo `cdn.jsdelivr.net/gh/fede/whatif@data/`.
3. **Dale permiso de escritura al workflow:** Settings → Actions → General → Workflow permissions → **Read and write**.
4. **Generá los datos por primera vez:** Actions → **Actualizar datos** → **Run workflow**. Al terminar vas a ver la rama `data`.
5. **Conectá Netlify:** Add new site → Import from Git → elegí el repo, rama `main`. No hace falta configurar nada más; `netlify.toml` ya dice que no hay build.

Desde ahí:

- Los datos se actualizan de lunes a sábado a las 19:17 hora argentina, sin deploys en Netlify.
- jsDelivr guarda en caché los archivos de una rama hasta 12 horas, así que un dato nuevo puede tardar hasta la mañana siguiente en verse. Para esta herramienta alcanza.
- Si Yahoo falla con un activo, se conserva el dato anterior y queda marcado `"stale": true` en el manifest. El sitio sigue andando.
- Si jsDelivr no responde, la página muestra los datos de ejemplo con el aviso, en vez de romperse.

**Consumo estimado de créditos en Netlify:** solo se sirve `index.html` (unos 25 KB por visita); fuentes, librería del gráfico y datos vienen de otros servidores. Netlify cobra 2 créditos cada 10.000 pedidos y 20 créditos por GB transferido, así que 10.000 visitas cuestan unos 9 créditos. Con 300 créditos al mes hay margen para decenas de miles de visitas más un puñado de deploys cuando cambies el diseño.

### Publicarlo en Vercel (gratis)

Los pasos 1 a 4 son los mismos de arriba. Después, en Vercel: **Add New → Project → Import** el repo, con Framework Preset **Other**, sin comando de build y con la raíz del repo como carpeta de salida. `vercel.json` ya evita que la rama `data` genere deploys.

El plan gratis de Vercel (Hobby) es solo para uso personal y no comercial. Si le ponés publicidad o lo monetizás, corresponde el plan Pro.

### Otras alternativas

El mismo repo también funciona en Cloudflare Pages o GitHub Pages: conectás la rama `main` y listo.

## Agregar activos

Sumá una línea en `scripts/config.json`:

```json
{"id": "COST", "name": "Costco (COST)", "group": "Acciones EE.UU. / CEDEARs", "yahoo": "COST"}
```

`yahoo` es el símbolo tal como aparece en Yahoo Finance (para cripto, por ejemplo `LINK-USD`). Tiene que cotizar en dólares. Los grupos del selector salen del campo `group`.

## Licencias y límites

- `yfinance` no es una API oficial: Yahoo puede limitar o cambiar sus endpoints, y sus términos restringen la redistribución. Para un proyecto gratuito y chico el riesgo es bajo; si lo monetizás, conviene pasar a un proveedor con licencia (Tiingo, Twelve Data).
- Lightweight Charts es open source (Apache 2.0) y pide atribución a TradingView; el pie de página ya la incluye.
- Nada de esto es recomendación de inversión, y la página lo dice.
