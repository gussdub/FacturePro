import React, { useState, useEffect } from "react";
import axios from "axios";
import { GitMerge, Plus, FileText } from "lucide-react";
import { BACKEND_URL } from "../config";

export default function BankReconciliationPage() {
  const [imports, setImports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState({ kind: "list" });

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

  useEffect(() => { fetchImports(); }, []);

  if (view.kind === "wizard") {
    return (
      <div style={{ padding: 24 }}>
        <p>Wizard (T12).</p>
        <button onClick={() => setView({ kind: "list" })}>Retour</button>
      </div>
    );
  }
  if (view.kind === "matching") {
    return (
      <div style={{ padding: 24 }}>
        <p>Matching screen for {view.importId} (T13).</p>
        <button onClick={() => setView({ kind: "list" })}>Retour</button>
      </div>
    );
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
