import requests
import pandas as pd
import time
from ta.trend import ADXIndicator, MACD, EMAIndicator
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
    print("🔍 Escaneando Binance para encontrar las monedas con más volumen...")
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
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"] # Respaldo

# Función mejorada para pedir distintos intervalos (1h y 5m)
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

    mensaje = f"{estado}\n🚀 Nuestro Alertador PRO detectó {simbolo} {direccion}\n\n📈 ROI: {round(roi, 2)}%\nEntrada: {precio_entrada} ➔ Precio Final: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Operación terminada.")

# --- EL NUEVO CEREBRO PROFESIONAL ---
def analizar_mercado(simbolo):
    try:
        # 1. ANÁLISIS MACRO (Gráfico de 1 Hora)
        df_1h = obtener_datos(simbolo, "1h", 250)
        df_1h['ema_200'] = EMAIndicator(close=df_1h['cierre'], window=200).ema_indicator()
        precio_1h = df_1h.iloc[-1]['cierre']
        ema_200 = df_1h.iloc[-1]['ema_200']
        
        tendencia_macro = "ALCISTA" if precio_1h > ema_200 else "BAJISTA"

        # 2. ANÁLISIS MICRO Y GATILLO (Gráfico de 5 Minutos)
        df_5m = obtener_datos(simbolo, "5m", 100)
        
        adx_ind = ADXIndicator(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        df_5m['adx'] = adx_ind.adx()
        df_5m['+di'] = adx_ind.adx_pos()
        df_5m['-di'] = adx_ind.adx_neg()
        
        df_5m['rsi'] = RSIIndicator(close=df_5m['cierre'], window=14).rsi()
        df_5m['macd_hist'] = MACD(close=df_5m['cierre']).macd_diff()
        
        # Calcular el ATR para el Stop Loss Dinámico
        atr_ind = AverageTrueRange(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        df_5m['atr'] = atr_ind.average_true_range()
        
        vela = df_5m.iloc[-2] 
        precio_actual = df_5m.iloc[-1]['cierre']
        atr_actual = df_5m.iloc[-1]['atr']
        
        print(f"📊 {simbolo} | Macro 1H: {tendencia_macro} | ADX: {round(vela['adx'],1)} | RSI: {round(vela['rsi'],1)}")

        # ESTRATEGIA LONG 🟢 (Solo si la Macro es Alcista)
        if tendencia_macro == "ALCISTA" and vela['adx'] > 25 and vela['+di'] > vela['-di'] and vela['rsi'] > 55 and vela['macd_hist'] > 0:
            sl = round(precio_actual - (atr_actual * 1.5), 4) # Stop Loss a 1.5 veces el ATR
            tp = round(precio_actual + (atr_actual * 3.0), 4) # Take Profit al doble del SL (Ratio 1:2)
            
            mensaje = f"🚨 SEÑAL INSTITUCIONAL 🚨\n\nMoneda: #{simbolo}\nDirección: LONG 🟢\nFiltro 1H: Aprobado ✅\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "LONG", precio_actual, tp, sl)
            return True

        # ESTRATEGIA SHORT 🔴 (Solo si la Macro es Bajista)
        elif tendencia_macro == "BAJISTA" and vela['adx'] > 25 and vela['-di'] > vela['+di'] and vela['rsi'] < 45 and vela['macd_hist'] < 0:
            sl = round(precio_actual + (atr_actual * 1.5), 4)
            tp = round(precio_actual - (atr_actual * 3.0), 4)
            
            mensaje = f"🚨 SEÑAL INSTITUCIONAL 🚨\n\nMoneda: #{simbolo}\nDirección: SHORT 🔴\nFiltro 1H: Aprobado ✅\n\n📌 Entrada: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "SHORT", precio_actual, tp, sl)
            return True

        return False
    except Exception as e:
        print(f"Error analizando {simbolo}: {e}")
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot Quant PRO (EMA 200 + ADX + ATR)...")
while True:
    try:
        top_monedas = obtener_top_monedas()
        print(f"\n🏆 Top monedas: {top_monedas}")
        
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
