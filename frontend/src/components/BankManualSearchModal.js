import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankManualSearchModal({ tx, onClose, onMatched }) {
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(() => new Set());
  const isCredit = (tx.amount_cad || 0) > 0;
  const txAmt = Math.abs(Number(tx.amount_cad) || 0);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const txDate = tx.date;
        const byRelevance = (a, b) => (a._dd - b._dd) || (a._ad - b._ad);
        if (isCredit) {
          const invs = (await axios.get(`${BACKEND_URL}/api/invoices`)).data || [];
          // Toutes les factures — payées grisées (comme le fait déjà le mode dépenses), pour qu'on
          // voie pourquoi une facture n'est pas cochable (déjà encaissée).
          const mapped = invs.map(i => {
            const paid = i.status === "paid";
            const outstanding = Number(i.outstanding_cad ?? i.total ?? 0);
            return {
              kind: "invoice_payment", id: i.id,
              disabled: paid || outstanding <= 0,
              outstanding,
              _mm: paid ? 1 : 0,
              _dd: _dateDiffDays(i.issue_date, txDate),
              _ad: Math.abs(outstanding - txAmt),
              label: `${i.invoice_number} — Total ${Number(i.total || 0).toFixed(2)} $ — Solde ${outstanding.toFixed(2)} $`
                     + (paid ? "  · déjà rapprochée" : ""),
            };
          });
          mapped.sort((a, b) => (a._mm - b._mm) || byRelevance(a, b));
          setResults(mapped);
        } else {
          const exps = (await axios.get(`${BACKEND_URL}/api/expenses`)).data || [];
          const mapped = exps.map(e => {
            const d = e.expense_date || e.date || "";
            const matched = !!e.bank_transaction_id;
            return {
              kind: "expense", id: e.id, disabled: matched,
              _mm: matched ? 1 : 0,
              _dd: _dateDiffDays(d, txDate),
              _ad: Math.abs(Number(e.amount_cad) - txAmt),
              label: `${d || "—"} — ${e.vendor || e.description || "(sans nom)"} — ${Number(e.amount_cad).toFixed(2)} $`
                     + (matched ? "  · déjà rapprochée" : ""),
            };
          });
          mapped.sort((a, b) => (a._mm - b._mm) || byRelevance(a, b));
          setResults(mapped);
        }
      } finally { setLoading(false); }
    })();
  }, [tx.id, isCredit, tx.date, tx.amount_cad, txAmt]);

  const filtered = results.filter(r => r.label.toLowerCase().includes(search.toLowerCase()));

  // Somme des soldes sélectionnés (factures seulement — pas de split dépenses en v1).
  const selectedSum = useMemo(() => {
    if (!isCredit) return 0;
    let s = 0;
    for (const r of results) {
      if (selected.has(r.id)) s += Number(r.outstanding || 0);
    }
    return Math.round(s * 100) / 100;
  }, [selected, results, isCredit]);

  const diff = Math.round((selectedSum - txAmt) * 100) / 100;
  // Tolérance identique au backend (`abs(total - tx_amount) > 0.01` → accepte 0.01) pour éviter
  // qu'un cent d'arrondi cascade bloque le bouton alors que le POST passerait.
  const exactMatch = Math.abs(diff) <= 0.01;

  const toggleSelect = (r) => {
    if (r.disabled) return;
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(r.id)) next.delete(r.id); else next.add(r.id);
      return next;
    });
  };

  // Match unitaire (dépense OU 1 seule facture sélectionnée) — POST kind + target_id.
  const matchSingle = async (kind, target_id) => {
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

  // Rapproche N factures (N ≥ 2) — POST kind=invoice_payment + target_ids.
  const matchSplit = async () => {
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/match`,
        { kind: "invoice_payment", target_ids: Array.from(selected) });
      onMatched();
    } catch (e) {
      window.alert(e.response?.data?.detail || "Erreur de matching");
      setBusy(false);
    }
  };

  // Comportement : dépenses → clic direct (pas de split v1). Factures → clic bascule checkbox ;
  // le rapprochement se déclenche par le bouton (mode explicite, évite le clic mal-placé).
  const onRowClick = (r) => {
    if (busy || r.disabled) return;
    if (isCredit) toggleSelect(r);
    else matchSingle(r.kind, r.id);
  };

  const nSel = selected.size;
  // N==1 : autoriser TOUJOURS (paiement partiel OU exact — _apply_match single accepte les 2).
  // N>=2 : exigence somme exacte (contrat split v1). Sans ça, une régression : un dépôt de 2000 $
  // sur une facture avec solde 5000 $ ne pourrait plus être enregistré comme paiement partiel.
  const canConfirm = isCredit && nSel >= 1 && !busy && (nSel === 1 || exactMatch);
  const singlePartial = nSel === 1 && !exactMatch;
  const confirmLabel = nSel <= 1
    ? (singlePartial ? "Rapprocher (paiement partiel)" : "Rapprocher cette facture")
    : `Rapprocher ces ${nSel} factures`;

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Chercher {isCredit ? "une ou plusieurs factures" : "une dépense"}</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <div style={{ background: "#f8fafb", padding: 10, borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
          {tx.date} — {tx.description} ({txAmt.toFixed(2)} $)
        </div>
        {isCredit && (
          <div style={{
            background: exactMatch ? "#ecfdf5" : (nSel > 0 ? "#fef3c7" : "#f3f4f6"),
            border: `1px solid ${exactMatch ? "#10b981" : (nSel > 0 ? "#f59e0b" : "#e5e7eb")}`,
            padding: 10, borderRadius: 6, marginBottom: 12, fontSize: 13,
            display: "flex", justifyContent: "space-between", alignItems: "center",
          }}>
            <span>
              Sélectionné : <strong>{selectedSum.toFixed(2)} $</strong>
              {" "}/ cible <strong>{txAmt.toFixed(2)} $</strong>
              {singlePartial && (
                <span style={{ color: "#b45309", marginLeft: 8 }}>
                  · paiement partiel ({txAmt.toFixed(2)} $ sur solde {selectedSum.toFixed(2)} $)
                </span>
              )}
              {nSel >= 2 && !exactMatch && (
                <span style={{ color: "#b45309", marginLeft: 8 }}>
                  · écart {diff > 0 ? "+" : ""}{diff.toFixed(2)} $ — sélection non rapprochable
                </span>
              )}
              {exactMatch && nSel > 0 && (
                <span style={{ color: "#047857", marginLeft: 8 }}>· somme exacte ✓</span>
              )}
            </span>
            {nSel > 1 && (
              <button onClick={() => setSelected(new Set())}
                      style={{ background: "none", border: "none", color: "#6b7280",
                               cursor: "pointer", fontSize: 12, textDecoration: "underline" }}>
                tout désélectionner
              </button>
            )}
          </div>
        )}
        <input placeholder="Filtrer…" value={search} onChange={(e) => setSearch(e.target.value)}
               style={{ width: "100%", padding: 6, marginBottom: 12, border: "1px solid #d1d5db", borderRadius: 4 }} />
        <div style={{ maxHeight: 360, overflowY: "auto", marginBottom: isCredit ? 12 : 0 }}>
          {loading && <p>Chargement…</p>}
          {!loading && filtered.map(r => {
            const checked = isCredit && selected.has(r.id);
            return (
              <div key={r.id} onClick={() => onRowClick(r)}
                   style={{ padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 13,
                            cursor: r.disabled ? "not-allowed" : (busy ? "wait" : "pointer"),
                            color: r.disabled ? "#9ca3af" : "inherit",
                            background: checked ? "#eff6ff" : "transparent",
                            display: "flex", alignItems: "center", gap: 8 }}
                   onMouseEnter={(e) => {
                     if (r.disabled || checked) return;
                     e.currentTarget.style.background = "#f3f4f6";
                   }}
                   onMouseLeave={(e) => {
                     e.currentTarget.style.background = checked ? "#eff6ff" : "transparent";
                   }}>
                {isCredit && (
                  <input type="checkbox" checked={checked} disabled={r.disabled || busy}
                         onChange={() => toggleSelect(r)}
                         onClick={(e) => e.stopPropagation()}
                         style={{ cursor: r.disabled ? "not-allowed" : "pointer" }} />
                )}
                <span style={{ flex: 1 }}>{r.label}</span>
              </div>
            );
          })}
          {!loading && filtered.length === 0 && <p style={{ color: "#6b7280" }}>Aucun résultat.</p>}
        </div>
        {isCredit && (
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={onClose} disabled={busy}
                    style={{ background: "#fff", border: "1px solid #d1d5db", color: "#374151",
                             padding: "8px 14px", borderRadius: 6, cursor: busy ? "wait" : "pointer",
                             fontSize: 13 }}>
              Annuler
            </button>
            <button onClick={() => nSel === 1
                                    ? matchSingle("invoice_payment", Array.from(selected)[0])
                                    : matchSplit()}
                    disabled={!canConfirm}
                    title={!canConfirm && nSel > 0
                      ? "La somme des soldes doit égaler exactement le montant de la transaction."
                      : ""}
                    style={{ background: canConfirm ? "#00A08C" : "#e5e7eb",
                             color: canConfirm ? "#fff" : "#9ca3af",
                             border: "none", padding: "8px 14px", borderRadius: 6,
                             cursor: canConfirm ? "pointer" : "not-allowed",
                             fontSize: 13, fontWeight: 600 }}>
              {confirmLabel}
            </button>
          </div>
        )}
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
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 720 };
