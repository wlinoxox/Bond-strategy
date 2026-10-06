"""用模擬資料跑一遍完整流程：因子計算 → 單因子五分位 → 多因子選券回測。

執行（在 repo 根目錄）：
    python -m credit_quant.demo

模擬資料刻意放進 value（錯價均值回歸）、股票動能外溢與 carry（利差高於預期違約損失）三種效果，
只是用來確認程式能跑、輸出長什麼樣子，數字本身沒有任何實證意義。
實際使用時，把 make_synthetic_panel() 換成自己的月資料即可（欄位見 factors.py）。
"""

import numpy as np
import pandas as pd

from .backtest import quintile_returns, run_backtest, summarize
from .factors import FACTORS, add_factors, prepare

RATINGS = {"AA": (60, 0.0002, 0.25), "A": (90, 0.0006, 0.35), "BBB": (140, 0.0018, 0.45)}
SECTORS = ["金融", "工業", "公用事業", "能源", "科技", "消費"]


def make_synthetic_panel(n_issuers=150, n_months=72, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rating = rng.choice(list(RATINGS), n_issuers, p=[0.15, 0.4, 0.45])
    sector = rng.choice(SECTORS, n_issuers)
    leverage = np.array([RATINGS[r][2] for r in rating]) + rng.normal(0, 0.08, n_issuers)
    equity_vol = 0.2 + leverage * 0.3 + rng.normal(0, 0.03, n_issuers)

    bonds = []
    for i in range(n_issuers):
        for k in range(rng.integers(1, 5)):
            bonds.append(
                {"issuer": i, "seq": k, "maturity": rng.uniform(1.5, 30), "amt": rng.lognormal(6.5, 0.6)}
            )
    bonds = pd.DataFrame(bonds)
    bond_ver = np.zeros(len(bonds), dtype=int)

    u = rng.normal(0, 0.15, n_issuers)  # 持續性的發行人溢酬（基本面），會累積股票訊號帶來的變化
    v = rng.normal(0, 0.04, n_issuers)  # 暫時性的錯價，會均值回歸 → value 效果
    mkt = 0.0  # 整體信用利差水準（log）
    eq_shocks = [rng.normal(0, 0.08, n_issuers) for _ in range(6)]
    dates = pd.date_range("2019-01-31", periods=n_months, freq="ME")

    rows, prev = [], None
    for t, date in enumerate(dates):
        if t > 0:
            mkt = 0.97 * mkt + rng.normal(0, 0.06)
            # 上個月股票表現好 → 這個月利差收窄（股票動能外溢）
            u = 0.98 * u - 0.05 * eq_shocks[-1] + rng.normal(0, 0.02, n_issuers)
            v = 0.85 * v + rng.normal(0, 0.02, n_issuers)
            bonds["maturity"] -= 1 / 12
            matured = bonds["maturity"] < 1
            bonds.loc[matured, "maturity"] = rng.uniform(5, 30, matured.sum())
            bond_ver[matured.to_numpy()] += 1
            eq_shocks = eq_shocks[1:] + [rng.normal(0, 0.08, n_issuers)]
        eq_6m = np.sum(eq_shocks, axis=0)

        base = np.array([RATINGS[rating[i]][0] for i in bonds["issuer"]])
        mat = bonds["maturity"].to_numpy()
        iss = bonds["issuer"].to_numpy()
        noise = rng.normal(0, 0.005, len(bonds))  # 報價雜訊，會造成短期反轉
        oas = base * (1 + 0.12 * np.sqrt(mat)) * np.exp(mkt + u[iss] + v[iss] + noise)
        sd = np.minimum(mat, 22) * 0.85
        bond_id = [f"B{i:03d}-{s}-{ver}" for i, s, ver in zip(iss, bonds["seq"], bond_ver)]

        cur = pd.DataFrame(
            {
                "date": date,
                "bond_id": bond_id,
                "issuer_id": [f"I{i:03d}" for i in iss],
                "rating": rating[iss],
                "sector": sector[iss],
                "oas": oas,
                "spread_duration": sd,
                "maturity_years": mat,
                "bench_weight": bonds["amt"].to_numpy(),
                "equity_ret_6m": eq_6m[iss],
                "equity_vol": equity_vol[iss],
                "leverage": leverage[iss],
            }
        )
        if prev is not None:
            p = prev.set_index("bond_id")
            same = cur["bond_id"].isin(p.index)
            po = p.reindex(cur["bond_id"])
            el = np.array([RATINGS[r][1] for r in cur["rating"]]) / 12
            ret = po["oas"].to_numpy() / 1e4 / 12 - po["spread_duration"].to_numpy() * (
                cur["oas"].to_numpy() - po["oas"].to_numpy()
            ) / 1e4 - el
            cur["excess_return"] = np.where(same, ret, np.nan)
        else:
            cur["excess_return"] = np.nan
        rows.append(cur)
        prev = cur
    return pd.concat(rows, ignore_index=True)


def main():
    pd.set_option("display.width", 120)
    panel = make_synthetic_panel()
    df = add_factors(prepare(panel))
    df = df[df["date"] >= df["date"].min() + pd.DateOffset(months=7)]  # 動能需要歷史資料

    print(f"模擬資料：{df['bond_id'].nunique()} 檔債券、{df['issuer_id'].nunique()} 個發行人、"
          f"{df['date'].nunique()} 個月\n")
    for f in list(FACTORS) + ["score"]:
        print(f"== {f}：分群內五分位，下個月超額報酬 ==")
        print(quintile_returns(df, f), "\n")

    print("== 多因子選券 vs. 基準（單邊成本 10bp）==")
    result = run_backtest(df, cost_bp=10.0)
    print(summarize(result).round(2).to_string())


if __name__ == "__main__":
    main()
