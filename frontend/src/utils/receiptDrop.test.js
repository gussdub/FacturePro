// Tests des helpers PURS du glisser-déposer de reçus.
// Le scan est FACTURÉ au quota : ce qui compte ici est de ne jamais laisser passer un fichier
// non pertinent (dépôt accidentel = scan consommé) ni dépasser le plafond du lot.
import {
  isReceiptFile, pickDroppedReceipts, dragHasFiles, MAX_RECEIPTS_PER_BATCH,
} from './receiptDrop';

const f = (name, type = '') => ({ name, type });

describe('isReceiptFile', () => {
  it('accepte les types MIME de reçus', () => {
    expect(isReceiptFile(f('a.jpg', 'image/jpeg'))).toBe(true);
    expect(isReceiptFile(f('a.png', 'image/png'))).toBe(true);
    expect(isReceiptFile(f('a.webp', 'image/webp'))).toBe(true);
    expect(isReceiptFile(f('a.gif', 'image/gif'))).toBe(true);
    expect(isReceiptFile(f('recu.pdf', 'application/pdf'))).toBe(true);
  });

  it('accepte via extension quand le navigateur ne donne pas de type', () => {
    expect(isReceiptFile(f('RECU.JPEG', ''))).toBe(true);
    expect(isReceiptFile(f('scan.PDF', ''))).toBe(true);
  });

  it('refuse les fichiers non pertinents', () => {
    expect(isReceiptFile(f('releve.csv', 'text/csv'))).toBe(false);
    expect(isReceiptFile(f('notes.txt', 'text/plain'))).toBe(false);
    expect(isReceiptFile(f('tableur.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'))).toBe(false);
    expect(isReceiptFile(f('archive.zip', 'application/zip'))).toBe(false);
  });

  it('refuse un dossier déposé (ni type ni extension) et les valeurs vides', () => {
    expect(isReceiptFile(f('Mes recus', ''))).toBe(false);
    expect(isReceiptFile(null)).toBe(false);
    expect(isReceiptFile(undefined)).toBe(false);
  });

  it("ne se laisse pas berner par une extension au milieu du nom", () => {
    expect(isReceiptFile(f('facture.pdf.exe', 'application/octet-stream'))).toBe(false);
  });
});

describe('pickDroppedReceipts', () => {
  it('ne garde que les reçus et ignore le reste', () => {
    const r = pickDroppedReceipts([
      f('a.jpg', 'image/jpeg'), f('releve.csv', 'text/csv'), f('b.pdf', 'application/pdf'),
    ]);
    expect(r.error).toBeNull();
    expect(r.files.map(x => x.name)).toEqual(['a.jpg', 'b.pdf']);
  });

  it('renvoie une erreur (et aucun fichier) si rien n’est acceptable', () => {
    const r = pickDroppedReceipts([f('releve.csv', 'text/csv')]);
    expect(r.files).toEqual([]);
    expect(r.error).toMatch(/Formats acceptés/);
  });

  it('renvoie une erreur sur un dépôt vide', () => {
    expect(pickDroppedReceipts([]).error).toMatch(/Formats acceptés/);
    expect(pickDroppedReceipts(null).error).toMatch(/Formats acceptés/);
  });

  it('refuse TOUT le lot au-delà du plafond (jamais de scan partiel surprise)', () => {
    const many = Array.from({ length: MAX_RECEIPTS_PER_BATCH + 1 },
      (_, i) => f(`r${i}.jpg`, 'image/jpeg'));
    const r = pickDroppedReceipts(many);
    expect(r.files).toEqual([]);
    expect(r.error).toMatch(/Max 20/);
  });

  it('accepte exactement le plafond', () => {
    const many = Array.from({ length: MAX_RECEIPTS_PER_BATCH },
      (_, i) => f(`r${i}.jpg`, 'image/jpeg'));
    const r = pickDroppedReceipts(many);
    expect(r.error).toBeNull();
    expect(r.files).toHaveLength(MAX_RECEIPTS_PER_BATCH);
  });
});

describe('dragHasFiles', () => {
  it('vrai seulement pour un glisser de fichiers', () => {
    expect(dragHasFiles({ types: ['Files'] })).toBe(true);
    expect(dragHasFiles({ types: ['text/plain'] })).toBe(false);
    expect(dragHasFiles({ types: [] })).toBe(false);
    expect(dragHasFiles(null)).toBe(false);
    expect(dragHasFiles(undefined)).toBe(false);
  });
});
