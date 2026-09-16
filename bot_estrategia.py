import requests
import pandas as pd
import time
import ccxt
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# --- CONEXIÓN PARA LA NUBE (RENDER) ---
from keep_alive import keep_alive
keep_alive()
# --------------------------------------

# 🔑 --- TUS LLAVES DE BINANCE (TESTNET) --- 🔑
# Reemplaza los textos entre comillas con las llaves que sacaste
API_KEY = "CUajXosd9bq1RGmWPIXlFjVU7mCHozGrgzPYM5hb6IaJA7eH5M7OmPzazQ12AGWO"
API_SECRET = "X9AqzMJWVzw47ZeQjajbylT3QU0UVBYMmWZYvNGh3AdcPNbpyXBlpUp4gKZ3JBpV"

# --- CONFIGURACIÓN TELEGRAM ---
TOKEN = "8624275801:AAHIyiTiofLOZJdZfhwww58kx88m940_l9c"
CHAT_ID = "-1003634379653"

# --- CONFIGURACIÓN DE TRADING ---
APALANCAMIENTO = 20
INVERSION_USD = 20  # Dólares (margen) que usará por cada operación
CANTIDAD_MONEDAS = 5

# --- CONECTAR BOT A BINANCE SIMULADOR ---
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})
exchange.set_sandbox_mode(True) # ¡SÚPER IMPORTANTE! Esto lo mantiene en dinero de mentira

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje})

def ejecutar_apertura(simbolo, direccion, precio_actual):
    try:
        simbolo_ccxt = simbolo.replace("USDT", "/USDT")
        
        # 1. Configurar apalancamiento
        exchange.set_leverage(APALANCAMIENTO, simbolo_ccxt)
        
        # 2. Calcular cuántas monedas comprar matemáticamente
        tamano_posicion_usd = INVERSION_USD * APALANCAMIENTO
        cantidad_monedas = tamano_posicion_usd / precio_actual
        
        # Redondear según las reglas exactas de Binance
        exchange.load_markets()
        cantidad_final = float(exchange.amount_to_precision(simbolo_ccxt, cantidad_monedas))
        
        # 3. Lanzar la orden al mercado
        side = 'buy' if direccion == "LONG" else 'sell'
        print(f"⚙️ Binance: Abriendo operación {direccion} en {simbolo_ccxt}...")
        exchange.create_market_order(simbolo_ccxt, side, cantidad_final)
        
        return cantidad_final
    except Exception as e:
        print(f"❌ Error al abrir orden en Binance: {e}")
        return 0

