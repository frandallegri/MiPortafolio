"""
Motor de scoring cuantitativo v2.
Combina senales de indicadores tecnicos en un score 0-100
que representa la probabilidad estimada de suba al dia siguiente.

Mejoras v2:
  1. Pesos dinamicos (calibracion por backtesting)
  2. Analisis multi-timeframe (semanal + mensual)
  3. Deteccion de regimen de mercado (bull/bear/sideways)
  4. Confirmacion precio-volumen
  5. Fuerza relativa vs Merval
  6. ML ensemble (cuando hay datos suficientes)
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Individual indicator signal."""
    name: str
    value: float       # Raw indicator value
    signal: int        # +1 (alcista), 0 (neutral), -1 (bajista)
    weight: float      # Weight in final score
    description: str   # Human-readable reason


# ──────────────────────────────────────────────
# ANALYZERS: INDICADORES DIARIOS (ORIGINALES)
# ──────────────────────────────────────────────

def analyze_rsi(indicators: dict, thresholds: dict = None) -> Signal:
    """RSI con umbrales adaptativos."""
    rsi = indicators.get("rsi_14")
    if rsi is None:
        return Signal("RSI(14)", 0, 0, 0, "Sin datos")

    # Umbrales adaptativos o defaults
    t = thresholds or {}
    os_strong = t.get("rsi_oversold", 30)
    os_weak = os_strong + 10
    ob_strong = t.get("rsi_overbought", 70)
    ob_weak = ob_strong - 10

    if rsi < os_strong:
        return Signal("RSI(14)", rsi, 1, 1.5, f"Sobrevendido ({rsi:.1f})")
    elif rsi < os_weak:
        return Signal("RSI(14)", rsi, 1, 0.8, f"Zona baja ({rsi:.1f})")
    elif rsi > ob_strong:
        return Signal("RSI(14)", rsi, -1, 1.5, f"Sobrecomprado ({rsi:.1f})")
    elif rsi > ob_weak:
        return Signal("RSI(14)", rsi, -1, 0.5, f"Zona alta ({rsi:.1f})")
    else:
        return Signal("RSI(14)", rsi, 0, 0.3, f"Neutral ({rsi:.1f})")


def analyze_macd(indicators: dict) -> Signal:
    """MACD: crossover signals."""
    macd = indicators.get("macd")
    signal = indicators.get("macd_signal")
    histogram = indicators.get("macd_histogram")

    if macd is None or signal is None:
        return Signal("MACD", 0, 0, 0, "Sin datos")

    if histogram is not None and histogram > 0 and macd > signal:
        strength = 1.2 if histogram > abs(macd) * 0.1 else 0.8
        return Signal("MACD", macd, 1, strength, f"Histograma positivo ({histogram:.4f})")
    elif histogram is not None and histogram < 0:
        strength = 1.2 if abs(histogram) > abs(macd) * 0.1 else 0.8
        return Signal("MACD", macd, -1, strength, f"Histograma negativo ({histogram:.4f})")
    else:
        return Signal("MACD", macd, 0, 0.3, "Neutral")


def analyze_bollinger(indicators: dict) -> Signal:
    """Bollinger Bands: %B position."""
    pband = indicators.get("bb_pband")

    if pband is None:
        return Signal("Bollinger", 0, 0, 0, "Sin datos")

    if pband < 0.05:
        return Signal("Bollinger", pband, 1, 1.3, f"Tocando banda inferior (%B={pband:.2f})")
    elif pband < 0.2:
        return Signal("Bollinger", pband, 1, 0.8, f"Cerca de banda inferior (%B={pband:.2f})")
    elif pband > 0.95:
        return Signal("Bollinger", pband, -1, 1.3, f"Tocando banda superior (%B={pband:.2f})")
    elif pband > 0.8:
        return Signal("Bollinger", pband, -1, 0.6, f"Cerca de banda superior (%B={pband:.2f})")
    else:
        return Signal("Bollinger", pband, 0, 0.3, f"Dentro de bandas (%B={pband:.2f})")


