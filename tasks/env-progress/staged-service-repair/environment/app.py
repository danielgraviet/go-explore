"""Warehouse inventory API. Reads /var/lib/inventory/store.db."""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_PATH = "/var/lib/inventory/store.db"


def _row(sku: str) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.execute(
            "SELECT sku, quantity, lot FROM items WHERE sku = ?",
            (sku,),
        )
        found = cur.fetchone()
    finally:
        con.close()
    if found is None:
        return None
    return {"sku": found[0], "quantity": found[1], "lot": found[2]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            self._send(200, {"ok": True})
            return
        if self.path.startswith("/items/"):
            sku = self.path.split("/items/", 1)[1].strip("/")
            row = _row(sku)
            if row is None:
                self._send(404, {"error": "not found"})
                return
            self._send(200, row)
            return
        self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