def ejecutar_cierre(simbolo, direccion, cantidad_final):
    try:
        simbolo_ccxt = simbolo.replace("USDT", "/USDT")
        # Para cerrar, hacemos una orden contraria
        side = 'sell' if direccion == "LONG" else 'buy'
        print(f"⚙️ Binance: Cerrando operación {direccion} en {simbolo_ccxt}...")
        exchange.create_market_order(simbolo_ccxt, side, cantidad_final)
    except Exception as e:
        print(f"❌ Error al cerrar orden en Binance: {e}")

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
        if isinstance(respuesta, dict) and 'msg' in respuesta:
            return None
        df = pd.DataFrame(respuesta, columns=['tiempo', 'apertura', 'maximo', 'minimo', 'cierre', 'volumen', 'cierre_tiempo', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
        df['cierre'] = df['cierre'].astype(float)
        df['maximo'] = df['maximo'].astype(float)
        df['minimo'] = df['minimo'].astype(float)
        return df
    except:
        return None

def vigilar_operacion(simbolo, direccion, precio_entrada, tp, sl, cantidad_comprada):
    print(f"👀 Bot Auto-Trading vigilando {simbolo}...")
    while True:
        try:
            precio_actual = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}").json()['price'])
            
            if direccion == "LONG":
                roi = ((precio_actual - precio_entrada) / precio_entrada) * APALANCAMIENTO * 100
                if precio_actual >= tp:
                    estado, emoji = "💥 TAKE PROFIT ALCANZADO 💥", "🎯🔥"
                    break
                elif precio_actual <= sl:
                    estado, emoji = "❌ STOP LOSS ALCANZADO ❌", "🛑"
                    break
            
            elif direccion == "SHORT":
                roi = ((precio_entrada - precio_actual) / precio_entrada) * APALANCAMIENTO * 100
                if precio_actual <= tp:
                    estado, emoji = "💥 TAKE PROFIT ALCANZADO 💥", "🎯🔥"
                    break
                elif precio_actual >= sl:
                    estado, emoji = "❌ STOP LOSS ALCANZADO ❌", "🛑"
                    break
            time.sleep(3)
        except:
            time.sleep(3)

    # 1. CIERRA LA OPERACIÓN EN BINANCE AUTOMÁTICAMENTE
    if cantidad_comprada > 0:
        ejecutar_cierre(simbolo, direccion, cantidad_comprada)

    # 2. MANDA EL REPORTE A TELEGRAM
    mensaje = f"{estado}\n🤖 AUTO-TRADING CERRADO: {simbolo}\n\n📈 PnL (Ganancia/Pérdida): {round(roi, 2)}%\nEntrada: {precio_entrada} ➔ Precio Final: {precio_actual}\n\n{emoji}"
    enviar_telegram(mensaje)
    print(f"✅ Auto-Trade finalizado.")

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
            tp = round(precio_actual + (atr_actual * 3.0), 4)
            
            # 1. Abre operación en Binance
            cantidad_comprada = ejecutar_apertura(simbolo, "LONG", precio_actual)
            
            # 2. Avisa a Telegram
            estado_api = "✅ COMPRA AUTOMÁTICA EN BINANCE" if cantidad_comprada > 0 else "⚠️ ERROR AL COMPRAR EN BINANCE"
            mensaje = f"🚨 ALERTA AUTO-TRADING 🚨\n\nMoneda: #{simbolo}\nDirección: LONG 🟢\n{estado_api}\n\n📌 Entrada Aprox: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            
            # 3. Se queda vigilando para cerrar
            vigilar_operacion(simbolo, "LONG", precio_actual, tp, sl, cantidad_comprada)
            return True

        # 🔴 GATILLO SHORT
        elif tendencia_4h == "BAJISTA" and tendencia_1h == "BAJISTA" and adx_5m > 20 and di_neg_5m > di_pos_5m and rsi_5m < 50:
            sl = round(precio_actual + (atr_actual * 1.5), 4)
            tp = round(precio_actual - (atr_actual * 3.0), 4)
            
            # 1. Abre operación en Binance
            cantidad_comprada = ejecutar_apertura(simbolo, "SHORT", precio_actual)
            
            # 2. Avisa a Telegram
            estado_api = "✅ VENTA AUTOMÁTICA EN BINANCE" if cantidad_comprada > 0 else "⚠️ ERROR AL VENDER EN BINANCE"
            mensaje = f"🚨 ALERTA AUTO-TRADING 🚨\n\nMoneda: #{simbolo}\nDirección: SHORT 🔴\n{estado_api}\n\n📌 Entrada Aprox: {precio_actual}\n🎯 TP: {tp}\n🛑 SL: {sl}"
            enviar_telegram(mensaje)
            
            # 3. Se queda vigilando para cerrar
            vigilar_operacion(simbolo, "SHORT", precio_actual, tp, sl, cantidad_comprada)
            return True

        return False
    except Exception as e:
        print(f"Error analizando {simbolo}: {e}")
        return False

# --- BUCLE PRINCIPAL ---
print("🚀 Iniciando Bot Cuántico de AUTO-TRADING (Binance Testnet)...")
while True:
    try:
        top_monedas = obtener_top_monedas()
        for moneda in top_monedas:
            hubo_operacion = analizar_mercado(moneda)
            if hubo_operacion:
                print("⏳ Pausa de 30 segundos tras cerrar el Auto-Trade...")
                time.sleep(30)
                break
            time.sleep(5) 
    except Exception as e:
        print(f"Error en bucle principal: {e}")
        time.sleep(10)
