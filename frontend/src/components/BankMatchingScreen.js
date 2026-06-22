import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { X, RotateCcw, Check, ArrowLeft, Lock } from "lucide-react";
import { BACKEND_URL } from "../config";
import BankSuggestionsActions from "./BankSuggestionsActions";
import BankCreateExpenseModal from "./BankCreateExpenseModal";
import BankCreateInvoiceModal from "./BankCreateInvoiceModal";
import BankManualSearchModal from "./BankManualSearchModal";

const fmt = (n) => Number(n || 0).toFixed(2);

export default function BankMatchingScreen({ importId, onBack }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [openManual, setOpenManual] = useState(null);
  const [openCreate, setOpenCreate] = useState(null);

  const fetchData = async () => {
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/imports/${importId}?per_page=500`);
      setData(r.data);
      setErr(null);
    } catch (e) {
      setErr("Erreur de chargement");
    }
  };

  useEffect(() => { fetchData(); }, [importId]);

  const filteredTxs = useMemo(() => {
    if (!data) return [];
    return data.transactions.filter(t => {
      if (filter === "unmatched" && t.status !== "unmatched") return false;
      if (filter === "matched" && t.status !== "matched") return false;
      if (filter === "ignored" && t.status !== "ignored") return false;
      if (search && !(t.description || "").toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [data, filter, search]);

  if (err) return <div style={{ padding: 24, color: "#dc2626" }}>{err}</div>;
  if (!data) return <div style={{ padding: 24 }}>Chargement…</div>;

  const imp = data.import;
  const totalActionable = (imp.row_count || 0) - (imp.skipped_rows || 0);
  const done = (imp.matched_count || 0) + (imp.ignored_count || 0);
  const pct = totalActionable > 0 ? Math.round((done / totalActionable) * 100) : 100;
  const isClosed = !!imp.closed_at;

  const onIgnore = async (tx) => {
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/ignore`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onUnignore = async (tx) => {
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/unignore`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onUnmatch = async (tx) => {
    if (!window.confirm("Défaire ce rapprochement ?")) return;
    setBusy(true);
    try { await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/unmatch`); await fetchData(); }
    finally { setBusy(false); }
  };
  const onClose = async () => {
    if (!window.confirm("Fermer cet import définitivement ?")) return;
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/imports/${importId}/close`);
      onBack();
    } finally { setBusy(false); }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <button onClick={onBack} style={{ background: "none", border: "none", cursor: "pointer", color: "#6b7280",
                                          marginBottom: 8, display: "inline-flex", alignItems: "center", gap: 4 }}>
        <ArrowLeft size={14} /> Retour
      </button>
      <h2 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 4px" }}>
        {imp.bank_label} — {(imp.imported_at || "").slice(0, 10)}
        {isClosed && <Lock size={16} style={{ color: "#6b7280" }} title="Fermé (lecture seule)" />}
      </h2>
      <div style={{ marginBottom: 16 }}>
        <div style={{ height: 8, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`,
                         background: pct === 100 ? "#059669" : "#00A08C",
                         transition: "width 0.3s" }} />
        </div>
        <div style={{ fontSize: 13, color: "#6b7280", marginTop: 4 }}>
          {done} / {totalActionable} ({pct} %)
        </div>
        {pct === 100 && !isClosed && (
          <button onClick={onClose} disabled={busy}
                  style={{ marginTop: 8, background: "#059669", color: "#fff",
                           border: "none", padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 13 }}>
            Fermer cet import
          </button>
        )}
      </div>
      <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        {[
          ["all", "Tout"],
          ["unmatched", "Non rapprochées"],
          ["matched", "Matchées"],
          ["ignored", "Ignorées"],
        ].map(([key, label]) => (
          <button key={key} onClick={() => setFilter(key)}
                  style={{ background: filter === key ? "#00A08C" : "#e5e7eb",
                           color: filter === key ? "#fff" : "#111",
                           border: "none", padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 13 }}>
            {label}
          </button>
        ))}
        <input placeholder="Recherche description…" value={search}
               onChange={(e) => setSearch(e.target.value)}
               style={{ padding: 6, marginLeft: "auto", border: "1px solid #d1d5db",
                        borderRadius: 4, fontSize: 13, minWidth: 200 }} />
      </div>
      <div>
        {filteredTxs.map(tx => (
          <TxRow key={tx.id} tx={tx} busy={busy} readOnly={isClosed}
                 onIgnore={() => onIgnore(tx)}
                 onUnignore={() => onUnignore(tx)}
                 onUnmatch={() => onUnmatch(tx)}
                 onOpenManual={() => setOpenManual(tx)}
                 onOpenCreate={() => setOpenCreate(tx)}
                 onRefresh={fetchData} />
        ))}
        {filteredTxs.length === 0 && <p style={{ color: "#6b7280" }}>Aucune transaction.</p>}
      </div>
      {openManual && (
        <BankManualSearchModal tx={openManual} onClose={() => setOpenManual(null)}
          onMatched={() => { setOpenManual(null); fetchData(); }} />
      )}
      {openCreate && ((openCreate.amount_cad || 0) < 0 ? (
        <BankCreateExpenseModal tx={openCreate} onClose={() => setOpenCreate(null)}
          onCreated={() => { setOpenCreate(null); fetchData(); }} />
      ) : (
        <BankCreateInvoiceModal tx={openCreate} onClose={() => setOpenCreate(null)}
          onCreated={() => { setOpenCreate(null); fetchData(); }} />
      ))}
    </div>
  );
}

