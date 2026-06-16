/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        goodpack: {
          navy:   '#1a3a5c',
          orange: '#e8722a',
        },
      },
    },
  },
  plugins: [],
}