def analyze_moving_averages(indicators: dict) -> Signal:
    """SMA/EMA alignment and price position."""
    close = indicators.get("close", 0)
    sma_20 = indicators.get("sma_20")
    sma_50 = indicators.get("sma_50")
    sma_200 = indicators.get("sma_200")
    ema_9 = indicators.get("ema_9")
    ema_21 = indicators.get("ema_21")

    if not all([sma_20, sma_50, ema_9]):
        return Signal("Medias Moviles", 0, 0, 0, "Sin datos")

    bullish_count = 0
    total = 0

    for ma_name, ma_val in [("SMA20", sma_20), ("SMA50", sma_50), ("SMA200", sma_200), ("EMA9", ema_9), ("EMA21", ema_21)]:
        if ma_val and ma_val > 0:
            total += 1
            if close > ma_val:
                bullish_count += 1

    # Golden/Death cross
    if sma_50 and sma_200 and sma_200 > 0:
        total += 1
        if sma_50 > sma_200:
            bullish_count += 1

    if total == 0:
        return Signal("Medias Moviles", 0, 0, 0.3, "Sin datos suficientes")

    ratio = bullish_count / total

    if ratio >= 0.8:
        return Signal("Medias Moviles", ratio, 1, 1.2, f"Fuerte tendencia alcista ({bullish_count}/{total})")
    elif ratio >= 0.6:
        return Signal("Medias Moviles", ratio, 1, 0.7, f"Tendencia alcista moderada ({bullish_count}/{total})")
    elif ratio <= 0.2:
        return Signal("Medias Moviles", ratio, -1, 1.2, f"Fuerte tendencia bajista ({bullish_count}/{total})")
    elif ratio <= 0.4:
        return Signal("Medias Moviles", ratio, -1, 0.7, f"Tendencia bajista moderada ({bullish_count}/{total})")
    else:
        return Signal("Medias Moviles", ratio, 0, 0.3, f"Sin tendencia clara ({bullish_count}/{total})")


def analyze_stochastic(indicators: dict, thresholds: dict = None) -> Signal:
    """Stochastic oscillator con umbrales adaptativos."""
    k = indicators.get("stoch_k")
    d = indicators.get("stoch_d")

    if k is None or d is None:
        return Signal("Estocastico", 0, 0, 0, "Sin datos")

    t = thresholds or {}
    os_val = t.get("stoch_oversold", 20)
    ob_val = t.get("stoch_overbought", 80)

    if k < os_val and d < os_val:
        sig = 1 if k > d else 0
        return Signal("Estocastico", k, max(sig, 1), 1.0, f"Sobrevendido (%K={k:.1f}, %D={d:.1f})")
    elif k > ob_val and d > ob_val:
        sig = -1 if k < d else 0
        return Signal("Estocastico", k, min(sig, -1), 1.0, f"Sobrecomprado (%K={k:.1f}, %D={d:.1f})")
    elif k > d:
        return Signal("Estocastico", k, 1, 0.5, f"Cruce alcista (%K={k:.1f} > %D={d:.1f})")
    else:
        return Signal("Estocastico", k, -1, 0.5, f"Cruce bajista (%K={k:.1f} < %D={d:.1f})")


def analyze_adx(indicators: dict) -> Signal:
    """ADX: trend strength. +DI vs -DI for direction."""
    adx = indicators.get("adx")
    pos = indicators.get("adx_pos")
    neg = indicators.get("adx_neg")

    if adx is None or pos is None or neg is None:
        return Signal("ADX", 0, 0, 0, "Sin datos")

    if adx < 20:
        return Signal("ADX", adx, 0, 0.3, f"Sin tendencia (ADX={adx:.1f})")

    if pos > neg:
        weight = 1.2 if adx > 30 else 0.8
        return Signal("ADX", adx, 1, weight, f"Tendencia alcista fuerte (ADX={adx:.1f}, +DI={pos:.1f})")
    else:
        weight = 1.2 if adx > 30 else 0.8
        return Signal("ADX", adx, -1, weight, f"Tendencia bajista fuerte (ADX={adx:.1f}, -DI={neg:.1f})")


def analyze_volume(indicators: dict) -> Signal:
    """Relative volume analysis."""
    rv = indicators.get("relative_volume")
    change = indicators.get("change_pct", 0)

    if rv is None:
        return Signal("Volumen", 0, 0, 0, "Sin datos")

    if rv > 2.0 and change > 0:
        return Signal("Volumen", rv, 1, 1.0, f"Alto volumen alcista (RV={rv:.1f}x)")
    elif rv > 2.0 and change < 0:
        return Signal("Volumen", rv, -1, 1.0, f"Alto volumen bajista (RV={rv:.1f}x)")
    elif rv > 1.5 and change > 0:
        return Signal("Volumen", rv, 1, 0.5, f"Volumen moderado alcista (RV={rv:.1f}x)")
    elif rv < 0.5:
        return Signal("Volumen", rv, 0, 0.2, f"Volumen muy bajo (RV={rv:.1f}x)")
    else:
        return Signal("Volumen", rv, 0, 0.3, f"Volumen normal (RV={rv:.1f}x)")


