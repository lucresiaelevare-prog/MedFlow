import { createContext, useContext, useCallback, useState, useEffect } from 'react';

const FocusContext = createContext(null);

const KEY = 'medflow-focus';

export const FocusProvider = ({ children }) => {
  const [focus, setFocus] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(KEY) === '1';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-focus', focus ? 'on' : 'off');
    try { window.localStorage.setItem(KEY, focus ? '1' : '0'); } catch (e) { /* noop */ }
  }, [focus]);

  const toggle = useCallback(() => setFocus((f) => !f), []);
  return (
    <FocusContext.Provider value={{ focus, setFocus, toggle }}>
      {children}
    </FocusContext.Provider>
  );
};

export const useFocus = () => {
  const ctx = useContext(FocusContext);
  if (!ctx) throw new Error('useFocus must be used within FocusProvider');
  return ctx;
};
