import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const AccessibilityContext = createContext(null);

const DEFAULTS = {
  font_size: 'md',
  high_contrast: false,
  simplified_ui: false,
  dyslexia_font: false,
  reduce_motion: false,
};

const STORAGE_KEY = 'medflow-a11y';

const applyToDom = (prefs) => {
  const el = document.documentElement;
  el.setAttribute('data-a11y-font', prefs.font_size || 'md');
  el.setAttribute('data-a11y-contrast', prefs.high_contrast ? 'high' : 'normal');
  el.setAttribute('data-a11y-simplified', prefs.simplified_ui ? 'true' : 'false');
  el.setAttribute('data-a11y-dyslexia', prefs.dyslexia_font ? 'true' : 'false');
  el.setAttribute('data-a11y-reduce-motion', prefs.reduce_motion ? 'true' : 'false');
};

export const AccessibilityProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [prefs, setPrefs] = useState(() => {
    if (typeof window === 'undefined') return DEFAULTS;
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null');
      if (saved && typeof saved === 'object') return { ...DEFAULTS, ...saved };
    } catch (e) { /* noop */ }
    return DEFAULTS;
  });

  // Aplica no DOM sempre que muda
  useEffect(() => {
    applyToDom(prefs);
    try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs)); } catch (e) { /* noop */ }
  }, [prefs]);

  // Sincroniza com o profile do servidor no mount
  useEffect(() => {
    if (isAuthenticated !== true) return;
    (async () => {
      try {
        const { data } = await api.get('/profile');
        const p = data?.profile || {};
        setPrefs((cur) => ({
          ...cur,
          font_size: p.font_size ?? cur.font_size,
          high_contrast: p.high_contrast ?? cur.high_contrast,
          simplified_ui: p.simplified_ui ?? cur.simplified_ui,
          dyslexia_font: p.dyslexia_font ?? cur.dyslexia_font,
          reduce_motion: p.reduce_motion ?? cur.reduce_motion,
        }));
      } catch (e) { /* silent — usuário sem sessão */ }
    })();
  }, [isAuthenticated]);

  const update = useCallback(async (patch) => {
    setPrefs((cur) => ({ ...cur, ...patch }));
    if (isAuthenticated !== true) return;
    try { await api.patch('/profile', patch); } catch (e) { /* noop */ }
  }, [isAuthenticated]);

  return (
    <AccessibilityContext.Provider value={{ prefs, update }}>
      {children}
    </AccessibilityContext.Provider>
  );
};

export const useAccessibility = () => {
  const ctx = useContext(AccessibilityContext);
  if (!ctx) throw new Error('useAccessibility must be used within AccessibilityProvider');
  return ctx;
};
