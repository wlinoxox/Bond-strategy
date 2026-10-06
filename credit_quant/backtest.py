"""只做多 + 因子傾斜的選券組合與回測（credit-quant.md 第 6.3 節的簡化版）。"""

import numpy as np
import pandas as pd

CELL = ["rating", "maturity_bucket"]


def build_portfolio(
    month: pd.DataFrame,
    score_col: str = "score",
    top_frac: float = 0.4,
    keep_frac: float = 0.5,
    prev_holdings: set | None = None,
) -> pd.Series:
    """單月選券。

    - 每個「評等 × 天期」分群的總權重 = 該分群在基準中的權重，維持信用 beta 接近基準
    - 分群內選分數前 top_frac 的債券；已持有且仍在前 keep_frac 的債券保留（降低換手）
    - 分群內以基準權重為起點，依 DTS 傾斜，使分群的加權平均 DTS 與基準一致
    """
    prev_holdings = prev_holdings or set()
    weights = {}
    for _, cell in month.groupby(CELL, observed=True):
        cell = cell.dropna(subset=[score_col])
        if cell.empty:
            continue
        cell_bench_w = cell["bench_weight"].sum()
        cell_bench_dts = (cell["bench_weight"] * cell["dts"]).sum() / cell_bench_w
        pct = cell[score_col].rank(pct=True, ascending=False)
        held = cell["bond_id"].isin(prev_holdings)
        chosen = cell[(pct <= top_frac) | (held & (pct <= keep_frac))]
        if chosen.empty:
            chosen = cell.nlargest(1, score_col)
        w = _match_dts(chosen["bench_weight"].to_numpy(), chosen["dts"].to_numpy(), cell_bench_dts)
        w = pd.Series(w * cell_bench_w, index=chosen.index)
        weights.update(dict(zip(chosen["bond_id"], w)))
    w = pd.Series(weights)
    return w / w.sum()


def _match_dts(base: np.ndarray, dts: np.ndarray, target: float) -> np.ndarray:
    """以 w ∝ base × exp(−k × DTS標準化) 傾斜權重，二分搜尋 k 使加權平均 DTS = target。
    target 超出可達範圍時，k 會停在邊界（盡量接近）。"""
    base = base / base.sum()
    if len(dts) == 1 or np.ptp(dts) == 0:
        return base
    x = (dts - dts.mean()) / dts.std()

    def avg_dts(k):
        w = base * np.exp(-k * x)
        return (w * dts).sum() / w.sum()

    lo, hi = -3.0, 3.0  # 限制傾斜幅度，避免權重集中在少數券
    for _ in range(40):
        mid = (lo + hi) / 2
        if avg_dts(mid) > target:
            lo = mid
        else:
            hi = mid
    w = base * np.exp(-lo * x)
    return w / w.sum()


def run_backtest(
    df: pd.DataFrame,
    score_col: str = "score",
    cost_bp: float | pd.Series = 10.0,
    **portfolio_kwargs,
) -> pd.DataFrame:
    """每月月底依訊號建倉，賺下個月的超額報酬。

    cost_bp：單邊交易成本（bp，佔交易金額），可以是常數或以 bond_id 為索引的 Series。
    回傳每月的組合／基準超額報酬、主動報酬、換手率、DTS 比。
    """
    rows = []
    prev_w = pd.Series(dtype=float)
    for date, month in df.groupby("date"):
        month = month.dropna(subset=["fwd_excess_return"])
        if month[score_col].notna().sum() == 0:
            continue
        w = build_portfolio(month, score_col, prev_holdings=set(prev_w.index), **portfolio_kwargs)
        m = month.set_index("bond_id")
        bench_w = m["bench_weight"] / m["bench_weight"].sum()

        trade = w.reindex(w.index.union(prev_w.index), fill_value=0) - prev_w.reindex(
            w.index.union(prev_w.index), fill_value=0
        )
        costs = cost_bp if np.isscalar(cost_bp) else cost_bp.reindex(trade.index).fillna(cost_bp.median())
        cost = (trade.abs() * costs).sum() / 1e4 if len(prev_w) else 0.0

        port_ret = (w * m.loc[w.index, "fwd_excess_return"]).sum() - cost
        bench_ret = (bench_w * m["fwd_excess_return"]).sum()
        rows.append(
            {
                "date": date,
                "portfolio": port_ret,
                "benchmark": bench_ret,
                "active": port_ret - bench_ret,
                "turnover": trade.abs().sum() / 2 if len(prev_w) else np.nan,
                "dts_ratio": (w * m.loc[w.index, "dts"]).sum() / (bench_w * m["dts"]).sum(),
                "n_bonds": len(w),
            }
        )
        prev_w = w
    return pd.DataFrame(rows).set_index("date")


def summarize(result: pd.DataFrame) -> pd.Series:
    """年化主動報酬、追蹤誤差、資訊比率 (IR)、平均換手率與 DTS 比。"""
    active = result["active"]
    te = active.std() * np.sqrt(12)
    return pd.Series(
        {
            "組合年化超額報酬 (bp)": result["portfolio"].mean() * 12 * 1e4,
            "基準年化超額報酬 (bp)": result["benchmark"].mean() * 12 * 1e4,
            "年化主動報酬 (bp)": active.mean() * 12 * 1e4,
            "追蹤誤差 (bp)": te * 1e4,
            "資訊比率 IR": active.mean() * 12 / te if te > 0 else np.nan,
            "月平均換手率": result["turnover"].mean(),
            "平均 DTS 比（組合/基準）": result["dts_ratio"].mean(),
            "平均持有檔數": result["n_bonds"].mean(),
        }
    )


def quintile_returns(df: pd.DataFrame, factor: str, n: int = 5) -> pd.DataFrame:
    """單因子研究：在「評等 × 天期」分群內分 n 組，看下個月平均超額報酬。

    同時回報 DTS 調整後報酬（超額報酬 ÷ DTS × 平均 DTS），檢查因子是否只是在押高 DTS。
    """
    d = df.dropna(subset=[factor, "fwd_excess_return"]).copy()
    d["q"] = d.groupby(["date"] + CELL, observed=True)[factor].transform(
        lambda s: pd.qcut(s.rank(method="first"), n, labels=False) + 1 if len(s) >= n else np.nan
    )
    d = d.dropna(subset=["q"])
    mean_dts = d["dts"].mean()
    d["dts_adj"] = d["fwd_excess_return"] / d["dts"] * mean_dts
    monthly = d.groupby(["date", "q"])[["fwd_excess_return", "dts_adj", "dts"]].mean()
    table = monthly.groupby("q").mean()
    table[["fwd_excess_return", "dts_adj"]] *= 12 * 1e4
    table.columns = ["年化超額報酬 (bp)", "DTS 調整後 (bp)", "平均 DTS"]
    table.index = [f"Q{int(q)}" for q in table.index]
    spread = monthly["fwd_excess_return"].unstack()
    ls = spread[n] - spread[1]
    table.loc[f"Q{n}-Q1"] = [
        ls.mean() * 12 * 1e4,
        (monthly["dts_adj"].unstack()[n] - monthly["dts_adj"].unstack()[1]).mean() * 12 * 1e4,
        np.nan,
    ]
    return table.round(2)
