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

# --- CONFIGURACIÓN DE TRADING SIMULADO ---
APALANCAMIENTO = 20
INVERSION_USD = 20  # Dólares virtuales por cada compra (DCA usará otros $20)
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
    print(f"⚙️ SIMULADOR: Abriendo {direccion} en {simbolo} por ${tamano_posicion_usd} virtuales...")
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

# --- EL VIGILANTE CON TRAILING STOP Y COMPENSACIÓN (DCA) ---
def vigilar_operacion(simbolo, direccion, precio_entrada, atr_actual, cantidad_comprada):
    print(f"👀 Bot Simulador vigilando {simbolo} (Estrategia DCA + 3 Fases)...")
    
    precio_promedio = precio_entrada
    inversion_actual_usd = INVERSION_USD
    cantidad_total = cantidad_comprada
    dca_activado = False
    fase = 0

    # Calcular niveles iniciales matemáticos
    if direccion == "LONG":
        sl_actual = precio_promedio - (atr_actual * 1.5)
        precio_dca = precio_promedio - (atr_actual * 0.75) # Exactamente a mitad del SL
        tp1 = precio_promedio + (atr_actual * 1.5)
        tp2 = precio_promedio + (atr_actual * 3.0)
        tp3 = precio_promedio + (atr_actual * 4.5)
    else:
        sl_actual = precio_promedio + (atr_actual * 1.5)
        precio_dca = precio_promedio + (atr_actual * 0.75)
        tp1 = precio_promedio - (atr_actual * 1.5)
        tp2 = precio_promedio - (atr_actual * 3.0)
        tp3 = precio_promedio - (atr_actual * 4.5)

    # Mensaje inicial al abrir la operación
    mensaje_inicial = f"🚨 ALERTA PAPER-TRADING 🚨\n\nMoneda: #{simbolo}\nDirección: {direccion} 🟢\n✅ Simulación Exitosa\n\n📌 Entrada: {precio_promedio}\n🎯 TP1: {round(tp1,4)} | TP2: {round(tp2,4)} | TP3: {round(tp3,4)}\n🛑 SL Inicial: {round(sl_actual,4)}\n🛡 Nivel de DCA (Rescate): {round(precio_dca,4)}"
    enviar_telegram(mensaje_inicial)

    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            # --- LÓGICA PARA LONG 🟢 ---
            if direccion == "LONG":
                roi = ((precio_actual - precio_promedio) / precio_promedio) * APALANCAMIENTO * 100
                
                # 1. LÓGICA DE COMPENSACIÓN (DCA) - Si el precio baja a mitad de camino del SL
                if not dca_activado and precio_actual <= precio_dca and fase == 0:
                    dca_activado = True
                    nueva_cantidad = ejecutar_apertura(simbolo, "LONG (Compensación)", precio_actual)
                    cantidad_total += nueva_cantidad
                    inversion_actual_usd += INVERSION_USD
                    
                    # Calcular el nuevo promedio real
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    
                    # Recalcular TPs para salir rápido en ganancia
                    tp1 = precio_promedio + (atr_actual * 1.5)
                    tp2 = precio_promedio + (atr_actual * 3.0)
                    tp3 = precio_promedio + (atr_actual * 4.5)
                    # El SL inicial se mantiene igual para respetar la zona de riesgo
                    
                    enviar_telegram(f"⚠️ COMPENSACIÓN ACTIVADA en #{simbolo} ⚠️\n\n📉 El precio bajó, inyectamos $20 virtuales más en {precio_actual}.\n\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevos TPs: {round(tp1,4)} | {round(tp2,4)} | {round(tp3,4)}")
                    continue

                # 2. LÓGICA DE TAKE PROFIT Y TRAILING STOP
                if fase == 0 and precio_actual >= tp1:
                    sl_actual = precio_promedio
                    fase = 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Precio Promedio (Riesgo Cero).")
                
                elif fase == 1 and precio_actual >= tp2:
                    sl_actual = tp1
                    fase = 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({round(tp2,4)})\n💰 SL movido a TP1.")
                
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
                roi = ((precio_promedio - precio_actual) / precio_promedio) * APALANCAMIENTO * 100
                
                # 1. LÓGICA DE COMPENSACIÓN (DCA) - Si el precio sube en contra
                if not dca_activado and precio_actual >= precio_dca and fase == 0:
                    dca_activado = True
                    nueva_cantidad = ejecutar_apertura(simbolo, "SHORT (Compensación)", precio_actual)
                    cantidad_total += nueva_cantidad
                    inversion_actual_usd += INVERSION_USD
                    
                    # Calcular el nuevo promedio real
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    
                    # Recalcular TPs para salir rápido en ganancia
                    tp1 = precio_promedio - (atr_actual * 1.5)
                    tp2 = precio_promedio - (atr_actual * 3.0)
                    tp3 = precio_promedio - (atr_actual * 4.5)
                    
                    enviar_telegram(f"⚠️ COMPENSACIÓN ACTIVADA en #{simbolo} ⚠️\n\n📈 El precio subió, inyectamos $20 virtuales más en {precio_actual}.\n\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevos TPs: {round(tp1,4)} | {round(tp2,4)} | {round(tp3,4)}")
                    continue

                # 2. LÓGICA DE TAKE PROFIT Y TRAILING STOP
                if fase == 0 and precio_actual <= tp1:
                    sl_actual = precio_promedio
                    fase = 1
                    enviar_telegram(f"✅ SIMULADOR: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Precio Promedio (Riesgo Cero).")
                
                elif fase == 1 and precio_actual <= tp2:
                    sl_actual = tp1
                    fase = 2
                    enviar_telegram(f"🔥 SIMULADOR: {simbolo} alcanzó TP2 ({round(tp2,4)})\n💰 SL movido a TP1.")
                
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
    ejecutar_cierre(simbolo, direccion, cantidad_total)
    ganancia_usd = round(inversion_actual_usd * (roi / 100), 2)

    # 2. Reporte Final (Calculando la ganancia sobre el total invertido)
    mensaje = f"{estado}\n🤖 PAPER TRADING CERRADO: {simbolo}\n\n📈 PnL: {round(roi, 2)}%\n💵 Resultado Aprox: ${ganancia_usd} USD\nEntrada Promedio: {round(precio_promedio,4)} ➔ Precio Salida: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Auto-Trade Simulado finalizado.")

