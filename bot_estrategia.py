import requests
import pandas as pd
import time
from datetime import datetime
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

# --- CONFIGURACIÓN DE TRADING SIMULADO ---
APALANCAMIENTO = 20
INVERSION_USD = 20  
CANTIDAD_MONEDAS = 20  # Top 20 de Binance

# --- ESTADÍSTICAS DIARIAS ---
operaciones_totales = 0
operaciones_ganadas = 0
operaciones_perdidas = 0
ganancia_diaria_usd = 0.0
ultimo_dia_reporte = datetime.now().day

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje})
    except:
        pass

def enviar_reporte_diario():
    global operaciones_totales, operaciones_ganadas, operaciones_perdidas, ganancia_diaria_usd
    
    if operaciones_totales > 0:
        win_rate = round((operaciones_ganadas / operaciones_totales) * 100, 2)
    else:
        win_rate = 0.0
        
    mensaje = f"📊 CORTE DE CAJA DIARIO 📊\n\n" \
              f"📈 Operaciones hoy: {operaciones_totales}\n" \
              f"✅ Ganadas: {operaciones_ganadas}\n" \
              f"❌ Perdidas: {operaciones_perdidas}\n" \
              f"🎯 Win Rate: {win_rate}%\n\n" \
              f"💵 Resultado Neto: ${round(ganancia_diaria_usd, 2)} USD\n\n" \
              f"🤖 Reiniciando contadores para mañana..."
    
    enviar_telegram(mensaje)
    
    operaciones_totales = 0
    operaciones_ganadas = 0
    operaciones_perdidas = 0
    ganancia_diaria_usd = 0.0

def ejecutar_apertura(simbolo, direccion, precio_actual):
    tamano_posicion_usd = INVERSION_USD * APALANCAMIENTO
    cantidad_monedas = tamano_posicion_usd / precio_actual
    print(f"⚙️ SIMULADOR: Abriendo {direccion} en {simbolo} por ${tamano_posicion_usd} virtuales...")
    return cantidad_monedas

def ejecutar_cierre(simbolo, direccion, cantidad_final):
    print(f"⚙️ SIMULADOR: Cerrando operación {direccion} en {simbolo}...")

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

def obtener_estado_bitcoin():
    try:
        df_btc = obtener_datos("BTCUSDT", "1h", 100)
        if df_btc is None or len(df_btc) < 20: return "NEUTRAL"
        adx_ind = ADXIndicator(high=df_btc['maximo'], low=df_btc['minimo'], close=df_btc['cierre'], window=14)
        adx, di_pos, di_neg = adx_ind.adx().iloc[-2], adx_ind.adx_pos().iloc[-2], adx_ind.adx_neg().iloc[-2]
        
        if adx > 20 and di_pos > di_neg: return "ALCISTA"
        if adx > 20 and di_neg > di_pos: return "BAJISTA"
        return "NEUTRAL"
    except:
        return "NEUTRAL"