def analyze_williams_r(indicators: dict) -> Signal:
    """Williams %R: -80 to -100 oversold, -20 to 0 overbought."""
    wr = indicators.get("williams_r")
    if wr is None:
        return Signal("Williams %R", 0, 0, 0, "Sin datos")

    if wr < -80:
        return Signal("Williams %R", wr, 1, 0.8, f"Sobrevendido ({wr:.1f})")
    elif wr > -20:
        return Signal("Williams %R", wr, -1, 0.8, f"Sobrecomprado ({wr:.1f})")
    else:
        return Signal("Williams %R", wr, 0, 0.3, f"Neutral ({wr:.1f})")


def analyze_cci(indicators: dict) -> Signal:
    """CCI: >100 overbought, <-100 oversold."""
    cci = indicators.get("cci_20")
    if cci is None:
        return Signal("CCI(20)", 0, 0, 0, "Sin datos")

    if cci < -100:
        return Signal("CCI(20)", cci, 1, 0.8, f"Sobrevendido ({cci:.1f})")
    elif cci < -50:
        return Signal("CCI(20)", cci, 1, 0.4, f"Zona baja ({cci:.1f})")
    elif cci > 100:
        return Signal("CCI(20)", cci, -1, 0.8, f"Sobrecomprado ({cci:.1f})")
    elif cci > 50:
        return Signal("CCI(20)", cci, -1, 0.4, f"Zona alta ({cci:.1f})")
    else:
        return Signal("CCI(20)", cci, 0, 0.3, f"Neutral ({cci:.1f})")


def analyze_mfi(indicators: dict) -> Signal:
    """MFI: like RSI but volume-weighted."""
    mfi = indicators.get("mfi_14")
    if mfi is None:
        return Signal("MFI(14)", 0, 0, 0, "Sin datos")

    if mfi < 20:
        return Signal("MFI(14)", mfi, 1, 1.0, f"Sobrevendido ({mfi:.1f})")
    elif mfi > 80:
        return Signal("MFI(14)", mfi, -1, 1.0, f"Sobrecomprado ({mfi:.1f})")
    else:
        return Signal("MFI(14)", mfi, 0, 0.3, f"Neutral ({mfi:.1f})")


# ──────────────────────────────────────────────
# NUEVOS ANALYZERS v2
# ──────────────────────────────────────────────

def analyze_relative_strength(indicators: dict) -> Signal:
    """Fuerza relativa vs Merval (20 dias)."""
    rs = indicators.get("rs_vs_merval")
    if rs is None:
        return Signal("Fuerza Relativa", 0, 0, 0, "Sin datos")

    if rs > 5:
        return Signal("Fuerza Relativa", rs, 1, 1.0, f"Supera al mercado ({rs:+.1f}%)")
    elif rs > 2:
        return Signal("Fuerza Relativa", rs, 1, 0.5, f"Ligeramente mejor ({rs:+.1f}%)")
    elif rs < -5:
        return Signal("Fuerza Relativa", rs, -1, 1.0, f"Debajo del mercado ({rs:+.1f}%)")
    elif rs < -2:
        return Signal("Fuerza Relativa", rs, -1, 0.5, f"Ligeramente peor ({rs:+.1f}%)")
    else:
        return Signal("Fuerza Relativa", rs, 0, 0.3, f"En linea con mercado ({rs:+.1f}%)")


def analyze_weekly_trend(indicators: dict) -> Signal:
    """Tendencia semanal (RSI + MACD + SMA semanal)."""
    w_rsi = indicators.get("weekly_rsi")
    w_macd = indicators.get("weekly_macd_hist")
    w_above_sma = indicators.get("weekly_above_sma20")

    if w_rsi is None:
        return Signal("Tend. Semanal", 0, 0, 0, "Sin datos")

    bull = 0
    total = 0

    # RSI semanal
    total += 1
    if w_rsi < 40:
        bull += 1  # Oversold weekly = bullish
    elif w_rsi > 60:
        bull += 0  # Overbought = bearish
    else:
        bull += 0.5

    # MACD semanal
    if w_macd is not None:
        total += 1
        bull += 1 if w_macd > 0 else 0

    # Precio vs SMA20 semanal
    if w_above_sma is not None:
        total += 1
        bull += 1 if w_above_sma else 0

    if total == 0:
        return Signal("Tend. Semanal", 0, 0, 0, "Sin datos")

    ratio = bull / total
    if ratio >= 0.7:
        return Signal("Tend. Semanal", ratio, 1, 1.0, f"Semanal alcista (RSI={w_rsi:.0f})")
    elif ratio <= 0.3:
        return Signal("Tend. Semanal", ratio, -1, 1.0, f"Semanal bajista (RSI={w_rsi:.0f})")
    else:
        return Signal("Tend. Semanal", ratio, 0, 0.3, f"Semanal neutral (RSI={w_rsi:.0f})")


