# -*- coding: utf-8 -*-
"""
Precious Metals Context Adapter (Gold & Silver Quant Engine).
Ingests Real Yields (TIP Proxy), Gold ETF & Miners Basket (GLD, IAU, GDX with Beta-Adjusted Model),
US Dollar Index (DXY), Volatility (VIX), Yield Curve Slope (2s10s / 3M10Y), and Economic Calendar.
"""
import datetime
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
import requests
import yfinance as yf
from loguru import logger

from backend.infrastructure.data_providers.adapters.base_adapter import BaseContextAdapter

# Module-level cache to minimize external network requests
_METALS_CACHE: Dict[str, Any] = {
    "report": None,
    "timestamp": 0,
    "batch_df": None,
    "batch_ts": 0,
}
CACHE_TTL_SECONDS = 300  # 5 minutes cache TTL


class PreciousMetalsAdapter(BaseContextAdapter):
    def __init__(self):
        self.VIX_RISK_OFF_THRESHOLD = 20.0
        self.tv_url = "https://economic-calendar.tradingview.com/events"
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/",
        }

    def _get_batch_macro_data(self) -> Dict[str, pd.DataFrame]:
        """
        Unified institutional macro downloader.
        Fetches full 1-month daily series for all 8 core intermarket instruments in a single batch HTTP request:
        - Physical Gold: GLD, IAU
        - Mining Equities: GDX
        - Real Yields: TIP
        - Monetary: ^TNX (10Y), ^IRX (3M T-bill)
        - Sentiment/Currency: ^VIX, DX-Y.NYB (DXY)
        """
        now_ts = time.time()
        if (
            _METALS_CACHE.get("batch_df") is not None
            and (now_ts - _METALS_CACHE.get("batch_ts", 0) < CACHE_TTL_SECONDS)
        ):
            return _METALS_CACHE["batch_df"]

        try:
            tickers = ["GLD", "IAU", "GDX", "TIP", "^TNX", "^IRX", "^VIX", "DX-Y.NYB"]
            df = yf.download(tickers, period="1mo", progress=False)
            if not df.empty and "Close" in df:
                res = {"close": df["Close"], "volume": df.get("Volume", pd.DataFrame())}
                _METALS_CACHE["batch_df"] = res
                _METALS_CACHE["batch_ts"] = now_ts
                return res
        except Exception as e:
            logger.warning(f"Batch macro download error: {e}")

        return {"close": pd.DataFrame(), "volume": pd.DataFrame()}

    # -------------------------------------------------------------
    # 1. Thu thập dữ liệu Lãi suất thực (Real Yields via TIP ETF + Z-Score)
    # -------------------------------------------------------------
    def get_real_yields_state(self) -> Dict[str, Any]:
        """
        Real Yields are the #1 fundamental valuation driver of Gold.
        Uses TIP (iShares TIPS Bond ETF) as an institutional proxy with Dynamic Z-Score:
        - Rising TIP price -> Real Yields falling -> Strongly BULLISH for Gold.
        - Falling TIP price -> Real Yields rising -> BEARISH pressure for Gold.
        """
        try:
            batch = self._get_batch_macro_data()
            close_df = batch.get("close", pd.DataFrame())
            if "TIP" in close_df.columns and not close_df["TIP"].dropna().empty:
                tip_hist = close_df["TIP"].dropna()
            else:
                tip_hist = yf.Ticker("TIP").history(period="1mo")["Close"].dropna()

            if tip_hist.empty or len(tip_hist) < 5:
                return {
                    "state": "Neutral (Steady)",
                    "tip_price": 0.0,
                    "tip_delta_5d": 0.0,
                    "tip_z_score": 0.0,
                    "bias": "NEUTRAL",
                    "reason": "TIP ETF data reloading...",
                }

            tip_curr = float(tip_hist.iloc[-1])
            tip_prev_5d = float(tip_hist.iloc[-5]) if len(tip_hist) >= 5 else float(tip_hist.iloc[0])
            delta_pct = ((tip_curr - tip_prev_5d) / tip_prev_5d) * 100.0

            r_tip = tip_hist.pct_change(fill_method=None).dropna()
            std_r = float(r_tip.std())
            z_score = float((r_tip.iloc[-1] - r_tip.mean()) / std_r) if std_r > 0 else 0.0

            if z_score >= 1.2 or delta_pct > 0.5:
                state = "Crashing Real Yields (Ultra-Bullish Outlier for Gold)"
                bias = "BULLISH"
                reason = f"TIP ETF rose {delta_pct:+.2f}% (5d, Z: {z_score:+.2f}σ) -> Real Yields plunging, massive structural tailwind for Gold."
            elif z_score >= 0.4 or delta_pct > 0.15:
                state = "Declining Real Yields (Bullish for Gold)"
                bias = "BULLISH"
                reason = f"TIP ETF rose {delta_pct:+.2f}% (5d, Z: {z_score:+.2f}σ) -> Real Yields falling, supportive of Gold buyers."
            elif z_score <= -1.2 or delta_pct < -0.5:
                state = "Surging Real Yields (Extreme Bearish Headwind for Gold)"
                bias = "BEARISH"
                reason = f"TIP ETF fell {delta_pct:+.2f}% (5d, Z: {z_score:+.2f}σ) -> Real Yields spiking, major headwind for Gold."
            elif z_score <= -0.4 or delta_pct < -0.15:
                state = "Rising Real Yields (Bearish Pressure)"
                bias = "BEARISH"
                reason = f"TIP ETF fell {delta_pct:+.2f}% (5d, Z: {z_score:+.2f}σ) -> Real Yields rising, creating headwind for Gold."
            else:
                state = "Consolidation / Neutral Real Yields"
                bias = "NEUTRAL"
                reason = f"TIP ETF steady {delta_pct:+.2f}% (5d, Z: {z_score:+.2f}σ) -> Real Yields rangebound."

            return {
                "state": state,
                "tip_price": round(tip_curr, 2),
                "tip_delta_5d": round(delta_pct, 2),
                "tip_z_score": round(z_score, 2),
                "bias": bias,
                "reason": reason,
            }
        except Exception as e:
            return {
                "state": "Neutral (Fallback)",
                "tip_price": 105.0,
                "tip_delta_5d": 0.0,
                "tip_z_score": 0.0,
                "bias": "NEUTRAL",
                "reason": f"Fallback TIP: {str(e)[:40]}",
            }

    # -------------------------------------------------------------
    # 2. Dòng tiền Rổ Quỹ ETF Vàng & Khai thác Mỏ (Beta-Adjusted Econometric Model)
    # -------------------------------------------------------------
    def get_gold_etf_basket_state(self) -> Dict[str, Any]:
        """
        Track institutional flow across Gold ETF & Miners complex with Econometric Beta-Adjusted Model:
        - GLD: SPDR Gold Shares (World's #1 physical gold ETF, ~$60B+ AUM)
        - IAU: iShares Gold Trust by BlackRock (World's #2 physical gold ETF, ~$30B+ AUM)
        - GDX: VanEck Gold Miners ETF (Econometric beta-adjusted leading alpha indicator)
        """
        try:
            batch = self._get_batch_macro_data()
            close_df = batch.get("close", pd.DataFrame())
            vol_df = batch.get("volume", pd.DataFrame())

            if close_df.empty or "GLD" not in close_df.columns:
                df = yf.download(["GLD", "IAU", "GDX"], period="1mo", progress=False)
                close_df = df["Close"]
                vol_df = df["Volume"]

            funds: Dict[str, Dict[str, Any]] = {}
            for ticker in ["GLD", "IAU", "GDX"]:
                try:
                    c = close_df[ticker].dropna()
                    v = vol_df[ticker].dropna() if ticker in vol_df.columns else pd.Series()
                    c_curr = float(c.iloc[-1])
                    c_prev_5d = float(c.iloc[-5]) if len(c) >= 5 else float(c.iloc[0])
                    chg_5d = ((c_curr - c_prev_5d) / c_prev_5d) * 100.0

                    r_fund = c.pct_change(fill_method=None).dropna()
                    std_r = float(r_fund.std())
                    z_ret = float((r_fund.iloc[-1] - r_fund.mean()) / std_r) if std_r > 0 else 0.0

                    if not v.empty:
                        vol_curr = float(v.iloc[-1])
                        vol_avg = float(v.mean())
                        vol_ratio = (vol_curr / vol_avg) if vol_avg > 0 else 1.0
                    else:
                        vol_curr, vol_ratio = 1000000.0, 1.0

                    if z_ret >= 0.8 and vol_ratio >= 1.0:
                        flow = "ACCUMULATION"
                    elif z_ret <= -0.8 and vol_ratio >= 1.0:
                        flow = "DISTRIBUTION"
                    elif chg_5d > 0.5:
                        flow = "ACCUMULATION"
                    elif chg_5d < -0.5:
                        flow = "DISTRIBUTION"
                    else:
                        flow = "NEUTRAL"

                    funds[ticker] = {
                        "price": round(c_curr, 2),
                        "change_5d": round(chg_5d, 2),
                        "vol_ratio": round(vol_ratio, 2),
                        "z_score": round(z_ret, 2),
                        "flow": flow,
                    }
                except Exception:
                    fallback_prices = {"GLD": 382.0, "IAU": 78.0, "GDX": 87.0}
                    funds[ticker] = {
                        "price": fallback_prices.get(ticker, 100.0),
                        "change_5d": 0.0,
                        "vol_ratio": 1.0,
                        "z_score": 0.0,
                        "flow": "NEUTRAL",
                    }

            gld_info = funds.get("GLD", {})
            iau_info = funds.get("IAU", {})
            gdx_info = funds.get("GDX", {})

            # 1. Phân tích đồng thuận ETF Vàng vật chất (Physical Bullion Flow)
            phys_acc = sum(1 for t in ["GLD", "IAU"] if funds.get(t, {}).get("flow") == "ACCUMULATION")
            phys_dist = sum(1 for t in ["GLD", "IAU"] if funds.get(t, {}).get("flow") == "DISTRIBUTION")

            if phys_acc == 2:
                physical_flow = "STRONG_ACCUMULATION"
                phys_desc = "Broad-based institutional bullion accumulation (GLD + IAU)"
            elif phys_acc == 1:
                physical_flow = "NET_ACCUMULATION"
                phys_desc = "Moderate institutional bullion inflow"
            elif phys_dist == 2:
                physical_flow = "STRONG_DISTRIBUTION"
                phys_desc = "Broad-based institutional bullion distribution (GLD + IAU)"
            elif phys_dist == 1:
                physical_flow = "NET_DISTRIBUTION"
                phys_desc = "Moderate institutional bullion outflow"
            else:
                physical_flow = "BALANCED"
                phys_desc = "Physical gold ETF flows neutral/balanced"

            # 2. HỒI QUY KINH TẾ LƯỢNG BÓC TÁCH ALPHA THỢ MỎ (Rolling Beta-Adjusted Model)
            beta = 1.85
            alpha_z = 0.0
            latest_alpha_pct = 0.0
            try:
                gld_c = close_df["GLD"].dropna()
                gdx_c = close_df["GDX"].dropna()
                r_gld = gld_c.pct_change(fill_method=None).dropna()
                r_gdx = gdx_c.pct_change(fill_method=None).dropna()
                common_idx = r_gld.index.intersection(r_gdx.index)
                if len(common_idx) >= 10:
                    rg = r_gld.loc[common_idx]
                    rx = r_gdx.loc[common_idx]
                    var_g = np.var(rg)
                    cov_xg = np.cov(rx, rg)[0, 1]
                    if var_g > 0:
                        beta = float(cov_xg / var_g)
                    alpha_s = rx - beta * rg
                    latest_alpha_pct = float(alpha_s.iloc[-1]) * 100.0
                    std_a = float(alpha_s.std())
                    alpha_z = float((alpha_s.iloc[-1] - alpha_s.mean()) / std_a) if std_a > 0 else 0.0
            except Exception as ex:
                logger.warning(f"Beta regression fallback: {ex}")

            gld_chg = gld_info.get("change_5d", 0.0)
            gdx_chg = gdx_info.get("change_5d", 0.0)
            miners_spread = round(gdx_chg - gld_chg, 2)

            if alpha_z >= 1.2 or (miners_spread >= 2.5 and latest_alpha_pct > 0.5):
                miners_signal = "BULLISH_ALPHA_LEAD"
                miners_desc = f"Miners generating abnormal alpha (Alpha: {latest_alpha_pct:+.2f}%, Z: {alpha_z:+.2f}σ, Beta={beta:.2f}) -> Genuine institutional front-running"
            elif alpha_z <= -1.2 or (miners_spread <= -2.5 and latest_alpha_pct < -0.5):
                miners_signal = "BEARISH_ALPHA_DIVERGENCE"
                miners_desc = f"Miners suffering abnormal negative alpha (Alpha: {latest_alpha_pct:+.2f}%, Z: {alpha_z:+.2f}σ, Beta={beta:.2f}) -> Leading divergence warns of spot exhaustion"
            else:
                miners_signal = "BETA_ALIGNED"
                miners_desc = f"Miners aligned with market beta (Beta={beta:.2f}, Alpha: {latest_alpha_pct:+.2f}%, Z: {alpha_z:+.2f}σ)"

            # 3. Đánh giá Đồng thuận Toàn diện Rổ Quỹ (Composite Quantitative Score)
            z_gld = gld_info.get("z_score", 0.0)
            z_iau = iau_info.get("z_score", 0.0)
            composite_score = round(0.4 * z_gld + 0.3 * z_iau + 0.5 * alpha_z, 2)

            if composite_score >= 0.8:
                composite_stance = "BULLISH_INFLOW"
            elif composite_score <= -0.8:
                composite_stance = "BEARISH_OUTFLOW"
            elif composite_score > 0.2:
                composite_stance = "MILD_ACCUMULATION"
            elif composite_score < -0.2:
                composite_stance = "MILD_DISTRIBUTION"
            else:
                composite_stance = "NEUTRAL"

            return {
                "composite_stance": composite_stance,
                "composite_score": composite_score,
                "physical_flow": physical_flow,
                "physical_desc": phys_desc,
                "miners_signal": miners_signal,
                "miners_desc": miners_desc,
                "miners_spread_5d": miners_spread,
                "miners_beta": round(beta, 2),
                "miners_alpha_pct": round(latest_alpha_pct, 2),
                "miners_alpha_z_score": round(alpha_z, 2),
                "funds": funds,
                # Direct GLD mapping for backward compatibility
                "gld_price": gld_info.get("price", 0.0),
                "gld_change_5d": gld_info.get("change_5d", 0.0),
                "volume_ratio": gld_info.get("vol_ratio", 1.0),
                "flow_status": gld_info.get("flow", "NEUTRAL"),
                "state": f"{composite_stance} ({phys_desc}; {miners_desc})",
                "reason": f"GLD: {gld_info.get('change_5d', 0):+.2f}% (Z: {z_gld:+.2f}σ), GDX Alpha: {latest_alpha_pct:+.2f}% (Z: {alpha_z:+.2f}σ, Beta={beta:.2f})",
            }
        except Exception as e:
            return {
                "composite_stance": "NEUTRAL",
                "composite_score": 0.0,
                "physical_flow": "BALANCED",
                "physical_desc": "Fallback ETF flows",
                "miners_signal": "BETA_ALIGNED",
                "miners_desc": "Fallback Miners alignment",
                "miners_spread_5d": 0.0,
                "miners_beta": 1.85,
                "miners_alpha_pct": 0.0,
                "miners_alpha_z_score": 0.0,
                "funds": {
                    "GLD": {"price": 382.0, "change_5d": 0.0, "vol_ratio": 1.0, "z_score": 0.0, "flow": "NEUTRAL"},
                    "IAU": {"price": 78.0, "change_5d": 0.0, "vol_ratio": 1.0, "z_score": 0.0, "flow": "NEUTRAL"},
                    "GDX": {"price": 87.0, "change_5d": 0.0, "vol_ratio": 1.0, "z_score": 0.0, "flow": "NEUTRAL"},
                },
                "gld_price": 382.0,
                "gld_change_5d": 0.0,
                "volume_ratio": 1.0,
                "flow_status": "NEUTRAL",
                "state": "Balanced (Fallback)",
                "reason": f"Fallback Gold ETF Basket: {str(e)[:40]}",
            }

    def get_gld_flow_state(self) -> Dict[str, Any]:
        """
        Backward-compatible method returning GLD-specific flow state.
        Now backed by the broader multi-ETF basket.
        """
        basket = self.get_gold_etf_basket_state()
        gld_fund = basket.get("funds", {}).get("GLD", {})
        flow_status = gld_fund.get("flow", basket.get("flow_status", "NEUTRAL"))
        return {
            "state": basket.get("state", "Balanced"),
            "gld_price": gld_fund.get("price", basket.get("gld_price", 382.0)),
            "gld_change_5d": gld_fund.get("change_5d", basket.get("gld_change_5d", 0.0)),
            "volume_ratio": gld_fund.get("vol_ratio", basket.get("volume_ratio", 1.0)),
            "flow_status": flow_status,
            "reason": basket.get("reason", "Synchronizing ETF flows..."),
        }

    # -------------------------------------------------------------
    # 3. Trạng thái thị trường vĩ mô (DXY & VIX)
    # -------------------------------------------------------------
    def get_market_state(self) -> Dict[str, Any]:
        try:
            batch = self._get_batch_macro_data()
            close_df = batch.get("close", pd.DataFrame())

            if "^VIX" in close_df.columns and not close_df["^VIX"].dropna().empty:
                vix_hist = close_df["^VIX"].dropna()
            else:
                vix_hist = yf.Ticker("^VIX").history(period="1mo")["Close"].dropna()

            if "DX-Y.NYB" in close_df.columns and not close_df["DX-Y.NYB"].dropna().empty:
                dxy_hist = close_df["DX-Y.NYB"].dropna()
            else:
                dxy_hist = yf.Ticker("DX-Y.NYB").history(period="1mo")["Close"].dropna()

            if vix_hist.empty or dxy_hist.empty:
                return {"state": "UNKNOWN", "vix": 0, "dxy": 0, "dxy_trend": "SIDEWAYS", "reason": "No data"}

            vix_current = float(vix_hist.iloc[-1])
            dxy_current = float(dxy_hist.iloc[-1])
            dxy_prev_5d = float(dxy_hist.iloc[-5]) if len(dxy_hist) >= 5 else float(dxy_hist.iloc[0])
            dxy_trend = "UP" if dxy_current > dxy_prev_5d else "DOWN"

            state = "Risk-Off" if vix_current >= self.VIX_RISK_OFF_THRESHOLD else "Risk-On"

            return {
                "state": state,
                "vix": round(vix_current, 2),
                "dxy": round(dxy_current, 2),
                "dxy_trend": dxy_trend,
                "reason": f"VIX = {vix_current:.2f} ({state}). DXY = {dxy_current:.2f} (5d Trend: {dxy_trend}).",
            }
        except Exception as e:
            return {"state": "UNKNOWN", "vix": 0, "dxy": 0, "dxy_trend": "SIDEWAYS", "reason": str(e)}

    # -------------------------------------------------------------
    # 4. Trạng thái tiền tệ & Độ dốc Đường cong Lợi suất (Yield Curve 2s10s / 3M10Y)
    # -------------------------------------------------------------
    def get_monetary_state(self) -> Dict[str, Any]:
        try:
            batch = self._get_batch_macro_data()
            close_df = batch.get("close", pd.DataFrame())

            if "^TNX" in close_df.columns and not close_df["^TNX"].dropna().empty:
                tnx_hist = close_df["^TNX"].dropna()
            else:
                tnx_hist = yf.Ticker("^TNX").history(period="1mo")["Close"].dropna()

            if tnx_hist.empty:
                return {"state": "UNKNOWN", "us10y": 0, "reason": "No data"}

            tnx_current = float(tnx_hist.iloc[-1])
            tnx_prev_5d = float(tnx_hist.iloc[-5]) if len(tnx_hist) >= 5 else float(tnx_hist.iloc[0])
            delta = tnx_current - tnx_prev_5d

            # Ingest Short-Term 3M Treasury Bill Yield (^IRX) for Yield Curve Analysis
            irx_val = 4.08
            curve_slope = 1.0
            curve_regime = "STEEPENING_CURVE"
            try:
                if "^IRX" in close_df.columns and not close_df["^IRX"].dropna().empty:
                    irx_hist = close_df["^IRX"].dropna()
                    irx_val = float(irx_hist.iloc[-1])
                    curve_slope = round(tnx_current - irx_val, 3)
                    if curve_slope < 0:
                        curve_regime = "INVERTED_CURVE (Recession Risk / Gold Haven)"
                    elif curve_slope > 0.8:
                        curve_regime = "STEEPENING_CURVE (Monetary Easing / Reflation)"
                    else:
                        curve_regime = "FLAT_CURVE"
            except Exception:
                pass

            if delta > 0.1:
                state = f"Hawkish (Yields Rising / Tightening) - {curve_regime}"
            elif delta < -0.1:
                state = f"Dovish (Yields Falling / Easing) - {curve_regime}"
            else:
                state = f"Neutral (Sideways) - {curve_regime}"

            return {
                "state": state,
                "us10y": round(tnx_current, 3),
                "us03m": round(irx_val, 3),
                "curve_slope": round(curve_slope, 3),
                "curve_regime": curve_regime,
                "delta_5d": round(delta, 3),
                "reason": f"US10Y = {tnx_current:.3f}%, 3M = {irx_val:.3f}%, Slope = {curve_slope:+.3f}% ({curve_regime})",
            }
        except Exception as e:
            return {"state": "UNKNOWN", "us10y": 0, "curve_slope": 0.0, "reason": str(e)}

    # -------------------------------------------------------------
    # 5. Lịch kinh tế TradingView & Telegram Scraper
    # -------------------------------------------------------------
    def _fetch_economic_events(self, days_back=30) -> list:
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(days=days_back)
        params = {
            "from": start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "to": now.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "countries": "US",
        }
        events = []
        try:
            res = requests.get(self.tv_url, params=params, headers=self.headers, timeout=5)
            if res.status_code == 200:
                events = res.json().get("result", [])
        except Exception:
            pass

        tele_db_path = Path(__file__).resolve().parents[4] / "data" / "local_calendar.json"
        if tele_db_path.exists():
            try:
                with open(tele_db_path, "r", encoding="utf-8") as f:
                    tele_events = json.load(f)
                events.extend(tele_events)
                events.sort(key=lambda x: x.get("date", ""), reverse=True)
            except Exception:
                pass
        return events

    def get_economic_state(self) -> Dict[str, Any]:
        events = self._fetch_economic_events(45)
        nfp_score, pmi_score, unemp_score = 0, 0, 0

        for e in events:
            title = e.get("title", "").upper()
            actual = e.get("actual")
            forecast = e.get("forecast")
            if actual is None or forecast is None or actual == "" or forecast == "":
                continue
            try:
                act_val = float(actual)
                for_val = float(forecast)
            except Exception:
                continue

            if "NON FARM" in title or "NONFARM" in title:
                nfp_score = 1 if act_val > for_val else -1
            elif "PMI" in title and ("MANUFACTURING" in title or "SERVICES" in title):
                pmi_score = 1 if act_val > 50 else -1
            elif "UNEMPLOYMENT RATE" in title:
                unemp_score = 1 if act_val < for_val else -1

        total = nfp_score + pmi_score + unemp_score
        if total >= 1:
            state = "Growth (Economic Expansion)"
        elif total <= -1:
            state = "Recession (Economic Contraction / Gold Haven)"
        else:
            state = "Recovery (Stabilization / Sideways)"

        return {
            "state": state,
            "reason": f"US Macro Scoreboard - NFP:{nfp_score}, PMI:{pmi_score}, Unemployment:{unemp_score}",
        }

    # -------------------------------------------------------------
    # 6. Tạo báo cáo tổng hợp (Unified Report with Caching)
    # -------------------------------------------------------------
    def generate_context_report(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        now_ts = time.time()
        if _METALS_CACHE["report"] is not None and (now_ts - _METALS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _METALS_CACHE["report"]

        tele_news = "No high-impact breaking news detected in the past 4 hours."
        try:
            tele_file = Path(__file__).resolve().parents[4] / "data" / "news_actual.json"
            if tele_file.exists():
                file_age = now_ts - os.path.getmtime(tele_file)
                if file_age < 4 * 3600:
                    with open(tele_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        tele_news = data.get("actual", tele_news)
                else:
                    os.remove(tele_file)
        except Exception:
            pass

        basket_state = self.get_gold_etf_basket_state()
        report = {
            "asset_class": "COMMODITY_PRECIOUS",
            "symbol": symbol,
            "Real_Yields": self.get_real_yields_state(),
            "Gold_ETF_Basket": basket_state,
            "SPDR_GLD_Flow": self.get_gld_flow_state(),
            "Market": self.get_market_state(),
            "Monetary": self.get_monetary_state(),
            "Economic": self.get_economic_state(),
            "Telegram_News": tele_news,
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        _METALS_CACHE["report"] = report
        _METALS_CACHE["timestamp"] = now_ts
        return report

    # -------------------------------------------------------------
    # 7. Tính toán Macro Bias định lượng cho Vàng
    # -------------------------------------------------------------
    def get_macro_bias(self, symbol: str = "XAUUSD") -> str:
        report = self.generate_context_report(symbol)
        real_y = report.get("Real_Yields", {})
        basket = report.get("Gold_ETF_Basket", {})
        gld = report.get("SPDR_GLD_Flow", {})
        mkt = report.get("Market", {})
        mon = report.get("Monetary", {})

        # Hệ thống chấm điểm trọng số định lượng cho Kim loại quý (Vàng/Bạc):
        score = 0.0

        # Trọng số 1: Lãi suất thực (Real Yields - TIP Proxy) -> Hệ số x2.0
        if real_y.get("bias") == "BULLISH":
            score += 2.0
        elif real_y.get("bias") == "BEARISH":
            score -= 2.0

        # Trọng số 2: DXY Dollar Index -> Hệ số x1.5
        if mkt.get("dxy_trend") == "DOWN":
            score += 1.5
        elif mkt.get("dxy_trend") == "UP":
            score -= 1.5

        # Trọng số 3: VIX (Tâm lý hoảng loạn/trú ẩn) -> Hệ số x1.0
        if mkt.get("state") == "Risk-Off":
            score += 1.0

        # Trọng số 4: Dòng tiền Rổ Quỹ Vàng & Cổ phiếu Khai thác (GLD, IAU, GDX) -> Hệ số x1.5
        if "composite_score" in basket:
            score += float(basket.get("composite_score", 0.0))
        else:
            if gld.get("flow_status") == "ACCUMULATION":
                score += 1.0
            elif gld.get("flow_status") == "DISTRIBUTION":
                score -= 1.0

        # Trọng số 5: Kỳ vọng chính sách tiền tệ US10Y
        if "Dovish" in mon.get("state", ""):
            score += 0.5
        elif "Hawkish" in mon.get("state", ""):
            score -= 0.5

        if score >= 1.5:
            return "BULLISH"
        elif score <= -1.5:
            return "BEARISH"
        return "NEUTRAL"

    # -------------------------------------------------------------
    # 8. Sinh đoạn Prompt chuyên biệt cho AI LLM
    # -------------------------------------------------------------
    def build_prompt_section(self, symbol: str, context_report: Dict[str, Any]) -> str:
        ry = context_report.get("Real_Yields", {})
        basket = context_report.get("Gold_ETF_Basket", {})
        funds = basket.get("funds", {})
        gld_f = funds.get("GLD", {})
        iau_f = funds.get("IAU", {})
        gdx_f = funds.get("GDX", {})
        mkt = context_report.get("Market", {})
        mon = context_report.get("Monetary", {})
        eco = context_report.get("Economic", {})
        news = context_report.get("Telegram_News", "No high-impact breaking news")
        macro_bias = self.get_macro_bias(symbol)

        prompt_part = f"""[INTERMARKET MACRO CONTEXT - PRECIOUS METALS ({symbol})]
- MACRO CONSENSUS BIAS: {macro_bias}
- Real Yields (TIP ETF Proxy): {ry.get('state', 'N/A')} (TIP: ${ry.get('tip_price', 0)}, 5d: {ry.get('tip_delta_5d', 0):+.2f}%, Z-Score: {ry.get('tip_z_score', 0):+.2f}σ)
- Institutional Gold ETF & Miners Basket (Econometric Beta Model):
  * SPDR Gold (GLD): ${gld_f.get('price', 0.0)} ({gld_f.get('change_5d', 0.0):+.2f}%, VolRatio: {gld_f.get('vol_ratio', 1.0):.1f}x, Z: {gld_f.get('z_score', 0):+.2f}σ) -> Flow: {gld_f.get('flow', 'NEUTRAL')}
  * iShares Gold (IAU): ${iau_f.get('price', 0.0)} ({iau_f.get('change_5d', 0.0):+.2f}%, VolRatio: {iau_f.get('vol_ratio', 1.0):.1f}x, Z: {iau_f.get('z_score', 0):+.2f}σ) -> Flow: {iau_f.get('flow', 'NEUTRAL')}
  * VanEck Miners (GDX Beta-Adjusted Lead): ${gdx_f.get('price', 0.0)} ({gdx_f.get('change_5d', 0.0):+.2f}%, VolRatio: {gdx_f.get('vol_ratio', 1.0):.1f}x, Z: {gdx_f.get('z_score', 0):+.2f}σ) -> {basket.get('miners_desc', 'Aligned')}
  * Composite Basket Stance: {basket.get('composite_stance', 'NEUTRAL')} (Score: {basket.get('composite_score', 0):+.2f}, {basket.get('physical_desc', 'Balanced')})
- US Dollar Index (DXY) & Market Risk (VIX): {mkt.get('state', 'N/A')} - {mkt.get('reason', '')}
- Monetary Policy & Yield Curve: {mon.get('state', 'N/A')} ({mon.get('reason', '')})
- Economic Regime: {eco.get('state', 'N/A')} ({eco.get('reason', '')})
- Breaking Macro / Geopolitical News: {news}
"""
        return prompt_part

    # -------------------------------------------------------------
    # 9. Đánh giá quy tắc rủi ro của Vàng tại Decision Gate
    # -------------------------------------------------------------
    def evaluate_risk_rules(self, symbol: str, signal: str, context_report: Dict[str, Any]) -> Tuple[bool, str]:
        macro_bias = self.get_macro_bias(symbol)
        ry = context_report.get("Real_Yields", {})
        basket = context_report.get("Gold_ETF_Basket", {})

        # Quy tắc 1: Cấm mở BUY Vàng nếu Lãi suất thực đang tăng dựng đứng và Macro Bias là BEARISH mạnh
        if signal == "BUY" and macro_bias == "BEARISH" and ry.get("bias") == "BEARISH":
            return False, "BUY Blocked: Real Yields surging & DXY rising. High risk of Gold sell-off."

        # Quy tắc 2: Cấm mở SELL Vàng nếu Lãi suất thực đang cắm đầu rơi và Quỹ Vàng đang gom hàng mạnh
        if signal == "SELL" and macro_bias == "BULLISH" and ry.get("bias") == "BULLISH":
            return False, "SELL Blocked: Real Yields dropping & Gold ETF institutional accumulation. Short squeeze risk."

        # Quy tắc 3: Cảnh báo phân kỳ âm của thợ mỏ (Miners Bearish Divergence) khi cố mở BUY
        if signal == "BUY" and basket.get("miners_signal") == "BEARISH_ALPHA_DIVERGENCE" and macro_bias == "BEARISH":
            return False, f"BUY Blocked: Gold Miners (GDX) suffering negative alpha (Alpha: {basket.get('miners_alpha_pct', 0):+.2f}%, Z: {basket.get('miners_alpha_z_score', 0):+.2f}σ), signaling exhaustion."

        return True, "Passed institutional Precious Metals macro governance rules."
