import requests
import pandas as pd
import time
from ta.trend import ADXIndicator, MACD
from ta.momentum import RSIIndicator

# --- CONEXIÓN PARA LA NUBE (RENDER) ---
from keep_alive import keep_alive
keep_alive()
# --------------------------------------

# --- CONFIGURACIÓN ---
TOKEN = "8624275801:AAHIyiTiofLOZJdZfhwww58kx88m940_l9c"
CHAT_ID = "-1003634379653"
APALANCAMIENTO = 20
CANTIDAD_MONEDAS = 5  # Escaneará el Top 5 de monedas con más volumen

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje})

# --- 1. BUSCADOR DE LAS MEJORES MONEDAS ---
def obtener_top_monedas():
    print("🔍 Escaneando Binance para encontrar las monedas con más volumen...")
    url = "https://api.binance.com/api/v3/ticker/24hr"
    respuesta = requests.get(url).json()
    
    mercados = [m for m in respuesta if m['symbol'].endswith('USDT')]
    mercados_ordenados = sorted(mercados, key=lambda x: float(x['quoteVolume']), reverse=True)
    
    top_monedas = []
    for m in mercados_ordenados:
        if m['symbol'] not in ['USDCUSDT', 'FDUSDUSDT']:
            top_monedas.append(m['symbol'])
        if len(top_monedas) == CANTIDAD_MONEDAS:
            break
    return top_monedas

# --- 2. DESCARGA DE DATOS ---
def obtener_datos(simbolo):
    url = f"https://api.binance.com/api/v3/klines?symbol={simbolo}&interval=5m&limit=100"
    respuesta = requests.get(url).json()
    df = pd.DataFrame(respuesta, columns=['tiempo', 'apertura', 'maximo', 'minimo', 'cierre', 'volumen', 'cierre_tiempo', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['cierre'] = df['cierre'].astype(float)
    df['maximo'] = df['maximo'].astype(float)
    df['minimo'] = df['minimo'].astype(float)
    return df

# --- 3. EL TRACKER DE RESULTADOS (LONG Y SHORT) ---
def vigilar_operacion(simbolo, direccion, precio_entrada, tp, sl):
    print(f"👀 Vigilando {simbolo} en {direccion}...")
    
    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            if direccion == "LONG":
                roi = ((precio_actual - precio_entrada) / precio_entrada) * APALANCAMIENTO * 100
                if precio_actual >= tp:
                    estado, emoji = "💥 RESULTADOS REALES 💥", "🎯🔥"
                    break
                elif precio_actual <= sl:
                    estado, emoji = "❌ OPERACIÓN CERRADA ❌ (Stop Loss)", "🛑"
                    break
            
            elif direccion == "SHORT":
                roi = ((precio_entrada - precio_actual) / precio_entrada) * APALANCAMIENTO * 100
                if precio_actual <= tp:
                    estado, emoji = "💥 RESULTADOS REALES 💥", "🎯🔥"
                    break
                elif precio_actual >= sl:
                    estado, emoji = "❌ OPERACIÓN CERRADA ❌ (Stop Loss)", "🛑"
                    break
                    
            time.sleep(3)
        except Exception:
            time.sleep(3)

    mensaje = f"{estado}\n🚀 Nuestro Alertador detectó {simbolo} {direccion}\n\n📈 ROI: {round(roi, 2)}%\nEntrada: {precio_entrada} ➔ Precio Final: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Operación de {simbolo} terminada.")

# --- 4. EL CEREBRO: ESTRATEGIA ADX + RSI + MACD ---
def analizar_mercado(simbolo):
    df = obtener_datos(simbolo)
    
    adx_ind = ADXIndicator(high=df['maximo'], low=df['minimo'], close=df['cierre'], window=14)
    df['adx'] = adx_ind.adx()
    df['+di'] = adx_ind.adx_pos()
    df['-di'] = adx_ind.adx_neg()
    
    df['rsi'] = RSIIndicator(close=df['cierre'], window=14).rsi()
    df['macd_hist'] = MACD(close=df['cierre']).macd_diff()
    
    vela = df.iloc[-2] 
    precio_actual = df.iloc[-1]['cierre']
    
    print(f"📊 {simbolo} -> ADX: {round(vela['adx'],1)} | RSI: {round(vela['rsi'],1)}")

    if vela['adx'] > 25 and vela['+di'] > vela['-di'] and vela['rsi'] > 55 and vela['macd_hist'] > 0:
        tp = round(precio_actual * 1.004, 4)
        sl = round(precio_actual * 0.996, 4)
        mensaje = f"🚨 SEÑAL SCALPING VIP 🚨\n\nMoneda: #{simbolo}\nDirección: LONG 🟢\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
        enviar_telegram(mensaje)
        vigilar_operacion(simbolo, "LONG", precio_actual, tp, sl)
        return True

    elif vela['adx'] > 25 and vela['-di'] > vela['+di'] and vela['rsi'] < 45 and vela['macd_hist'] < 0:
        tp = round(precio_actual * 0.996, 4)
        sl = round(precio_actual * 1.004, 4)
        mensaje = f"🚨 SEÑAL SCALPING VIP 🚨\n\nMoneda: #{simbolo}\nDirección: SHORT 🔴\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
        enviar_telegram(mensaje)
        vigilar_operacion(simbolo, "SHORT", precio_actual, tp, sl)
        return True

    return False

# --- 5. BUCLE PRINCIPAL MULTI-MONEDA ---
print("🚀 Iniciando Escáner de Criptomonedas (Volumen + ADX + RSI + MACD)...")
while True:
    try:
        top_monedas = obtener_top_monedas()
        print(f"🏆 Top monedas a vigilar: {top_monedas}")
        
        for moneda in top_monedas:
            hubo_operacion = analizar_mercado(moneda)
            if hubo_operacion:
                print("⏳ Pausa de 30 segundos tras cerrar la operación...")
                time.sleep(30)
                break
            time.sleep(2)
    except Exception as e:
        print(f"Error general: {e}")
        time.sleep(10)