/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        "city-dark": "#0a0f1e",
        "city-panel": "#111827",
        "city-border": "#1f2937",
        "city-accent": "#3b82f6",
        "risk-high": "#ef4444",
        "risk-med": "#f59e0b",
        "risk-low": "#22c55e",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        typing: "typing 1.5s steps(20) infinite",
      },
    },
  },
  plugins: [],
};