function TxRow({ tx, busy, readOnly, onIgnore, onUnignore, onUnmatch, onOpenManual, onOpenCreate, onRefresh }) {
  const isDebit = tx.amount_cad != null && tx.amount_cad < 0;
  const stateColor = tx.parse_error ? "#dc2626"
    : tx.status === "matched" ? "#059669"
    : tx.status === "ignored" ? "#9ca3af"
    : "#f59e0b";
  return (
    <div style={{ borderLeft: `4px solid ${stateColor}`, background: "#fff",
                  padding: 12, marginBottom: 8, borderRadius: 4,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, color: "#6b7280" }}>{tx.date || "—"}</div>
          <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {tx.description}
          </div>
          {tx.parse_error && (
            <div style={{ color: "#dc2626", fontSize: 12 }}>Ligne illisible (date ou montant)</div>
          )}
          {tx.status === "matched" && (
            <div style={{ color: "#059669", fontSize: 12 }}>
              Rapproché ({tx.match_kind === "invoice_payment" ? "facture" : "dépense"})
            </div>
          )}
        </div>
        <div style={{ fontWeight: 600, color: isDebit ? "#dc2626" : "#059669", minWidth: 100, textAlign: "right" }}>
          {tx.amount_cad != null ? fmt(tx.amount_cad) + " $" : "—"}
        </div>
        {!readOnly && (
          <div style={{ display: "flex", gap: 6 }}>
            {tx.status === "unmatched" && !tx.parse_error && (
              <button onClick={onIgnore} disabled={busy} title="Ignorer"
                      style={iconBtn}><X size={14} /></button>
            )}
            {tx.status === "matched" && (
              <button onClick={onUnmatch} disabled={busy} title="Défaire"
                      style={iconBtn}><RotateCcw size={14} /></button>
            )}
            {tx.status === "ignored" && (
              <button onClick={onUnignore} disabled={busy} title="Restaurer"
                      style={iconBtn}><Check size={14} /></button>
            )}
            {tx.parse_error && tx.status === "unmatched" && (
              <button onClick={onIgnore} disabled={busy} title="Ignorer"
                      style={iconBtn}><X size={14} /></button>
            )}
          </div>
        )}
      </div>
      {!readOnly && tx.status === "unmatched" && !tx.parse_error && (
        <BankSuggestionsActions tx={tx}
          onMatched={onRefresh} onIgnore={onIgnore}
          onOpenManual={onOpenManual}
          onOpenCreate={onOpenCreate} />
      )}
    </div>
  );
}

const iconBtn = { background: "#f3f4f6", border: "none", padding: 6, borderRadius: 4,
                  cursor: "pointer", display: "inline-flex", alignItems: "center" };
