"""RTL Generation Agent (SCRUM-25): natural-language request -> saved .v file."""
import re
import sys
from pathlib import Path

from agents.gemini_client import GeminiClient

ROOT = Path(__file__).resolve().parents[2]
PROMPT_VERSION = "v1.0"
PROMPT_PATH = ROOT / "prompts" / "rtl_gen" / PROMPT_VERSION / "system_prompt.md"
OUTPUT_DIR = ROOT / "outputs"


class RTLGenerationError(Exception):
    """Raised when the model reply is not a usable Verilog module."""


def load_system_prompt(path=PROMPT_PATH) -> str:
    return Path(path).read_text(encoding="utf-8")


def extract_verilog(text: str) -> str:
    match = re.search(
        r"```(?:verilog|systemverilog|v)?[ \t]*\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    return (match.group(1) if match else text).strip()


def validate_verilog(code: str) -> str:
    """Cheap guard against bad LLM output. Returns the module name or raises."""
    modules = re.findall(r"^\s*module\s+(\w+)", code, re.MULTILINE)
    ends = re.findall(r"^\s*endmodule\b", code, re.MULTILINE)
    if len(modules) != 1 or len(ends) != 1:
        raise RTLGenerationError(
            f"Expected exactly one module/endmodule, found {len(modules)}/{len(ends)}"
        )
    return modules[0]


def generate_rtl(request: str, client=None, out_dir=OUTPUT_DIR) -> Path:
    client = client or GeminiClient()
    prompt = f"{load_system_prompt()}\n\n---\nHARDWARE REQUEST:\n{request}"
    raw = client.generate(prompt)
    code = extract_verilog(raw)
    name = validate_verilog(code)  # reject before writing anything to disk
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.v"
    path.write_text(code + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) or "8-bit synchronous counter with asynchronous reset"
    print("Saved:", generate_rtl(request))