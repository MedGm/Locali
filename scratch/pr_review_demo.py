"""Demo file for checking the Locali review workflow on a pull request. Not meant to be merged."""

import subprocess


def archive(path):
    # user-controlled path reaches a shell: the review should flag this and block the PR
    return subprocess.run(f"tar czf backup.tgz {path}", shell=True)
