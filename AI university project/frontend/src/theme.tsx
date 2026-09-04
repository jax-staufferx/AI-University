import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark';
type TextSize = 'small' | 'medium' | 'large' | 'xlarge';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  textSize: TextSize;
  setTextSize: (size: TextSize) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const TEXT_SIZE_PX: Record<TextSize, number> = {
  small: 16,
  medium: 18,
  large: 20,
  xlarge: 22,
};

function getInitialTheme(): Theme {
  const stored = localStorage.getItem('pla-theme');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getInitialTextSize(): TextSize {
  const stored = localStorage.getItem('pla-text-size');
  if (stored === 'small' || stored === 'medium' || stored === 'large' || stored === 'xlarge') return stored;
  return 'medium';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [textSize, setTextSizeState] = useState<TextSize>(getInitialTextSize);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('pla-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty('--reading-size', `${TEXT_SIZE_PX[textSize]}px`);
    localStorage.setItem('pla-text-size', textSize);
  }, [textSize]);

  const toggleTheme = () => setTheme((t) => (t === 'light' ? 'dark' : 'light'));
  const setTextSize = (size: TextSize) => setTextSizeState(size);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, textSize, setTextSize }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
