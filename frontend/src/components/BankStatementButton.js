import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { FileSearch } from "lucide-react";
import { BACKEND_URL } from "../config";

/**
 * Ouvre / télécharge le RELEVÉ ORIGINAL d'un import bancaire — évite de retourner sur le site
 * de la banque. Servi par GET /api/bank/imports/{id}/statement (authentifié, scopé org).
 *
 * - PDF  → modale in-app (<iframe>). `window.open()` après un `await` est bloqué par Safari iOS
 *          (hors geste utilisateur) : on affiche donc dans l'app, comme pour les reçus.
 * - CSV/XLSX → téléchargement du fichier original (un CSV ne s'affiche pas comme un document ;
 *          l'écran de rapprochement montre déjà les lignes parsées).
 *
 * N'est rendu que si l'import a bien un fichier conservé (has_statement_file) — les imports
 * antérieurs à cette fonctionnalité n'en ont pas.
 */
export default function BankStatementButton({ importId, source, bankLabel, variant = "icon" }) {
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState(null); // { url }
  const [error, setError] = useState("");

  // Pas de fuite d'object URL si le composant est démonté alors que la modale est ouverte.
  const viewingRef = useRef(null);
  viewingRef.current = viewing;
  useEffect(() => () => {
    if (viewingRef.current?.url) URL.revokeObjectURL(viewingRef.current.url);
  }, []);

  const isPdf = (source || "").toLowerCase() === "pdf";
  const ext = (source || "").toLowerCase() === "xlsx" ? "xlsx" : (isPdf ? "pdf" : "csv");

  const fetchBlob = async (download) => {
    const r = await axios.get(
      `${BACKEND_URL}/api/bank/imports/${importId}/statement${download ? "?download=1" : ""}`,
      { responseType: "blob" }
    );
    return r.data;
  };

  const triggerDownload = (blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `releve-${(bankLabel || "banque").replace(/[^A-Za-z0-9._-]+/g, "_")}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    // Révocation DIFFÉRÉE : révoquer synchronement juste après click() annule le téléchargement
    // dans plusieurs navigateurs (le blob disparaît avant que le transfert ne démarre).
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  };

  const open = async (e) => {
    if (e) e.stopPropagation();
    setBusy(true);
    setError("");
    try {
      if (isPdf) {
        const blob = await fetchBlob(false);
        setViewing({ url: URL.createObjectURL(blob) });
      } else {
        triggerDownload(await fetchBlob(true));
      }
    } catch (err) {
      setError(
        err.response?.status === 404
          ? "Relevé original non conservé pour cet import."
          : "Impossible d'ouvrir le relevé."
      );
    } finally {
      setBusy(false);
    }
  };

  const close = () => setViewing((prev) => {
    if (prev?.url) URL.revokeObjectURL(prev.url);
    return null;
  });

  const label = isPdf ? "Voir le relevé original" : "Télécharger le relevé original";

  return (
    <>
      {variant === "icon" ? (
        <button onClick={open} disabled={busy} title={label}
                data-testid={`statement-btn-${importId}`}
                style={{ background: "none", border: "none", padding: 4,
                         cursor: busy ? "wait" : "pointer", color: "#0369a1",
                         opacity: busy ? 0.5 : 1 }}>
          <FileSearch size={16} />
        </button>
      ) : (
        <button onClick={open} disabled={busy} data-testid={`statement-btn-${importId}`}
                style={{ display: "inline-flex", alignItems: "center", gap: 6,
                         background: "#f0f9ff", color: "#0369a1", border: "1px solid #bae6fd",
                         padding: "8px 14px", borderRadius: 8,
                         cursor: busy ? "wait" : "pointer", fontSize: 14 }}>
          <FileSearch size={14} /> {busy ? "Ouverture…" : label}
        </button>
      )}

      {error && (
        <div style={{ color: "#b91c1c", fontSize: 12, marginTop: 4 }}>{error}</div>
      )}

      {viewing && (
        <div onClick={close}
             style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 70,
                      display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: "#fff", borderRadius: 12, width: "100%", maxWidth: 900,
                        height: "90vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                          padding: "12px 16px", borderBottom: "1px solid #e5e7eb" }}>
              <strong style={{ fontSize: 14 }}>Relevé original — {bankLabel}</strong>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {/* vrai geste utilisateur → non bloqué par iOS */}
                <a href={viewing.url} target="_blank" rel="noreferrer"
                   style={{ fontSize: 13, color: "#0369a1" }}>Ouvrir en plein écran</a>
                <button onClick={() => fetchBlob(true).then(triggerDownload).catch(() => {})}
                        style={{ background: "#f0f9ff", color: "#0369a1", border: "1px solid #bae6fd",
                                 padding: "6px 10px", borderRadius: 6, cursor: "pointer", fontSize: 13 }}>
                  Télécharger
                </button>
                <button onClick={close}
                        style={{ background: "none", border: "none", fontSize: 22,
                                 cursor: "pointer", color: "#6b7280", lineHeight: 1 }}>×</button>
              </div>
            </div>
            <iframe title="Relevé original" src={viewing.url}
                    style={{ flex: 1, width: "100%", border: "none" }} />
          </div>
        </div>
      )}
    </>
  );
}
