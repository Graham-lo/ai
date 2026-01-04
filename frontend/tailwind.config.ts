import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        body: ["var(--font-body)", "sans-serif"],
      },
      colors: {
        ink: "#111111",
        slate: "#2B2B2B",
        haze: "#F3F2EE",
        ember: "#C5532D",
        moss: "#3E6B5B",
        dusk: "#233044",
      },
      backgroundImage: {
        grain:
          "radial-gradient(circle at 20% 20%, rgba(197,83,45,0.08), transparent 40%), radial-gradient(circle at 80% 10%, rgba(35,48,68,0.08), transparent 45%), radial-gradient(circle at 30% 80%, rgba(62,107,91,0.08), transparent 40%)",
      },
    },
  },
  plugins: [typography],
};

export default config;
