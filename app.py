import streamlit as st
import requests
import urllib3
import ssl
import time
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

sesion = requests.Session()
sesion.mount('https://', SSLAdapter())

def obtener_dolar(casa):
    try:
        r = sesion.get(f"https://dolarapi.com/v1/dolares/{casa}", timeout=10)
        d = r.json()
        return d.get("compra"), d.get("venta")
    except:
        return None, None

def obtener_argentinadatos(endpoint):
    try:
        r = sesion.get(f"https://api.argentinadatos.com/v1/{endpoint}", timeout=10)
        d = r.json()
        if isinstance(d, list) and len(d) > 0:
            return d[-1]
        return d
    except:
        return None

def obtener_bcra(id_variable):
    try:
        r = sesion.get(f"https://api.bcra.gob.ar/estadisticas/v4.0/monetarias/{id_variable}", timeout=10)
        d = r.json()
        return d["results"][0]["detalle"][0]["valor"]
    except:
        return None

def obtener_tir_bonistas(ticker):
    try:
        url = f"https://bonistas.com/bono-cotizacion-rendimiento-precio-hoy/{ticker}"
        r = sesion.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        spans = soup.find_all("span", class_="font-mono text-sm tabular-nums font-semibold text-foreground")
        if len(spans) > 4:
            return spans[4].text.strip()
        return "—"
    except:
        return "—"

@st.cache_data(ttl=300)
def cargar_datos():
    of_c, of_v   = obtener_dolar("oficial")
    bl_c, bl_v   = obtener_dolar("blue")
    mep_c, mep_v = obtener_dolar("bolsa")
    ccl_c, ccl_v = obtener_dolar("contadoconliqui")
    may_c, may_v = obtener_dolar("mayorista")

    riesgo_raw    = obtener_argentinadatos("finanzas/indices/riesgo-pais")
    riesgo_pais   = riesgo_raw.get("valor") if riesgo_raw else None
    infla_raw     = obtener_argentinadatos("finanzas/indices/inflacion")
    inflacion_mes = infla_raw.get("valor") if infla_raw else None
    infla_ia_raw  = obtener_argentinadatos("finanzas/indices/inflacion-interanual")
    inflacion_12m = infla_ia_raw.get("valor") if infla_ia_raw else None

    badlar   = obtener_bcra(7)
    adelanto = obtener_bcra(145)

    instrumentos = ["S30A6", "S29Y6", "TZX26", "TX26", "TZXM7", "D30A6", "TZVD6", "BPOC7", "GD38"]
    rendimientos = {}
    for ticker in instrumentos:
        rendimientos[ticker] = obtener_tir_bonistas(ticker)
        time.sleep(0.3)

    return {
        "dolares": {
            "Oficial":   {"Compra": of_c,  "Venta": of_v},
            "Blue":      {"Compra": bl_c,  "Venta": bl_v},
            "MEP":       {"Compra": mep_c, "Venta": mep_v},
            "CCL":       {"Compra": ccl_c, "Venta": ccl_v},
            "Mayorista": {"Compra": may_c, "Venta": may_v},
        },
        "mercado": {
            "Riesgo País":       f"{riesgo_pais} pts" if riesgo_pais else "—",
            "Inflación mensual": f"{inflacion_mes}%" if inflacion_mes else "—",
            "Inflación 12m":     f"{inflacion_12m}%" if inflacion_12m else "—",
        },
        "bcra": {
            "BADLAR (PF > $1M)":  f"{badlar}% TNA" if badlar else "—",
            "Adelanto Cta. Cte.": f"{adelanto}% TNA" if adelanto else "—",
        },
        "rendimientos": rendimientos,
        "hora": datetime.now().strftime("%d/%m/%Y  %H:%M:%S")
    }

# === INTERFAZ ===
st.set_page_config(page_title="Monitor Financiero", page_icon="📊", layout="centered")

st.markdown("""
    <h1 style='color:#0A2D50; margin-bottom:0'>📊 Monitor Financiero</h1>
    <p style='color:#0096A0; font-weight:bold; margin-top:0'>WL HNOS & ASOC</p>
""", unsafe_allow_html=True)

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()

with st.spinner("Consultando APIs..."):
    datos = cargar_datos()

st.caption(f"Última actualización: {datos['hora']}")

st.divider()

# DÓLARES
st.subheader("💵 Dólares")
cols = st.columns(5)
for i, (nombre, vals) in enumerate(datos["dolares"].items()):
    with cols[i]:
        compra = f"${vals['Compra']:,.0f}".replace(",", ".") if vals["Compra"] else "—"
        venta  = f"${vals['Venta']:,.0f}".replace(",", ".") if vals["Venta"] else "—"
        st.metric(label=nombre, value=venta, delta=f"Compra: {compra}")

st.divider()

# MERCADO Y BCRA
col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Mercado")
    for nombre, valor in datos["mercado"].items():
        st.metric(label=nombre, value=valor)

with col2:
    st.subheader("🏦 BCRA — Tasas")
    for nombre, valor in datos["bcra"].items():
        st.metric(label=nombre, value=valor)

st.divider()

# RENDIMIENTOS
st.subheader("📋 Rendimientos — Instrumentos Sugeridos")
filas = [{"Ticker": ticker, "TIR / YTM": tir} for ticker, tir in datos["rendimientos"].items()]
st.table(filas)

st.caption("Fuentes: BCRA · DolarAPI · ArgentinaDatos · Bonistas.com")
