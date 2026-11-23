/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb', // Primary brand #2563EB
          700: '#1d4ed8', // Primary hover #1D4ED8
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        sidebar: {
          bg: '#111827',
          border: '#1f2937',
          text: '#9ca3af',
          active: '#2563eb',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        'enterprise': '10px',
      },
    },
  },
  plugins: [],
}
