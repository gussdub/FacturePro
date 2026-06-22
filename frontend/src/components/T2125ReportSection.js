import React, { useState, useEffect } from "react";
import axios from "axios";
import { FileText, Download, AlertCircle, Info } from "lucide-react";
import { BACKEND_URL } from "../config";


const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 5 }, (_, i) => CURRENT_YEAR - i);


export default function T2125ReportSection() {
  const [year, setYear] = useState(CURRENT_YEAR - 1);
  const [basis, setBasis] = useState("accrual");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/settings/company`)
      .then(r => setSettings(r.data))
      .catch(() => setSettings({}))
      .finally(() => setSettingsLoading(false));
  }, []);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const r = await axios.get(
        `${BACKEND_URL}/api/reports/t2125?year=${year}&basis=${basis}`);
      setReport(r.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Erreur lors de la génération du rapport");
    } finally {
      setLoading(false);
    }
  };

  const download = async (format) => {
    try {
      const r = await axios.get(
        `${BACKEND_URL}/api/reports/t2125/${format}?year=${year}&basis=${basis}`,
        { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `t2125-${year}-${basis}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(`Erreur lors du téléchargement ${format.toUpperCase()}`);
    }
  };

  if (settingsLoading) {
    return <div style={{ padding: 24 }}>Chargement…</div>;
  }

  if (settings?.entity_type && settings.entity_type !== "sole_proprietor") {
    return (
      <div style={{ padding: 24 }}>
        <div style={{ background: "#dbeafe", color: "#1e40af", padding: 16,
                       borderRadius: 8, display: "flex", gap: 12, alignItems: "flex-start" }}>
          <Info size={20} style={{ flexShrink: 0 }} />
          <div>
            <strong>Ce rapport est destiné aux entreprises individuelles.</strong>
            <p style={{ margin: "6px 0 0", fontSize: 14 }}>
              Pour ta société, utilise l'onglet « État des résultats » — ton comptable
              saura adapter pour le T2.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: "0 0 16px", fontSize: 20, fontWeight: 700,
                    display: "flex", alignItems: "center", gap: 8 }}>
        <FileText size={20} /> Déclaration T2125 (entreprise individuelle)
      </h2>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-end", marginBottom: 24,
                     flexWrap: "wrap" }}>
        <div>
          <label style={{ display: "block", fontSize: 13, color: "#6b7280", marginBottom: 4 }}>
            Année fiscale
          </label>
          <select value={year} onChange={e => setYear(parseInt(e.target.value, 10))}
                  style={{ padding: 8, border: "1px solid #d1d5db", borderRadius: 6,
                           fontSize: 14, minWidth: 120 }}>
            {YEAR_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div>
          <label style={{ display: "block", fontSize: 13, color: "#6b7280", marginBottom: 4 }}>
            Base
          </label>
          <div style={{ display: "flex", gap: 12 }}>
            <label style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 14 }}>
              <input type="radio" name="basis" value="accrual"
                     checked={basis === "accrual"} onChange={e => setBasis(e.target.value)} />
              Exercice
            </label>
            <label style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 14 }}>
              <input type="radio" name="basis" value="cash"
                     checked={basis === "cash"} onChange={e => setBasis(e.target.value)} />
              Caisse
            </label>
          </div>
        </div>
        <button onClick={generate} disabled={loading}
                style={{ background: "#00A08C", color: "#fff", border: "none",
                         padding: "10px 20px", borderRadius: 8, cursor: "pointer",
                         fontWeight: 600, fontSize: 14 }}>
          {loading ? "Génération…" : "Générer"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", color: "#991b1b", padding: 12,
                       borderRadius: 6, marginBottom: 16, display: "flex",
                       gap: 8, alignItems: "center" }}>
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {report && <ReportPreview report={report} onDownload={download} />}
    </div>
  );
}


