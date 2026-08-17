"""
StratX Interactive Quant Desk Chat Console (chat_console.py)
Dedicated companion chat terminal for steering the StratX Autonomous Research Desk:
1. Powered by DeepSeek-V4 Flash on Local Ollama for ultra-fast, responsive interactive steering.
2. Directly wired to the live orchestrator loop and physical Vantage Markets MT5 Terminal.
3. Transmits live steering directives instantly to the autonomous discovery loop.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

class Colors:
    WHITE_BOLD  = '\033[1;38;2;255;255;255m'
    WHITE       = '\033[38;2;245;245;245m'
    PURPLE_BOLD = '\033[1;38;2;190;70;255m'
    PURPLE      = '\033[38;2;190;70;255m'
    LIME_BOLD   = '\033[1;38;2;57;255;20m'
    LIME        = '\033[38;2;57;255;20m'
    PINK_BOLD   = '\033[1;38;2;255;110;199m'
    PINK        = '\033[38;2;255;110;199m'
    YELLOW_BOLD = '\033[1;38;2;255;230;50m'
    YELLOW      = '\033[38;2;255;230;50m'
    CYAN_BOLD   = '\033[1;38;2;0;255;255m'
    CYAN        = '\033[38;2;0;255;255m'
    ENDC        = '\033[0m'

DIRECTIVE_FILE = Path("C:/Trading/DE40-Research/directive.txt")

SYSTEM_PROMPT = """You are the StratX Quant Desk Copilot running on DeepSeek-V4 Flash.
You are directly connected to the StratX Autonomous Research Engine and the physical Vantage Markets MT5 Terminal (located at C:\\Users\\Tommy\\AppData\\Roaming\\Vantage Markets MT5 Terminal\\terminal64.exe).

CAPABILITIES & ARCHITECTURE:
- The StratX engine automatically compiles MQL5 EAs via the Vantage MetaEditor CLI (0 errors).
- It physically executes headless backtests inside the user's Vantage MT5 terminal on GER40.s / DE40 historical ticks.
- It parses the actual HTML reports from AppData\\Roaming\\MetaQuotes\\Terminal\\E07A066BDB2C10AD677A715C4DEC32A2.
- The user's chat messages are transmitted live into directive.txt to steer the research loop.

RULES:
1. NEVER output generic AI disclaimers such as "As an AI, I cannot access your terminal or execute tests". The system DOES execute them automatically.
2. Confirm user directives with concise, actionable quantitative responses.
3. If the user asks to test on Vantage MT5, confirm that Vantage Markets MT5 Terminal (E07A066BDB2C10AD677A715C4DEC32A2) is the active execution terminal and report what the orchestrator is doing.
4. Keep explanations sharp, concise, and focused on institutional quant concepts (OLS regression, Volume Profile, Frankfurt ORB, VWAP, SMC sweeps)."""

# Routed to DeepSeek-V4 Flash on Local Ollama
GATEWAYS = [
    {
        "name": "Local Ollama (DeepSeek V4 Flash 0731)",
        "url": "http://127.0.0.1:11434/v1/chat/completions",
        "key": "ollama",
        "model": "deepseek-v4-flash:0731"
    }
]

def stream_flash_desk(user_msg: str):
    for gw in GATEWAYS:
        headers = {
            "Authorization": f"Bearer {gw['key']}",
            "Content-Type": "application/json",
            "Connection": "keep-alive"
        }
        payload = {
            "model": gw["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            "stream": True,
            "temperature": 0.2
        }
        
        req = urllib.request.Request(gw["url"], data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        is_reasoning = False
        is_content = False
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                for line in response:
                    l = line.decode("utf-8").strip()
                    if not l.startswith("data:") or l[5:].strip() == "[DONE]":
                        continue
                    try:
                        data = json.loads(l[5:].strip())
                        delta = data["choices"][0].get("delta", {})
                        r = delta.get("reasoning_content") or delta.get("reasoning", "")
                        c = delta.get("content", "")
                        
                        if r:
                            if not is_reasoning:
                                print(f"\n{Colors.PINK_BOLD}🤔 [THINKING]:{Colors.ENDC}\n", end="", flush=True)
                                is_reasoning = True
                                is_content = False
                            print(f"{Colors.PINK}{r}{Colors.ENDC}", end="", flush=True)
                            
                        if c:
                            if not is_content:
                                print(f"\n\n{Colors.LIME_BOLD}💡 [QUANT DESK]:{Colors.ENDC}\n", end="", flush=True)
                                is_content = True
                                is_reasoning = False
                            print(f"{Colors.WHITE_BOLD}{c}{Colors.ENDC}", end="", flush=True)
                    except Exception:
                        continue
            print("\n", flush=True)
            return
        except Exception as e:
            print(f"\n{Colors.YELLOW}[Notice]: {e}{Colors.ENDC}\n", flush=True)

def main():
    print(f"\n{Colors.PURPLE_BOLD}{'='*60}")
    print(f"   {Colors.WHITE_BOLD}Strat X Quant Desk CHAT{Colors.ENDC}")
    print(f"{Colors.PURPLE_BOLD}{'='*60}{Colors.ENDC}\n")
    print(f"{Colors.WHITE}Commands:{Colors.ENDC}")
    print(f"  • Type {Colors.YELLOW_BOLD}!steer <instruction>{Colors.ENDC} to inject a directive into the research loop.")
    print(f"  • Type any question or message to converse directly with the Quant Desk.")
    print(f"  • Type {Colors.YELLOW_BOLD}exit{Colors.ENDC} to close this chat pane.\n")

    while True:
        try:
            user_input = input(f"{Colors.CYAN_BOLD}Quant > {Colors.ENDC}").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            break

        if user_input.startswith("!steer "):
            directive = user_input[7:].strip()
            DIRECTIVE_FILE.write_text(directive, encoding="utf-8")
            print(f"\n{Colors.LIME_BOLD}✅ [DIRECTIVE TRANSMITTED TO LIVE ORCHESTRATOR]{Colors.ENDC}")
            print(f"{Colors.WHITE}The Head Quant will execute: \"{directive}\" on the next iteration.{Colors.ENDC}\n")
        else:
            DIRECTIVE_FILE.write_text(user_input, encoding="utf-8")
            print(f"\n{Colors.YELLOW}[Transmitted to Loop & Streaming Flash Desk...]{Colors.ENDC}")
            stream_flash_desk(user_input)

if __name__ == "__main__":
    main()
