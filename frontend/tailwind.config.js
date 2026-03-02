/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f4f8',
          100: '#d9e2ec',
          200: '#bcccdc',
          300: '#9fb3c8',
          400: '#829ab1',
          500: '#627d98',
          600: '#486581',
          700: '#334e68',
          800: '#243b53',
          900: '#1e3a5f',
          950: '#102a43',
        },
        priority: {
          immediate: '#dc2626',
          urgent: '#ea580c',
          scheduled: '#ca8a04',
          deferred: '#6b7280',
        },
        status: {
          new: '#6b7280',
          assigned: '#2563eb',
          accepted: '#4f46e5',
          'in-progress': '#7c3aed',
          'waiting-ops': '#d97706',
          'waiting-parts': '#d97706',
          resolved: '#16a34a',
          verified: '#0d9488',
          closed: '#1f2937',
          escalated: '#dc2626',
        },
      },
      animation: {
        'pulse-border': 'pulse-border 2s ease-in-out infinite',
        'flash-red': 'flash-red 1s ease-in-out infinite',
      },
      keyframes: {
        'pulse-border': {
          '0%, 100%': { borderColor: 'rgb(220 38 38)' },
          '50%': { borderColor: 'rgb(220 38 38 / 0.3)' },
        },
        'flash-red': {
          '0%, 100%': { backgroundColor: 'rgb(220 38 38)' },
          '50%': { backgroundColor: 'rgb(220 38 38 / 0.6)' },
        },
      },
      minHeight: {
        touch: '48px',
      },
      minWidth: {
        touch: '48px',
      },
    },
  },
  plugins: [],
};
