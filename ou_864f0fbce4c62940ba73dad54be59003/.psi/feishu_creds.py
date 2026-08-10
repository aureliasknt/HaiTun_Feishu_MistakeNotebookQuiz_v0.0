"""Extract Feishu app credentials from the running Channel process and run a feishu tool call.

Usage:
    python feishu_creds.py <module_function> <json_args>
Example:
    python feishu_creds.py feishu_bitable_list_tables '{"app_token": "..."}'
"""
import asyncio
import importlib
import json
import os
import subprocess
import sys

TOOLS_DIR = r"D:\haitun agent\psi-agent\examples\haitun-workspace\tools"


def _channel_creds():
    """Find the running `channel feishu` process and read --app-id/--app-secret."""
    out = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'channel feishu' } | "
            "ForEach-Object { $_.CommandLine }",
        ],
        capture_output=True, text=True, timeout=30,
    )
    app_id = app_secret = None
    for line in (out.stdout or "").splitlines():
        m = __import__("re").search(r"--app-id\s+(\S+)", line)
        if m:
            app_id = m.group(1)
        m = __import__("re").search(r"--app-secret\s+(\S+)", line)
        if m:
            app_secret = m.group(1)
        if app_id and app_secret:
            break
    return app_id, app_secret


def main():
    func_name = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    app_id, app_secret = _channel_creds()
    if not app_id or not app_secret:
        print(json.dumps({"ok": False, "message": "channel creds not found"}))
        return 1
    os.environ["PSI_FEISHU_APP_ID"] = app_id
    os.environ["PSI_FEISHU_APP_SECRET"] = app_secret
    sys.path.insert(0, TOOLS_DIR)
    mod = importlib.import_module(func_name.split(".")[0] if "." in func_name else func_name)
    fn = getattr(mod, func_name.split(".")[-1] if "." in func_name else func_name)
    result = asyncio.run(fn(**args))
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
