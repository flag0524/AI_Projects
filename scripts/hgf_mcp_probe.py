"""Higgsfield MCP 라이브 플로우 프로브 — 전체 try-on 경로 검증.

mcp.higgsfield.ai/mcp (JSON-RPC over streamable HTTP, Bearer 인증)로:
  initialize → media_upload → PUT → media_confirm → generate_image → poll → download

이 스크립트가 검증한 호출 형태를 higgsfield_provider MCP 클라이언트로 옮긴다.
실제 외부 호출 + 크레딧 소모. 키는 인자 또는 .env에서.
"""
import os
import sys
import io
import json
import time
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("HIGGSFIELD_API_KEY", "")
URL = os.environ.get("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp")
H = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {KEY}",
}


def _parse_sse(text):
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    return {"raw": text[:300]}


def _rpc(client, method, params=None, rid=None):
    body = {"jsonrpc": "2.0", "method": method}
    if rid is not None:
        body["id"] = rid
    if params is not None:
        body["params"] = params
    r = client.post(URL, headers=H, json=body)
    r.raise_for_status()
    return _parse_sse(r.text) if r.text else {}


def _tool(client, name, args, rid):
    d = _rpc(client, "tools/call", {"name": name, "arguments": args}, rid)
    res = d.get("result", {})
    if res.get("isError"):
        raise RuntimeError(f"{name} error: {res}")
    return res.get("structuredContent") or {}


def main():
    model_path = ROOT / "backend" / "assets" / "templates" / "model_neutral.jpg"
    top_path = ROOT / "input" / "real" / "top.png"

    with httpx.Client(timeout=60) as c:
        _rpc(c, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "probe", "version": "0"}}, rid=1)
        _rpc(c, "notifications/initialized")

        # 1) media_upload
        up = _tool(c, "media_upload", {"files": [
            {"filename": "model.jpg", "content_type": "image/jpeg"},
            {"filename": "top.png", "content_type": "image/png"},
        ]}, rid=2)
        uploads = up["uploads"]
        print("uploads:", [u["media_id"] for u in uploads])

        # 2) PUT bytes
        for u, path in zip(uploads, [model_path, top_path]):
            data = path.read_bytes()
            r = httpx.put(u["upload_url"], headers={"Content-Type": u["content_type"]},
                          content=data, timeout=60)
            print("PUT", path.name, r.status_code)

        # 3) media_confirm
        ids = [u["media_id"] for u in uploads]
        _tool(c, "media_confirm", {"type": "image", "media_ids": ids}, rid=3)
        print("confirmed")

        # 4) generate_image (단일-호출 다중입력)
        gen = _tool(c, "generate_image", {"params": {
            "model": os.environ.get("HIGGSFIELD_TRYON_MODEL", "nano_banana_pro"),
            "prompt": "Full-body fashion photo of the model from the first image "
                      "wearing the exact white blouse from the second image. "
                      "Preserve garment details. Neutral studio background, front view.",
            "aspect_ratio": "2:3",
            "medias": [{"value": ids[0], "role": "image"},
                       {"value": ids[1], "role": "image"}],
        }}, rid=4)
        job_id = gen["results"][0]["id"]
        print("job:", job_id, "status:", gen["results"][0]["status"])

        # 5) poll job_display
        url = None
        for _ in range(40):
            time.sleep(3)
            disp = _tool(c, "job_display", {"id": job_id}, rid=5)
            st = disp["results"][0]["status"]
            print("  poll:", st)
            if st == "completed":
                url = disp["results"][0]["results"]["rawUrl"]
                break
            if st in ("failed", "nsfw", "canceled", "cancelled"):
                raise RuntimeError(f"job {st}")
        if not url:
            raise RuntimeError("poll timeout")

        # 6) download
        img_bytes = httpx.get(url, timeout=60).content
        out = ROOT / "output" / "mcp_probe_result.png"
        Image.open(io.BytesIO(img_bytes)).convert("RGB").save(out)
        print("SAVED", out)


if __name__ == "__main__":
    main()
