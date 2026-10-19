#!/usr/bin/env python3
"""Execute plain-Python notebook cells without requiring nbformat/nbclient.

This project notebook intentionally contains no magics. The runner executes code
cells in a shared namespace, captures textual output, persists a partial notebook
on failure, and writes a normal nbformat JSON file on success.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import time
import traceback
from pathlib import Path


def compact_display(value=None, **_: object) -> None:
    if value is None:
        return
    if hasattr(value, "to_string"):
        try:
            print(value.to_string())
            return
        except Exception:
            pass
    print(repr(value))


def stream_output(name: str, text: str) -> dict:
    return {"name": name, "output_type": "stream", "text": text.splitlines(keepends=True)}


def save_notebook(notebook: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(notebook, handle, indent=1, ensure_ascii=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    with args.input.open(encoding="utf-8") as handle:
        notebook = json.load(handle)

    namespace = {
        "__name__": "__main__",
        "__file__": str(args.input.resolve()),
        "display": compact_display,
    }
    started = time.time()
    execution_count = 0
    notebook.setdefault("metadata", {})["stdlib_execution"] = {
        "runner": Path(__file__).name,
        "started_unix": started,
        "python": sys.version,
        "cwd": os.getcwd(),
    }

    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        code = "".join(cell.get("source", []))
        execution_count += 1
        cell["execution_count"] = execution_count
        cell["outputs"] = []
        print(f"[runner] cell {index} start", flush=True)
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(compile(code, f"{args.input.name}:cell-{index}", "exec"), namespace)
        except BaseException as exc:
            out_text = stdout.getvalue()
            err_text = stderr.getvalue()
            if out_text:
                cell["outputs"].append(stream_output("stdout", out_text))
            if err_text:
                cell["outputs"].append(stream_output("stderr", err_text))
            tb = traceback.format_exc()
            cell["outputs"].append({
                "ename": type(exc).__name__,
                "evalue": str(exc),
                "output_type": "error",
                "traceback": tb.splitlines(),
            })
            notebook["metadata"]["stdlib_execution"].update({
                "completed": False,
                "failed_cell": index,
                "elapsed_seconds": time.time() - started,
            })
            save_notebook(notebook, args.output)
            print(f"[runner] cell {index} FAILED; partial notebook: {args.output}", flush=True)
            print(tb, file=sys.stderr, flush=True)
            return 1

        out_text = stdout.getvalue()
        err_text = stderr.getvalue()
        if out_text:
            cell["outputs"].append(stream_output("stdout", out_text))
        if err_text:
            cell["outputs"].append(stream_output("stderr", err_text))
        print(f"[runner] cell {index} done ({len(out_text)} stdout chars)", flush=True)

    notebook["metadata"]["stdlib_execution"].update({
        "completed": True,
        "elapsed_seconds": time.time() - started,
        "code_cells_executed": execution_count,
    })
    save_notebook(notebook, args.output)
    print(f"[runner] complete: {args.output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
