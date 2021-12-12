import os
import logging
import subprocess

import yaml
from git import GitCommandError

LOGGER = logging.getLogger(__name__)


def rerender(git_repo):
    LOGGER.info('rerendering')

    changed = ensure_output_validation_is_on(git_repo)

    curr_head = git_repo.active_branch.commit
    ret = subprocess.call(
        ["conda", "smithy", "rerender", "-c", "auto", "--no-check-uptodate"],
        cwd=git_repo.working_dir,
        env={
            k: v
            for k, v in os.environ.items()
            if k not in ["INPUT_GITHUB_TOKEN"] and "GITHUB_TOKEN" not in k
        },
    )

    if ret:
        changed, rerender_error = False, True
    elif git_repo.active_branch.commit == curr_head:
        changed, rerender_error = False, False
    else:
        subprocess.call(
           ["git", "checkout", "HEAD~1", "--", ".github/workflows/*"],
           cwd=git_repo.working_dir,
        )
        subprocess.call(
           ["git", "commit", "--amend", "--allow-empty", "--no-edit"],
           cwd=git_repo.working_dir,
        )
        changed, rerender_error = True, False

    return changed, rerender_error


def ensure_output_validation_is_on(git_repo):
    pth = os.path.join(git_repo.working_dir, "conda-forge.yml")
    if os.path.exists(pth):
        with open(pth, "r") as fp:
            cfg = yaml.safe_load(fp)
    else:
        cfg = {}

    if not cfg.get("conda_forge_output_validation", False):
        cfg["conda_forge_output_validation"] = True

        with open(pth, "w") as fp:
            fp.write(yaml.dump(cfg, default_flow_style=False))

        subprocess.run(
            "git add conda-forge.yml",
            shell=True,
            cwd=git_repo.working_dir,
        )
        return True
    else:
        return False


def comment_and_push_per_changed(
    *,
    changed, rerender_error, git_repo, pull, pr_branch, pr_owner, pr_repo
):
    LOGGER.info(
        'pushing and commenting: branch|owner|repo = %s|%s|%s',
        pr_branch,
        pr_owner,
        pr_repo,
    )

    message = None
    if changed:
        try:
            git_repo.remotes.origin.set_url(
                "https://%s:%s@github.com/%s/%s.git" % (
                    os.environ['GITHUB_ACTOR'],
                    os.environ['INPUT_GITHUB_TOKEN'],
                    pr_owner,
                    pr_repo,
                ),
                push=True,
            )
            git_repo.remotes.origin.push()
        except GitCommandError as e:
            LOGGER.critical(repr(e))
            message = """\
Hi! This is the friendly automated conda-forge-webservice.
I tried to rerender for you, but it looks like I wasn't able to push to the {}
branch of {}/{}. Did you check the "Allow edits from maintainers" box?

**NOTE**: PRs from organization accounts cannot be rerendered because of GitHub
permissions.
""".format(pr_branch, pr_owner, pr_repo)
        finally:
            git_repo.remotes.origin.set_url(
                "https://github.com/%s/%s.git" % (
                    pr_owner,
                    pr_repo,
                ),
                push=True,
            )
    else:
        if rerender_error:
            doc_url = (
                "https://conda-forge.org/docs/maintainer/updating_pkgs.html"
                "#rerendering-with-conda-smithy-locally"
            )
            message = """\
Hi! This is the friendly automated conda-forge-webservice.
I tried to rerender for you but ran into some issues, please ping conda-forge/core
for further assistance. You can also try [re-rendering locally]({}).
""".format(doc_url)
        else:
            message = """\
Hi! This is the friendly automated conda-forge-webservice.
I tried to rerender for you, but it looks like there was nothing to do.
"""

    if message is not None:
        pull.create_issue_comment(message)
