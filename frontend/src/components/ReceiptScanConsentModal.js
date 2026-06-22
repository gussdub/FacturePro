import React from "react";
import { X } from "lucide-react";

export default function ReceiptScanConsentModal({ onAccept, onCancel }) {
  return (
    <div style={overlay} onClick={onCancel}>
      <div onClick={(e) => e.stopPropagation()} style={modal}>
        <div style={{ display: "flex", justifyContent: "space-between",
                       alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Utilisation de l'IA pour scanner</h3>
          <button onClick={onCancel}
                  style={{ background: "none", border: "none", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>
        <p style={{ fontSize: 14, lineHeight: 1.5, color: "#374151" }}>
          L'image de votre reçu sera envoyée à <strong>Anthropic</strong> (claude.ai)
          pour extraction automatique des données (vendor, date, montants, taxes).
        </p>
        <p style={{ fontSize: 14, lineHeight: 1.5, color: "#374151" }}>
          Les images sont stockées <strong>dans votre compte FacturePro</strong> et
          supprimées quand vous supprimez la dépense correspondante. Conservation
          conforme aux exigences de l'ARC (6 ans).
        </p>
        <p style={{ fontSize: 13, color: "#6b7280", fontStyle: "italic" }}>
          Ce consentement n'est demandé qu'une fois.
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
          <button onClick={onCancel} style={btnGray}>Annuler</button>
          <button onClick={onAccept} style={btnPrimary}>J'accepte</button>
        </div>
      </div>
    </div>
  );
}

const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  zIndex: 1100 };
const modal = { background: "#fff", borderRadius: 12, padding: 24,
                width: "90%", maxWidth: 480 };
const btnGray = { background: "#e5e7eb", border: "none", padding: "8px 16px",
                  borderRadius: 6, cursor: "pointer" };
const btnPrimary = { background: "#00A08C", color: "#fff", border: "none",
                     padding: "8px 16px", borderRadius: 6, cursor: "pointer",
                     fontWeight: 600 };