def analyze_monthly_trend(indicators: dict) -> Signal:
    """Tendencia mensual (RSI + posicion vs SMA)."""
    m_rsi = indicators.get("monthly_rsi")
    m_above_sma = indicators.get("monthly_above_sma10")

    if m_rsi is None and m_above_sma is None:
        return Signal("Tend. Mensual", 0, 0, 0, "Sin datos")

    bull = 0
    total = 0

    if m_rsi is not None:
        total += 1
        if m_rsi < 40:
            bull += 1
        elif m_rsi > 60:
            bull += 0
        else:
            bull += 0.5

    if m_above_sma is not None:
        total += 1
        bull += 1 if m_above_sma else 0

    if total == 0:
        return Signal("Tend. Mensual", 0, 0, 0, "Sin datos")

    ratio = bull / total
    val = m_rsi if m_rsi is not None else 0

    if ratio >= 0.7:
        return Signal("Tend. Mensual", val, 1, 0.8, f"Mensual alcista (RSI={val:.0f})")
    elif ratio <= 0.3:
        return Signal("Tend. Mensual", val, -1, 0.8, f"Mensual bajista (RSI={val:.0f})")
    else:
        return Signal("Tend. Mensual", val, 0, 0.3, f"Mensual neutral (RSI={val:.0f})")


def analyze_volume_price_confirm(indicators: dict) -> Signal:
    """Confirmacion cruzada precio-volumen."""
    rv = indicators.get("relative_volume")
    change = indicators.get("change_pct", 0)
    rsi = indicators.get("rsi_14")
    macd_hist = indicators.get("macd_histogram")

    if rv is None or rv == 0:
        return Signal("Vol-Precio", 0, 0, 0, "Sin datos")

    # Senales de precio alcistas
    price_up = change > 0
    rsi_room = rsi is not None and rsi < 55  # Tiene espacio para subir
    macd_pos = macd_hist is not None and macd_hist > 0
    bullish_count = sum([price_up, rsi_room, macd_pos])

    if rv > 1.5 and bullish_count >= 2:
        return Signal("Vol-Precio", rv, 1, 1.2, f"Volumen confirma suba (RV={rv:.1f}x, {bullish_count}/3 alcistas)")
    elif rv > 1.5 and bullish_count <= 1:
        return Signal("Vol-Precio", rv, -1, 1.2, f"Volumen confirma baja (RV={rv:.1f}x, {bullish_count}/3 alcistas)")
    elif rv > 1.0 and bullish_count >= 2:
        return Signal("Vol-Precio", rv, 1, 0.5, f"Confirmacion moderada alcista (RV={rv:.1f}x)")
    elif rv < 0.5:
        return Signal("Vol-Precio", rv, 0, 0.2, f"Sin confirmacion de volumen (RV={rv:.1f}x)")
    else:
        return Signal("Vol-Precio", rv, 0, 0.3, f"Volumen neutral (RV={rv:.1f}x)")


# ──────────────────────────────────────────────
# ANALYZERS v3: DIVERGENCIAS, ICHIMOKU, Z-SCORE
# ──────────────────────────────────────────────

def analyze_rsi_divergence(indicators: dict) -> Signal:
    """Divergencia RSI-Precio: senal muy potente de cambio de tendencia."""
    bull_div = indicators.get("rsi_bull_div", 0)
    bear_div = indicators.get("rsi_bear_div", 0)
    rsi = indicators.get("rsi_14", 50)

    if bull_div > 0:
        return Signal("Div. RSI", rsi, 1, 1.5, f"Divergencia alcista (RSI={rsi:.0f}, precio en minimo pero RSI sube)")
    elif bear_div > 0:
        return Signal("Div. RSI", rsi, -1, 1.5, f"Divergencia bajista (RSI={rsi:.0f}, precio en maximo pero RSI baja)")
    else:
        return Signal("Div. RSI", rsi, 0, 0.1, "Sin divergencia")


