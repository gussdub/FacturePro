// Helpers PURS du glisser-déposer de reçus (page Dépenses).
// Isolés ici pour être testables sans DOM ni montage du gros composant ExpensesPage.

export const RECEIPT_MIMES = [
  'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf',
];

export const MAX_RECEIPTS_PER_BATCH = 20;

/** Un fichier déposé est-il un reçu acceptable ? (MIME, sinon extension : certains navigateurs /
 *  systèmes de fichiers ne renseignent pas le type.) */
export function isReceiptFile(file) {
  if (!file) return false;
  if (RECEIPT_MIMES.includes(file.type)) return true;
  // Un dossier déposé arrive sans type ET sans extension → exclu par la regex.
  return /\.(jpe?g|png|webp|gif|pdf)$/i.test(file.name || '');
}

/**
 * Trie les fichiers d'un dépôt.
 * @returns {{files: File[], error: string|null}} `error` non nul ⇒ ne rien scanner.
 */
export function pickDroppedReceipts(fileList) {
  const all = Array.from(fileList || []);
  const files = all.filter(isReceiptFile);
  if (files.length === 0) {
    return { files: [], error: 'Formats acceptés : JPG, PNG, WEBP, GIF ou PDF.' };
  }
  if (files.length > MAX_RECEIPTS_PER_BATCH) {
    return { files: [], error: `Max ${MAX_RECEIPTS_PER_BATCH} fichiers par lot` };
  }
  return { files, error: null };
}

/** Le glisser en cours transporte-t-il des FICHIERS (et non une sélection de texte / un élément) ? */
export function dragHasFiles(dataTransfer) {
  return Array.from(dataTransfer?.types || []).includes('Files');
}
