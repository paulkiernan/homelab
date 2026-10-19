// Conventional Commits: `type(scope): subject`. Renovate already writes chore(deps) commits in this
// form; the CI commitlint job holds every other commit to the same shape. Body line length is
// not enforced: wrapping prose at 100 columns is a style choice, not part of the convention.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'body-max-line-length': [0],
  },
};