def analyze_obv_divergence(indicators: dict) -> Signal:
    """Divergencia OBV-Precio: acumulacion/distribucion oculta."""
    bull_div = indicators.get("obv_bull_div", 0)
    bear_div = indicators.get("obv_bear_div", 0)

    if bull_div > 0:
        return Signal("Div. OBV", 1, 1, 1.3, "Acumulacion oculta (OBV sube, precio baja)")
    elif bear_div > 0:
        return Signal("Div. OBV", -1, -1, 1.3, "Distribucion oculta (OBV baja, precio sube)")
    else:
        return Signal("Div. OBV", 0, 0, 0.1, "Sin divergencia")


def analyze_ichimoku(indicators: dict) -> Signal:
    """Ichimoku Cloud: posicion respecto a la nube + TK cross."""
    above = indicators.get("above_kumo", 0)
    below = indicators.get("below_kumo", 0)
    tk = indicators.get("tk_cross", 0)

    if above > 0 and tk > 0:
        return Signal("Ichimoku", 1, 1, 1.2, "Sobre nube + Tenkan>Kijun (fuerte alcista)")
    elif above > 0:
        return Signal("Ichimoku", 1, 1, 0.8, "Sobre la nube Ichimoku")
    elif below > 0 and tk == 0:
        return Signal("Ichimoku", -1, -1, 1.2, "Bajo nube + Tenkan<Kijun (fuerte bajista)")
    elif below > 0:
        return Signal("Ichimoku", -1, -1, 0.8, "Bajo la nube Ichimoku")
    elif tk > 0:
        return Signal("Ichimoku", 0.5, 1, 0.5, "Cruce TK alcista (dentro de nube)")
    else:
        return Signal("Ichimoku", 0, 0, 0.3, "Dentro de nube / neutral")


def analyze_zscore(indicators: dict) -> Signal:
    """Z-Score: reversion a la media. >2 = sobreextendido, <-2 = oportunidad."""
    z = indicators.get("zscore_50")
    if z is None:
        return Signal("Z-Score", 0, 0, 0, "Sin datos")

    if z < -2:
        return Signal("Z-Score", z, 1, 1.3, f"Muy sobrevendido (Z={z:.2f}, >2 desvios bajo media)")
    elif z < -1:
        return Signal("Z-Score", z, 1, 0.7, f"Bajo la media (Z={z:.2f})")
    elif z > 2:
        return Signal("Z-Score", z, -1, 1.3, f"Muy sobreextendido (Z={z:.2f}, >2 desvios sobre media)")
    elif z > 1:
        return Signal("Z-Score", z, -1, 0.7, f"Sobre la media (Z={z:.2f})")
    else:
        return Signal("Z-Score", z, 0, 0.3, f"Cerca de la media (Z={z:.2f})")


def analyze_momentum_atr(indicators: dict) -> Signal:
    """Momentum normalizado por ATR: cambio de 5 dias / volatilidad."""
    m = indicators.get("momentum_atr")
    if m is None:
        return Signal("Mom. ATR", 0, 0, 0, "Sin datos")

    if m > 2:
        return Signal("Mom. ATR", m, 1, 1.0, f"Fuerte impulso alcista ({m:.1f} ATRs en 5d)")
    elif m > 1:
        return Signal("Mom. ATR", m, 1, 0.5, f"Impulso alcista moderado ({m:.1f} ATRs)")
    elif m < -2:
        return Signal("Mom. ATR", m, -1, 1.0, f"Fuerte impulso bajista ({m:.1f} ATRs en 5d)")
    elif m < -1:
        return Signal("Mom. ATR", m, -1, 0.5, f"Impulso bajista moderado ({m:.1f} ATRs)")
    else:
        return Signal("Mom. ATR", m, 0, 0.3, f"Sin impulso ({m:.1f} ATRs)")


# ──────────────────────────────────────────────
# ANALYZERS v4: PATRONES, GAPS, CONFLUENCIA
# ──────────────────────────────────────────────

