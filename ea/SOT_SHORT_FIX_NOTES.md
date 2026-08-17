# SOT Short-Side Fidelity Fix Notes

EA: `ea/DE40_SOT_HOST_v0.1.mq5` (module S = SOT v4.0 GER40 port).
Reference (READ-ONLY ground truth): `C:\Trading\Terminal-X-V2-Recovered\engine_py\`
(`intensity.py`, `fvg.py`, `breakretest.py`, `impulse.py`, `filters.py`,
`orchestrator.py`, `config.py`) + `verified_configs/GER40.json`.
Spec applied: `C:\tmp\S1_SOT_SHORT_FIX_SPEC.md` (supervisor-adjudicated).
Trigger: MT5 parity 2025-08-01..2026-07-02 — shorts 6 @ 0% WR vs engine-X shorts
21 @ 76.2% (longs ported OK: 30 vs 29).

## PRIMARY FIX — spurious H4 confluence gate (short killer)

| Item | Before | After | Engine reference |
|------|--------|-------|------------------|
| `InpSotUseConf` default | `input bool InpSotUseConf = true;` (line 237) | `= false;` | `config.py:336-347` — `resolve_confluence_symbol("GER40")` returns `None` (empty custom symbol, not in `_AUTO_CONFLUENCE`), so `load_overrides()` forces `use_confluence=False`; Pine's `confluenceUsable` is TRANSPARENT for unmappable symbols (`StratX_V1_Builder.pine:1503`). `orchestrator.py:263-265` → `conf_buy/conf_sell = all True`. |
| `SotConfPass` sign | kept | reverted to original (short needs falling slope `b[0] < b[lookback]`) — sign was already CONSISTENT, per spec "do NOT invert". | — |

## SECONDARY symmetric fidelity fixes (both sides)

### B — Imbalance (FVG) (`SotScanBLong` / `SotScanBShort`)
| Fix | Before | After | Engine reference |
|-----|--------|-------|------------------|
| Gap anchors | `low[m-1]` vs `high[m+1]` (1-bar mis-wire) | bull `low[m] > high[m+2]`; bear `high[m] < low[m+2]` | `fvg.py:57-58` (`h[i-2]<l[i]` / `l[i-2]>h[i]`) |
| Zone edges | `top=low[m-1]/bot=high[m+1]` etc. | bull `top=low[m]`, `bot=high[m+2]`; bear `top=low[m+2]`, `bot=high[m]` | `fvg.py:60-77` |
| Zone-creation impulse mult | `1.3` (`InpSotImpBodyMult`) | `InpSotDispMult = 1.5` (new input) | config `"Impulse Size x Avg Body" = 1.5` = `disp_mult` |
| Arming | absent | armed only after close beyond far edge (bull `close>top`; bear `close<bot`) | `fvg.py:79-81` |
| Touch depth | near edge (bull `tLow>zoneTop` / bear `tHigh<zoneBot`) | far edge: bull `low[1]<=zoneBot`; bear `high[1]>=zoneTop` | `orchestrator.py:86-92` |
| Mitigation guard | over-strict historical midpoint scan | 2-bar far-edge rule (bull `c[2]<bot && c[1]<bot`; bear `c[2]>top && c[1]>top`) | `orchestrator.py:95-102` |
| Min gap 0.15 ATR | enforced | removed (input kept, default 0.0) | `fvg.py` has no min-gap |
| Staleness | `m in [3..15]` | `m in [2..14]` | `fvg_max_bars=14` |
| Recency gate | absent | added `SotRecentImpulse(dir)` (1.3 × sma(body,14)), window `j∈[2..14]` | `impulse.py:16-46` + `orchestrator.py:105-120` |

### D — Break & Retest (`SotScanDLong` / `SotScanDShort`)
| Fix | Before | After | Engine reference |
|-----|--------|-------|------------------|
| Entry timing | trigger-candle-break (`close[1]>high[r]` / `<low[r]`) | removed; fires on retest bar (Touch) | `breakretest.py:72-77,103-108` (`entry_timing=="Touch"`) |
| Retest | two-sided band `[level-tol, level]` / `[level, level+tol]` | one-sided: long `low[1]<=level+tol`; short `high[1]>=level-tol` | `breakretest.py:71,102` |
| Break recency | `b in [3..38]` | `b in [2..InpSotDMaxBarsAfterBreak+1]` = `[2..9]` | `breakretest.py:60-61,91-92` (max_bars=8) |
| Impulse filter | break-bar body `>=1.3*avgBody` | removed; recency gate `SotRecentImpulse(dir)` (gated by `InpSotDImpFilter`) | `impulse.py` recency, not break-bar body |

### Router + news (`SotEngine`)
| Fix | Before | After | Engine reference |
|-----|--------|-------|------------------|
| Router priority | B before D | D before B | `orchestrator.py:311-316` (B&R > Imbalance) |
| News block | `if(!SotNewsPass(gmtMin)) return;` | removed | `orchestrator.py:203-210` (news windows cosmetic-only) |

## Branches verified as correct (per spec — unchanged)

- `SotTrendDir` (signs + 1-bar lag correct: `f>s -> long`, `f<s -> short`).
- SL/TP geometry (ATR6 ×1.7, RR 1.0), sessions/day/NATR gates, magic/mask,
  Modules A–H, host shell.

## Compile

```
Result: 0 errors, 0 warnings, cpu='X64 Regular'
```
Log: `ea\sot_shortfix_compile.log`.