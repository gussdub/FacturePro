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
        const txDate = tx.date;
        const txAmt = Math.abs(Number(tx.amount_cad) || 0);
        // Trie par DATE la plus proche de la transaction (le rapprochement le plus probable en
        // haut), puis par montant le plus proche pour départager.
        const byRelevance = (a, b) => (a._dd - b._dd) || (a._ad - b._ad);
        if (isCredit) {
          const invs = (await axios.get(`${BACKEND_URL}/api/invoices`)).data || [];
          const eligible = invs
            .filter(i => ["sent", "partial", "overdue"].includes(i.status))
            .map(i => ({
              kind: "invoice_payment", id: i.id,
              _dd: _dateDiffDays(i.issue_date, txDate),
              _ad: Math.abs(Number(i.outstanding_cad ?? i.total) - txAmt),
              label: `${i.invoice_number} — Total ${Number(i.total).toFixed(2)} $ — Solde ${Number(i.outstanding_cad ?? i.total).toFixed(2)} $`,
            }));
          eligible.sort(byRelevance);
          setResults(eligible);
        } else {
          const exps = (await axios.get(`${BACKEND_URL}/api/expenses`)).data || [];
          const eligible = exps
            .filter(e => !e.bank_transaction_id)  // exclut les dépenses déjà rapprochées
            .map(e => {
              const d = e.expense_date || e.date || "";
              return {
                kind: "expense", id: e.id,
                _dd: _dateDiffDays(d, txDate),
                _ad: Math.abs(Number(e.amount_cad) - txAmt),
                label: `${d || "—"} — ${e.vendor || e.description || "(sans nom)"} — ${Number(e.amount_cad).toFixed(2)} $`,
              };
            });
          eligible.sort(byRelevance);
          setResults(eligible);
        }
      } finally { setLoading(false); }
    })();
  }, [tx.id, isCredit, tx.date, tx.amount_cad]);

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

// Écart en jours entre deux dates 'YYYY-MM-DD' (grand nombre si absente/invalide -> en bas).
function _dateDiffDays(a, b) {
  if (!a || !b) return 1e9;
  const da = new Date(String(a).slice(0, 10) + "T00:00:00");
  const db = new Date(String(b).slice(0, 10) + "T00:00:00");
  if (isNaN(da.getTime()) || isNaN(db.getTime())) return 1e9;
  return Math.abs((da - db) / 86400000);
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 640 };
