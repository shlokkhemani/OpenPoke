import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e1effe',
          200: '#c3dffe',
          300: '#a5cffe',
          400: '#87bffe',
          500: '#69affd',
          600: '#4b9ffd',
          700: '#2d8ffd',
          800: '#0f7ffd',
          900: '#0a66cc'
        }
      }
    },
  },
  darkMode: 'class'
};

export default config;

