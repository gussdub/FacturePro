import React, { useState, useEffect } from "react";
import axios from "axios";
import { BACKEND_URL } from "../config";

export default function BankSuggestionsActions({ tx, onMatched, onIgnore, onOpenManual, onOpenCreate }) {
  const [suggestions, setSuggestions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${BACKEND_URL}/api/bank/transactions/${tx.id}/suggestions`)
      .then(r => { if (!cancelled) setSuggestions(r.data); })
      .catch(() => { if (!cancelled) setSuggestions({ invoices: [], expenses: [] }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tx.id]);

  const confirm = async (kind, target_id) => {
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/match`,
        { kind, target_id });
      onMatched();
    } catch (e) {
      window.alert(e.response?.data?.detail || "Erreur de matching");
    } finally { setBusy(false); }
  };

  if (loading) return <small style={{ color: "#6b7280" }}>Chargement…</small>;
  const top = suggestions?.invoices?.[0] || suggestions?.expenses?.[0];
  const isCredit = (tx.amount_cad || 0) > 0;

  return (
    <div style={{ marginTop: 6, display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
      {top && top.invoice && (
        <>
          <small style={{ flex: 1, minWidth: 200 }}>
            <strong>{top.invoice.invoice_number}</strong> — {top.client_name}{" "}
            ({Number(top.invoice.outstanding_cad ?? top.invoice.total).toFixed(2)} $)
          </small>
          <button onClick={() => confirm("invoice_payment", top.invoice.id)} disabled={busy} style={btnGreen}>
            Confirmer
          </button>
        </>
      )}
      {top && top.expense && (
        <>
          <small style={{ flex: 1, minWidth: 200 }}>
            {top.expense.vendor || top.expense.description}{" "}
            ({Number(top.expense.amount_cad).toFixed(2)} $)
          </small>
          <button onClick={() => confirm("expense", top.expense.id)} disabled={busy} style={btnGreen}>
            Confirmer
          </button>
        </>
      )}
      <button onClick={onOpenManual} disabled={busy} style={btnGray}>Chercher</button>
      <button onClick={onOpenCreate} disabled={busy} style={btnGray}>
        Créer {isCredit ? "facture" : "dépense"}
      </button>
      <button onClick={onIgnore} disabled={busy} style={btnGray}>Ignorer</button>
    </div>
  );
}

const btnGreen = { background: "#059669", color: "#fff", border: "none",
                   padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 };
const btnGray = { background: "#e5e7eb", border: "none",
                  padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 };