def analyze_candlestick_patterns(indicators: dict) -> Signal:
    """Patrones de velas japonesas."""
    hammer = indicators.get("candle_hammer", 0)
    bull_engulf = indicators.get("candle_bull_engulf", 0)
    bear_engulf = indicators.get("candle_bear_engulf", 0)
    morning = indicators.get("candle_morning_star", 0)
    evening = indicators.get("candle_evening_star", 0)
    doji = indicators.get("candle_doji", 0)

    # Patrones alcistas
    if morning > 0:
        return Signal("Velas", 1, 1, 1.4, "Morning Star (reversion alcista fuerte)")
    if bull_engulf > 0:
        return Signal("Velas", 1, 1, 1.2, "Envolvente alcista")
    if hammer > 0:
        return Signal("Velas", 1, 1, 1.0, "Martillo (posible piso)")

    # Patrones bajistas
    if evening > 0:
        return Signal("Velas", -1, -1, 1.4, "Evening Star (reversion bajista fuerte)")
    if bear_engulf > 0:
        return Signal("Velas", -1, -1, 1.2, "Envolvente bajista")

    # Doji = indecision
    if doji > 0:
        return Signal("Velas", 0, 0, 0.4, "Doji (indecision)")

    return Signal("Velas", 0, 0, 0.1, "Sin patron")


def analyze_gap(indicators: dict) -> Signal:
    """Gaps de precio con confirmacion de volumen."""
    gap_up = indicators.get("gap_up", 0)
    gap_down = indicators.get("gap_down", 0)
    vol_confirm = indicators.get("gap_vol_confirm", 0)

    if gap_up > 0:
        if vol_confirm > 1.5:
            return Signal("Gap", gap_up, 1, 1.3, f"Gap alcista con volumen ({gap_up:.1f}%, RV={vol_confirm:.1f}x)")
        else:
            return Signal("Gap", gap_up, 1, 0.5, f"Gap alcista sin volumen ({gap_up:.1f}%) — posible trampa")
    elif gap_down < 0:
        if vol_confirm > 1.5:
            return Signal("Gap", gap_down, -1, 1.3, f"Gap bajista con volumen ({gap_down:.1f}%, RV={vol_confirm:.1f}x)")
        else:
            return Signal("Gap", gap_down, -1, 0.5, f"Gap bajista sin volumen ({gap_down:.1f}%)")

    return Signal("Gap", 0, 0, 0.1, "Sin gap")


# ──────────────────────────────────────────────
# ANALYZERS v4b: MACRO + CROSS-MARKET
# ──────────────────────────────────────────────

def analyze_macro(indicators: dict) -> Signal:
    """Senales macro: riesgo pais + spread CCL/MEP + dolar CCL tendencia."""
    rp_chg = indicators.get("riesgo_pais_7d_chg")
    spread_chg = indicators.get("spread_7d_chg")
    ccl_chg = indicators.get("ccl_7d_chg")

    if rp_chg is None and spread_chg is None and ccl_chg is None:
        return Signal("Macro", 0, 0, 0, "Sin datos macro")

    bull = 0
    total = 0

    # Riesgo pais bajando = alcista para acciones/bonos
    if rp_chg is not None:
        total += 1
        if rp_chg < -3:
            bull += 1
        elif rp_chg > 5:
            bull += 0  # Subiendo fuerte = malo
        else:
            bull += 0.5

    # Spread CCL/MEP comprimiendose = menos incertidumbre = alcista
    if spread_chg is not None:
        total += 1
        if spread_chg < -0.5:
            bull += 1  # Spread bajando
        elif spread_chg > 1:
            bull += 0  # Spread subiendo = incertidumbre
        else:
            bull += 0.5

    # Dolar CCL estable o bajando = alcista para acciones en pesos
    if ccl_chg is not None:
        total += 1
        if ccl_chg < -1:
            bull += 1  # CCL bajando = pesos se fortalecen
        elif ccl_chg > 3:
            bull += 0  # CCL subiendo fuerte = huida a dolar
        else:
            bull += 0.5

    if total == 0:
        return Signal("Macro", 0, 0, 0, "Sin datos macro")

    ratio = bull / total
    desc_parts = []
    if rp_chg is not None:
        desc_parts.append(f"RP {rp_chg:+.1f}%")
    if spread_chg is not None:
        desc_parts.append(f"Spread {spread_chg:+.1f}pp")
    if ccl_chg is not None:
        desc_parts.append(f"CCL {ccl_chg:+.1f}%")
    desc = ", ".join(desc_parts)

    if ratio >= 0.7:
        return Signal("Macro", ratio, 1, 1.0, f"Macro alcista ({desc})")
    elif ratio <= 0.3:
        return Signal("Macro", ratio, -1, 1.0, f"Macro bajista ({desc})")
    else:
        return Signal("Macro", ratio, 0, 0.3, f"Macro neutral ({desc})")


