/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
  ],
  theme: {
    extend: {
      colors: {
        orange: {
          DEFAULT: '#FF7900',
          hover: '#E66D00',
          light: '#FFF5EB',
          dark: '#CC6100',
        },
      },
    },
  },
  plugins: [],
}

