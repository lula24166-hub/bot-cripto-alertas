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

# --- CONFIGURACIÓN TELEGRAM ---
TOKEN = "8624275801:AAHIyiTiofLOZJdZfhwww58kx88m940_l9c"
CHAT_ID = "-1003634379653"

# --- CONFIGURACIÓN DE TRADING SIMULADO (PAPER TRADING) ---
APALANCAMIENTO = 20
INVERSION_USD = 20  # Dólares virtuales que usará por operación
CANTIDAD_MONEDAS = 5

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje})
    except:
        pass

# --- FUNCIONES DE SIMULACIÓN (PAPER TRADING) ---
def ejecutar_apertura(simbolo, direccion, precio_actual):
    tamano_posicion_usd = INVERSION_USD * APALANCAMIENTO
    cantidad_monedas = tamano_posicion_usd / precio_actual
    print(f"⚙️ SIMULADOR: Abriendo operación {direccion} virtual en {simbolo} por ${tamano_posicion_usd}...")
    return cantidad_monedas

def ejecutar_cierre(simbolo, direccion, cantidad_final):
    print(f"⚙️ SIMULADOR: Cerrando operación {direccion} en {simbolo}. Registrando ganancias...")

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
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={simbolo}&interval={intervalo}&limit={limite}"
        respuesta = requests.get(url).json()
        if isinstance(respuesta, dict) and 'msg' in respuesta: return None
        df = pd.DataFrame(respuesta, columns=['tiempo', 'apertura', 'maximo', 'minimo', 'cierre', 'volumen', 'cierre_tiempo', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
        df['cierre'] = df['cierre'].astype(float)
        df['maximo'] = df['maximo'].astype(float)
        df['minimo'] = df['minimo'].astype(float)
        return df
    except:
        return None

# --- EL VIGILANTE CON TRAILING STOP (SIMULADO) ---
def vigilar_operacion(simbolo, direccion, precio_entrada, tp1, tp2, tp3, sl_inicial, cantidad_comprada):
    print(f"👀 Bot Simulador vigilando {simbolo} (Estrategia 3 Fases)...")
    
    fase = 0  
    sl_actual = sl_inicial

    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            # --- LÓGICA PARA LONG 🟢 ---
            if direccion == "LONG":
                roi = ((precio_actual - precio_entrada) / precio_entrada) * APALANCAMIENTO * 100
                
                if fase == 0 and precio_actual >= tp1:
                    sl_actual = precio_entrada
                    fase = 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({tp1})\n🛡 SL movido a Precio de Entrada.")
                
                elif fase == 1 and precio_actual >= tp2:
                    sl_actual = tp1
                    fase = 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({tp2})\n💰 SL movido a TP1.")
                
                elif precio_actual >= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                
                elif precio_actual <= sl_actual:
                    if fase == 0:
                        estado, emoji = "❌ STOP LOSS TOCADO ❌", "🛑"
                    else:
                        estado, emoji = "🛡 TRAILING STOP TOCADO (Salida Segura) 🛡", "✅"
                    break

            # --- LÓGICA PARA SHORT 🔴 ---
            elif direccion == "SHORT":
                roi = ((precio_entrada - precio_actual) / precio_entrada) * APALANCAMIENTO * 100
                
                if fase == 0 and precio_actual <= tp1:
                    sl_actual = precio_entrada
                    fase = 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({tp1})\n🛡 SL movido a Precio de Entrada.")
                
                elif fase == 1 and precio_actual <= tp2:
                    sl_actual = tp1
                    fase = 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({tp2})\n💰 SL movido a TP1.")
                
                elif precio_actual <= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                
                elif precio_actual >= sl_actual:
                    if fase == 0:
                        estado, emoji = "❌ STOP LOSS TOCADO ❌", "🛑"
                    else:
                        estado, emoji = "🛡 TRAILING STOP TOCADO (Salida Segura) 🛡", "✅"
                    break

            time.sleep(3)
        except Exception as e:
            time.sleep(3)

    # 1. Cierre Simulado
    ejecutar_cierre(simbolo, direccion, cantidad_comprada)
    ganancia_usd = round(INVERSION_USD * (roi / 100), 2)

    # 2. Reporte Final
    mensaje = f"{estado}\n🤖 PAPER TRADING CERRADO: {simbolo}\n\n📈 PnL: {round(roi, 2)}%\n💵 Ganancia/Pérdida Aprox: ${ganancia_usd} USD\nEntrada: {precio_entrada} ➔ Precio Salida: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Auto-Trade Simulado finalizado.")

def analizar_mercado(simbolo):
    try:
        # Filtro 4H
        df_4h = obtener_datos(simbolo, "4h", 100)
        if df_4h is None or len(df_4h) < 20: return False 
        adx_4h_ind = ADXIndicator(high=df_4h['maximo'], low=df_4h['minimo'], close=df_4h['cierre'], window=14)
        adx_4h, di_pos_4h, di_neg_4h = adx_4h_ind.adx().iloc[-2], adx_4h_ind.adx_pos().iloc[-2], adx_4h_ind.adx_neg().iloc[-2]
        tendencia_4h = "ALCISTA" if (adx_4h > 15 and di_pos_4h > di_neg_4h) else "BAJISTA" if (adx_4h > 15 and di_neg_4h > di_pos_4h) else "NEUTRAL"
        time.sleep(1) 
        
        # Filtro 1H
        df_1h = obtener_datos(simbolo, "1h", 100)
        if df_1h is None or len(df_1h) < 20: return False
        adx_1h_ind = ADXIndicator(high=df_1h['maximo'], low=df_1h['minimo'], close=df_1h['cierre'], window=14)
        adx_1h, di_pos_1h, di_neg_1h = adx_1h_ind.adx().iloc[-2], adx_1h_ind.adx_pos().iloc[-2], adx_1h_ind.adx_neg().iloc[-2]
        tendencia_1h = "ALCISTA" if (adx_1h > 15 and di_pos_1h > di_neg_1h) else "BAJISTA" if (adx_1h > 15 and di_neg_1h > di_pos_1h) else "NEUTRAL"
        time.sleep(1)

        # Gatillo 5m
        df_5m = obtener_datos(simbolo, "5m", 100)
        if df_5m is None or len(df_5m) < 20: return False
        adx_5m_ind = ADXIndicator(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        adx_5m, di_pos_5m, di_neg_5m = adx_5m_ind.adx().iloc[-2], adx_5m_ind.adx_pos().iloc[-2], adx_5m_ind.adx_neg().iloc[-2]
        rsi_5m = RSIIndicator(close=df_5m['cierre'], window=14).rsi().iloc[-2]
        
        atr_ind = AverageTrueRange(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        atr_actual, precio_actual = atr_ind.average_true_range().iloc[-1], df_5m.iloc[-1]['cierre']

        print(f"📊 {simbolo} | 4H: {tendencia_4h} | 1H: {tendencia_1h} | 5M: {round(adx_5m,1)}")

        # 🟢 GATILLO LONG
        if tendencia_4h == "ALCISTA" and tendencia_1h == "ALCISTA" and adx_5m > 20 and di_pos_5m > di_neg_5m and rsi_5m > 50:
            sl = round(precio_actual - (atr_actual * 1.5), 4)
            tp1 = round(precio_actual + (atr_actual * 1.5), 4)
            tp2 = round(precio_actual + (atr_actual * 3.0), 4)
            tp3 = round(precio_actual + (atr_actual * 4.5), 4)
            
            cantidad_comprada = ejecutar_apertura(simbolo, "LONG", precio_actual)
            
            mensaje = f"🚨 ALERTA PAPER-TRADING 🚨\n\nMoneda: #{simbolo}\nDirección: LONG 🟢\n✅ Simulación Exitosa\n\n📌 Entrada: {precio_actual}\n🎯 TP1: {tp1} | TP2: {tp2} | TP3: {tp3}\n🛑 SL Inicial: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "LONG", precio_actual, tp1, tp2, tp3, sl, cantidad_comprada)
            return True

        # 🔴 GATILLO SHORT
        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 20 and di_neg_5m > di_pos_5m and rsi_5m < 50:
            sl = round(precio_actual + (atr_actual * 1.5), 4)
            tp1 = round(precio_actual - (atr_actual * 1.5), 4)
            tp2 = round(precio_actual - (atr_actual * 3.0), 4)
            tp3 = round(precio_actual - (atr_actual * 4.5), 4)
            
            cantidad_comprada = ejecutar_apertura(simbolo, "SHORT", precio_actual)
            
            mensaje = f"🚨 ALERTA PAPER-TRADING 🚨\n\nMoneda: #{simbolo}\nDirección: SHORT 🔴\n✅ Simulación Exitosa\n\n📌 Entrada: {precio_actual}\n🎯 TP1: {tp1} | TP2: {tp2} | TP3: {tp3}\n🛑 SL Inicial: {sl}"
            enviar_telegram(mensaje)
            vigilar_operacion(simbolo, "SHORT", precio_actual, tp1, tp2, tp3, sl, cantidad_comprada)
            return True

        return False
    except Exception as e:
        print(f"Error analizando {simbolo}: {e}")
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot en MODO SIMULADOR (Paper Trading)...")
while True:
    try:
        top_monedas = obtener_top_monedas()
        for moneda in top_monedas:
            hubo_operacion = analizar_mercado(moneda)
            if hubo_operacion:
                print("⏳ Pausa de 30 segundos tras cerrar simulación...")
                time.sleep(30)
                break
            time.sleep(5) 
    except Exception as e:
        print(f"Error en bucle principal: {e}")
        time.sleep(10)
