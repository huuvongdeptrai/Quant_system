# -*- coding: utf-8 -*-
"""
DatasetRecorder: Institutional Data Harvesting & LoRA Dataset Synthesizer.
Collects and structures live inference pairs (Preprocessed Context -> AI Decisions -> Real Trade PnL)
for supervised fine-tuning (SFT) and Direct Preference Optimization (DPO) on local LLMs.
"""
import os
import json
import time
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

# Default storage directory
_ROOT_DIR = Path(__file__).resolve().parents[3]
_STORAGE_DIR = _ROOT_DIR / "storage" / "training_data"
_DATASET_FILE = _STORAGE_DIR / "lora_dataset_sft.jsonl"
_TRADE_INDEX_FILE = _STORAGE_DIR / "trade_index.json"


class DatasetRecorder:
    """
    Automated Data Harvester for Quantitative LLM Fine-Tuning.
    Saves prompts, technical/macro features, AI responses, and real trade outcomes.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DatasetRecorder, cls).__new__(cls)
            cls._instance._init_recorder()
        return cls._instance

    def _init_recorder(self):
        try:
            _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create storage directory: {e}")

        self.dataset_file = _DATASET_FILE
        self.index_file = _TRADE_INDEX_FILE

        # In-memory ticket to sample_id map
        self.ticket_map: Dict[int, str] = {}
        self._load_ticket_index()

    def _load_ticket_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.ticket_map = {int(k): str(v) for k, v in data.items()}
            except Exception:
                self.ticket_map = {}

    def _save_ticket_index(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.ticket_map, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save ticket index: {e}")

    def record_inference(
        self,
        symbol: str,
        prompt: str,
        ai_response: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Records a single distilled feature prompt and corresponding AI decision.
        Returns unique sample_id.
        """
        now = datetime.datetime.now()
        sample_id = f"SMP_{symbol}_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        record = {
            "id": sample_id,
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "system": (
                "You are an institutional Quantitative Portfolio Analyst & Risk Strategist. "
                "Analyze the following intermarket and price action inputs. "
                "Return EXACTLY 1 valid JSON object (no markdown, no preamble). "
                "ALL OUTPUT MUST BE IN PROFESSIONAL ENGLISH."
            ),
            "instruction": "Evaluate the quantitative market context and formulate primary and invalidation scenarios.",
            "input": prompt,
            "output": json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else str(ai_response),
            # Standard ShareGPT / OpenAI / Unsloth format
            "conversations": [
                {"from": "human", "value": prompt},
                {"from": "gpt", "value": json.dumps(ai_response, ensure_ascii=False) if isinstance(ai_response, dict) else str(ai_response)},
            ],
            "metadata": metadata or {},
            "trade_outcome": {
                "status": "ANALYSIS_ONLY",
                "ticket": None,
                "entry_price": 0.0,
                "exit_price": 0.0,
                "pnl": 0.0,
                "rr_ratio": 0.0,
                "quality_tag": "NEUTRAL",
            },
        }

        try:
            with open(self.dataset_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug(f"[DatasetRecorder] Recorded inference sample {sample_id} for {symbol}")
        except Exception as e:
            logger.warning(f"[DatasetRecorder] Failed to append sample {sample_id}: {e}")

        return sample_id

    def link_trade_execution(
        self,
        sample_id: str,
        ticket: int,
        entry_price: float,
        sl: float,
        tp: float,
        direction: str,
        lot: float = 0.01,
    ):
        """
        Links an executed MT5 order ticket to an existing inference sample.
        """
        if not sample_id:
            return

        self.ticket_map[int(ticket)] = sample_id
        self._save_ticket_index()

        self._update_record_field(
            sample_id=sample_id,
            updates={
                "trade_outcome.status": "ACTIVE_TRADE",
                "trade_outcome.ticket": int(ticket),
                "trade_outcome.entry_price": round(float(entry_price), 4),
                "trade_outcome.sl": round(float(sl), 4),
                "trade_outcome.tp": round(float(tp), 4),
                "trade_outcome.direction": direction,
                "trade_outcome.lot": round(float(lot), 2),
                "trade_outcome.opened_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        logger.info(f"[DatasetRecorder] Linked ticket #{ticket} to sample {sample_id}")

    def record_trade_outcome(
        self,
        ticket: int,
        pnl: float,
        exit_price: float,
        reason: str = "CLOSED",
    ):
        """
        Updates the dataset record with the actual PnL outcome when the trade exits.
        Labels high R:R wins as GOLDEN_SAMPLE for supervised fine-tuning.
        """
        ticket = int(ticket)
        sample_id = self.ticket_map.get(ticket)
        if not sample_id:
            logger.debug(f"[DatasetRecorder] No sample linked to ticket #{ticket}")
            return

        status = "WIN" if pnl > 0.0 else ("LOSS" if pnl < 0.0 else "BREAKEVEN")
        quality_tag = "GOLDEN_SAMPLE" if (pnl > 0 and "TP" in reason.upper()) else ("INVALIDATION_SAMPLE" if pnl < 0 else "NORMAL")

        self._update_record_field(
            sample_id=sample_id,
            updates={
                "trade_outcome.status": status,
                "trade_outcome.pnl": round(float(pnl), 2),
                "trade_outcome.exit_price": round(float(exit_price), 4),
                "trade_outcome.close_reason": reason,
                "trade_outcome.quality_tag": quality_tag,
                "trade_outcome.closed_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        logger.info(f"[DatasetRecorder] Updated sample {sample_id} with outcome: {status} (PnL: ${pnl:+.2f}, Tag: {quality_tag})")

    def _update_record_field(self, sample_id: str, updates: Dict[str, Any]):
        """
        Thread-safe file update replacing record in jsonl.
        """
        if not self.dataset_file.exists():
            return

        try:
            lines = []
            with open(self.dataset_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            modified = False
            for i, line in enumerate(lines):
                try:
                    obj = json.loads(line)
                    if obj.get("id") == sample_id:
                        for k, v in updates.items():
                            if "." in k:
                                p1, p2 = k.split(".", 1)
                                if p1 not in obj or not isinstance(obj[p1], dict):
                                    obj[p1] = {}
                                obj[p1][p2] = v
                            else:
                                obj[k] = v
                        lines[i] = json.dumps(obj, ensure_ascii=False) + "\n"
                        modified = True
                        break
                except Exception:
                    continue

            if modified:
                with open(self.dataset_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
        except Exception as e:
            logger.warning(f"[DatasetRecorder] Error updating record {sample_id}: {e}")

    def get_dataset_summary(self) -> Dict[str, Any]:
        """
        Returns statistical summary of harvested data.
        """
        if not self.dataset_file.exists():
            return {
                "total_samples": 0,
                "active_trades": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "golden_samples": 0,
                "analysis_only": 0,
                "win_rate": 0.0,
                "file_size_kb": 0.0,
            }

        total, active, wins, losses, be, golden, analysis = 0, 0, 0, 0, 0, 0, 0
        try:
            with open(self.dataset_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    total += 1
                    try:
                        obj = json.loads(line)
                        out = obj.get("trade_outcome", {})
                        st = out.get("status", "ANALYSIS_ONLY")
                        tag = out.get("quality_tag", "")
                        if st == "WIN":
                            wins += 1
                        elif st == "LOSS":
                            losses += 1
                        elif st == "BREAKEVEN":
                            be += 1
                        elif st == "ACTIVE_TRADE":
                            active += 1
                        else:
                            analysis += 1

                        if tag == "GOLDEN_SAMPLE":
                            golden += 1
                    except Exception:
                        pass

            finished = wins + losses
            win_rate = (wins / finished * 100.0) if finished > 0 else 0.0
            size_kb = os.path.getsize(self.dataset_file) / 1024.0

            return {
                "total_samples": total,
                "active_trades": active,
                "wins": wins,
                "losses": losses,
                "breakeven": be,
                "golden_samples": golden,
                "analysis_only": analysis,
                "win_rate": round(win_rate, 1),
                "file_size_kb": round(size_kb, 2),
            }
        except Exception as e:
            logger.warning(f"Error getting dataset summary: {e}")
            return {"total_samples": 0, "error": str(e)}

    def export_golden_samples_for_training(self, output_file: Optional[str] = None) -> str:
        """
        Exports only verified high-quality samples (GOLDEN_SAMPLE & WIN)
        ready for direct drag-and-drop into Google Colab / Unsloth SFTTrainer.
        """
        if output_file is None:
            output_file = str(_STORAGE_DIR / "unsloth_lora_train.json")

        golden_list = []
        if self.dataset_file.exists():
            with open(self.dataset_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        tag = obj.get("trade_outcome", {}).get("quality_tag", "")
                        status = obj.get("trade_outcome", {}).get("status", "")
                        if tag == "GOLDEN_SAMPLE" or status == "WIN":
                            # Unsloth format
                            golden_list.append({
                                "instruction": obj.get("instruction", ""),
                                "input": obj.get("input", ""),
                                "output": obj.get("output", ""),
                            })
                    except Exception:
                        pass

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(golden_list, f, indent=2, ensure_ascii=False)

        logger.info(f"[DatasetRecorder] Exported {len(golden_list)} golden samples to {output_file}")
        return output_file


# Global singleton instance
dataset_recorder = DatasetRecorder()