def analyze_sp500_cross(indicators: dict) -> Signal:
    """S&P 500 lag 1 dia — impacta especialmente CEDEARs."""
    sp_ret = indicators.get("sp500_return_1d")
    sp_5d = indicators.get("sp500_return_5d")
    asset_type = indicators.get("_asset_type", "")

    if sp_ret is None:
        return Signal("S&P 500", 0, 0, 0, "Sin datos S&P")

    # Peso mayor para CEDEARs
    base_weight = 1.2 if asset_type == "CEDEAR" else 0.5

    # Combinar retorno 1d y 5d
    if sp_ret > 1:
        sig = 1
        desc = f"S&P subio {sp_ret:+.1f}% ayer"
    elif sp_ret < -1:
        sig = -1
        desc = f"S&P bajo {sp_ret:+.1f}% ayer"
    elif sp_5d is not None and sp_5d > 2:
        sig = 1
        desc = f"S&P +{sp_5d:.1f}% en 5d"
    elif sp_5d is not None and sp_5d < -2:
        sig = -1
        desc = f"S&P {sp_5d:.1f}% en 5d"
    else:
        return Signal("S&P 500", sp_ret, 0, 0.2, f"S&P estable ({sp_ret:+.1f}%)")

    return Signal("S&P 500", sp_ret, sig, base_weight, desc)


# ──────────────────────────────────────────────
# COMPOSITE SCORING ENGINE v4
# ──────────────────────────────────────────────

ALL_ANALYZERS = [
    # Diarios (originales, 10)
    analyze_rsi,
    analyze_macd,
    analyze_bollinger,
    analyze_moving_averages,
    analyze_stochastic,
    analyze_adx,
    analyze_volume,
    analyze_williams_r,
    analyze_cci,
    analyze_mfi,
    # v2: Multi-timeframe + contexto (4)
    analyze_relative_strength,
    analyze_weekly_trend,
    analyze_monthly_trend,
    analyze_volume_price_confirm,
    # v3: Divergencias + estadisticos (5)
    analyze_rsi_divergence,
    analyze_obv_divergence,
    analyze_ichimoku,
    analyze_zscore,
    analyze_momentum_atr,
    # v4: Patrones + gaps (2)
    analyze_candlestick_patterns,
    analyze_gap,
    # v4b: Macro + cross-market (2)
    analyze_macro,
    analyze_sp500_cross,
]


# Grupos de indicadores para confluencia
INDICATOR_GROUPS = {
    "oscillator": {"RSI(14)", "Estocastico", "Williams %R", "CCI(20)", "MFI(14)"},
    "trend": {"MACD", "Medias Moviles", "ADX", "Ichimoku", "Tend. Semanal", "Tend. Mensual"},
    "momentum": {"Mom. ATR", "Z-Score", "Fuerza Relativa"},
    "volume": {"Volumen", "Vol-Precio", "Div. OBV"},
    "reversal": {"Div. RSI", "Bollinger", "Velas", "Gap"},
    "macro": {"Macro", "S&P 500"},
}


