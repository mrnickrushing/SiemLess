/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#0f1117',
          card: '#1a1f2e',
          border: '#2a3148',
          accent: '#2dd4aa',
          'accent-dim': '#1ab894',
          text: '#e2e8f0',
          muted: '#8892a4',
          critical: '#ff3b3b',
          high: '#ff8c00',
          medium: '#ffd700',
          low: '#4a9eff',
          info: '#00bcd4',
          success: '#2dd4aa',
          warning: '#ffd700',
          danger: '#ff3b3b',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      backgroundImage: {
        'gradient-cyber': 'linear-gradient(135deg, #0f1117 0%, #1a1f2e 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.2s ease-in-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
