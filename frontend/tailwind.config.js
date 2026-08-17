/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  safelist: [
    'bg-brand', 'text-brand', 'border-brand',
    'bg-success', 'text-success', 'border-success',
    'bg-attention', 'text-attention', 'border-attention',
    'bg-care', 'text-care', 'border-care',
    'text-zinc-900', 'text-zinc-700', 'text-zinc-500', 'text-zinc-400',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', '"SF Mono"', 'Menlo', 'monospace'],
        display: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      colors: {
        // MedFlow clinical brand tokens
        brand: {
          DEFAULT: '#1F6FEB',
          hover:   '#1957C4',
          soft:    '#E7EFFE',
        },
        success:   { DEFAULT: '#059669', soft: '#D1FAE5' },
        attention: { DEFAULT: '#F59E0B', soft: '#FEF3C7' },
        care:      { DEFAULT: '#DC6B4C', soft: '#FDE7DE' },
        hairline: '#E5E5E7',
        canvas:   '#FFFFFF',
        surface:  '#FAFAFB',

        // Zinc-based neutral scale (Anthropic Console / Vercel-like)
        stone: {
          50:  '#FAFAFB',
          100: '#F4F4F5',
          200: '#E5E5E7',
          300: '#D4D4D8',
          400: '#A1A1AA',
          500: '#71717A',
          600: '#52525B',
          700: '#3F3F46',
          800: '#27272A',
          900: '#0A0A0B',
        },
        // Keep sage/terracotta as aliases pointing to semantic tokens (legacy support)
        sage: {
          50:  '#ECFDF5',
          100: '#D1FAE5',
          500: '#059669',
          600: '#047857',
          700: '#065F46',
          800: '#064E3B',
        },
        terracotta: {
          50:  '#FDE7DE',
          100: '#FBD3C1',
          500: '#DC6B4C',
          600: '#B85539',
          700: '#8A3D28',
        },
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 500ms cubic-bezier(0.16,1,0.3,1) both',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