def vigilar_operacion(simbolo, direccion, precio_entrada, atr_actual, cantidad_comprada):
    global operaciones_totales, operaciones_ganadas, operaciones_perdidas, ganancia_diaria_usd
    
    precio_promedio = precio_entrada
    inversion_actual_usd = INVERSION_USD
    cantidad_total = cantidad_comprada
    dca_activado = False
    fase = 0

    # 🔥 MODO DEFENSIVO: Stop Loss alejado a 2.0 ATR y DCA a 1.0 ATR
    if direccion == "LONG":
        sl_actual = precio_promedio - (atr_actual * 2.0)
        precio_dca = precio_promedio - (atr_actual * 1.0)
        tp1 = precio_promedio + (atr_actual * 1.5)
        tp2 = precio_promedio + (atr_actual * 3.0)
        tp3 = precio_promedio + (atr_actual * 4.5)
    else:
        sl_actual = precio_promedio + (atr_actual * 2.0)
        precio_dca = precio_promedio + (atr_actual * 1.0)
        tp1 = precio_promedio - (atr_actual * 1.5)
        tp2 = precio_promedio - (atr_actual * 3.0)
        tp3 = precio_promedio - (atr_actual * 4.5)

    mensaje_inicial = f"🚨 ALERTA PAPER-TRADING (DEFENSIVO) 🚨\n\nMoneda: #{simbolo}\nDirección: {direccion}\n✅ Simulación Exitosa\n👑 Filtro BTC: Aprobado\n\n📌 Entrada: {precio_promedio}\n🎯 TP1: {round(tp1,4)} | TP2: {round(tp2,4)} | TP3: {round(tp3,4)}\n🛑 SL Inicial: {round(sl_actual,4)}\n🛡 Nivel de DCA: {round(precio_dca,4)}"
    enviar_telegram(mensaje_inicial)

    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            if direccion == "LONG":
                roi = ((precio_actual - precio_promedio) / precio_promedio) * APALANCAMIENTO * 100
                
                if not dca_activado and precio_actual <= precio_dca and fase == 0:
                    dca_activado = True
                    cantidad_total += ejecutar_apertura(simbolo, "LONG (Compensación)", precio_actual)
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio + (atr_actual * 1.5), precio_promedio + (atr_actual * 3.0), precio_promedio + (atr_actual * 4.5)
                    enviar_telegram(f"⚠️ COMPENSACIÓN ACTIVADA en #{simbolo} ⚠️\n\n📉 Inyectamos $20 virtuales en {precio_actual}.\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevos TPs: {round(tp1,4)} | {round(tp2,4)} | {round(tp3,4)}")
                    continue

                if fase == 0 and precio_actual >= tp1:
                    sl_actual, fase = precio_promedio, 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Riesgo Cero.")
                elif fase == 1 and precio_actual >= tp2:
                    sl_actual, fase = tp1, 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({round(tp2,4)})\n💰 SL movido a TP1.")
                elif precio_actual >= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                elif precio_actual <= sl_actual:
                    estado, emoji = ("❌ STOP LOSS TOCADO ❌", "🛑") if fase == 0 else ("🛡 TRAILING STOP TOCADO 🛡", "✅")
                    break

            elif direccion == "SHORT":
                roi = ((precio_promedio - precio_actual) / precio_promedio) * APALANCAMIENTO * 100
                
                if not dca_activado and precio_actual >= precio_dca and fase == 0:
                    dca_activado = True
                    cantidad_total += ejecutar_apertura(simbolo, "SHORT (Compensación)", precio_actual)
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio - (atr_actual * 1.5), precio_promedio - (atr_actual * 3.0), precio_promedio - (atr_actual * 4.5)
                    enviar_telegram(f"⚠️ COMPENSACIÓN ACTIVADA en #{simbolo} ⚠️\n\n📈 Inyectamos $20 virtuales en {precio_actual}.\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevos TPs: {round(tp1,4)} | {round(tp2,4)} | {round(tp3,4)}")
                    continue

                if fase == 0 and precio_actual <= tp1:
                    sl_actual, fase = precio_promedio, 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Riesgo Cero.")
                elif fase == 1 and precio_actual <= tp2:
                    sl_actual, fase = tp1, 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({round(tp2,4)})\n💰 SL movido a TP1.")
                elif precio_actual <= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                elif precio_actual >= sl_actual:
                    estado, emoji = ("❌ STOP LOSS TOCADO ❌", "🛑") if fase == 0 else ("🛡 TRAILING STOP TOCADO 🛡", "✅")
                    break

            time.sleep(3)
        except Exception as e:
            time.sleep(3)

    ejecutar_cierre(simbolo, direccion, cantidad_total)
    ganancia_usd = round(inversion_actual_usd * (roi / 100), 2)
    
    operaciones_totales += 1
    ganancia_diaria_usd += ganancia_usd
    if ganancia_usd > 0:
        operaciones_ganadas += 1
    else:
        operaciones_perdidas += 1

    mensaje = f"{estado}\n🤖 PAPER TRADING CERRADO: {simbolo}\n\n📈 PnL: {round(roi, 2)}%\n💵 Resultado Aprox: ${ganancia_usd} USD\nEntrada: {round(precio_promedio,4)} ➔ Salida: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)

