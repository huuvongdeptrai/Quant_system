import json
import time
from typing import List, Dict, Any

def scrape_financial_news() -> List[Dict[str, Any]]:
    """
    R&D script to fetch market news and economic statements.
    """
    return [
        {
            "timestamp": time.time(),
            "source": "ForexFactory",
            "title": "US CPI Inflation data comes in lower than expected.",
            "content": "Consumer Price Index rose 0.2% month-over-month, below economic consensus of 0.3%."
        }
    ]

def save_to_jsonl(records: List[Dict[str, Any]], output_path: str = "research/macro_dataset.jsonl"):
    with open(output_path, "a", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Saved {len(records)} records to {output_path}")

if __name__ == "__main__":
    records = scrape_financial_news()
    save_to_jsonl(records)
