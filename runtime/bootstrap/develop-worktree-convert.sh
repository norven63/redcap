#!/usr/bin/env bash
set -euo pipefail

old_repo="/Users/norven/workspace/redcap"
target="/Users/norven/workspace/AI Era/redcap"
parent="/Users/norven/workspace/AI Era"
stamp="${REDCAP_DEVELOP_STAMP:-$(date +%Y%m%d-%H%M%S)}"
backup="${parent}/redcap.pre-develop-${stamp}"

if [[ ! -d "${old_repo}/.git" ]]; then
  echo "old repo is not a git checkout: ${old_repo}" >&2
  exit 1
fi

if [[ ! -d "${target}" ]]; then
  echo "target workspace missing: ${target}" >&2
  exit 1
fi

if git -C "${target}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "target is already a git worktree: ${target}" >&2
  exit 1
fi

if git -C "${old_repo}" show-ref --verify --quiet refs/heads/develop; then
  echo "develop branch already exists in ${old_repo}" >&2
  exit 1
fi

if [[ -n "$(git -C "${old_repo}" status --porcelain)" ]]; then
  echo "old repo has dirty working tree changes; refusing branch conversion" >&2
  git -C "${old_repo}" status --short >&2
  exit 1
fi

if [[ -e "${backup}" ]]; then
  echo "backup already exists: ${backup}" >&2
  exit 1
fi

echo "backup=${backup}"
mv "${target}" "${backup}"

rollback() {
  local exit_code=$?
  if [[ ${exit_code} -ne 0 ]]; then
    echo "conversion failed; attempting rollback" >&2
    git -C "${old_repo}" worktree remove --force "${target}" >/dev/null 2>&1 || true
    git -C "${old_repo}" branch -D develop >/dev/null 2>&1 || true
    if [[ -d "${backup}" && ! -e "${target}" ]]; then
      mv "${backup}" "${target}"
    fi
  fi
  exit "${exit_code}"
}
trap rollback EXIT

git -C "${old_repo}" worktree add -b develop "${target}" main
rsync -a --delete --exclude='.git' "${backup}/" "${target}/"

diff_preview="$(mktemp)"
rsync -a --dry-run --delete --exclude='.git' "${backup}/" "${target}/" >"${diff_preview}"
if [[ -s "${diff_preview}" ]]; then
  echo "worktree differs from backup after rsync:" >&2
  cat "${diff_preview}" >&2
  exit 1
fi
rm -f "${diff_preview}"

git -C "${target}" add -A
git -C "${target}" commit -m "feat(revival): bootstrap clean RedCap develop workspace" -m "Replace the legacy worktree contents on develop with the revived RedCap runtime, contracts, assets, and documentation. Keep local Codex hook config and generated evidence ignored in the worktree." -m "作者:redcap"

git -C "${target}" status --short --branch
git -C "${old_repo}" worktree list --porcelain
git -C "${old_repo}" branch --list develop

trap - EXIT
echo "REDCAP_DEVELOP_WORKTREE_READY backup=${backup}"
