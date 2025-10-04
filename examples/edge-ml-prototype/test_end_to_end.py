import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def run(cmd):
    proc = subprocess.run(shlex.split(cmd), cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout)
    print(proc.stderr, file=sys.stderr)
    assert proc.returncode == 0


def test_cloud_runs():
    run(
        f"{sys.executable} example_node.py --role cloud"
        f" --name test-model")


def test_edge_runs():
    run(
        f"{sys.executable} example_node.py --role edge"
        f"--node-id test-edge --baseline-seed 1"
    )
