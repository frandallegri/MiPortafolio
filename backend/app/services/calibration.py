"""
Calibracion dinamica de pesos y ML ensemble.
Analiza scoring_results historicos para ajustar pesos segun precision real.
"""
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring import ScoringResult

logger = logging.getLogger(__name__)

# Pesos base (los originales del motor de reglas)
BASE_WEIGHTS = {
    "RSI(14)": 1.0,
    "MACD": 1.0,
    "Bollinger": 1.0,
    "Medias Moviles": 1.0,
    "Estocastico": 1.0,
    "ADX": 1.0,
    "Volumen": 1.0,
    "Williams %R": 1.0,
    "CCI(20)": 1.0,
    "MFI(14)": 1.0,
    "Fuerza Relativa": 1.0,
    "Tend. Semanal": 1.0,
    "Tend. Mensual": 1.0,
    "Vol-Precio": 1.0,
}

# Cache de pesos calibrados
_calibrated_weights: dict | None = None
_calibration_date: date | None = None

# Minimo de registros necesarios para calibrar
MIN_RECORDS_FOR_CALIBRATION = 100


async def calibrate_weights(db: AsyncSession) -> dict:
    """
    Analiza scoring_results historicos y calcula precision de cada indicador.
    Retorna un dict {indicator_name: weight_multiplier} donde multiplier >1
    significa que el indicador predice mejor que el promedio.
    """
    global _calibrated_weights, _calibration_date

    # Buscar resultados con actual_direction
    result = await db.execute(
        select(ScoringResult)
        .where(ScoringResult.actual_direction.isnot(None))
        .where(ScoringResult.indicators_detail.isnot(None))
        .order_by(ScoringResult.date.desc())
        .limit(2000)
    )
    rows = result.scalars().all()

    if len(rows) < MIN_RECORDS_FOR_CALIBRATION:
        logger.info(f"Calibracion: solo {len(rows)} registros (necesita {MIN_RECORDS_FOR_CALIBRATION})")
        return {}

    # Analizar precision por indicador
    indicator_stats = {}  # {name: {"correct": int, "total": int}}

    for row in rows:
        if not row.indicators_detail or not row.actual_direction:
            continue

        actual_up = row.actual_direction == "up"

        for sig in row.indicators_detail:
            name = sig.get("name", "")
            signal = sig.get("signal", 0)

            if signal == 0:
                continue  # Neutral signals don't count

            if name not in indicator_stats:
                indicator_stats[name] = {"correct": 0, "total": 0}

            indicator_stats[name]["total"] += 1

            # Correct if: signal=+1 and actual=up, or signal=-1 and actual=down
            if (signal > 0 and actual_up) or (signal < 0 and not actual_up):
                indicator_stats[name]["correct"] += 1

    # Calcular weight multipliers
    weights = {}
    avg_accuracy = 0.5  # baseline 50%

    for name, stats in indicator_stats.items():
        if stats["total"] < 20:
            continue  # Insufficient data for this indicator
        accuracy = stats["correct"] / stats["total"]
        # Multiplier: accuracy / baseline. If 60% accurate = 1.2x weight
        multiplier = accuracy / avg_accuracy
        # Clamp to [0.3, 2.0] to prevent extreme adjustments
        multiplier = max(0.3, min(2.0, multiplier))
        weights[name] = round(multiplier, 3)
        logger.info(f"  {name}: accuracy={accuracy:.1%} ({stats['correct']}/{stats['total']}) -> weight={multiplier:.3f}")

    _calibrated_weights = weights
    _calibration_date = date.today()

    logger.info(f"Calibracion completada: {len(weights)} indicadores calibrados de {len(rows)} registros")
    return weights


def get_calibrated_weights() -> dict:
    """Retorna pesos calibrados (o vacio si no hay calibracion)."""
    return _calibrated_weights or {}


# ────────────────────────────────────────
# ML ENSEMBLE MODEL
# ────────────────────────────────────────

_ml_model = None
_ml_features: list[str] = []


async def train_ml_model(db: AsyncSession) -> dict:
    """
    Entrena un modelo ML (RandomForest) con datos historicos de scoring.
    Features: valores de indicadores. Target: actual_direction (up/down).
    """
    global _ml_model, _ml_features

    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import cross_val_score
    except ImportError:
        logger.warning("scikit-learn no instalado, ML deshabilitado")
        return {"status": "disabled", "reason": "scikit-learn not installed"}

    # Cargar datos
    result = await db.execute(
        select(ScoringResult)
        .where(ScoringResult.actual_direction.isnot(None))
        .where(ScoringResult.indicators_detail.isnot(None))
        .order_by(ScoringResult.date)
    )
    rows = result.scalars().all()

    if len(rows) < 200:
        return {"status": "insufficient_data", "records": len(rows), "needed": 200}

    # Construir dataset
    records = []
    for row in rows:
        if not row.indicators_detail or row.actual_direction not in ("up", "down"):
            continue

        features = {}
        for sig in row.indicators_detail:
            name = sig.get("name", "").replace(" ", "_").replace("(", "").replace(")", "")
            features[f"sig_{name}"] = sig.get("signal", 0)
            features[f"val_{name}"] = sig.get("value", 0)
            features[f"wgt_{name}"] = sig.get("weight", 0)

        features["score"] = row.score
        features["confidence"] = row.confidence
        features["target"] = 1 if row.actual_direction == "up" else 0
        records.append(features)

    df = pd.DataFrame(records)
    if len(df) < 200:
        return {"status": "insufficient_data", "records": len(df), "needed": 200}

    # Separar features y target
    target = df["target"]
    features = df.drop(columns=["target"]).fillna(0)
    _ml_features = list(features.columns)

    # Entrenar Random Forest
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=10,
        random_state=42,
        class_weight="balanced",
    )

    # Cross-validation
    scores = cross_val_score(model, features, target, cv=5, scoring="accuracy")
    avg_accuracy = float(np.mean(scores))

    # Entrenar modelo final con todos los datos
    model.fit(features, target)
    _ml_model = model

    # Feature importance
    importances = dict(zip(_ml_features, model.feature_importances_))
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

    logger.info(f"ML model trained: accuracy={avg_accuracy:.1%}, records={len(df)}")

    return {
        "status": "trained",
        "accuracy": round(avg_accuracy * 100, 1),
        "records": len(df),
        "top_features": [{
            "feature": f, "importance": round(imp, 4)
        } for f, imp in top_features],
    }


def predict_ml(indicators_detail: list[dict], score: float, confidence: float) -> Optional[float]:
    """
    Predice probabilidad de suba usando el modelo ML.
    Retorna float 0-100 o None si el modelo no esta entrenado.
    """
    if _ml_model is None or not _ml_features:
        return None

    try:
        features = {}
        for sig in indicators_detail:
            name = sig.get("name", "").replace(" ", "_").replace("(", "").replace(")", "")
            features[f"sig_{name}"] = sig.get("signal", 0)
            features[f"val_{name}"] = sig.get("value", 0)
            features[f"wgt_{name}"] = sig.get("weight", 0)

        features["score"] = score
        features["confidence"] = confidence

        # Build feature vector in correct order
        X = pd.DataFrame([features]).reindex(columns=_ml_features, fill_value=0)
        prob = _ml_model.predict_proba(X)[0]

        # prob[1] = probability of class 1 (up)
        ml_score = float(prob[1]) * 100
        return round(ml_score, 1)
    except Exception as e:
        logger.warning(f"ML prediction error: {e}")
        return None
