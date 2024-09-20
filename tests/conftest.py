import contextlib
import os
import subprocess
import tempfile

import pytest


@contextlib.contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


def _change_action_branch(branch):
    print("moving repo to %s action" % branch, flush=True)
    subprocess.run("git checkout main", shell=True, check=True)

    data = (
        branch,
        "rerendering_github_token: ${{ secrets.RERENDERING_GITHUB_TOKEN }}",
    )

    with open(".github/workflows/webservices.yml", "w") as fp:
        fp.write(
            """\
on: repository_dispatch

jobs:
  webservices:
    runs-on: ubuntu-latest
    name: webservices
    steps:
      - name: webservices
        id: webservices
        uses: conda-forge/webservices-dispatch-action@%s
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          %s
"""
            % data
        )

    print("committing...", flush=True)
    subprocess.run(
        "git add -f .github/workflows/webservices.yml", shell=True, check=True
    )
    subprocess.run(
        "git commit "
        "--allow-empty "
        "-m "
        "'[ci skip] move rerender action to branch %s'" % branch,
        shell=True,
        check=True,
    )

    print("push to origin...", flush=True)
    subprocess.run("git pull", shell=True, check=True)
    subprocess.run("git push", shell=True, check=True)


@pytest.fixture(scope="session")
def setup_test_action():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pushd(tmpdir):
            print("cloning...", flush=True)
            subprocess.run(
                "git clone "
                "https://x-access-token:${GH_TOKEN}@github.com/conda-forge/"
                "conda-forge-webservices.git",
                shell=True,
                check=True,
            )

            with pushd("conda-forge-webservices"):
                yield _change_action_branch
                _change_action_branch("main")
