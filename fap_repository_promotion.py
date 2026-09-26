from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import subprocess
import tempfile
from typing import Iterable

from fap_repository_executor import FileEdit, RepositoryPatchExecutor
from fap_repository_planner import PatchPlan
from fap_repository_verifier import (
    RepositoryVerifier,
    VerificationCommand,
    VerificationReport,
)


@dataclass(frozen=True)
class PromotionApproval:
    plan_id: str
    expected_base_commit: str
    allow_candidate_branch: bool
    reason: str
    branch_prefix: str = "fap/candidate"


@dataclass(frozen=True)
class PromotionReport:
    version: str
    plan_id: str
    state: str
    base_commit: str
    branch: str | None
    commit_sha: str | None
    verification: VerificationReport | None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class VerifiedCandidatePromoter:
    """V87.69 explicit gate from verified sandbox candidate to local branch.

    Promotion here means only:
      verified patch -> Git commit object -> new local candidate branch.

    It never checks out the candidate in the source tree, never moves the
    current branch, never pushes, never opens a PR, and never merges to main.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        executor: RepositoryPatchExecutor | None = None,
        verifier: RepositoryVerifier | None = None,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.executor = executor or RepositoryPatchExecutor(self.root)
        self.verifier = verifier or RepositoryVerifier()
        if self.executor.root != self.root:
            raise ValueError("executor root does not match promoter root")

    def promote(
        self,
        plan: PatchPlan,
        edits: Iterable[FileEdit],
        commands: Iterable[VerificationCommand],
        approval: PromotionApproval,
    ) -> PromotionReport:
        try:
            branch = self._validate_approval(plan, approval)
        except Exception as exc:
            return self._reject(
                plan.plan_id,
                "",
                None,
                (f"approval_rejected:{type(exc).__name__}:{exc}",),
            )

        source_head_before = self._git(
            self.root, "rev-parse", "--verify", "HEAD"
        ).stdout.strip()
        if source_head_before != approval.expected_base_commit:
            return self._reject(
                plan.plan_id,
                source_head_before,
                None,
                ("base_commit_mismatch",),
            )
        if self._branch_exists(branch):
            return self._reject(
                plan.plan_id,
                source_head_before,
                None,
                (f"candidate_branch_already_exists:{branch}",),
            )

        source_status_before = self._git(
            self.root, "status", "--porcelain", "--untracked-files=all"
        ).stdout
        edit_tuple = tuple(edits)
        command_tuple = tuple(commands)

        commit_sha: str | None = None
        ref_created = False
        try:
            with self.executor.open(plan) as session:
                if session.base_commit != approval.expected_base_commit:
                    return self._reject(
                        plan.plan_id,
                        session.base_commit,
                        None,
                        ("sandbox_base_commit_mismatch",),
                    )

                execution = session.apply(edit_tuple)
                if execution.state != "applied_in_sandbox":
                    return self._reject(
                        plan.plan_id,
                        session.base_commit,
                        None,
                        ("execution_rejected",) + tuple(execution.errors),
                    )

                verification = self.verifier.verify(
                    session,
                    execution,
                    command_tuple,
                )
                if verification.state != "verified_candidate":
                    return self._reject(
                        plan.plan_id,
                        session.base_commit,
                        verification,
                        ("verification_not_verified_candidate",)
                        + tuple(verification.errors),
                    )

                commit_sha = self._build_commit_object(
                    session.path,
                    session.temp_parent,
                    session.base_commit,
                    execution.files,
                    plan.plan_id,
                    approval.reason,
                )

                self._create_candidate_ref(branch, commit_sha)
                ref_created = True

                source_head_after = self._git(
                    self.root, "rev-parse", "--verify", "HEAD"
                ).stdout.strip()
                source_status_after = self._git(
                    self.root, "status", "--porcelain", "--untracked-files=all"
                ).stdout
                if source_head_after != source_head_before:
                    raise RuntimeError("source HEAD moved during candidate promotion")
                if source_status_after != source_status_before:
                    raise RuntimeError(
                        "source working tree changed during candidate promotion"
                    )

                return PromotionReport(
                    version="fap.repository.promotion.v1",
                    plan_id=plan.plan_id,
                    state="candidate_branch_created",
                    base_commit=session.base_commit,
                    branch=branch,
                    commit_sha=commit_sha,
                    verification=verification,
                    errors=(),
                )
        except Exception as exc:
            # If a ref was created immediately before a postcondition failed,
            # remove it only when this call created it and it still points at
            # the exact commit produced by this call.
            if ref_created and commit_sha:
                self._remove_candidate_ref_if_owned(branch, commit_sha)
            return self._reject(
                plan.plan_id,
                source_head_before,
                None,
                (f"promotion_failed:{type(exc).__name__}:{exc}",),
            )

    def _validate_approval(
        self,
        plan: PatchPlan,
        approval: PromotionApproval,
    ) -> str:
        if approval.plan_id != plan.plan_id:
            raise ValueError("approval plan_id mismatch")
        if not approval.allow_candidate_branch:
            raise ValueError("candidate branch creation not approved")
        if not approval.expected_base_commit.strip():
            raise ValueError("expected_base_commit is required")
        if not approval.reason.strip():
            raise ValueError("promotion reason is required")
        prefix = approval.branch_prefix.strip().strip("/")
        if not prefix or prefix.startswith("-"):
            raise ValueError("invalid branch prefix")
        if any(x in prefix for x in ("..", " ", "~", "^", ":", "?", "*", "[", "\\")):
            raise ValueError("invalid branch prefix")
        branch = f"{prefix}/{plan.plan_id[:16]}"
        check = self._git(
            self.root,
            "check-ref-format", "--branch", branch,
            check=False,
        )
        if check.returncode != 0:
            raise ValueError(f"invalid candidate branch name: {branch}")
        return branch

    def _build_commit_object(
        self,
        worktree: Path,
        temp_parent: Path,
        base_commit: str,
        files,
        plan_id: str,
        reason: str,
    ) -> str:
        expected = {item.path for item in files}
        if not expected:
            raise ValueError("verified candidate contains no changed files")

        index_path = temp_parent / "promotion.index"
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(index_path)

        self._git_env(worktree, env, "read-tree", base_commit)

        for item in files:
            path = item.path
            if item.operation == "delete":
                self._git_env(
                    worktree,
                    env,
                    "update-index", "--force-remove", "--", path,
                )
                continue

            target = worktree / path
            if not target.is_file() or target.is_symlink():
                raise ValueError(f"candidate file unavailable: {path}")
            blob = self._git(
                worktree,
                "hash-object", "-w", "--no-filters", "--", path,
            ).stdout.strip()
            mode = "100644"
            if item.operation == "modify":
                ls = self._git(
                    worktree,
                    "ls-tree", "-z", base_commit, "--", path,
                ).stdout
                if ls:
                    mode = ls.split(None, 1)[0]
            self._git_env(
                worktree,
                env,
                "update-index", "--add", "--cacheinfo",
                mode, blob, path,
            )

        tree = self._git_env(worktree, env, "write-tree").stdout.strip()
        changed = self._git(
            worktree,
            "diff", "--name-only", "-z", base_commit, tree, "--",
        ).stdout
        changed_paths = {x for x in changed.split("\x00") if x}
        if changed_paths != expected:
            raise ValueError(
                "candidate tree path set differs from verified execution: "
                f"expected={sorted(expected)} actual={sorted(changed_paths)}"
            )

        diff_check = self._git(
            worktree,
            "diff", "--check", base_commit, tree, "--",
            check=False,
        )
        if diff_check.returncode != 0:
            raise ValueError("candidate tree failed git diff --check")

        commit_env = os.environ.copy()
        commit_env.update(
            {
                "GIT_AUTHOR_NAME": "FAP Verified Candidate",
                "GIT_AUTHOR_EMAIL": "fap-candidate@local.invalid",
                "GIT_COMMITTER_NAME": "FAP Verified Candidate",
                "GIT_COMMITTER_EMAIL": "fap-candidate@local.invalid",
            }
        )
        message = (
            f"FAP verified candidate {plan_id[:16]}\n\n"
            f"Plan: {plan_id}\n"
            f"Reason: {reason.strip()[:500]}"
        )
        commit = self._git_env(
            worktree,
            commit_env,
            "commit-tree", tree, "-p", base_commit, "-m", message,
        ).stdout.strip()
        if not commit:
            raise RuntimeError("git commit-tree returned no commit")
        return commit

    def _create_candidate_ref(self, branch: str, commit_sha: str) -> None:
        object_format = self._git(
            self.root, "rev-parse", "--show-object-format"
        ).stdout.strip()
        zero = "0" * (64 if object_format == "sha256" else 40)
        self._git(
            self.root,
            "update-ref", f"refs/heads/{branch}", commit_sha, zero,
        )

    def _branch_exists(self, branch: str) -> bool:
        proc = self._git(
            self.root,
            "show-ref", "--verify", "--quiet", f"refs/heads/{branch}",
            check=False,
        )
        return proc.returncode == 0

    def _remove_candidate_ref_if_owned(
        self,
        branch: str,
        expected_commit: str,
    ) -> None:
        if not branch or not expected_commit:
            return
        ref = f"refs/heads/{branch}"
        current = self._git(
            self.root,
            "rev-parse", "--verify", ref,
            check=False,
        )
        if current.returncode != 0 or current.stdout.strip() != expected_commit:
            return
        # Delete atomically only if the ref still points at our commit.
        self._git(
            self.root,
            "update-ref", "-d", ref, expected_commit,
            check=False,
        )

    @staticmethod
    def _git(
        cwd: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
            shell=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed with {proc.returncode}: "
                f"{proc.stdout[:20000].strip()}"
            )
        return proc

    @staticmethod
    def _git_env(
        cwd: Path,
        env: dict[str, str],
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
            shell=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed with {proc.returncode}: "
                f"{proc.stdout[:20000].strip()}"
            )
        return proc

    @staticmethod
    def _reject(
        plan_id: str,
        base_commit: str,
        verification: VerificationReport | None,
        errors: tuple[str, ...],
    ) -> PromotionReport:
        return PromotionReport(
            version="fap.repository.promotion.v1",
            plan_id=plan_id,
            state="rejected",
            base_commit=base_commit,
            branch=None,
            commit_sha=None,
            verification=verification,
            errors=errors,
        )
