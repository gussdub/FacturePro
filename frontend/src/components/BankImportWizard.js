import React, { useState, useEffect } from "react";
import axios from "axios";
import { Upload, ArrowRight, X } from "lucide-react";
import { BACKEND_URL } from "../config";

const DEFAULT_MAPPING = {
  delimiter: ",", has_header: true,
  date_column: 0, date_format: "YYYY-MM-DD",
  description_column: 1,
  amount_mode: "single", amount_column: 2,
  debit_column: null, credit_column: null,
  sign_convention: "positive_is_credit",
};

export default function BankImportWizard({ onCancel, onDone }) {
  const [step, setStep] = useState(1);
  const [bankLabel, setBankLabel] = useState("");
  const [file, setFile] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [mapping, setMapping] = useState(DEFAULT_MAPPING);
  const [saveMapping, setSaveMapping] = useState(true);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/bank/mappings`)
      .then(r => setMappings(r.data || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const trimmed = bankLabel.trim().toLowerCase();
    if (!trimmed) return;
    const found = mappings.find(m => (m.bank_label || "").trim().toLowerCase() === trimmed);
    if (found) {
      setMapping({
        delimiter: found.delimiter || ",",
        has_header: !!found.has_header,
        date_column: found.date_column ?? 0,
        date_format: found.date_format || "YYYY-MM-DD",
        description_column: found.description_column ?? 1,
        amount_mode: found.amount_mode || "single",
        amount_column: found.amount_column,
        debit_column: found.debit_column,
        credit_column: found.credit_column,
        sign_convention: found.sign_convention || "positive_is_credit",
      });
    }
  }, [bankLabel, mappings]);

  const onFileChosen = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) {
      setErr("Fichier trop volumineux (max 5 MB)"); return;
    }
    setFile(f); setErr(null);
  };

  const goStep2 = () => {
    if (!file || !bankLabel.trim()) {
      setErr("Banque et fichier requis"); return;
    }
    setErr(null);
    setStep(2);
  };

  const runPreview = async () => {
    setBusy(true); setErr(null); setPreview(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(
        `${BACKEND_URL}/api/bank/imports?dry_run=true`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      setPreview(r.data);
    } catch (e) {
      setErr(e.response?.data?.detail || "Erreur de parsing");
    } finally { setBusy(false); }
  };

  const doImport = async () => {
    setBusy(true); setErr(null);
    try {
      if (saveMapping && bankLabel.trim()) {
        try {
          await axios.post(`${BACKEND_URL}/api/bank/mappings`,
            { ...mapping, bank_label: bankLabel });
        } catch { /* déjà existant ou limite atteinte — ignorer */ }
      }
      const fd = new FormData();
      fd.append("file", file);
      fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(`${BACKEND_URL}/api/bank/imports`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      onDone(r.data.import.id);
    } catch (e) {
      if (e.response?.status === 409) {
        setErr(`Ce CSV a déjà été importé.`);
      } else if (e.response?.status === 413) {
        setErr("Fichier trop volumineux (max 5 MB / 5000 lignes).");
      } else {
        setErr(e.response?.data?.detail || "Erreur d'import");
      }
    } finally { setBusy(false); }
  };

  const previewValid = () => {
    const dateOK = mapping.date_column != null;
    const descOK = mapping.description_column != null;
    const amountOK = mapping.amount_mode === "single"
      ? mapping.amount_column != null
      : (mapping.debit_column != null && mapping.credit_column != null);
    return dateOK && descOK && amountOK;
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>Nouvel import — Étape {step} / 2</h2>
        <button onClick={onCancel} style={{ background: "none", border: "none", cursor: "pointer" }}>
          <X size={20} />
        </button>
      </div>
      {err && <div style={{ background: "#fee2e2", color: "#991b1b", padding: 10, borderRadius: 6, marginBottom: 12 }}>{err}</div>}

      {step === 1 && (
        <div>
          <label style={{ display: "block", marginBottom: 12 }}>
            Banque (ex: « Desjardins perso »)
            <input list="bank-list" value={bankLabel}
                   onChange={(e) => setBankLabel(e.target.value)}
                   style={{ width: "100%", padding: 8, border: "1px solid #d1d5db", borderRadius: 6, marginTop: 4 }} />
            <datalist id="bank-list">
              {mappings.map(m => <option key={m.id} value={m.bank_label} />)}
            </datalist>
          </label>
          <div style={{ marginTop: 16, padding: 24, border: "2px dashed #d1d5db", borderRadius: 8, textAlign: "center" }}>
            <Upload size={32} style={{ opacity: 0.5 }} />
            <p>Choisis un fichier CSV (max 5 MB / 5000 lignes)</p>
            <input type="file" accept=".csv,text/csv" onChange={onFileChosen} />
            {file && <p style={{ color: "#059669", marginTop: 8 }}>{file.name} ({(file.size / 1024).toFixed(1)} Ko)</p>}
          </div>
          <button onClick={goStep2} disabled={!file || !bankLabel.trim()}
                  style={{ marginTop: 16, background: "#00A08C", color: "#fff", border: "none",
                           padding: "10px 20px", borderRadius: 8, cursor: "pointer",
                           opacity: (!file || !bankLabel.trim()) ? 0.5 : 1,
                           display: "inline-flex", alignItems: "center", gap: 6 }}>
            Suivant <ArrowRight size={14} />
          </button>
        </div>
      )}

      {step === 2 && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
            <label>Délimiteur
              <select value={mapping.delimiter}
                      onChange={(e) => setMapping({ ...mapping, delimiter: e.target.value })}
                      style={{ width: "100%", padding: 6, marginTop: 4 }}>
                <option value=",">,</option>
                <option value=";">;</option>
                <option value={"\t"}>tab</option>
              </select>
            </label>
            <label>Format date
              <select value={mapping.date_format}
                      onChange={(e) => setMapping({ ...mapping, date_format: e.target.value })}
                      style={{ width: "100%", padding: 6, marginTop: 4 }}>
                <option>YYYY-MM-DD</option>
                <option>DD/MM/YYYY</option>
                <option>MM/DD/YYYY</option>
              </select>
            </label>
            <label>Première ligne
              <select value={mapping.has_header ? "yes" : "no"}
                      onChange={(e) => setMapping({ ...mapping, has_header: e.target.value === "yes" })}
                      style={{ width: "100%", padding: 6, marginTop: 4 }}>
                <option value="yes">En-têtes</option>
                <option value="no">Données</option>
              </select>
            </label>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
            <label>Colonne Date (index 0-based)
              <input type="number" min="0" value={mapping.date_column ?? 0}
                     onChange={(e) => setMapping({ ...mapping, date_column: parseInt(e.target.value, 10) || 0 })}
                     style={{ width: "100%", padding: 6, marginTop: 4 }} />
            </label>
            <label>Colonne Description (index)
              <input type="number" min="0" value={mapping.description_column ?? 1}
                     onChange={(e) => setMapping({ ...mapping, description_column: parseInt(e.target.value, 10) || 0 })}
                     style={{ width: "100%", padding: 6, marginTop: 4 }} />
            </label>
            <label>Mode montant
              <select value={mapping.amount_mode}
                      onChange={(e) => setMapping({ ...mapping, amount_mode: e.target.value })}
                      style={{ width: "100%", padding: 6, marginTop: 4 }}>
                <option value="single">Une colonne (signé)</option>
                <option value="debit_credit">Débit + Crédit</option>
              </select>
            </label>
            {mapping.amount_mode === "single" ? (
              <label>Colonne Montant
                <input type="number" min="0" value={mapping.amount_column ?? 2}
                       onChange={(e) => setMapping({ ...mapping, amount_column: parseInt(e.target.value, 10) || 0 })}
                       style={{ width: "100%", padding: 6, marginTop: 4 }} />
              </label>
            ) : (
              <div style={{ display: "flex", gap: 10 }}>
                <label style={{ flex: 1 }}>Col Débit
                  <input type="number" min="0" value={mapping.debit_column ?? 2}
                         onChange={(e) => setMapping({ ...mapping, debit_column: parseInt(e.target.value, 10) || 0 })}
                         style={{ width: "100%", padding: 6, marginTop: 4 }} />
                </label>
                <label style={{ flex: 1 }}>Col Crédit
                  <input type="number" min="0" value={mapping.credit_column ?? 3}
                         onChange={(e) => setMapping({ ...mapping, credit_column: parseInt(e.target.value, 10) || 0 })}
                         style={{ width: "100%", padding: 6, marginTop: 4 }} />
                </label>
              </div>
            )}
          </div>
          <label style={{ display: "block", marginBottom: 12 }}>
            <input type="checkbox" checked={mapping.sign_convention === "positive_is_credit"}
                   onChange={(e) => setMapping({
                     ...mapping,
                     sign_convention: e.target.checked ? "positive_is_credit" : "positive_is_debit",
                   })} />
            {" "}Convention: positif = crédit (décocher si ta banque inverse)
          </label>
          <label style={{ display: "block", marginBottom: 12 }}>
            <input type="checkbox" checked={saveMapping}
                   onChange={(e) => setSaveMapping(e.target.checked)} />
            {" "}Sauvegarder ce mapping comme « {bankLabel} »
          </label>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <button onClick={runPreview} disabled={busy || !previewValid()}
                    style={{ background: "#e5e7eb", padding: "8px 16px", border: "none", borderRadius: 6, cursor: "pointer" }}>
              {busy ? "…" : "Vérifier"}
            </button>
            <button onClick={doImport} disabled={!preview || busy}
                    style={{ background: "#00A08C", color: "#fff", padding: "8px 16px", border: "none", borderRadius: 6,
                             cursor: "pointer", opacity: (!preview || busy) ? 0.5 : 1 }}>
              {busy ? "Import…" : "Importer"}
            </button>
            <button onClick={() => setStep(1)}
                    style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer" }}>
              ← Retour
            </button>
          </div>
          {preview && (
            <div>
              <h4>Aperçu ({preview.total_rows} lignes au total) :</h4>
              <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#f3f4f6", textAlign: "left" }}>
                    <th style={{ padding: 6 }}>Date</th>
                    <th style={{ padding: 6 }}>Description</th>
                    <th style={{ padding: 6, textAlign: "right" }}>Montant</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.parsed_rows.map((r, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #e5e7eb",
                                         color: r.parse_error ? "#dc2626" : "inherit" }}>
                      <td style={{ padding: 6 }}>{r.date || "—"}</td>
                      <td style={{ padding: 6 }}>{r.description}</td>
                      <td style={{ padding: 6, textAlign: "right" }}>
                        {r.amount_cad != null ? r.amount_cad.toFixed(2) + " $" : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
