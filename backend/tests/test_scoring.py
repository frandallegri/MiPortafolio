"""Tests unitarios para el motor de scoring v2."""
import pytest
from app.services.scoring import (
    calculate_score,
    analyze_rsi,
    analyze_macd,
    analyze_bollinger,
    analyze_moving_averages,
    analyze_relative_strength,
    analyze_weekly_trend,
    analyze_monthly_trend,
    analyze_volume_price_confirm,
)


def make_indicators(**overrides):
    """Helper: crea un dict de indicadores con valores por defecto neutrales."""
    base = {
        "close": 100.0,
        "prev_close": 99.0,
        "change_pct": 1.01,
        "rsi_14": 50.0,
        "macd": 0.0,
        "macd_signal": 0.0,
        "macd_histogram": 0.0,
        "bb_pband": 0.5,
        "bb_upper": 110.0,
        "bb_middle": 100.0,
        "bb_lower": 90.0,
        "sma_20": 99.0,
        "sma_50": 97.0,
        "sma_200": 95.0,
        "ema_9": 100.0,
        "ema_21": 99.0,
        "ema_50": 97.0,
        "stoch_k": 50.0,
        "stoch_d": 50.0,
        "adx": 25.0,
        "adx_pos": 20.0,
        "adx_neg": 15.0,
        "relative_volume": 1.0,
        "williams_r": -50.0,
        "cci_20": 0.0,
        "mfi_14": 50.0,
    }
    base.update(overrides)
    return base


class TestRSI:
    def test_oversold_bullish(self):
        sig = analyze_rsi({"rsi_14": 25})
        assert sig.signal == 1
        assert sig.weight > 1.0

    def test_overbought_bearish(self):
        sig = analyze_rsi({"rsi_14": 75})
        assert sig.signal == -1

    def test_neutral(self):
        sig = analyze_rsi({"rsi_14": 50})
        assert sig.signal == 0


class TestMACD:
    def test_bullish_histogram(self):
        sig = analyze_macd({"macd": 1.0, "macd_signal": 0.5, "macd_histogram": 0.5})
        assert sig.signal == 1

    def test_bearish_histogram(self):
        sig = analyze_macd({"macd": -1.0, "macd_signal": -0.5, "macd_histogram": -0.5})
        assert sig.signal == -1


class TestBollinger:
    def test_near_lower_band(self):
        sig = analyze_bollinger({"bb_pband": 0.03, "close": 90.5, "bb_lower": 90, "bb_upper": 110})
        assert sig.signal == 1

    def test_near_upper_band(self):
        sig = analyze_bollinger({"bb_pband": 0.97, "close": 109.5, "bb_lower": 90, "bb_upper": 110})
        assert sig.signal == -1


class TestRelativeStrength:
    def test_outperforming(self):
        sig = analyze_relative_strength({"rs_vs_merval": 8.0})
        assert sig.signal == 1
        assert sig.weight >= 1.0

    def test_underperforming(self):
        sig = analyze_relative_strength({"rs_vs_merval": -7.0})
        assert sig.signal == -1

    def test_inline(self):
        sig = analyze_relative_strength({"rs_vs_merval": 0.5})
        assert sig.signal == 0


class TestWeeklyTrend:
    def test_bullish_weekly(self):
        sig = analyze_weekly_trend({"weekly_rsi": 35, "weekly_macd_hist": 0.5, "weekly_above_sma20": True})
        assert sig.signal == 1

    def test_bearish_weekly(self):
        sig = analyze_weekly_trend({"weekly_rsi": 72, "weekly_macd_hist": -0.5, "weekly_above_sma20": False})
        assert sig.signal == -1


class TestMonthlyTrend:
    def test_bullish_monthly(self):
        sig = analyze_monthly_trend({"monthly_rsi": 35, "monthly_above_sma10": True})
        assert sig.signal == 1

    def test_bearish_monthly(self):
        sig = analyze_monthly_trend({"monthly_rsi": 70, "monthly_above_sma10": False})
        assert sig.signal == -1


class TestVolumePriceConfirm:
    def test_volume_confirms_up(self):
        sig = analyze_volume_price_confirm({
            "relative_volume": 2.0, "change_pct": 3.0,
            "rsi_14": 45, "macd_histogram": 0.1
        })
        assert sig.signal == 1

    def test_volume_confirms_down(self):
        sig = analyze_volume_price_confirm({
            "relative_volume": 2.0, "change_pct": -2.0,
            "rsi_14": 70, "macd_histogram": -0.3
        })
        assert sig.signal == -1


class TestCompositeScore:
    def test_bullish_scenario(self):
        """All indicators bullish should give score > 70."""
        indicators = make_indicators(
            rsi_14=25,
            macd=1.0, macd_signal=0.5, macd_histogram=0.5,
            bb_pband=0.03,
            stoch_k=15, stoch_d=12,
            adx=35, adx_pos=30, adx_neg=10,
            williams_r=-85,
            cci_20=-120,
            mfi_14=15,
            relative_volume=2.5,
        )
        result = calculate_score(indicators)
        assert result["score"] > 70
        assert result["signal"] == "compra"

    def test_bearish_scenario(self):
        """All indicators bearish should give score < 35."""
        indicators = make_indicators(
            rsi_14=80,
            macd=-1.0, macd_signal=-0.5, macd_histogram=-0.5,
            bb_pband=0.97,
            stoch_k=85, stoch_d=88,
            adx=35, adx_pos=10, adx_neg=30,
            williams_r=-10,
            cci_20=120,
            mfi_14=85,
            relative_volume=2.5,
            change_pct=-2.0,
        )
        result = calculate_score(indicators)
        assert result["score"] < 35
        assert result["signal"] == "venta"

    def test_neutral_scenario(self):
        """Mixed indicators should give score near 50."""
        indicators = make_indicators()
        result = calculate_score(indicators)
        assert 30 < result["score"] < 70

    def test_returns_all_fields(self):
        result = calculate_score(make_indicators())
        assert "score" in result
        assert "signal" in result
        assert "confidence" in result
        assert "signals" in result
        assert "bullish_count" in result
        assert "bearish_count" in result
        assert "regime" in result
        assert "ml_score" in result
        assert "ensemble_score" in result

    def test_score_bounds(self):
        """Score should always be between 0 and 100."""
        for rsi in [5, 25, 50, 75, 95]:
            result = calculate_score(make_indicators(rsi_14=rsi))
            assert 0 <= result["score"] <= 100

    def test_regime_bull_boosts_buy(self):
        """Bull regime should boost buy signals."""
        indicators = make_indicators(rsi_14=25, macd=1.0, macd_signal=0.5, macd_histogram=0.5)
        base = calculate_score(indicators)
        boosted = calculate_score(indicators, regime={"regime": "bull", "weight_modifier": 1.15})
        assert boosted["score"] >= base["score"]

    def test_regime_bear_dampens_buy(self):
        """Bear regime should dampen buy signals."""
        indicators = make_indicators(rsi_14=25, macd=1.0, macd_signal=0.5, macd_histogram=0.5)
        base = calculate_score(indicators)
        dampened = calculate_score(indicators, regime={"regime": "bear", "weight_modifier": 0.80})
        assert dampened["score"] <= base["score"]
