import React, { useState, useEffect } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankManualSearchModal({ tx, onClose, onMatched }) {
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const isCredit = (tx.amount_cad || 0) > 0;

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        if (isCredit) {
          const invs = (await axios.get(`${BACKEND_URL}/api/invoices`)).data || [];
          const eligible = invs.filter(i => ["sent", "partial", "overdue"].includes(i.status));
          setResults(eligible.map(i => ({
            kind: "invoice_payment", id: i.id,
            label: `${i.invoice_number} — Total ${Number(i.total).toFixed(2)} $ — Solde ${Number(i.outstanding_cad ?? i.total).toFixed(2)} $`,
          })));
        } else {
          const exps = (await axios.get(`${BACKEND_URL}/api/expenses`)).data || [];
          const eligible = exps.filter(e => !e.bank_transaction_id);
          setResults(eligible.map(e => ({
            kind: "expense", id: e.id,
            label: `${e.expense_date || e.date || "—"} — ${e.vendor || e.description || "(sans nom)"} — ${Number(e.amount_cad).toFixed(2)} $`,
          })));
        }
      } finally { setLoading(false); }
    })();
  }, [tx.id, isCredit]);

  const match = async (kind, target_id) => {
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/match`,
        { kind, target_id });
      onMatched();
    } catch (e) {
      window.alert(e.response?.data?.detail || "Erreur de matching");
      setBusy(false);
    }
  };

  const filtered = results.filter(r => r.label.toLowerCase().includes(search.toLowerCase()));

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Chercher {isCredit ? "une facture" : "une dépense"}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ background: "#f8fafb", padding: 10, borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
          {tx.date} — {tx.description} ({Math.abs(tx.amount_cad).toFixed(2)} $)
        </div>
        <input placeholder="Filtrer…" value={search} onChange={(e) => setSearch(e.target.value)}
               style={{ width: "100%", padding: 6, marginBottom: 12, border: "1px solid #d1d5db", borderRadius: 4 }} />
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          {loading && <p>Chargement…</p>}
          {!loading && filtered.map(r => (
            <div key={r.id} onClick={() => !busy && match(r.kind, r.id)}
                 style={{ padding: 8, borderBottom: "1px solid #e5e7eb", cursor: busy ? "wait" : "pointer", fontSize: 13 }}
                 onMouseEnter={(e) => e.currentTarget.style.background = "#f3f4f6"}
                 onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              {r.label}
            </div>
          ))}
          {!loading && filtered.length === 0 && <p style={{ color: "#6b7280" }}>Aucun résultat.</p>}
        </div>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 640 };
