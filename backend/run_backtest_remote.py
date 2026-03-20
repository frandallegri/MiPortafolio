"""
Ejecuta el backtest llamando al backend en Render ticker por ticker.
No necesita conexion directa a la DB (evita problemas de SSL en Windows).
Uso: python run_backtest_remote.py
"""
import requests
import time
import sys

API_URL = "https://miportafolio-api.onrender.com"
EMAIL = "frandallegri@gmail.com"
PASSWORD = "sasa"

# Tickers con datos historicos suficientes
TICKERS = [
    # Acciones argentinas
    "GGAL", "TECO2", "BMA", "BBAR", "PAMP", "TXAR", "ALUA", "YPFD",
    "RICH", "CAPX", "BOLT", "AUSO", "BYMA", "AGRO", "GARO", "GBAN",
    "METR", "CECO2", "HARG", "MOLI", "TGSU2", "LOMA", "SUPV", "CEPU",
    "EDN", "COME", "IRSA", "CRES", "MIRG", "SEMI", "VALO", "BHIP",
    "MORI", "CARC", "FERR", "LONG", "INVJ", "CTIO", "RIGO", "DGCU2",
    # Bonos
    "AL30", "AL35", "GD30", "GD35", "AE38", "AL41", "GD41", "GD38", "GD46",
    # CEDEARs
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX",
]


def login():
    r = requests.post(f"{API_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def backtest_ticker(token, ticker):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API_URL}/analysis/backtest/{ticker}", headers=headers, timeout=120)
    if r.status_code != 200:
        return None
    return r.json()


def calibrate(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API_URL}/analysis/calibrate", headers=headers, timeout=60)
    return r.json() if r.status_code == 200 else {}


def train_ml(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API_URL}/analysis/train-ml", headers=headers, timeout=120)
    return r.json() if r.status_code == 200 else {}


def get_accuracy(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_URL}/analysis/accuracy", headers=headers, timeout=60)
    return r.json() if r.status_code == 200 else {}


def main():
    print("=" * 60)
    print("BACKTEST REMOTO - MiPortafolio")
    print(f"Backend: {API_URL}")
    print(f"Tickers: {len(TICKERS)}")
    print("=" * 60)

    # Login
    print("\nLogueando...")
    try:
        token = login()
        print("OK!")
    except Exception as e:
        print(f"Error de login: {e}")
        print("El backend puede estar dormido. Esperando 30s y reintentando...")
        time.sleep(30)
        token = login()

    # Backtest ticker por ticker
    print(f"\n{'='*60}")
    print(f"PASE 1: Backtest de {len(TICKERS)} tickers")
    print(f"{'='*60}")

    results = []
    total_scores = 0
    total_correct = 0

    for i, ticker in enumerate(TICKERS):
        print(f"  [{i+1}/{len(TICKERS)}] {ticker}...", end=" ", flush=True)
        try:
            result = backtest_ticker(token, ticker)
            if result and "error" not in result:
                scores = result.get("scores", 0)
                acc = result.get("accuracy", 0)
                total_scores += scores
                total_correct += result.get("correct", 0)
                results.append(result)
                print(f"{scores} dias, accuracy={acc}%")
            else:
                print("sin datos suficientes")
        except Exception as e:
            print(f"error: {e}")
            # Re-login si el token expiro
            if "401" in str(e):
                token = login()

    overall_acc = (total_correct / total_scores * 100) if total_scores > 0 else 0
    print(f"\nPase 1 completo: {total_scores} scores, accuracy={overall_acc:.1f}%")
    print(f"Tickers procesados: {len(results)}")

    # Calibrar
    print(f"\n{'='*60}")
    print("CALIBRACION")
    print(f"{'='*60}")
    cal = calibrate(token)
    print(f"Indicadores calibrados: {cal.get('calibrated_indicators', 0)}")
    if cal.get("weights"):
        for name, w in sorted(cal["weights"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {w:.3f}x")

    # ML
    print(f"\n{'='*60}")
    print("ML TRAINING")
    print(f"{'='*60}")
    ml = train_ml(token)
    print(f"Status: {ml.get('status', 'unknown')}")
    if ml.get("accuracy"):
        print(f"Accuracy: {ml['accuracy']}%")

    # Metricas finales
    print(f"\n{'='*60}")
    print("METRICAS FINALES")
    print(f"{'='*60}")
    metrics = get_accuracy(token)
    print(f"Precision general: {metrics.get('overall_accuracy', 'N/A')}%")
    print(f"Total predicciones: {metrics.get('total_predictions', 0)}")

    if metrics.get("signal_accuracy"):
        print("\nPor senal:")
        for sig, data in metrics["signal_accuracy"].items():
            print(f"  {sig}: {data['accuracy']}% ({data['correct']}/{data['total']})")

    if metrics.get("score_buckets"):
        print("\nPor rango de score (% que realmente subio):")
        for bucket, data in metrics["score_buckets"].items():
            print(f"  Score {bucket}: {data['pct_up']}% subio (n={data['count']})")

    if metrics.get("indicator_ranking"):
        print("\nRanking de indicadores:")
        for ind in metrics["indicator_ranking"]:
            emoji = "+" if ind["accuracy"] >= 55 else "-" if ind["accuracy"] < 50 else "~"
            print(f"  {emoji} {ind['name']}: {ind['accuracy']}% ({ind['correct']}/{ind['total']})")

    print(f"\n{'='*60}")
    print("COMPLETO! Los resultados estan en la DB.")
    print("Abri /accuracy en la web para verlos.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
