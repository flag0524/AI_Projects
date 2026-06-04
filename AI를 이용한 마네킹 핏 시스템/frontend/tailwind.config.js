/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Pretendard", "system-ui", "sans-serif"],
      },
      colors: {
        ink:    "#1a1a1a",
        paper:  "#f7f5f0",
        warm:   "#e8e4dc",
        accent: "#c8502a",
        muted:  "#888070",
        border: "#d8d4cc",
      },
    },
  },
  plugins: [],
};
