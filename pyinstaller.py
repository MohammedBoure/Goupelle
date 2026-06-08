import os
import subprocess
import sys


def build_production():
    project_dir = os.path.abspath(os.path.dirname(__file__))
    spec_path = os.path.join(project_dir, "Goupelle.spec")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        spec_path,
    ]

    print("Building compact Goupelle executable...")
    subprocess.check_call(command, cwd=project_dir)
    print(os.path.join(project_dir, "dist", "Goupelle.exe"))


if __name__ == "__main__":
    build_production()
