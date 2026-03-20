const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("token", token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
    }
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("No autorizado");
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Error del servidor" }));
      throw new Error(err.detail || `Error ${res.status}`);
    }

    return res.json();
  }

  // Auth
  async login(email: string, password: string) {
    const data = await this.request<{ access_token: string; email: string }>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }
    );
    this.setToken(data.access_token);
    return data;
  }

  // Market
  async getLiveStocks() {
    return this.request<any[]>("/market/live/stocks");
  }

  async getLiveCedears() {
    return this.request<any[]>("/market/live/cedears");
  }

  async getLiveBonds() {
    return this.request<any[]>("/market/live/bonds");
  }

  async getLiveAll() {
    return this.request<Record<string, any[]>>("/market/live/all");
  }

  async getDollarRates() {
    return this.request<Record<string, any>>("/market/dollar");
  }

  async getMacroLatest() {
    return this.request<Record<string, any>>("/market/macro/latest");
  }

  async getPriceHistory(ticker: string, days = 90) {
    return this.request<any[]>(`/market/prices/${ticker}?days=${days}`);
  }

  // Analysis
  async getIndicators(ticker: string) {
    return this.request<any>(`/analysis/indicators/${ticker}`);
  }

  async getScore(ticker: string) {
    return this.request<any>(`/analysis/score/${ticker}`);
  }

  async getScanner(minScore = 0, assetType?: string) {
    let url = `/analysis/scanner?min_score=${minScore}`;
    if (assetType) url += `&asset_type=${assetType}`;
    return this.request<any>(url);
  }

  async getScoringHistory(ticker: string, days = 30) {
    return this.request<any[]>(`/analysis/scoring-history/${ticker}?days=${days}`);
  }

  async getTickerHistory(ticker: string) {
    return this.request<any>(`/history/${ticker}`);
  }

  async triggerBacktest() {
    return this.request<any>("/analysis/full-pipeline", { method: "POST" });
  }

  async getBacktestStatus() {
    return this.request<any>("/analysis/backtest/status");
  }

  async getMomentum(topN = 10) {
    return this.request<any>(`/analysis/momentum?top_n=${topN}`);
  }

  async getMomentumBacktest(topN = 5) {
    return this.request<any>(`/analysis/momentum/backtest?top_n=${topN}`);
  }

  async getAccuracy(ticker?: string) {
    const url = ticker ? `/analysis/accuracy?ticker=${ticker}` : "/analysis/accuracy";
    return this.request<any>(url);
  }

  async getBacktestResults() {
    return this.request<any>("/analysis/backtest/status");
  }

  async getRedundancy() {
    return this.request<any>("/analysis/redundancy");
  }

  async getRegime() {
    return this.request<any>("/analysis/regime");
  }

  // Portfolio
  async getPositions(openOnly = true) {
    return this.request<any[]>(`/portfolio/positions?open_only=${openOnly}`);
  }

  async createPosition(data: any) {
    return this.request<any>("/portfolio/positions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async closePosition(id: number, data: any) {
    return this.request<any>(`/portfolio/positions/${id}/close`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deletePosition(id: number) {
    return this.request<any>(`/portfolio/positions/${id}`, {
      method: "DELETE",
    });
  }

  async getPortfolioSummary() {
    return this.request<any>("/portfolio/summary");
  }

  // Admin
  async triggerSync() {
    return this.request<any>("/admin/sync", { method: "POST" });
  }

  async triggerScoring() {
    return this.request<any>("/admin/run-scoring", { method: "POST" });
  }
}

export const api = new ApiClient();
