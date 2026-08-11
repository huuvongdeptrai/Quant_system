import sys
import argparse
import logging
from system.bot_daemon import BotDaemon

def main():
    parser = argparse.ArgumentParser(description="Quant AI Wyckoff Main Entry Point")
    parser.add_argument("--mode", type=str, default="daemon", choices=["daemon", "ui"], help="Run mode: daemon or ui")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info(f"Bootstrapping QUANT_AI_WYCKOFF in '{args.mode}' mode...")

    if args.mode == "daemon":
        daemon = BotDaemon()
        daemon.start()
    elif args.mode == "ui":
        print("To launch Streamlit UI, run: streamlit run app/ui_main.py")

if __name__ == "__main__":
    main()