function ReportPreview({ report, onDownload }) {
  const fmtMoney = (v) => {
    const abs = Math.abs(Number(v || 0)).toFixed(2);
    const [intPart, decPart] = abs.split(".");
    const withSep = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return `${v < 0 ? "-" : ""}${withSep},${decPart} $`;
  };

  const adjustmentLines = new Set(["9945", "9281"]);

  return (
    <div>
      <div style={{ background: "#f8fafb", padding: 12, borderRadius: 6,
                     marginBottom: 16, fontSize: 13, color: "#6b7280" }}>
        <strong>{report.company_name || "(sans nom)"}</strong>
        {" · "}BN : {report.bn_number || "—"}
        {" · "}Province : {report.province}
        {" · "}Base : {report.basis === "accrual" ? "Exercice" : "Caisse"}
        {" · "}Période : {report.period.start} au {report.period.end}
      </div>

      {report.is_partial_year && (
        <div style={{ background: "#fef3c7", color: "#92400e", padding: 12,
                       borderRadius: 6, marginBottom: 16, fontSize: 14 }}>
          ⚠ <strong>Rapport partiel</strong> — l'année n'est pas terminée. Données du
          1er janvier à aujourd'hui uniquement.
        </div>
      )}

      <h3 style={{ margin: "16px 0 8px", fontSize: 16 }}>Revenus bruts (ligne 8000)</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14,
                       marginBottom: 16 }}>
        <tbody>
          <tr style={{ background: "#f8fafb" }}>
            <td style={{ padding: 8 }}>8000</td>
            <td style={{ padding: 8 }}>Recettes brutes</td>
            <td style={{ padding: 8, textAlign: "right", fontWeight: 600 }}>
              {fmtMoney(report.gross_income)}
            </td>
          </tr>
        </tbody>
      </table>

      <h3 style={{ margin: "16px 0 8px", fontSize: 16 }}>Dépenses</h3>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14,
                       marginBottom: 8 }}>
        <thead>
          <tr style={{ background: "#00A08C", color: "#fff" }}>
            <th style={{ padding: 8, textAlign: "left" }}>Ligne</th>
            <th style={{ padding: 8, textAlign: "left" }}>Libellé</th>
            <th style={{ padding: 8, textAlign: "right" }}>Brut</th>
            <th style={{ padding: 8, textAlign: "right" }}>Déductible</th>
          </tr>
        </thead>
        <tbody>
          {report.expenses_by_arc_line.map(line => (
            <tr key={line.arc_line + line.categories.join(",")}
                style={{ background: adjustmentLines.has(line.arc_line) ? "#eff6ff" : "transparent" }}>
              <td style={{ padding: 8 }}>{line.arc_line}</td>
              <td style={{ padding: 8 }}>
                {line.label}
                {line.note && (
                  <span style={{ color: "#6b7280", fontSize: 12, marginLeft: 6 }}>
                    ({line.note})
                  </span>
                )}
              </td>
              <td style={{ padding: 8, textAlign: "right" }}>{fmtMoney(line.gross)}</td>
              <td style={{ padding: 8, textAlign: "right" }}>{fmtMoney(line.deductible)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14,
                       marginBottom: 16 }}>
        <tbody>
          <tr style={{ background: "#f3f4f6", fontWeight: 600 }}>
            <td style={{ padding: 8, width: 60 }}></td>
            <td style={{ padding: 8 }}>Total dépenses déductibles</td>
            <td style={{ padding: 8, textAlign: "right" }}>
              {fmtMoney(report.total_expenses_deductible)}
            </td>
          </tr>
          <tr style={{ background: "#00A08C", color: "#fff", fontWeight: 700 }}>
            <td style={{ padding: 8 }}>9369</td>
            <td style={{ padding: 8 }}>Bénéfice net</td>
            <td style={{ padding: 8, textAlign: "right" }}>
              {fmtMoney(report.net_income)}
            </td>
          </tr>
        </tbody>
      </table>

      <div style={{ background: "#fef3c7", border: "1px solid #d1d5db", padding: 16,
                     borderRadius: 6, marginBottom: 16 }}>
        <strong>À compléter manuellement sur le T2125 officiel</strong>
        <ul style={{ margin: "8px 0 0", paddingLeft: 20, fontSize: 14, color: "#374151" }}>
          <li><strong>Déduction pour amortissement (DPA)</strong> — Annexe T2125-DPA (ligne 9936)</li>
          <li><strong>Bureau à domicile</strong>, si applicable : taxes municipales, intérêts hypothécaires, assurance habitation — ligne 9945</li>
          <li><strong>Véhicule</strong> : amortissement et intérêts (DPA véhicule) — sous-ligne 9281</li>
        </ul>
      </div>

      <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 16 }}>
        Pour le rapport TPS/TVQ détaillé, consulte l'onglet TPS/TVQ.
      </p>

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => onDownload("pdf")}
                style={{ background: "#00A08C", color: "#fff", border: "none",
                         padding: "10px 20px", borderRadius: 8, cursor: "pointer",
                         fontWeight: 600, display: "inline-flex",
                         alignItems: "center", gap: 6 }}>
          <Download size={16} /> Télécharger PDF
        </button>
        <button onClick={() => onDownload("csv")}
                style={{ background: "#fff", color: "#00A08C", border: "1.5px solid #00A08C",
                         padding: "10px 20px", borderRadius: 8, cursor: "pointer",
                         fontWeight: 600, display: "inline-flex",
                         alignItems: "center", gap: 6 }}>
          <Download size={16} /> Télécharger CSV
        </button>
      </div>
    </div>
  );
}
