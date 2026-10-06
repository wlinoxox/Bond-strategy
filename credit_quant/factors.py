"""信用因子計算。

輸入為月資料的長表 (panel)，每列是一檔債券在一個月底的資料。必要欄位：

    date             月底日期
    bond_id          債券代碼
    issuer_id        發行人代碼
    rating           評等分群，例如 "AA", "A", "BBB"
    sector           產業
    oas              選擇權調整後利差 (bp)
    spread_duration  利差存續期間 (年)
    maturity_years   剩餘年限
    excess_return    當月超額報酬（相對同存續期間公債，小數，例如 0.002 = 20bp）

選用欄位（有的話才會計算對應因子）：

    equity_ret_6m    發行公司過去 6 個月股票報酬
    equity_vol       發行公司股票波動度
    leverage         市場槓桿 = 負債 / (負債 + 市值)
"""

import numpy as np
import pandas as pd

MATURITY_BINS = [0, 3, 5, 7, 10, np.inf]
MATURITY_LABELS = ["1-3y", "3-5y", "5-7y", "7-10y", "10y+"]

# 分群內至少要有幾檔債券，z-score 才算可靠；不足時退回較粗的分群
MIN_GROUP_SIZE = 8


def prepare(panel: pd.DataFrame) -> pd.DataFrame:
    """加上 DTS、天期分群與下個月的超額報酬（回測用）。"""
    df = panel.sort_values(["bond_id", "date"]).copy()
    df["dts"] = df["spread_duration"] * df["oas"]
    df["maturity_bucket"] = pd.cut(
        df["maturity_years"], MATURITY_BINS, labels=MATURITY_LABELS
    ).astype(str)
    df["fwd_excess_return"] = df.groupby("bond_id")["excess_return"].shift(-1)
    return df


def zscore_within(df: pd.DataFrame, col: str, groups: list[str], clip: float = 3.0) -> pd.Series:
    """在 date × groups 分群內計算 z-score，截尾到 ±clip。

    分群檔數不足 MIN_GROUP_SIZE 時，逐步去掉最後一個分群欄位重算。
    """
    out = pd.Series(np.nan, index=df.index)
    remaining = df.index
    for k in range(len(groups), -1, -1):
        keys = ["date"] + groups[:k]
        sub = df.loc[remaining]
        g = sub.groupby(keys, observed=True)[col]
        size = g.transform("size")
        ok = size >= MIN_GROUP_SIZE if k > 0 else size > 1
        z = (sub[col] - g.transform("mean")) / g.transform("std")
        out.loc[ok[ok].index] = z[ok]
        remaining = ok[~ok].index
        if len(remaining) == 0:
            break
    return out.clip(-clip, clip)


NEUTRAL_GROUPS = ["rating", "maturity_bucket", "sector"]


def carry_signal(df: pd.DataFrame) -> pd.Series:
    """Carry：同評等、同天期、同產業內的 OAS 高低。用 log 讓分配較對稱。"""
    tmp = df.assign(_log_oas=np.log(df["oas"].clip(lower=1)))
    return zscore_within(tmp, "_log_oas", NEUTRAL_GROUPS)


def value_signal(df: pd.DataFrame) -> pd.Series:
    """Value：每個月做橫斷面迴歸
    log(OAS) ~ 評等 + 產業 + 利差存續期間 (+ 股票波動度)，取殘差（越大越便宜）。
    """
    controls = ["spread_duration"] + (["equity_vol"] if "equity_vol" in df else [])
    resid = pd.Series(np.nan, index=df.index)
    for _, sub in df.groupby("date"):
        sub = sub.dropna(subset=controls + ["oas"])
        if len(sub) < 30:
            continue
        x = pd.get_dummies(sub[["rating", "sector"]], drop_first=True, dtype=float)
        x[controls] = sub[controls]
        x.insert(0, "const", 1.0)
        y = np.log(sub["oas"].clip(lower=1)).to_numpy()
        beta, *_ = np.linalg.lstsq(x.to_numpy(), y, rcond=None)
        resid.loc[sub.index] = y - x.to_numpy() @ beta
    tmp = df.assign(_resid=resid)
    return zscore_within(tmp, "_resid", ["rating"])


def momentum_signal(df: pd.DataFrame, lookback: int = 6, skip: int = 1) -> pd.Series:
    """Momentum：股票動能（有 equity_ret_6m 時）與債券動能各半。

    債券動能 = 過去 lookback 個月的累積超額報酬，跳過最近 skip 個月，
    避免買賣價差反彈與評價價格延遲造成的短期反轉。
    """
    bond_mom = (
        df.groupby("bond_id")["excess_return"]
        .transform(lambda s: s.shift(skip).rolling(lookback - skip, min_periods=lookback - skip).sum())
    )
    # 用 DTS 標準化：高 DTS 的債券本來就波動大
    tmp = df.assign(_bond_mom=bond_mom / df["dts"].clip(lower=1))
    z = zscore_within(tmp, "_bond_mom", NEUTRAL_GROUPS)
    if "equity_ret_6m" in df:
        z_eq = zscore_within(df, "equity_ret_6m", ["rating", "sector"])
        z = pd.concat([z, z_eq], axis=1).mean(axis=1)
    return z


def defensive_signal(df: pd.DataFrame) -> pd.Series:
    """Defensive：同評等內，利差存續期間短、槓桿低者分數高。"""
    parts = [-zscore_within(df, "spread_duration", ["rating"])]
    if "leverage" in df:
        parts.append(-zscore_within(df, "leverage", ["rating", "sector"]))
    return pd.concat(parts, axis=1).mean(axis=1)


FACTORS = {
    "carry": carry_signal,
    "value": value_signal,
    "momentum": momentum_signal,
    "defensive": defensive_signal,
}


def add_factors(df: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """計算各因子與綜合分數。綜合分數先在債券層級加權，再取發行人平均，
    避免同一發行人的多檔債券被重複計算。"""
    weights = weights or {name: 1.0 for name in FACTORS}
    out = df.copy()
    for name in weights:
        out[name] = FACTORS[name](out)
    total = sum(weights.values())
    raw = sum(out[name].fillna(0) * w for name, w in weights.items()) / total
    issuer_avg = raw.groupby([out["date"], out["issuer_id"]]).transform("mean")
    # 發行人分數為主，保留一點債券層級差異（同發行人內選較便宜的券）
    out["score"] = 0.7 * issuer_avg + 0.3 * raw
    return out
