import React, { useState, useEffect } from "react";
import axios from "axios";
import { GitMerge, Plus, FileText, Trash2 } from "lucide-react";
import { BACKEND_URL } from "../config";
import BankImportWizard from "../components/BankImportWizard";
import BankMatchingScreen from "../components/BankMatchingScreen";

export default function BankReconciliationPage() {
  const [imports, setImports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState({ kind: "list" });
  const [deletingId, setDeletingId] = useState(null);

  const fetchImports = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${BACKEND_URL}/api/bank/imports`);
      setImports(r.data);
    } catch (e) {
      console.error("fetch imports failed", e);
    } finally {
      setLoading(false);
    }
  };

  // Supprime un import + ses transactions. La cascade backend DÉLIE (ne supprime pas) les
  // dépenses/factures rapprochées ; le window.confirm sert de garde (action irréversible).
  const deleteImport = async (imp, e) => {
    e.stopPropagation();  // ne pas ouvrir l'écran de rapprochement en cliquant sur la corbeille
    const matched = imp.matched_count || 0;
    const msg = matched > 0
      ? `Supprimer l'import « ${imp.bank_label} » ?\n\n${matched} transaction(s) rapprochée(s) seront dé-liées `
        + `— les dépenses/factures liées ne sont PAS supprimées, elles perdent seulement le lien de rapprochement.\n\nCette action est irréversible.`
      : `Supprimer l'import « ${imp.bank_label} » et ses ${imp.row_count} transactions ?\n\nCette action est irréversible.`;
    if (!window.confirm(msg)) return;
    setDeletingId(imp.id);
    try {
      await axios.delete(`${BACKEND_URL}/api/bank/imports/${imp.id}?force=true`);
      await fetchImports();
    } catch (err) {
      alert(err.response?.data?.detail || "Erreur lors de la suppression de l'import.");
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => { fetchImports(); }, []);

  if (view.kind === "wizard") {
    return <BankImportWizard
      onCancel={() => setView({ kind: "list" })}
      onDone={(importId) => { fetchImports(); setView({ kind: "matching", importId }); }}
    />;
  }
  if (view.kind === "matching") {
    return <BankMatchingScreen
      importId={view.importId}
      onBack={() => { fetchImports(); setView({ kind: "list" }); }} />;
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1 style={{ display: "flex", alignItems: "center", gap: 8, margin: 0, fontSize: 24, fontWeight: 700 }}>
          <GitMerge size={24} /> Rapprochement bancaire
        </h1>
        <button onClick={() => setView({ kind: "wizard" })}
                style={{ background: "#00A08C", color: "#fff", border: "none",
                         padding: "8px 16px", borderRadius: 8, cursor: "pointer",
                         display: "inline-flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 600 }}>
          <Plus size={16} /> Nouvel import
        </button>
      </div>
      {loading && <p>Chargement…</p>}
      {!loading && imports.length === 0 && (
        <div style={{ textAlign: "center", padding: 60, color: "#6b7280" }}>
          <FileText size={48} style={{ opacity: 0.4 }} />
          <p>Aucun import bancaire pour l'instant.</p>
          <button onClick={() => setView({ kind: "wizard" })}
                  style={{ background: "#00A08C", color: "#fff", border: "none",
                           padding: "10px 20px", borderRadius: 8, cursor: "pointer",
                           fontSize: 14, fontWeight: 600 }}>
            Importer votre premier relevé
          </button>
        </div>
      )}
      {!loading && imports.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, padding: 16, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#f3f4f6", textAlign: "left" }}>
                <th style={{ padding: 10 }}>Date</th>
                <th style={{ padding: 10 }}>Banque</th>
                <th style={{ padding: 10, textAlign: "right" }}>Lignes</th>
                <th style={{ padding: 10, textAlign: "right" }}>Rapproché</th>
                <th style={{ padding: 10, textAlign: "right" }}>Progress</th>
                <th style={{ padding: 10 }}>État</th>
                <th style={{ padding: 10, textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {imports.map((imp) => {
                const total = (imp.row_count || 0) - (imp.skipped_rows || 0);
                const done = (imp.matched_count || 0) + (imp.ignored_count || 0);
                const pct = total > 0 ? Math.round((done / total) * 100) : 0;
                return (
                  <tr key={imp.id}
                      style={{ borderBottom: "1px solid #e5e7eb", cursor: "pointer" }}
                      onClick={() => setView({ kind: "matching", importId: imp.id })}>
                    <td style={{ padding: 10 }}>{(imp.imported_at || "").slice(0, 10)}</td>
                    <td style={{ padding: 10 }}>{imp.bank_label}</td>
                    <td style={{ padding: 10, textAlign: "right" }}>{imp.row_count}</td>
                    <td style={{ padding: 10, textAlign: "right" }}>{done} / {total}</td>
                    <td style={{ padding: 10, textAlign: "right" }}>{pct} %</td>
                    <td style={{ padding: 10, color: imp.closed_at ? "#6b7280" : "#059669" }}>
                      {imp.closed_at ? "Fermé" : "Ouvert"}
                    </td>
                    <td style={{ padding: 10, textAlign: "right" }}>
                      <button onClick={(e) => deleteImport(imp, e)} disabled={deletingId === imp.id}
                              title="Supprimer cet import"
                              style={{ background: "none", border: "none", padding: 4,
                                       cursor: deletingId === imp.id ? "wait" : "pointer",
                                       color: "#dc2626", opacity: deletingId === imp.id ? 0.5 : 1 }}>
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
