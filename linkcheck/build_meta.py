import subprocess

from setuptools import build_meta as default
from setuptools.build_meta import *  # noqa: F401, F403


def compile_translation_files():
    print("Compile translation files")
    subprocess.run(["django-admin", "compilemessages"], cwd="linkcheck")


def build_sdist(sdist_directory, config_settings=None):
    compile_translation_files()
    return default.build_sdist(sdist_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    compile_translation_files()
    return default.build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )
