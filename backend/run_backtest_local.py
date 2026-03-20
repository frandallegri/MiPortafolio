"""
Script para correr el backtest desde tu PC.
Se conecta directo a la base de datos PostgreSQL de Render.
Uso: python run_backtest_local.py

NOTA: Si SSL falla en Windows, usar el endpoint remoto:
  curl -X POST https://miportafolio-api.onrender.com/analysis/full-pipeline
"""
import asyncio
import os
import sys
import time

# Agregar el directorio backend al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setear la DB de Render (externa)
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://miportafolio_user:Iyl1y3zU0dNTQwx07pCk4T6cf1hezGhF"
    "@dpg-d6ubt97diees73deturg-a.oregon-postgres.render.com:5432/miportafolio"
)


async def main():
    import ssl as _ssl
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as AS
    from sqlalchemy.orm import sessionmaker

    # Crear engine con SSL para conexion externa a Render
    ssl_ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = _ssl.CERT_NONE

    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        connect_args={"ssl": ssl_ctx},
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
    )
    async_session_local = sessionmaker(engine, class_=AS, expire_on_commit=False)

    # Reemplazar la session factory global
    import app.database as _db
    _db.async_session = async_session_local
    from app.services.backtesting import run_backtest, compute_accuracy_metrics, analyze_redundancy
    from app.services.calibration import calibrate_weights, train_ml_model

    print("=" * 60)
    print("BACKTEST LOCAL - MiPortafolio")
    print("Conectando a PostgreSQL de Render...")
    print("=" * 60)

    # Test connection
    async with engine.begin() as conn:
        from sqlalchemy import text
        r = await conn.execute(text("SELECT count(*) FROM prices_daily"))
        cnt = r.scalar()
        print(f"Conexion OK! {cnt} barras en la base de datos.")

    async with async_session_local() as db:
        # ═══ PASE 1 ═══
        print("\n[PASE 1] Backtest con pesos por defecto...")
        t0 = time.time()
        bt1 = await run_backtest(db)
        t1 = time.time()
        print(f"  Resultado: {bt1['total_scores']} scores, accuracy={bt1['overall_accuracy']}%")
        print(f"  Tickers procesados: {bt1['tickers_processed']}")
        print(f"  Tiempo: {t1-t0:.1f}s")

        for tr in bt1.get("ticker_results", []):
            print(f"    {tr['ticker']}: {tr['scores']} dias, accuracy={tr['accuracy']}%")

        # ═══ CALIBRACION 1 ═══
        print("\n[CALIBRACION 1] Ajustando pesos segun precision real...")
        cal1 = await calibrate_weights(db)
        print(f"  Indicadores calibrados: {len(cal1)}")
        for name, mult in sorted(cal1.items(), key=lambda x: x[1], reverse=True):
            print(f"    {name}: {mult:.3f}x")

        # ═══ PASE 2 ═══
        print("\n[PASE 2] Re-backtest con pesos calibrados...")
        t2 = time.time()
        bt2 = await run_backtest(db, calibrated_weights=cal1)
        t3 = time.time()
        print(f"  Resultado: accuracy={bt2['overall_accuracy']}%")
        print(f"  Mejora: {bt2['overall_accuracy'] - bt1['overall_accuracy']:+.1f}%")
        print(f"  Tiempo: {t3-t2:.1f}s")

        # ═══ CALIBRACION 2 ═══
        print("\n[CALIBRACION 2] Re-calibrando con datos del pase 2...")
        cal2 = await calibrate_weights(db)
        print(f"  Indicadores calibrados: {len(cal2)}")

        # ═══ ML ═══
        print("\n[ML] Entrenando modelo RandomForest...")
        ml = await train_ml_model(db)
        print(f"  Status: {ml.get('status')}")
        if ml.get('accuracy'):
            print(f"  Accuracy: {ml['accuracy']}%")
        if ml.get('top_features'):
            print("  Top features:")
            for f in ml['top_features'][:5]:
                print(f"    {f['feature']}: {f['importance']:.4f}")

        # ═══ METRICAS ═══
        print("\n[METRICAS] Calculando precision final...")
        metrics = await compute_accuracy_metrics(db)
        print(f"  Precision general: {metrics.get('overall_accuracy', 0)}%")
        print(f"  Total predicciones: {metrics.get('total_predictions', 0)}")

        if metrics.get('signal_accuracy'):
            print("  Por senal:")
            for sig, data in metrics['signal_accuracy'].items():
                print(f"    {sig}: {data['accuracy']}% ({data['correct']}/{data['total']})")

        if metrics.get('score_buckets'):
            print("  Por rango de score:")
            for bucket, data in metrics['score_buckets'].items():
                print(f"    Score {bucket}: {data['pct_up']}% subio (n={data['count']})")

        if metrics.get('indicator_ranking'):
            print("\n  Ranking de indicadores:")
            for ind in metrics['indicator_ranking']:
                emoji = "✓" if ind['accuracy'] >= 55 else "✗" if ind['accuracy'] < 50 else "~"
                print(f"    {emoji} {ind['name']}: {ind['accuracy']}% ({ind['correct']}/{ind['total']})")

        # ═══ REDUNDANCIA ═══
        print("\n[REDUNDANCIA] Analizando correlaciones...")
        red = await analyze_redundancy(db)
        if red.get('high_correlation_groups'):
            print("  Grupos correlacionados:")
            for group in red['high_correlation_groups']:
                print(f"    {', '.join(group)}")

    print("\n" + "=" * 60)
    print("BACKTEST COMPLETO")
    print(f"Pase 1: {bt1['overall_accuracy']}% -> Pase 2: {bt2['overall_accuracy']}%")
    print("Los resultados ya estan guardados en la base de datos.")
    print("Abri /accuracy en la web para verlos.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
