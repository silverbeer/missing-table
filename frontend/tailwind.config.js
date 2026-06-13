/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      colors: {
        // Midnight Amber palette (SB-144): deep-navy brand chrome + warm amber accent.
        brand: {
          50: '#eef3fb',
          100: '#d4e0f5',
          200: '#aac3ea',
          300: '#779edb',
          400: '#4a72c9',
          500: '#1e40af', // primary navy
          600: '#1a3793', // header / hover
          700: '#152c75',
          800: '#112357',
          900: '#0c1838',
        },
        accent: {
          50: '#fef6e7',
          100: '#fde8bf',
          200: '#fbd187',
          300: '#f9b84e',
          400: '#f59e0b', // accent amber
          500: '#d97f06',
          600: '#b45309', // text-safe amber on light surfaces
          700: '#8f3f0a',
          800: '#6b2f0a',
          900: '#45200a',
        },
        // Semantic tokens (SB-146) — flip with .dark via CSS vars in style.css.
        surface: {
          DEFAULT: 'rgb(var(--color-surface) / <alpha-value>)',
          alt: 'rgb(var(--color-surface-alt) / <alpha-value>)',
        },
        card: 'rgb(var(--color-card) / <alpha-value>)',
        fg: {
          DEFAULT: 'rgb(var(--color-fg) / <alpha-value>)',
          muted: 'rgb(var(--color-fg-muted) / <alpha-value>)',
        },
        line: 'rgb(var(--color-line) / <alpha-value>)',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};
