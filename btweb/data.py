from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OhlcvDaily


def load_ohlcv_dataframe(
    session: Session, *, symbol: str, start_date: date, end_date: date
) -> pd.DataFrame | None:
    stmt = (
        select(
            OhlcvDaily.trade_date,
            OhlcvDaily.open,
            OhlcvDaily.high,
            OhlcvDaily.low,
            OhlcvDaily.close,
            OhlcvDaily.volume,
        )
        .where(OhlcvDaily.symbol == symbol)
        .where(OhlcvDaily.trade_date >= start_date)
        .where(OhlcvDaily.trade_date <= end_date)
        .order_by(OhlcvDaily.trade_date.asc())
    )

    rows = session.execute(stmt).all()
    if not rows:
        return None

    df = pd.DataFrame(
        rows, columns=["trade_date", "open", "high", "low", "close", "volume"]
    )
    df["datetime"] = pd.to_datetime(df["trade_date"])
    df = df.drop(columns=["trade_date"]).set_index("datetime")
    df["openinterest"] = 0
    return df

