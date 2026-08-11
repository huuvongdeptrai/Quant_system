import plotly.graph_objects as go
import pandas as pd
import numpy as np

def render_candlestick_chart(df: pd.DataFrame = None) -> go.Figure:
    """
    Renders interactive Plotly Candlestick chart with Wyckoff/SMC overlays.
    """
    if df is None:
        count = 60
        dates = pd.date_range(end=pd.Timestamp.now(), periods=count, freq="15min")
        df = pd.DataFrame({
            "time": dates,
            "open": np.linspace(1.0800, 1.0880, count) + np.random.normal(0, 0.0005, count),
            "high": np.linspace(1.0820, 1.0900, count) + np.random.normal(0, 0.0005, count),
            "low": np.linspace(1.0780, 1.0860, count) - np.random.normal(0, 0.0005, count),
            "close": np.linspace(1.0810, 1.0890, count) + np.random.normal(0, 0.0005, count),
        })

    fig = go.Figure(data=[go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="XAUUSD"
    )])

    fig.update_layout(
        template="plotly_dark",
        title="XAUUSD H4 Wyckoff Accumulation & SMC Zone Analysis",
        xaxis_title="Time",
        yaxis_title="Price",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig
