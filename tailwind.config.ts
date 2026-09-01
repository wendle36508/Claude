import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fresh: "#16a34a",
        pickedover: "#d97706",
        empty: "#dc2626",
        stale: "#6b7280",
      },
    },
  },
  plugins: [],
};

export default config;
