// Conventional Commits: `type(scope): subject`. Renovate already writes chore(deps) commits in this
// form; the CI commitlint job holds every other commit to the same shape.
export default { extends: ['@commitlint/config-conventional'] };
