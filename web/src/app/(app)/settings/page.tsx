"use client";

import { FormEvent, useEffect, useState } from "react";
import { PageHeader, Panel } from "@/components/ui";

const FX_KEY = "crm_usd_vnd_rate";
const TG_TOKEN_KEY = "crm_telegram_bot_token";
const TG_CHAT_KEY = "crm_telegram_chat_id";

export default function SettingsPage() {
  const [rate, setRate] = useState("25000");
  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [fxSaved, setFxSaved] = useState(false);
  const [tgSaved, setTgSaved] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setRate(localStorage.getItem(FX_KEY) || "25000");
    setToken(localStorage.getItem(TG_TOKEN_KEY) || "");
    setChatId(localStorage.getItem(TG_CHAT_KEY) || "");
  }, []);

  function saveFx(e: FormEvent) {
    e.preventDefault();
    const n = Number(rate);
    if (!Number.isFinite(n) || n <= 0) return;
    localStorage.setItem(FX_KEY, String(n));
    setFxSaved(true);
    window.setTimeout(() => setFxSaved(false), 2000);
  }

  function saveTelegram(e: FormEvent) {
    e.preventDefault();
    localStorage.setItem(TG_TOKEN_KEY, token.trim());
    localStorage.setItem(TG_CHAT_KEY, chatId.trim());
    setTgSaved(true);
    window.setTimeout(() => setTgSaved(false), 2000);
  }

  return (
    <>
      <PageHeader
        title="Settings"
        description="FX display rate and Telegram credentials (stored in this browser). Server-side Telegram send still runs from Streamlit."
      />

      <Panel title="FX">
        <form className="stack" onSubmit={saveFx}>
          <label className="field" style={{ maxWidth: 280 }}>
            <span>USD / VND rate</span>
            <input
              type="number"
              step="1"
              min="1"
              value={rate}
              onChange={(e) => setRate(e.target.value)}
            />
          </label>
          <div className="toolbar">
            <button type="submit" className="btn btn-primary">
              Save exchange rate
            </button>
            {fxSaved ? <span className="muted small">Saved locally.</span> : null}
          </div>
        </form>
      </Panel>

      <Panel title="Telegram">
        <form className="stack" onSubmit={saveTelegram}>
          <label className="field">
            <span>BOT_TOKEN</span>
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="123456:ABC…"
            />
          </label>
          <label className="field" style={{ maxWidth: 320 }}>
            <span>CHAT_ID</span>
            <input
              value={chatId}
              onChange={(e) => setChatId(e.target.value)}
              placeholder="-100…"
            />
          </label>
          <p className="muted small">
            Values are kept in browser localStorage for this device. Reminder
            notifications are still sent from the Streamlit Reminder Center.
          </p>
          <div className="toolbar">
            <button type="submit" className="btn btn-primary">
              Save
            </button>
            {tgSaved ? <span className="muted small">Saved locally.</span> : null}
          </div>
        </form>
      </Panel>
    </>
  );
}
