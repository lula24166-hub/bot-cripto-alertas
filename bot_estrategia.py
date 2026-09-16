import requests
import pandas as pd
import time
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# --- CONEXIÓN PARA LA NUBE (RENDER) ---
from keep_alive import keep_alive
keep_alive()
# --------------------------------------

# --- CONFIGURACIÓN ---
TOKEN = "8624275801:AAHIyiTiofLOZJdZfhwww58kx88m940_l9c"
CHAT_ID = "-1003634379653"
APALANCAMIENTO = 20
CANTIDAD_MONEDAS = 5  

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje})

def obtener_top_monedas():
    try:
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
    except:
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

def obtener_datos(simbolo, intervalo, limite):
    url = f"https://api.binance.com/api/v3/klines?symbol={simbolo}&interval={intervalo}&limit={limite}"
    respuesta = requests.get(url).json()
    df = pd.DataFrame(respuesta, columns=['tiempo', 'apertura', 'maximo', 'minimo', 'cierre', 'volumen', 'cierre_tiempo', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    df['cierre'] = df['cierre'].astype(float)
    df['maximo'] = df['maximo'].astype(float)
    df['minimo'] = df['minimo'].astype(float)
    return df

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
        except:
            time.sleep(3)

    mensaje = f"{estado}\n🚀 Estrategia DOBLE ADX en {simbolo}\nDirección: {direccion}\n\n📈 ROI: {round(roi, 2)}%\nEntrada: {precio_entrada} ➔ Precio Final: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Operación terminada.")

# --- EL CEREBRO: ESTRATEGIA MULTI-ADX (COPIA DE TRADER PRO) ---
def analizar_mercado(simbolo):
    try:
        # 1. FILTRO 4 HORAS (Tendencia Macro)
        df_4h = obtener_datos(simbolo, "4h", 100)
        adx_4h_ind = ADXIndicator(high=df_4h['maximo'], low=df_4h['minimo'], close=df_4h['cierre'], window=14)
        adx_4h = adx_4h_ind.adx().iloc[-2]
        di_pos_4h = adx_4h_ind.adx_pos().iloc[-2]
        di_neg_4h = adx_4h_ind.adx_neg().iloc[-2]

        tendencia_4h = "NEUTRAL"
        if adx_4h > 20: # Exigimos fuerza mayor a 20
            if di_pos_4h > di_neg_4h: tendencia_4h = "ALCISTA"
            elif di_neg_4h > di_pos_4h: tendencia_4h = "BAJISTA"

        # 2. FILTRO 1 HORA (Confirmación)
        df_1h = obtener_datos(simbolo, "1h", 100)
        adx_1h_ind = ADXIndicator(high=df_1h['maximo'], low=df_1h['minimo'], close=df_1h['cierre'], window=14)
        adx_1h = adx_1h_ind.adx().iloc[-2]
        di_pos_1h = adx_1h_ind.adx_pos().iloc[-2]
        di_neg_1h = adx_1h_ind.adx_neg().iloc[-2]

        tendencia_1h = "NEUTRAL"
        if adx_1h > 20:
            if di_pos_1h > di_neg_1h: tendencia_1h = "ALCISTA"
            elif di_neg_1h > di_pos_1h: tendencia_1h = "BAJISTA"

        # 3. GATILLO 5 MINUTOS y ATR
        df_5m = obtener_datos(simbolo, "5m", 100)
        adx_5m_ind = ADXIndicator(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        adx_5m = adx_5m_ind.adx().iloc[-2]
        di_pos_5m = adx_5m_ind.adx_pos().iloc[-2]
        di_neg_5m = adx_5m_ind.adx_neg().iloc[-2]
        
        rsi_5m = RSIIndicator(close=df_5m['cierre'], window=14).rsi().iloc[-2]
        
        atr_ind = AverageTrueRange(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        atr_actual = atr_ind.average_true_range().iloc[-1]
        precio_actual = df_5m.iloc[-1]['cierre']

        print(f"📊 {simbolo} | 4H: {tendencia_4h} ({round(adx_4h,1)}) | 1H: {tendencia_1h} ({round(adx_1h,1)}) | Gatillo 5M: {round(adx_5m,1)}")

        # ESTRATEGIA LONG 🟢 (Triple Alineación)
        if tendencia_4h == "ALCISTA" and tendencia_1h == "ALCISTA" and adx_5m > 25 and di_pos_5m > di_neg_5m and rsi_5m > 50:
            sl = round(precio_actual - (atr_actual * 1.5), 4)
            tp = round(precio_actual + (atr_actual * 3.0), 4)
            
            mensaje = f"🚨 SEÑAL INSTITUCIONAL (DOBLE ADX) 🚨\n\nMoneda: #{simbolo}\nDirección: LONG 🟢\nFuerza 4H: Aprobado ✅\nFuerza 1H: Aprobado ✅\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "LONG", precio_actual, tp, sl)
            return True

        # ESTRATEGIA SHORT 🔴 (Triple Alineación)
        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 25 and di_neg_5m > di_pos_5m and rsi_5m < 50:
            sl = round(precio_actual + (atr_actual * 1.5), 4)
            tp = round(precio_actual - (atr_actual * 3.0), 4)
            
            mensaje = f"🚨 SEÑAL INSTITUCIONAL (DOBLE ADX) 🚨\n\nMoneda: #{simbolo}\nDirección: SHORT 🔴\nFuerza 4H: Aprobado ✅\nFuerza 1H: Aprobado ✅\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "SHORT", precio_actual, tp, sl)
            return True

        return False
    except Exception as e:
        print(f"Error analizando {simbolo}: {e}")
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot con Estrategia Multi-ADX de 4H y 1H...")
while True:
    try:
        top_monedas = obtener_top_monedas()
        
        for moneda in top_monedas:
            hubo_operacion = analizar_mercado(moneda)
            if hubo_operacion:
                print("⏳ Pausa de 30 segundos tras cerrar la operación...")
                time.sleep(30)
                break
            time.sleep(2)
    except Exception as e:
        print(f"Error en bucle principal: {e}")
        time.sleep(10)
