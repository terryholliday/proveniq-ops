"use client";

import { useState } from "react";

type Props = {
  assetId: string;
};

function opsApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_OPS_API_BASE_URL || "http://127.0.0.1:8012";
}

export function BeginInventoryScanButton({ assetId }: Props) {
  const [status, setStatus] = useState<"idle" | "starting" | "started" | "error">("idle");
  const [message, setMessage] = useState<string>("");

  async function onClick() {
    setStatus("starting");
    setMessage("");

    try {
      const base = opsApiBaseUrl();

      const tipRes = await fetch(`${base}/v1/ops/assets/${assetId}/tip`, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
      });

      if (!tipRes.ok) {
        const text = await tipRes.text();
        throw new Error(`tip:${tipRes.status}:${text}`);
      }

      const tip = (await tipRes.json()) as { aggregate_version: number };
      const ifMatch = String(tip.aggregate_version ?? 0);
      const ifMatchHeader = `"${ifMatch}"`;

      const idempotencyKey = globalThis.crypto?.randomUUID
        ? globalThis.crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

      const body = {
        event_type: "INVENTORY_SCAN_STARTED",
        evidence: {
          policy: "OPTIONAL",
          evidence_hash: `sha256:${"0".repeat(64)}`,
          waiver_reason: null,
        },
        payload: {
          scan_scope: "LOCATION",
          source: "OPS_DASHBOARD",
        },
      };

      const res = await fetch(`${base}/v1/ops/assets/${assetId}/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "If-Match": ifMatchHeader,
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`append:${res.status}:${text}`);
      }

      const envelope = (await res.json()) as { event_id?: string; aggregate_version?: number };
      setStatus("started");
      setMessage(`Scan started. v${envelope.aggregate_version ?? "?"} • ${envelope.event_id ?? ""}`);
    } catch (e: any) {
      setStatus("error");
      setMessage(e?.message || "Failed to start scan");
    }
  }

  return (
    <div className="space-y-3">
      <button
        onClick={onClick}
        disabled={status === "starting"}
        className={`w-full px-3 py-2 rounded text-sm font-medium border ${
          status === "starting"
            ? "bg-gray-800 text-gray-400 border-gray-700"
            : "bg-emerald-600 text-white border-emerald-500 hover:bg-emerald-500"
        }`}
      >
        {status === "starting" ? "Starting…" : "Begin Inventory Scan"}
      </button>

      {message ? (
        <div
          className={`text-xs font-mono rounded p-2 border ${
            status === "error"
              ? "bg-red-900/20 border-red-800 text-red-400"
              : "bg-gray-900/50 border-gray-700 text-gray-300"
          }`}
        >
          {message}
        </div>
      ) : null}
    </div>
  );
}
