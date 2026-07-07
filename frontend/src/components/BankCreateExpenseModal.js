import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { X } from "lucide-react";
import { BACKEND_URL } from "../config";

function taxCodeLabel(cat, entityType) {
  if (!cat) return '';
  if (entityType === 'corporation') {
    return cat.gifi_code ? ` — GIFI ${cat.gifi_code}` : '';
  }
  return cat.t2125_line ? ` — T2125 ligne ${cat.t2125_line}` : '';
}

export default function BankCreateExpenseModal({ tx, onClose, onCreated }) {
  const [categoryCatalog, setCategoryCatalog] = useState({ categories: [], groups: {} });
  const [entityType, setEntityType] = useState('sole_proprietor');
  const [categoryCode, setCategoryCode] = useState("");
  const [vendor, setVendor] = useState((tx.description || "").slice(0, 60));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/expense-categories`)
      .then(r => setCategoryCatalog(r.data || { categories: [], groups: {} }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    axios.get(`${BACKEND_URL}/api/settings/company`)
      .then(r => setEntityType(r.data?.entity_type || 'sole_proprietor'))
      .catch(() => {});
  }, []);

  const groupedCategories = useMemo(() => {
    const grouped = {};
    (categoryCatalog.categories || []).forEach(cat => {
      const g = cat.group || 'other';
      if (!grouped[g]) grouped[g] = [];
      grouped[g].push(cat);
    });
    return grouped;
  }, [categoryCatalog]);

  const submit = async (e) => {
    e.preventDefault();
    if (!categoryCode) { setErr("Catégorie requise"); return; }
    setBusy(true);
    try {
      await axios.post(`${BACKEND_URL}/api/bank/transactions/${tx.id}/create-expense`,
        { category_code: categoryCode, vendor });
      onCreated();
    } catch (e) {
      setErr(e.response?.data?.detail || "Erreur");
    } finally { setBusy(false); }
  };

  return (
    <div style={overlay} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Créer une dépense</h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer" }}><X size={18} /></button>
        </div>
        <form onSubmit={submit}>
          <div style={{ background: "#f8fafb", padding: 10, borderRadius: 6, marginBottom: 12, fontSize: 13 }}>
            <div style={{ color: "#6b7280" }}>Depuis ligne CSV :</div>
            <div><strong>{tx.date} — {tx.description}</strong></div>
            <div><strong>{Math.abs(tx.amount_cad).toFixed(2)} $ CAD</strong></div>
          </div>
          <label style={{ display: "block", marginBottom: 12 }}>Vendeur
            <input value={vendor} onChange={(e) => setVendor(e.target.value)}
                   style={{ width: "100%", padding: 6, marginTop: 4, border: "1px solid #d1d5db", borderRadius: 4 }} />
          </label>
          <label style={{ display: "block", marginBottom: 12 }}>Catégorie ARC *
            <select value={categoryCode} onChange={(e) => setCategoryCode(e.target.value)}
                    required style={{ width: "100%", padding: 6, marginTop: 4, border: "1px solid #d1d5db", borderRadius: 4 }}>
              <option value="">— choisir —</option>
              {Object.entries(groupedCategories)
                .filter(([groupKey]) => groupKey !== 'other')
                .map(([groupKey, cats]) => (
                  <optgroup key={groupKey} label={categoryCatalog.groups?.[groupKey] || groupKey}>
                    {cats.map(c => (
                      <option key={c.code} value={c.code}>
                        {c.label_fr || c.label || c.code}
                        {c.deductible_percentage < 100 ? ` ${c.deductible_percentage}%` : ''}
                        {taxCodeLabel(c, entityType)}
                      </option>
                    ))}
                  </optgroup>
                ))
              }
              {groupedCategories.other && (
                <optgroup label={categoryCatalog.groups?.other || 'Autre'}>
                  {groupedCategories.other.map(c => (
                    <option key={c.code} value={c.code}>
                      {c.label_fr || c.label || c.code}
                      {taxCodeLabel(c, entityType)}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </label>
          {err && <p style={{ color: "#dc2626", fontSize: 13 }}>{err}</p>}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={busy} style={btnGreen}>{busy ? "…" : "Créer"}</button>
            <button type="button" onClick={onClose} style={btnGray}>Annuler</button>
          </div>
        </form>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modal = { background: "#fff", borderRadius: 12, padding: 20, width: "90%", maxWidth: 520 };
const btnGreen = { background: "#059669", color: "#fff", border: "none",
                   padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
const btnGray = { background: "#e5e7eb", border: "none",
                  padding: "8px 16px", borderRadius: 6, cursor: "pointer" };
