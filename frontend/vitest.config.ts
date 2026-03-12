import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  root: path.resolve(__dirname, ".."),
  resolve: {
    alias: {
      "@": __dirname,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./frontend/tests/setup.ts"],
    include: ["frontend/tests/**/*.test.ts", "frontend/tests/**/*.test.tsx"],
  },
});
