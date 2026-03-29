# noqa:INP001
import fileinput
import json
import re
import sys

PY_VERSIONS_RE = re.compile(r"^py(\d)(\d+)")


def main():
    actions_matrix = []

    with fileinput.input() as f:
        for tox_env_line in f:
            tox_env = tox_env_line.rstrip()

            if python_match := PY_VERSIONS_RE.match(tox_env):
                version_tuple = python_match.groups()
            else:
                version_tuple = sys.version_info[0:2]

            python_version = "{}.{}".format(*version_tuple)
            actions_matrix.append(
                {
                    "python": python_version,
                    "tox_env": tox_env,
                }
            )

    print(json.dumps(actions_matrix))  # noqa:T201


if __name__ == "__main__":
    main()
