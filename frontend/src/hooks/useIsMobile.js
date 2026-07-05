import { useState, useEffect } from 'react';

// Vrai quand la largeur du viewport est sous le point de rupture (défaut 768px = tablette/mobile).
// Réactif au redimensionnement/rotation. Utilisé pour adapter les mises en page inline
// (grilles multi-colonnes → 1 colonne, barre latérale off-canvas, modales pleine largeur…).
export default function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' && window.innerWidth < breakpoint
  );
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < breakpoint);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [breakpoint]);
  return isMobile;
}