def analizar_mercado(simbolo, estado_btc):
    try:
        # 🔥 MODO DEFENSIVO: Exigir ADX > 20 (tendencias más claras)
        df_4h = obtener_datos(simbolo, "4h", 100)
        if df_4h is None or len(df_4h) < 20: return False 
        adx_4h_ind = ADXIndicator(high=df_4h['maximo'], low=df_4h['minimo'], close=df_4h['cierre'], window=14)
        adx_4h, di_pos_4h, di_neg_4h = adx_4h_ind.adx().iloc[-2], adx_4h_ind.adx_pos().iloc[-2], adx_4h_ind.adx_neg().iloc[-2]
        tendencia_4h = "ALCISTA" if (adx_4h > 20 and di_pos_4h > di_neg_4h) else "BAJISTA" if (adx_4h > 20 and di_neg_4h > di_pos_4h) else "NEUTRAL"
        
        df_1h = obtener_datos(simbolo, "1h", 100)
        if df_1h is None or len(df_1h) < 20: return False
        adx_1h_ind = ADXIndicator(high=df_1h['maximo'], low=df_1h['minimo'], close=df_1h['cierre'], window=14)
        adx_1h, di_pos_1h, di_neg_1h = adx_1h_ind.adx().iloc[-2], adx_1h_ind.adx_pos().iloc[-2], adx_1h_ind.adx_neg().iloc[-2]
        tendencia_1h = "ALCISTA" if (adx_1h > 20 and di_pos_1h > di_neg_1h) else "BAJISTA" if (adx_1h > 20 and di_neg_1h > di_pos_1h) else "NEUTRAL"

        df_5m = obtener_datos(simbolo, "5m", 100)
        if df_5m is None or len(df_5m) < 20: return False
        adx_5m_ind = ADXIndicator(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        adx_5m, di_pos_5m, di_neg_5m = adx_5m_ind.adx().iloc[-2], adx_5m_ind.adx_pos().iloc[-2], adx_5m_ind.adx_neg().iloc[-2]
        rsi_5m = RSIIndicator(close=df_5m['cierre'], window=14).rsi().iloc[-2]
        
        atr_ind = AverageTrueRange(high=df_5m['maximo'], low=df_5m['minimo'], close=df_5m['cierre'], window=14)
        atr_actual, precio_actual = atr_ind.average_true_range().iloc[-1], df_5m.iloc[-1]['cierre']

        # 🟢 GATILLO LONG (Modo Defensivo: RSI < 70 para no comprar el techo)
        if tendencia_4h == "ALCISTA" and tendencia_1h == "ALCISTA" and adx_5m > 25 and di_pos_5m > di_neg_5m and (50 < rsi_5m < 70):
            if estado_btc == "BAJISTA":
                return False
            cantidad_comprada = ejecutar_apertura(simbolo, "LONG", precio_actual)
            vigilar_operacion(simbolo, "LONG", precio_actual, atr_actual, cantidad_comprada)
            return True

        # 🔴 GATILLO SHORT (Modo Defensivo: RSI > 30 para no vender el piso)
        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 25 and di_neg_5m > di_pos_5m and (30 < rsi_5m < 50):
            if estado_btc == "ALCISTA":
                return False
            cantidad_comprada = ejecutar_apertura(simbolo, "SHORT", precio_actual)
            vigilar_operacion(simbolo, "SHORT", precio_actual, atr_actual, cantidad_comprada)
            return True

        return False
    except Exception as e:
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot DCA PRO (Modo Defensivo Activado)...")
while True:
    try:
        ahora = datetime.now()
        
        if ahora.hour == 0 and ahora.day != ultimo_dia_reporte:
            enviar_reporte_diario()
            ultimo_dia_reporte = ahora.day

        top_monedas = obtener_top_monedas()
        estado_btc = obtener_estado_bitcoin()
        print(f"\n👑 ESTADO DEL REY BITCOIN (1H): {estado_btc}")
        print("--------------------------------------------------")
        
        for moneda in top_monedas:
            hubo_operacion = analizar_mercado(moneda, estado_btc)
            if hubo_operacion:
                print("⏳ Pausa de 30 segundos tras cerrar simulación...")
                time.sleep(30)
                break
            time.sleep(1) 
            
    except Exception as e:
        time.sleep(10)
