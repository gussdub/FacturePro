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
  const [rematching, setRematching] = useState(false);
  const [err, setErr] = useState(null);
  const [openManual, setOpenManual] = useState(null);
  const [openCreate, setOpenCreate] = useState(null);
  const [showComparison, setShowComparison] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [cmpBusy, setCmpBusy] = useState(false);

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
  // Relance l'auto-match sur les transactions encore non rapprochées (après avoir saisi de
  // nouvelles dépenses, ou pour ré-appliquer le matcheur). Ne touche pas aux rapprochées/ignorées.
  const onRematch = async () => {
    setBusy(true); setRematching(true); setErr(null);
    try {
      const r = await axios.post(`${BACKEND_URL}/api/bank/imports/${importId}/rematch`);
      await fetchData();
      const n = r.data?.auto_matched || 0;
      alert(n > 0
        ? `${n} transaction(s) rapprochée(s) automatiquement.`
        : "Aucun nouveau rapprochement automatique trouvé (montant + date proche + nom requis).");
    } catch {
      setErr("Erreur lors du re-rapprochement");
    } finally { setBusy(false); setRematching(false); }
  };

  // Rapport de comparaison relevé ↔ dépenses (feature #7.14) : classe chaque retrait
  // (concordante / écart de conversion / absente) SANS rien créer automatiquement.
  const loadComparison = async () => {
    setCmpBusy(true); setErr(null);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/imports/${importId}/comparison`);
      setComparison(r.data); setShowComparison(true);
    } catch { setErr("Erreur lors de la comparaison"); }
    finally { setCmpBusy(false); }
  };
  const refreshComparison = async () => {
    const r = await axios.get(`${BACKEND_URL}/api/bank/imports/${importId}/comparison`);
    setComparison(r.data);
  };
  // « Adopter le montant de la banque » : rapproche la dépense à la transaction → _apply_match
  // remplace le CAD estimé par le vrai montant débité + recalcule le taux + re-poste le GL.
  const adoptBank = async (line) => {
    setCmpBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${line.tx_id}/match`,
                       { kind: "expense", target_id: line.expense.id });
    } catch (e) {
      alert(e.response?.data?.detail || "Erreur lors de l'adoption du montant.");
    } finally {
      // Toujours resynchroniser (succès ET 409 « déjà rapprochée ») → le rapport ne reste
      // jamais périmé avec un bouton Adopter fantôme.
      try { await fetchData(); await refreshComparison(); } catch { /* rapport gardé tel quel */ }
      setCmpBusy(false);
    }
  };
  // « Créer » : ouvre la modale de création existante (optionnel, à la main — jamais en lot).
  // Construit un tx minimal depuis la ligne du rapport si la transaction n'est pas dans la page
  // chargée (import > 500 lignes) → le bouton n'est plus un no-op silencieux.
  const createFromLine = (line) => {
    const tx = (data.transactions || []).find(t => t.id === line.tx_id)
      || { id: line.tx_id, date: line.date, description: line.description,
           amount_cad: -Math.abs(line.bank_amount || 0) };
    setShowComparison(false); setOpenCreate(tx);
  };
  // « Lier » (correspondance probable) : même montant + date qu'une dépense existante mais nom
  // différent (ex. terminal « Pêcherie Manicouagan » vs reçu « Resto-Poissonnerie Manic »). On
  // rapproche la transaction à CETTE dépense au lieu d'en recréer une (doublon). Réutilise /match.
  const linkExpense = async (line) => {
    const e = line.expense || {};
    if (!window.confirm(
      `Lier cette transaction à la dépense existante « ${e.vendor || e.description || ""} » `
      + `(${fmt(e.amount_cad)} $) ?\n\nÀ utiliser si c'est le même commerçant sous un autre nom.`)) return;
    setCmpBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${line.tx_id}/match`,
                       { kind: "expense", target_id: e.id });
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur lors du lien.");
    } finally {
      try { await fetchData(); await refreshComparison(); } catch { /* rapport gardé tel quel */ }
      setCmpBusy(false);
    }
  };
  const cmpDownload = async (ext, mime) => {
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/imports/${importId}/comparison/${ext}`,
                                { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: mime }));
      const a = document.createElement("a"); a.href = url;
      a.download = `comparaison-${(imp.bank_label || "releve")}.${ext}`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch { alert("Erreur lors de l'export."); }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <style>{"@keyframes bmspin{to{transform:rotate(360deg)}}@keyframes bmbar{0%{margin-left:-40%}100%{margin-left:100%}}"}</style>
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
      {!isClosed && (
        <div style={{ marginBottom: 14 }}>
          <button onClick={onRematch} disabled={busy}
                  title="Comparer à nouveau les transactions non rapprochées avec tes dépenses/factures"
                  style={{ background: "#fff", color: "#00A08C", border: "1.5px solid #00A08C",
                           padding: "6px 14px", borderRadius: 6, cursor: busy ? "wait" : "pointer", fontSize: 13,
                           fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 6,
                           opacity: busy && !rematching ? 0.5 : 1 }}>
            <RotateCcw size={14} style={{ animation: rematching ? "bmspin 0.8s linear infinite" : "none" }} />
            {rematching ? "Rapprochement en cours…" : "Relancer le rapprochement auto"}
          </button>
          {rematching && (
            <div style={{ marginTop: 8, height: 4, background: "#e5e7eb", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ height: "100%", width: "40%", background: "#00A08C",
                            borderRadius: 2, animation: "bmbar 1.1s ease-in-out infinite" }} />
            </div>
          )}
        </div>
      )}
      <div style={{ marginBottom: 14 }}>
        <button onClick={loadComparison} disabled={cmpBusy}
                title="Comparer les retraits du relevé à tes dépenses déjà saisies (sans rien créer)"
                style={{ background: "#00A08C", color: "#fff", border: "none", padding: "6px 14px",
                         borderRadius: 6, cursor: cmpBusy ? "wait" : "pointer", fontSize: 13, fontWeight: 600 }}>
          {cmpBusy && !showComparison ? "Comparaison…" : "Comparer aux dépenses (relevé ↔ dépenses)"}
        </button>
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
      {showComparison && comparison && (
        <div onClick={() => setShowComparison(false)}
             style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", display: "flex",
                      alignItems: "center", justifyContent: "center", zIndex: 1400, padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: "#fff", borderRadius: 10, width: "100%", maxWidth: 920,
                        maxHeight: "92vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "12px 16px", borderBottom: "1px solid #e5e7eb" }}>
              <strong style={{ fontSize: 16 }}>Comparaison relevé ↔ dépenses</strong>
              <button onClick={() => setShowComparison(false)}
                      style={{ background: "none", border: "none", cursor: "pointer",
                               fontSize: 22, color: "#6b7280", lineHeight: 1 }}>×</button>
            </div>
            <div style={{ padding: "10px 16px", display: "flex", gap: 16, flexWrap: "wrap",
                          fontSize: 13, borderBottom: "1px solid #f3f4f6", alignItems: "center" }}>
              <span style={{ color: "#059669", fontWeight: 600 }}>✓ {comparison.summary.concordante} concordante(s)</span>
              <span style={{ color: "#b45309", fontWeight: 600 }}>⚠ {comparison.summary.ecart} écart(s)</span>
              {comparison.summary.possible > 0 && (
                <span style={{ color: "#7c3aed", fontWeight: 600 }}>≈ {comparison.summary.possible} probable(s)</span>
              )}
              <span style={{ color: "#dc2626", fontWeight: 600 }}>＋ {comparison.summary.absente} absente(s)</span>
              <span style={{ color: "#6b7280" }}>Écart de change total : {fmt(comparison.summary.total_fx_ecart)} $</span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <button onClick={() => cmpDownload("pdf", "application/pdf")} style={cmpBtn("#00A08C")}>PDF</button>
                <button onClick={() => cmpDownload("csv", "text/csv")} style={cmpBtn("#1f2937")}>CSV</button>
              </span>
            </div>
            <div style={{ overflow: "auto", padding: "8px 16px" }}>
              {comparison.lines.length === 0 && (
                <p style={{ color: "#6b7280" }}>Aucun retrait à comparer dans ce relevé.</p>
              )}
              {comparison.lines.map((ln) => {
                const meta = {
                  concordante: { c: "#059669", t: "Concordante", bg: "#ecfdf5" },
                  ecart: { c: "#b45309", t: "Écart", bg: "#fffbeb" },
                  possible: { c: "#7c3aed", t: "Correspondance probable", bg: "#f5f3ff" },
                  absente: { c: "#dc2626", t: "Absente", bg: "#fef2f2" },
                }[ln.status] || { c: "#6b7280", t: ln.status, bg: "#f9fafb" };
                return (
                  <div key={ln.tx_id} style={{ borderLeft: `4px solid ${meta.c}`, background: meta.bg,
                        padding: "8px 12px", marginBottom: 6, borderRadius: 4 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ color: meta.c, fontWeight: 700, fontSize: 12 }}>{meta.t}</span>
                        <span style={{ color: "#6b7280", fontSize: 12, marginLeft: 8 }}>{ln.date}</span>
                        <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {ln.description}
                        </div>
                        {ln.expense && (
                          <div style={{ fontSize: 12, color: "#6b7280" }}>
                            Dépense : {ln.expense.vendor || ln.expense.description} — {fmt(ln.expense.amount_cad)} $ {ln.expense.currency}
                          </div>
                        )}
                      </div>
                      <div style={{ textAlign: "right", minWidth: 110 }}>
                        <div style={{ fontWeight: 600 }}>Banque {fmt(ln.bank_amount)} $</div>
                        {ln.status === "ecart" && (
                          <div style={{ fontSize: 12, color: "#b45309" }}>écart {fmt(ln.ecart)} $</div>
                        )}
                      </div>
                      <div style={{ minWidth: 140, textAlign: "right" }}>
                        {ln.can_adopt && (
                          <button onClick={() => adoptBank(ln)} disabled={cmpBusy || isClosed}
                                  style={cmpBtn("#b45309")}>Adopter le montant banque</button>
                        )}
                        {ln.status === "ecart" && !ln.can_adopt && (
                          <span style={{ fontSize: 11, color: "#b45309" }}>
                            {ln.already_matched ? "déjà rapprochée" : "à vérifier (dépense CAD)"}
                          </span>
                        )}
                        {ln.status === "possible" && ln.can_link && !isClosed && (
                          <div style={{ display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-end" }}>
                            <button onClick={() => linkExpense(ln)} disabled={cmpBusy}
                                    style={cmpBtn("#7c3aed")}>Lier à cette dépense</button>
                            <button onClick={() => createFromLine(ln)} disabled={cmpBusy}
                                    style={{ background: "none", border: "none", color: "#6b7280",
                                             fontSize: 11, cursor: "pointer", textDecoration: "underline" }}>
                              Créer quand même
                            </button>
                          </div>
                        )}
                        {ln.status === "absente" && !isClosed && (
                          <button onClick={() => createFromLine(ln)} style={cmpBtn("#dc2626")}>Créer</button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const cmpBtn = (bg) => ({ background: bg, color: "#fff", border: "none", padding: "5px 10px",
                          borderRadius: 5, cursor: "pointer", fontSize: 12, fontWeight: 600 });

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
