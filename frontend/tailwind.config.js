/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        alan: {
          blue: '#2563eb',      // 깔끔한 파란색 (강조용)
          gray: {
            50: '#f9fafb',
            100: '#f3f4f6',
            200: '#e5e7eb',
            300: '#d1d5db',
            600: '#4b5563',
            700: '#374151',
            900: '#111827',
          }
        },
      },
    },
  },
  plugins: [],
}