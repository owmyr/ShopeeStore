import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        graphite: {
          DEFAULT: "#121316",
          surface: "#1A1B20",
          card: "#22232A",
          border: "#2E3038",
          subtle: "#3A3D47",
          muted: "#8E9099",
          dim: "#5E606A",
        },
      },
      aspectRatio: {
        "3/4": "3 / 4",
      },
      fontFamily: {
        sans: ["var(--font-plus-jakarta-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
