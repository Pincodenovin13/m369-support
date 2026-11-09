import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#fff5ed",
          100: "#ffe8d4",
          200: "#ffcda8",
          300: "#ffaa70",
          400: "#ff7a37",
          500: "#FF6B35",
          600: "#f04e16",
          700: "#c73c12",
          800: "#9e3214",
          900: "#7f2b14",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
