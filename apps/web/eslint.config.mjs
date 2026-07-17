import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

// Next 16 removed the `next lint` command; ESLint runs directly against this
// flat config. eslint-config-next ships flat-config arrays for its shareable
// configs, so we spread them here.
const eslintConfig = [
  { ignores: [".next/**", "node_modules/**", "next-env.d.ts"] },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    // Adopting ESLint after Next 16 removed `next lint` surfaces a backlog of
    // newer strict react-hooks rules in existing components. Keep them visible
    // as warnings (non-blocking) rather than block CI or risk behavior changes
    // by rewriting effects; tighten to "error" as the components are cleaned up.
    rules: {
      "react-hooks/purity": "warn",
      "react-hooks/set-state-in-effect": "warn",
      "react/no-unescaped-entities": "warn",
    },
  },
];

export default eslintConfig;
