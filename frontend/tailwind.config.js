/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // 主品牌色：沉静墨青（心理学测试更稳重）
        // 50-950 跨度同时覆盖亮色（低 ink-50）和深色（高 ink-950）背景
        ink: {
          50: '#f5f7f8',
          100: '#e6ecee',
          200: '#cad5d9',
          300: '#a3b3ba',
          400: '#7a8d96',
          500: '#5d717a',
          600: '#4b5d65',
          700: '#3e4d54',
          800: '#354144',
          900: '#1f2629',
          950: '#0f1316',
        },
        // 强调色：暖橘 — 给选项和 CTA
        ember: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
        },
        // 暗色背景层（在 dark 模式下作为"卡片表面"叠加在 ink-950 上）
        surface: {
          light: '#ffffff',
          DEFAULT: '#ffffff',
          dark: '#1a2024',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei"',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        serif: ['"Source Han Serif SC"', '"Noto Serif CJK SC"', 'Georgia', 'serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
}
