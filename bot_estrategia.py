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

# --- CONEXIÓN BYBIT TESTNET (V5) ---
from pybit.unified_trading import HTTP

BYBIT_API_KEY = "OQnc2BQViHZDx9jDbt"
BYBIT_API_SECRET = "DeAql4WjU8Jpz5HgIPoJ2oqynQFwHlTwhH2X"

try:
    session = HTTP(
        testnet=True,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
    )
    print("✅ Conectado a Bybit Testnet exitosamente.")
except Exception as e:
    print(f"❌ Error conectando a Bybit: {e}")

# --- CONFIGURACIÓN DE TRADING ---
APALANCAMIENTO = 10  
INVERSION_USD = 20  
CANTIDAD_MONEDAS = 12  

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
        
    mensaje = f"📊 CORTE DE CAJA DIARIO 📊\n\n📈 Operaciones hoy: {operaciones_totales}\n✅ Ganadas: {operaciones_ganadas}\n❌ Perdidas: {operaciones_perdidas}\n🎯 Win Rate: {win_rate}%\n\n💵 Resultado Neto: ${round(ganancia_diaria_usd, 2)} USD\n\n🤖 Reiniciando contadores para mañana..."
    enviar_telegram(mensaje)
    operaciones_totales, operaciones_ganadas, operaciones_perdidas, ganancia_diaria_usd = 0, 0, 0, 0.0

# --- FUNCIONES DE EJECUCIÓN EN BYBIT ---
def obtener_precision_bybit(simbolo):
    try:
        info = session.get_instruments_info(category="linear", symbol=simbolo)
        step = info['result']['list'][0]['lotSizeFilter']['qtyStep']
        return len(step.split('.')[1]) if '.' in step else 0
    except:
        return 3

def ejecutar_apertura(simbolo, direccion, precio_actual):
    decimales = obtener_precision_bybit(simbolo)
    tamano_posicion_usd = INVERSION_USD * APALANCAMIENTO
    cantidad_monedas = round(tamano_posicion_usd / precio_actual, decimales)
    
    side = "Buy" if "LONG" in direccion else "Sell"
    
    try:
        try:
            session.set_leverage(category="linear", symbol=simbolo, buyLeverage=str(APALANCAMIENTO), sellLeverage=str(APALANCAMIENTO))
        except:
            pass # Si ya está en 10x, Bybit arroja un error inofensivo que ignoramos
            
        session.place_order(
            category="linear",
            symbol=simbolo,
            side=side,
            orderType="Market",
            qty=str(cantidad_monedas)
        )
        print(f"✅ BYBIT: Orden {side} ejecutada en {simbolo}. Cantidad: {cantidad_monedas}")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error BYBIT al abrir {simbolo}: {error_msg}")
        enviar_telegram(f"⚠️ ERROR BYBIT AL ABRIR {simbolo} ⚠️\n\nMotivo del Exchange:\n{error_msg}\n\n👉 Revisa que tengas fondos USDT en tu cuenta 'Derivados' de Testnet o chequea los permisos de la API Key.")
        
    return cantidad_monedas

def ejecutar_cierre(simbolo, direccion, cantidad_final):
    decimales = obtener_precision_bybit(simbolo)
    cantidad_str = str(round(cantidad_final, decimales))
    side = "Sell" if "LONG" in direccion else "Buy" 
    
    try:
        session.place_order(
            category="linear",
            symbol=simbolo,
            side=side,
            orderType="Market",
            qty=cantidad_str,
            reduceOnly=True 
        )
        print(f"✅ BYBIT: Operación CERRADA en {simbolo}.")
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error BYBIT al cerrar {simbolo}: {error_msg}")
        enviar_telegram(f"⚠️ ERROR BYBIT AL CERRAR {simbolo} ⚠️\n\nMotivo del Exchange:\n{error_msg}")

