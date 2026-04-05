/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
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
        brand: {
          50: '#e8f0ff',
          100: '#c0d4ff',
          200: '#99b8ff',
          300: '#6694ff',
          400: '#3370ff',
          500: '#0257fe', // logo blue
          600: '#0047d4',
          700: '#0038aa',
          800: '#002b82',
          900: '#001e5a',
        },
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
};
