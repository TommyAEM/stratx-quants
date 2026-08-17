"""
StratX Fast Isolated Compiler Inner-Loop (compiler_loop.py)
Prevents false L1-L5 strategy escalations on MQL5 syntax errors:
1. Compiles MQL5 via metaeditor64.exe.
2. Parses compile log for exact line errors and warnings.
3. Automatically repairs code via fast isolated LLM feedback loop (DeepSeek Flash) without advancing strategy iteration.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

class MQL5CompilerLoop:
    DEFAULT_METAEDITOR_PATH = Path("C:/Program Files/Vantage Markets MT5 Terminal/metaeditor64.exe")

    def __init__(self, metaeditor_path: Optional[str] = None):
        self.metaeditor_path = Path(metaeditor_path) if metaeditor_path else self.DEFAULT_METAEDITOR_PATH
        if not self.metaeditor_path.exists():
            fallbacks = [
                Path("C:/Program Files/MetaTrader 5/metaeditor64.exe"),
                Path(os.path.expanduser("~")) / "AppData/Roaming/MetaQuotes/Terminal/metaeditor64.exe"
            ]
            for fb in fallbacks:
                if fb.exists():
                    self.metaeditor_path = fb
                    break

    def parse_compile_log(self, log_path: Path) -> Dict[str, Any]:
        """
        Parses MetaEditor compilation log file.
        Returns error count, warning count, and structured error list.
        """
        if not log_path.exists():
            return {
                "success": False,
                "errors": ["Compilation log file not generated."],
                "error_count": 1,
                "warning_count": 0
            }

        content = ""
        for encoding in ["utf-16", "utf-8", "latin-1"]:
            try:
                content = log_path.read_text(encoding=encoding)
                break
            except Exception:
                continue

        lines = content.splitlines()
        errors = []
        warnings = []
        is_success = False

        summary_error_count = None
        summary_warning_count = None

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check summary line: "X error(s), Y warning(s)"
            sum_match = re.search(r"(\d+)\s+error\(s\),\s+(\d+)\s+warning\(s\)", line_str, re.IGNORECASE)
            if sum_match:
                summary_error_count = int(sum_match.group(1))
                summary_warning_count = int(sum_match.group(2))
                if summary_error_count == 0:
                    is_success = True
                continue

            if "0 errors, 0 warnings" in line_str or "Result: 0 errors" in line_str:
                is_success = True
                continue

            if "error" in line_str.lower():
                errors.append(line_str)
            elif "warning" in line_str.lower():
                warnings.append(line_str)

        err_cnt = summary_error_count if summary_error_count is not None else len(errors)
        warn_cnt = summary_warning_count if summary_warning_count is not None else len(warnings)

        return {
            "success": is_success or (err_cnt == 0 and len(lines) > 0),
            "error_count": err_cnt,
            "warning_count": warn_cnt,
            "errors": errors,
            "warnings": warnings,
            "raw_log": content
        }

    def compile_mql5(self, source_path: Path) -> Dict[str, Any]:
        """
        Executes metaeditor64.exe compilation.
        """
        source_path = Path(source_path).resolve()
        log_path = source_path.with_suffix(".log")
        
        if log_path.exists():
            try:
                log_path.unlink()
            except Exception:
                pass

        if not self.metaeditor_path.exists():
            return {
                "compiled": False,
                "error_count": 1,
                "errors": [f"MetaEditor executable not found at {self.metaeditor_path}"]
            }

        cmd = [
            str(self.metaeditor_path),
            f"/compile:{source_path}",
            f"/log:{log_path}"
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, timeout=30)
            log_res = self.parse_compile_log(log_path)
            return {
                "source_path": str(source_path),
                "compiled": log_res["success"],
                "error_count": log_res["error_count"],
                "warning_count": log_res["warning_count"],
                "errors": log_res["errors"],
                "warnings": log_res["warnings"]
            }
        except subprocess.TimeoutExpired:
            return {
                "compiled": False,
                "error_count": 1,
                "errors": ["Compilation timed out after 30 seconds."]
            }
        except Exception as e:
            return {
                "compiled": False,
                "error_count": 1,
                "errors": [f"Compilation execution failed: {str(e)}"]
            }

    def compile_with_repair_loop(
        self,
        source_path: Path,
        llm_client: Any,
        max_repairs: int = 3
    ) -> Dict[str, Any]:
        """
        Fast isolated compiler repair loop:
        If compilation fails, calls DeepSeek Flash to fix syntax errors immediately
        without incrementing strategy iteration or escalating repair ladder.
        """
        source_path = Path(source_path)
        for attempt in range(1, max_repairs + 1):
            compile_res = self.compile_mql5(source_path)
            if compile_res["compiled"]:
                return {
                    "status": "COMPILED_SUCCESSFULLY",
                    "attempts": attempt,
                    "source_path": str(source_path)
                }

            if attempt == max_repairs:
                return {
                    "status": "COMPILATION_FAILED_FATAL",
                    "attempts": attempt,
                    "errors": compile_res["errors"]
                }

            current_code = source_path.read_text(encoding="utf-8")
            messages = [
                {
                    "role": "system",
                    "content": "You are the MQL5 Architect. Your task is to fix compilation syntax errors in MQL5 code. Output complete, corrected MQL5 code only."
                },
                {
                    "role": "user",
                    "content": f"The following MQL5 code failed compilation with these errors:\n{json.dumps(compile_res['errors'], indent=2)}\n\nSource Code:\n```mql5\n{current_code}\n```\nFix the errors and output ONLY the complete corrected MQL5 source code."
                }
            ]
            repair_res = llm_client.call_llm(messages, role_tier="FLASH")
            
            repaired_code = repair_res["content"]
            md_match = re.search(r"```(?:mql5|cpp)?\s*([\s\S]*?)\s*```", repaired_code, re.IGNORECASE)
            if md_match:
                repaired_code = md_match.group(1).strip()
            
            source_path.write_text(repaired_code, encoding="utf-8")

        return {"status": "COMPILATION_FAILED", "errors": compile_res["errors"]}