# --- MOTOR DE DATOS (BINANCE) ---
def obtener_top_monedas():
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        respuesta = requests.get(url).json()
        mercados = [m for m in respuesta if m['symbol'].endswith('USDT')]
        mercados_ordenados = sorted(mercados, key=lambda x: float(x['quoteVolume']), reverse=True)
        top_monedas = []
        lista_negra = ["USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "EURUSDT", "GUSDT", "TRBUSDT", "PEPEUSDT", "WIFUSDT", "FLOKIUSDT", "BONKUSDT", "SHIBUSDT", "BOMEUSDT", "NOTUSDT", "RLUSDUSDT", "USDEUSDT", "USDDUSDT", "USDPUSDT"]
        
        for m in mercados_ordenados:
            simbolo = m['symbol']
            if simbolo not in lista_negra and not simbolo.startswith('1000'):
                top_monedas.append(simbolo)
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
        df['volumen'] = df['volumen'].astype(float)
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

# --- VIGILANTE CON TRAILING Y DOBLE DCA ---
def vigilar_operacion(simbolo, direccion, precio_entrada, atr_actual, cantidad_comprada):
    global operaciones_totales, operaciones_ganadas, operaciones_perdidas, ganancia_diaria_usd
    
    precio_promedio = precio_entrada
    inversion_actual_usd = INVERSION_USD
    cantidad_total = cantidad_comprada
    dca1_activado = False
    dca2_activado = False
    fase = 0

    if direccion == "LONG":
        sl_actual = precio_entrada - (atr_actual * 3.0)
        precio_dca1 = precio_entrada - (atr_actual * 1.0)
        precio_dca2 = precio_entrada - (atr_actual * 2.0)
        tp1 = precio_promedio + (atr_actual * 1.5)
        tp2 = precio_promedio + (atr_actual * 3.0)
        tp3 = precio_promedio + (atr_actual * 6.0) 
    else:
        sl_actual = precio_entrada + (atr_actual * 3.0)
        precio_dca1 = precio_entrada + (atr_actual * 1.0)
        precio_dca2 = precio_entrada + (atr_actual * 2.0)
        tp1 = precio_promedio - (atr_actual * 1.5)
        tp2 = precio_promedio - (atr_actual * 3.0)
        tp3 = precio_promedio - (atr_actual * 6.0)

    mensaje_inicial = f"🚨 BYBIT TESTNET EN VIVO 🚨\n\nMoneda: #{simbolo}\nDirección: {direccion}\n✅ Volumen Ballena: Detectado\n👑 Filtro BTC: Aprobado\n\n📌 Entrada: {precio_promedio}\n🎯 TP1 (Activa Trailing): {round(tp1,4)}\n🛑 SL Inicial: {round(sl_actual,4)}\n🛡 DCA 1: {round(precio_dca1,4)} | DCA 2: {round(precio_dca2,4)}"
    enviar_telegram(mensaje_inicial)

    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            if direccion == "LONG":
                roi = ((precio_actual - precio_promedio) / precio_promedio) * APALANCAMIENTO * 100
                
                if not dca1_activado and precio_actual <= precio_dca1 and fase == 0:
                    dca1_activado = True
                    cantidad_agregada = ejecutar_apertura(simbolo, "LONG (Compensación 1)", precio_actual)
                    cantidad_total += cantidad_agregada
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio + (atr_actual * 1.5), precio_promedio + (atr_actual * 3.0), precio_promedio + (atr_actual * 6.0)
                    enviar_telegram(f"⚠️ COMPENSACIÓN 1 ACTIVADA en #{simbolo} ⚠️\n\n📉 Inyectamos $20 en Bybit a {precio_actual}.\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevo TP1: {round(tp1,4)}")
                    continue

                if dca1_activado and not dca2_activado and precio_actual <= precio_dca2 and fase == 0:
                    dca2_activado = True
                    cantidad_agregada = ejecutar_apertura(simbolo, "LONG (Compensación 2)", precio_actual)
                    cantidad_total += cantidad_agregada
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio + (atr_actual * 1.5), precio_promedio + (atr_actual * 3.0), precio_promedio + (atr_actual * 6.0)
                    enviar_telegram(f"🆘 COMPENSACIÓN 2 (ÚLTIMA) en #{simbolo} 🆘\n\n📉 Inyectamos otros $20 en Bybit a {precio_actual}.\n📊 Promedio Final: {round(precio_promedio,4)}\n🎯 Nuevo TP1: {round(tp1,4)}")
                    continue

                if fase == 0 and precio_actual >= tp1:
                    sl_actual, fase = precio_promedio + (atr_actual * 0.3), 1
                    enviar_telegram(f"✅ BYBIT: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Ganancia Asegurada.\n🌊 Trailing Fluido Activado.")
                elif fase == 1 and precio_actual >= tp2:
                    fase = 2
                    enviar_telegram(f"🔥 BYBIT: {simbolo} rompió TP2 ({round(tp2,4)})\n🚀 Trailing Dinámico persiguiendo el precio.")
                elif precio_actual >= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                
                if fase >= 1:
                    nuevo_sl = precio_actual - (atr_actual * 1.5)
                    if nuevo_sl > sl_actual:
                        sl_actual = nuevo_sl 

                if precio_actual <= sl_actual:
                    estado, emoji = ("❌ STOP LOSS TOCADO ❌", "🛑") if fase == 0 else ("🛡 TRAILING STOP TOCADO 🛡", "✅")
                    break

            elif direccion == "SHORT":
                roi = ((precio_promedio - precio_actual) / precio_promedio) * APALANCAMIENTO * 100
                
                if not dca1_activado and precio_actual >= precio_dca1 and fase == 0:
                    dca1_activado = True
                    cantidad_agregada = ejecutar_apertura(simbolo, "SHORT (Compensación 1)", precio_actual)
                    cantidad_total += cantidad_agregada
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio - (atr_actual * 1.5), precio_promedio - (atr_actual * 3.0), precio_promedio - (atr_actual * 6.0)
                    enviar_telegram(f"⚠️ COMPENSACIÓN 1 ACTIVADA en #{simbolo} ⚠️\n\n📈 Inyectamos $20 en Bybit a {precio_actual}.\n📊 Nuevo Promedio: {round(precio_promedio,4)}\n🎯 Nuevo TP1: {round(tp1,4)}")
                    continue

                if dca1_activado and not dca2_activado and precio_actual >= precio_dca2 and fase == 0:
                    dca2_activado = True
                    cantidad_agregada = ejecutar_apertura(simbolo, "SHORT (Compensación 2)", precio_actual)
                    cantidad_total += cantidad_agregada
                    inversion_actual_usd += INVERSION_USD
                    precio_promedio = (inversion_actual_usd * APALANCAMIENTO) / cantidad_total
                    tp1, tp2, tp3 = precio_promedio - (atr_actual * 1.5), precio_promedio - (atr_actual * 3.0), precio_promedio - (atr_actual * 6.0)
                    enviar_telegram(f"🆘 COMPENSACIÓN 2 (ÚLTIMA) en #{simbolo} 🆘\n\n📈 Inyectamos otros $20 en Bybit a {precio_actual}.\n📊 Promedio Final: {round(precio_promedio,4)}\n🎯 Nuevo TP1: {round(tp1,4)}")
                    continue

                if fase == 0 and precio_actual <= tp1:
                    sl_actual, fase = precio_promedio - (atr_actual * 0.3), 1
                    enviar_telegram(f"✅ BYBIT: {simbolo} alcanzó TP1 ({round(tp1,4)})\n🛡 SL movido a Ganancia Asegurada.\n🌊 Trailing Fluido Activado.")
                elif fase == 1 and precio_actual <= tp2:
                    fase = 2
                    enviar_telegram(f"🔥 BYBIT: {simbolo} rompió TP2 ({round(tp2,4)})\n🚀 Trailing Dinámico persiguiendo el precio.")
                elif precio_actual <= tp3:
                    estado, emoji = "💥 TAKE PROFIT FINAL ALCANZADO 💥", "🎯🏆"
                    break
                
                if fase >= 1:
                    nuevo_sl = precio_actual + (atr_actual * 1.5)
                    if nuevo_sl < sl_actual:
                        sl_actual = nuevo_sl

                if precio_actual >= sl_actual:
                    estado, emoji = ("❌ STOP LOSS TOCADO ❌", "🛑") if fase == 0 else ("🛡 TRAILING STOP TOCADO 🛡", "✅")
                    break

            time.sleep(3)
        except Exception as e:
            time.sleep(3)

    # --- CIERRE FÍSICO EN BYBIT ---
    ejecutar_cierre(simbolo, direccion, cantidad_total)
    
    ganancia_usd = round(inversion_actual_usd * (roi / 100), 2)
    operaciones_totales += 1
    ganancia_diaria_usd += ganancia_usd
    if ganancia_usd > 0:
        operaciones_ganadas += 1
    else:
        operaciones_perdidas += 1

    mensaje = f"{estado}\n🤖 BYBIT TESTNET CERRADO: {simbolo}\n\n📈 PnL: {round(roi, 2)}%\n💵 Resultado Aprox: ${ganancia_usd} USD\nEntrada: {round(precio_promedio,4)} ➔ Salida: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)

def analizar_mercado(simbolo, estado_btc):
    try:
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

        volumen_promedio = df_5m['volumen'].rolling(window=20).mean().iloc[-2]
        volumen_actual = df_5m['volumen'].iloc[-2]
        filtro_volumen = volumen_actual > volumen_promedio 

        if tendencia_4h == "ALCISTA" and tendencia_1h == "ALCISTA" and adx_5m > 25 and di_pos_5m > di_neg_5m and (50 < rsi_5m < 70) and filtro_volumen:
            if estado_btc == "BAJISTA":
                return False
            cantidad_comprada = ejecutar_apertura(simbolo, "LONG", precio_actual)
            vigilar_operacion(simbolo, "LONG", precio_actual, atr_actual, cantidad_comprada)
            return True

        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 25 and di_neg_5m > di_pos_5m and (30 < rsi_5m < 50) and filtro_volumen:
            if estado_btc == "ALCISTA":
                return False
            cantidad_comprada = ejecutar_apertura(simbolo, "SHORT", precio_actual)
            vigilar_operacion(simbolo, "SHORT", precio_actual, atr_actual, cantidad_comprada)
            return True

        return False
    except Exception as e:
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot DCA PRO (CONECTADO A BYBIT TESTNET)...")
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
                print("⏳ Pausa de 30 segundos tras cerrar posición en Bybit...")
                time.sleep(30)
                break
            time.sleep(1) 
            
    except Exception as e:
        time.sleep(10)
