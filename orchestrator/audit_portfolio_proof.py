import sys
import json
from pathlib import Path
sys.path.insert(0, 'C:/Trading/DE40-Research')
from orchestrator.mt5_adapter import write_and_compile_mql5

portfolio_dir = Path('C:/Trading/DE40-Research/Portfolio')
vantage_experts = Path(r'C:\Users\Tommy\AppData\Roaming\MetaQuotes\Terminal\E07A066BDB2C10AD677A715C4DEC32A2\MQL5\Experts')
vantage_experts.mkdir(parents=True, exist_ok=True)

print("=== 1. COMPILING MASTER PORTFOLIO EA & MODULES IN VANTAGE MT5 ===")
master_file = portfolio_dir / 'DE40_X1X_MASTER_PORTFOLIO.mq5'
if master_file.exists():
    ok, log = write_and_compile_mql5(vantage_experts / 'DE40_X1X_MASTER_PORTFOLIO.mq5', master_file.read_text(encoding='utf-8'))
    print(f"Master Portfolio EA Compiled: {ok} | Log: {log}")

for mq5 in portfolio_dir.glob('Module_*.mq5'):
    ok, log = write_and_compile_mql5(vantage_experts / mq5.name, mq5.read_text(encoding='utf-8'))
    print(f"Compiled {mq5.name}: {ok} | Log: {log}")

print("\n=== 2. LISTING COMPILED .EX5 BINARIES IN VANTAGE EXPERTS FOLDER ===")
for f in vantage_experts.glob("*.ex5"):
    print(f"  • {f.name} ({f.stat().st_size} bytes)")

print("\n=== 3. BACKTEST AUDIT TRAIL & VECTOR BRAIN PROOF ===")
brain_file = Path('C:/Trading/DE40-Research/stratx_brain/vector_memory_collection.json')
if brain_file.exists():
    mems = json.loads(brain_file.read_text(encoding='utf-8'))
    print(f"Total Stored Backtest Memories: {len(mems)}")
    for m in mems:
        print(f"  • ID: {m['id']} | Trades: {m.get('total_trades', 0)} | WinRate: {m.get('win_rate', 0)*100:.1f}% | ProfitFactor: {m.get('profit_factor', 0):.2f} | MaxDD: {m.get('max_drawdown', 0)*100:.1f}% | MaxConsecLoss: {m.get('max_consec_losses', 0)} | Status: {m.get('status')} | Confidence: {m.get('confidence', 0):.2f}")
