import sys
from pathlib import Path

def main():
    path = Path("Kho_Do_An/Quant_AI_V2.2/research/build_ch4_perfect.py")
    content = open(path, "r", encoding="utf-8").read()
    
    # Replace "dưới .0" with "dưới $5.0"
    content = content.replace("dưới .0", "dưới $5.0")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed $5.0 in build_ch4_perfect.py successfully")

if __name__ == "__main__":
    main()
