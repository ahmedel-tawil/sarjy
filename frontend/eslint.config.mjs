// Flat config entrypoint. `eslint.strict.mjs` next to this file is SYNCED --
// `code-standards setup` overwrites it, and `setup --dry-run` fails CI if
// you edit it. Put every repo-specific decision HERE instead, in the override
// block below: later entries win, so you can relax a rule, add a framework
// exemption, or scope one to a directory without forking the canonical file.
import strict from "./eslint.strict.mjs";

// Bun, Testing Library, and Playwright are opt-in because their global test
// syntax overlaps other runners. To enable them, replace the import above with:
//   import { createConfig } from "./eslint.strict.mjs";
//   const strict = createConfig({
//     testFrameworks: ["vitest", "bun", "node", "testing-library", "playwright"],
//     playwrightTestFiles: ["tests/browser/**/*.spec.ts"],
//   });

export default [
  ...strict,

  // --- repo-specific overrides -------------------------------------------
  // Example: your router generates bracketed filenames that unicorn rejects.
  //
  // {
  //   files: ["src/routes/**/*.tsx"],
  //   rules: {
  //     "unicorn/filename-case": ["error", {
  //       cases: { kebabCase: true },
  //       ignore: [String.raw`^\[`],
  //     }],
  //   },
  // },
];
