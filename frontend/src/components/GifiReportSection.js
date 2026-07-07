import React, { useState, useEffect } from "react";
import axios from "axios";
import { BACKEND_URL } from "../config";

export default function GifiReportSection() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [basis, setBasis] = useState("accrual");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    setLoading(true); setErr(null);
    axios.get(`${BACKEND_URL}/api/reports/gifi?year=${year}&basis=${basis}`)
      .then(r => setReport(r.data))
      .catch(e => setErr(e.response?.data?.detail || "Erreur"))
      .finally(() => setLoading(false));
  }, [year, basis]);

  const download = (fmt) => {
    window.open(`${BACKEND_URL}/api/reports/gifi/${fmt}?year=${year}&basis=${basis}`);
  };

  return (
    <div style={{ padding: 16 }}>
      <h3 style={{ margin: "0 0 12px" }}>Sommaire GIFI</h3>
      <p style={{ color: "#6b7280", fontSize: 13, marginTop: 0 }}>
        Sommaire des dépenses par code GIFI (Index général des renseignements financiers,
        RC4088) — utilisé pour la déclaration T2 (fédéral) et CO-17 (Québec) d'une
        société par actions.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <label>Année <input type="number" value={year} min="2000" max="2100"
                              onChange={(e) => setYear(parseInt(e.target.value || currentYear, 10))}
                              style={{ padding: 4, width: 80, border: "1px solid #d1d5db", borderRadius: 4 }} />
        </label>
        <label>Base
          <select value={basis} onChange={(e) => setBasis(e.target.value)}
                  style={{ padding: 4, marginLeft: 4, border: "1px solid #d1d5db", borderRadius: 4 }}>
            <option value="accrual">Comptabilité d'exercice</option>
            <option value="cash">Encaissements/décaissements</option>
          </select>
        </label>
        <button onClick={() => download("csv")} disabled={loading || !report}
                style={btn}>Exporter CSV</button>
        <button onClick={() => download("pdf")} disabled={loading || !report}
                style={btn}>Exporter PDF</button>
      </div>
      {loading && <p>Chargement…</p>}
      {err && <p style={{ color: "#dc2626" }}>{err}</p>}
      {report && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8fafb", textAlign: "left" }}>
              <th style={th}>Code GIFI</th>
              <th style={th}>Libellé</th>
              <th style={{ ...th, textAlign: "right" }}>Montant CAD</th>
            </tr>
          </thead>
          <tbody>
            {report.lines.map(ln => (
              <tr key={ln.code}>
                <td style={td}>{ln.code}</td>
                <td style={td}>{ln.label}</td>
                <td style={{ ...td, textAlign: "right" }}>{ln.amount.toFixed(2)} $</td>
              </tr>
            ))}
            <tr style={{ fontWeight: 600, background: "#f8fafb" }}>
              <td style={td}></td>
              <td style={td}>Total</td>
              <td style={{ ...td, textAlign: "right" }}>{report.total.toFixed(2)} $</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}

const btn = { background: "#00A08C", color: "#fff", border: "none",
              padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontSize: 13 };
const th = { padding: 8, borderBottom: "1px solid #e5e7eb" };
const td = { padding: 8, borderBottom: "1px solid #f3f4f6" };