def analizar_mercado(simbolo):
    try:
        df_4h = obtener_datos(simbolo, "4h", 100)
        if df_4h is None or len(df_4h) < 20: return False 
        adx_4h_ind = ADXIndicator(high=df_4h['maximo'], low=df_4h['minimo'], close=df_4h['cierre'], window=14)
        adx_4h, di_pos_4h, di_neg_4h = adx_4h_ind.adx().iloc[-2], adx_4h_ind.adx_pos().iloc[-2], adx_4h_ind.adx_neg().iloc[-2]
        tendencia_4h = "ALCISTA" if (adx_4h > 15 and di_pos_4h > di_neg_4h) else "BAJISTA" if (adx_4h > 15 and di_neg_4h > di_pos_4h) else "NEUTRAL"
        time.sleep(1) 
        
        df_1h = obtener_datos(simbolo, "1h", 100)
        if df_1h is None or len(df_1h) < 20: return False
        adx_1h_ind = ADXIndicator(high=df_1h['maximo'], low=df_1h['minimo'], close=df_1h['cierre'], window=14)
        adx_1h, di_pos_1h, di_neg_1h = adx_1h_ind.adx().iloc[-2], adx_1h_ind.adx_pos().iloc[-2], adx_1h_ind.adx_neg().iloc[-2]
        tendencia_1h = "ALCISTA" if (adx_1h > 15 and di_pos_1h > di_neg_1h) else "BAJISTA" if (adx_1h > 15 and di_neg_1h > di_pos_1h) else "NEUTRAL"
        time.sleep(1)

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
            cantidad_comprada = ejecutar_apertura(simbolo, "LONG", precio_actual)
            vigilar_operacion(simbolo, "LONG", precio_actual, atr_actual, cantidad_comprada)
            return True

        # 🔴 GATILLO SHORT
        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 20 and di_neg_5m > di_pos_5m and rsi_5m < 50:
            cantidad_comprada = ejecutar_apertura(simbolo, "SHORT", precio_actual)
            vigilar_operacion(simbolo, "SHORT", precio_actual, atr_actual, cantidad_comprada)
            return True

        return False
    except Exception as e:
        print(f"Error analizando {simbolo}: {e}")
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot DCA PRO (Paper Trading)...")
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