def calculate_score(
    indicators: dict,
    *,
    regime: dict | None = None,
    calibrated_weights: dict | None = None,
    thresholds: dict | None = None,
) -> dict:
    """
    Calculate the composite probability score for an asset.

    Args:
        indicators: dict of indicator values
        regime: market regime dict from detect_regime()
        calibrated_weights: dict {indicator_name: multiplier} from calibration

    Returns:
        {
            "score": float (0-100),
            "signal": str ("compra" | "venta" | "neutral"),
            "confidence": float (0-100),
            "signals": list of signal details,
            "bullish_count": int,
            "bearish_count": int,
            "neutral_count": int,
            "regime": str,
            "ml_score": float | None,
            "ensemble_score": float | None,
        }
    """
    signals: list[Signal] = []
    # Analyzers que aceptan thresholds
    _adaptive_analyzers = {analyze_rsi, analyze_stochastic}
    for analyzer in ALL_ANALYZERS:
        try:
            if thresholds and analyzer in _adaptive_analyzers:
                sig = analyzer(indicators, thresholds=thresholds)
            else:
                sig = analyzer(indicators)
            signals.append(sig)
        except Exception as e:
            logger.warning(f"Error in {analyzer.__name__}: {e}")

    if not signals:
        return _empty_result()

    # ── Aplicar calibracion de pesos ──
    if calibrated_weights:
        for sig in signals:
            if sig.name in calibrated_weights and sig.weight > 0:
                sig.weight *= calibrated_weights[sig.name]

    # ── Aplicar ajuste de regimen ──
    regime_mod = 1.0
    regime_name = "neutral"
    if regime:
        regime_mod = regime.get("weight_modifier", 1.0)
        regime_name = regime.get("regime", "neutral")

    # Weighted score calculation
    weighted_sum = 0.0
    total_weight = 0.0
    bullish = 0
    bearish = 0
    neutral = 0

    for sig in signals:
        if sig.weight > 0:
            effective_weight = sig.weight

            # En bear market: reducir peso de senales de compra, aumentar venta
            if regime_name == "bear" and sig.signal > 0:
                effective_weight *= regime_mod  # 0.80
            elif regime_name == "bear" and sig.signal < 0:
                effective_weight *= (2 - regime_mod)  # 1.20
            elif regime_name == "bull" and sig.signal > 0:
                effective_weight *= regime_mod  # 1.15
            elif regime_name == "bull" and sig.signal < 0:
                effective_weight *= (2 - regime_mod)  # 0.85

            normalized = (sig.signal + 1) / 2  # -1->0, 0->0.5, +1->1
            weighted_sum += normalized * effective_weight
            total_weight += effective_weight

        if sig.signal > 0:
            bullish += 1
        elif sig.signal < 0:
            bearish += 1
        else:
            neutral += 1

    # Final score: 0-100
    if total_weight > 0:
        score = (weighted_sum / total_weight) * 100
    else:
        score = 50.0

    score = max(0, min(100, score))

    # ── CONFLUENCIA: bonus cuando grupos distintos coinciden ──
    group_signals = {}  # {group: avg_signal}
    for sig in signals:
        for group_name, members in INDICATOR_GROUPS.items():
            if sig.name in members and sig.signal != 0 and sig.weight > 0:
                if group_name not in group_signals:
                    group_signals[group_name] = []
                group_signals[group_name].append(sig.signal)

    if len(group_signals) >= 3:
        # Contar cuantos grupos son bullish vs bearish
        groups_bullish = sum(1 for sigs in group_signals.values() if sum(sigs) > 0)
        groups_bearish = sum(1 for sigs in group_signals.values() if sum(sigs) < 0)
        total_groups = len(group_signals)

        # Si 3+ grupos distintos coinciden, bonus de confluencia
        if groups_bullish >= 3:
            confluence_bonus = min(8.0, groups_bullish * 2.0)
            score = min(100, score + confluence_bonus)
        elif groups_bearish >= 3:
            confluence_penalty = min(8.0, groups_bearish * 2.0)
            score = max(0, score - confluence_penalty)

    # ── SCORE MOMENTUM: si el score viene subiendo, reforzar ──
    prev_score = indicators.get("_prev_score")
    if prev_score is not None:
        score_delta = score - prev_score
        if score_delta > 15:
            score = min(100, score + 3)  # Score acelerando al alza
        elif score_delta < -15:
            score = max(0, score - 3)  # Score acelerando a la baja

    # Confidence: based on agreement between indicators
    total_with_signal = bullish + bearish
    if total_with_signal > 0:
        agreement = max(bullish, bearish) / total_with_signal
        confidence = agreement * 100
    else:
        confidence = 0.0

    # ── ML Ensemble ──
    ml_score = None
    ensemble_score = None
    signals_detail = [
        {
            "name": s.name,
            "value": round(s.value, 4) if isinstance(s.value, float) else s.value,
            "signal": s.signal,
            "weight": round(s.weight, 3),
            "description": s.description,
        }
        for s in signals
    ]

    try:
        from app.services.calibration import predict_ml
        ml_score = predict_ml(signals_detail, score, confidence)
        if ml_score is not None:
            # Ensemble: 40% reglas + 60% ML (ML se entrena con mas datos)
            ensemble_score = round(0.4 * score + 0.6 * ml_score, 1)
    except Exception:
        pass

    # Use ensemble if available, otherwise use rule-based score
    final_score = round(ensemble_score if ensemble_score is not None else score, 1)

    # Signal classification
    if final_score >= 65:
        signal = "compra"
    elif final_score <= 35:
        signal = "venta"
    else:
        signal = "neutral"

    return {
        "score": final_score,
        "rule_score": round(score, 1),
        "signal": signal,
        "confidence": round(confidence, 1),
        "signals": signals_detail,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "regime": regime_name,
        "ml_score": ml_score,
        "ensemble_score": ensemble_score,
    }


def _empty_result() -> dict:
    return {
        "score": 50.0,
        "rule_score": 50.0,
        "signal": "neutral",
        "confidence": 0.0,
        "signals": [],
        "bullish_count": 0,
        "bearish_count": 0,
        "neutral_count": 0,
        "regime": "neutral",
        "ml_score": None,
        "ensemble_score": None,
    }
