/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        cyber: {
          bg: "#0a0a0f",
          "bg-secondary": "#111118",
          card: "#16161f",
          "card-hover": "#1c1c28",
          accent: "#00ffa3",
          "accent-dim": "#00cc82",
          info: "#3b82f6",
          warning: "#f59e0b",
          error: "#ef4444",
          border: "#27272a",
        },
      },
      fontFamily: {
        heading: ['JetBrains Mono', 'monospace'],
        body: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
