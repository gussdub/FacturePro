import React, { useState, useEffect, useRef } from "react";
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
  const [presets, setPresets] = useState([]);
  const [presetHint, setPresetHint] = useState(null);
  const [mapping, setMapping] = useState(DEFAULT_MAPPING);
  const [saveMapping, setSaveMapping] = useState(true);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [err, setErr] = useState(null);
  const previewSeq = useRef(0);
  const previewInFlight = useRef(false);
  // Un PDF est routé vers l'extraction IA. Détecté par MAGIC-BYTES dans onFileChosen
  // (aligné exactement sur le backend raw[:16].lstrip().startswith("%PDF")), jamais par
  // extension/MIME — sinon un PDF renommé .csv échapperait au bon flux et facturerait un scan.
  const [isPdf, setIsPdf] = useState(false);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/bank/mappings`)
      .then(r => setMappings(r.data || []))
      .catch(() => {});
    axios.get(`${BACKEND_URL}/api/bank/presets`)
      .then(r => setPresets(r.data || []))
      .catch(() => {});
  }, []);

  // Sélection d'un préréglage intégré (ex. Desjardins AccèsD) : pré-remplit les colonnes.
  // L'aperçu (dry-run) reste la validation avant l'import.
  const applyPreset = (key) => {
    const p = presets.find(x => x.key === key);
    if (!p) { setPresetHint(null); return; }
    setMapping({ ...DEFAULT_MAPPING, ...p.mapping });
    if (!bankLabel.trim()) setBankLabel(p.label);
    setPresetHint(p.hint || null);
  };

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

  const onFileChosen = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    // Détection PDF par magic-bytes (%PDF, préambule d'espaces toléré) — aligne sur le backend.
    let pdf = false;
    try {
      const head = new Uint8Array(await f.slice(0, 16).arrayBuffer());
      let i = 0;
      while (i < head.length && (head[i] === 0x20 || head[i] === 0x09 || head[i] === 0x0a || head[i] === 0x0d)) i++;
      pdf = head[i] === 0x25 && head[i + 1] === 0x50 && head[i + 2] === 0x44 && head[i + 3] === 0x46; // "%PDF"
    } catch {
      pdf = f.type === "application/pdf" || /\.pdf$/i.test(f.name || "");
    }
    const capMb = pdf ? 10 : 5;
    if (f.size > capMb * 1024 * 1024) {
      setErr(`Fichier trop volumineux (max ${capMb} MB)`); return;
    }
    previewSeq.current++;          // invalide toute réponse d'aperçu encore en vol
    previewInFlight.current = false; // libère la garde (le fichier a changé)
    setIsPdf(pdf);
    setFile(f); setErr(null); setPreview(null); setPreviewing(false);
  };

  const goStep2 = () => {
    if (!file || !bankLabel.trim()) {
      setErr("Banque et fichier requis"); return;
    }
    setErr(null);
    setStep(2);
  };

  // Aperçu en direct : appelle le dry-run backend (le VRAI _parse_csv_rows) et n'applique
  // que la réponse de la DERNIÈRE requête (garde anti-course via previewSeq), pour que ce
  // qui s'affiche = exactement ce qui sera importé.
  const refreshPreview = async () => {
    // Un PDF n'a pas de mapping de colonnes ; sinon on exige un mapping valide.
    if (!file || (!isPdf && !previewValid())) return;
    // Garde SYNCHRONE anti-double-fire (double-clic, StrictMode) : évite 2 dry_run — donc
    // 2 scans facturés — sur un PDF. Le disabled React n'agit qu'au recommit, trop tard.
    if (previewInFlight.current) return;
    previewInFlight.current = true;
    const seq = ++previewSeq.current;
    setPreviewing(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (!isPdf) fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(
        `${BACKEND_URL}/api/bank/imports?dry_run=true`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      if (seq === previewSeq.current) setPreview(r.data);
    } catch (e) {
      if (seq === previewSeq.current) {
        setErr(e.response?.data?.detail || "Erreur de parsing");
        setPreview(null);
      }
    } finally {
      previewInFlight.current = false;
      if (seq === previewSeq.current) setPreviewing(false);
    }
  };

  // Relance l'aperçu (débounced 400 ms) à chaque changement de fichier ou de réglage de
  // mapping quand on est à l'étape 2. Le nettoyage annule le timer si un nouveau changement
  // arrive avant l'échéance.
  useEffect(() => {
    // PDF exclu : son extraction (Claude, facturée) est déclenchée par un bouton explicite,
    // jamais en direct — sinon chaque frappe consommerait un scan.
    if (step !== 2 || isPdf || !file || !previewValid()) return;
    const t = setTimeout(() => { refreshPreview(); }, 400);
    return () => clearTimeout(t);
  }, [step, file, mapping, isPdf]);

  const doImport = async () => {
    setBusy(true); setErr(null);
    try {
      if (!isPdf && saveMapping && bankLabel.trim()) {
        try {
          await axios.post(`${BACKEND_URL}/api/bank/mappings`,
            { ...mapping, bank_label: bankLabel });
        } catch { /* déjà existant ou limite atteinte — ignorer */ }
      }
      const fd = new FormData();
      fd.append("file", file);
      if (!isPdf) fd.append("mapping", JSON.stringify(mapping));
      fd.append("bank_label", bankLabel);
      const r = await axios.post(`${BACKEND_URL}/api/bank/imports`, fd,
        { headers: { "Content-Type": "multipart/form-data" } });
      onDone(r.data.import.id);
    } catch (e) {
      if (e.response?.status === 409) {
        setErr("Ce fichier a déjà été importé.");
      } else if (e.response?.status === 413) {
        setErr("Fichier trop volumineux.");
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

  // Ambiguïté JJ/MM vs MM/JJ : si TOUTES les dates de l'aperçu ont un jour ≤ 12, on ne peut
  // pas distinguer les deux formats -> on avertit (choisir le mauvais préréglage FR/EN
  // décalerait le mois sans erreur visible). Dès qu'une date a un jour ≥ 13, le format est levé.
  const showDateAmbiguityWarning = (() => {
    if (!preview || !preview.parsed_rows) return false;
    if (mapping.date_format !== "DD/MM/YYYY" && mapping.date_format !== "MM/DD/YYYY") return false;
    const days = preview.parsed_rows
      .filter(r => r.date)
      .map(r => parseInt(String(r.date).slice(8, 10), 10));
    return days.length > 0 && days.every(d => d <= 12);
  })();

  // Tableau d'aperçu partagé (CSV live + PDF après extraction). Lignes en erreur en rouge.
  const previewTable = preview ? (
    <div>
      {!isPdf && showDateAmbiguityWarning && (
        <div style={{ background: "#fef3c7", color: "#92400e", padding: 10, borderRadius: 6, marginBottom: 10, fontSize: 13 }}>
          ⚠️ Toutes les dates de l'aperçu ont un jour ≤ 12 : impossible de distinguer
          JJ/MM de MM/JJ. Assure-toi d'avoir choisi le bon préréglage (français =
          JJ/MM/AAAA, anglais = MM/JJ/AAAA) — sinon le mois sera inversé sans erreur visible.
        </div>
      )}
      <h4>Aperçu ({preview.total_rows} lignes au total) :</h4>
      <div style={{ maxHeight: 360, overflowY: "auto", border: "1px solid #e5e7eb", borderRadius: 6 }}>
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
    </div>
  ) : null;

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
          {presets.length > 0 && (
            <label style={{ display: "block", marginBottom: 12 }}>
              Préréglage (optionnel)
              <select defaultValue="" onChange={(e) => applyPreset(e.target.value)}
                      style={{ width: "100%", padding: 8, border: "1px solid #d1d5db", borderRadius: 6, marginTop: 4 }}>
                <option value="">— Configuration manuelle —</option>
                {presets.map(p => <option key={p.key} value={p.key}>{p.label}</option>)}
              </select>
              {presetHint && (
                <p style={{ fontSize: 12, color: "#6b7280", marginTop: 6, lineHeight: 1.4 }}>💡 {presetHint}</p>
              )}
            </label>
          )}
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
            <p>Choisis un fichier <strong>CSV</strong> (max 5 MB / 5000 lignes) ou un <strong>relevé PDF</strong> (max 10 MB, extraction IA)</p>
            <input type="file" accept=".csv,text/csv,.pdf,application/pdf" onChange={onFileChosen} />
            {file && <p style={{ color: "#059669", marginTop: 8 }}>{file.name} ({(file.size / 1024).toFixed(1)} Ko){isPdf ? " — PDF (extraction IA)" : ""}</p>}
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

      {step === 2 && isPdf && (
        <div>
          <div style={{ background: "#fef3c7", color: "#92400e", padding: 12, borderRadius: 6, marginBottom: 14, fontSize: 13, lineHeight: 1.5 }}>
            ⚠️ <strong>Extraction par IA.</strong> Les transactions sont lues automatiquement depuis
            le PDF. <strong>Vérifie chaque ligne</strong> (date, montant, dépôt = positif /
            retrait = négatif) avant d'importer — l'IA peut manquer ou mal lire une ligne.
            1 relevé = 1 scan de ton quota mensuel.
          </div>
          {!preview ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button onClick={refreshPreview} disabled={previewing}
                      style={{ background: "#00A08C", color: "#fff", padding: "10px 20px", border: "none",
                               borderRadius: 8, cursor: "pointer", opacity: previewing ? 0.6 : 1 }}>
                {previewing ? "Analyse en cours…" : "Analyser le relevé (IA)"}
              </button>
              <button onClick={() => setStep(1)}
                      style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer" }}>
                ← Retour
              </button>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
                <button onClick={doImport} disabled={busy || previewing}
                        style={{ background: "#00A08C", color: "#fff", padding: "8px 16px", border: "none", borderRadius: 6,
                                 cursor: "pointer", opacity: (busy || previewing) ? 0.5 : 1 }}>
                  {busy ? "Import…" : "Importer"}
                </button>
                <button onClick={refreshPreview} disabled={previewing}
                        style={{ background: "#e5e7eb", padding: "8px 16px", border: "none", borderRadius: 6, cursor: "pointer" }}>
                  {previewing ? "…" : "Ré-analyser"}
                </button>
                <button onClick={() => setStep(1)}
                        style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer" }}>
                  ← Retour
                </button>
              </div>
              {previewTable}
            </>
          )}
        </div>
      )}

      {step === 2 && !isPdf && (
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
          <p style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
            L'aperçu ci-dessous se met à jour <strong>en direct</strong> quand tu changes un réglage.
            Confirme que les <strong>dates</strong> et les <strong>montants</strong> (dépôts positifs,
            retraits négatifs) sont corrects avant d'importer.
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
            <button onClick={doImport} disabled={!preview || busy || previewing}
                    style={{ background: "#00A08C", color: "#fff", padding: "8px 16px", border: "none", borderRadius: 6,
                             cursor: "pointer", opacity: (!preview || busy || previewing) ? 0.5 : 1 }}>
              {busy ? "Import…" : "Importer"}
            </button>
            <button onClick={() => setStep(1)}
                    style={{ background: "none", border: "none", color: "#6b7280", cursor: "pointer" }}>
              ← Retour
            </button>
            {previewing && <span style={{ fontSize: 12, color: "#6b7280" }}>Mise à jour de l'aperçu…</span>}
          </div>
          {!previewValid() && (
            <p style={{ fontSize: 13, color: "#92400e", background: "#fef3c7", padding: 10, borderRadius: 6 }}>
              Renseigne les colonnes (Date, Description, Montant) pour générer l'aperçu en direct.
            </p>
          )}
          {previewTable}
        </div>
      )}
    </div>
  );
}
