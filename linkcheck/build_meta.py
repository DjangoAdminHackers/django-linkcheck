import os
import subprocess

from setuptools import build_meta as default
from setuptools.build_meta import *  # noqa: F401, F403


def compile_translation_files():
    print("Compiling translation files...")
    subprocess.run(["django-admin", "compilemessages"], cwd="linkcheck")


def should_compile_translation_files():
    skip_translations = os.environ.get("LINKCHECK_SKIP_TRANSLATIONS")
    if skip_translations and skip_translations.lower() in ("1", "true", "yes", "t", "y"):
        return False

    return True


def build_sdist(sdist_directory, config_settings=None):
    if should_compile_translation_files():
        compile_translation_files()

    return default.build_sdist(sdist_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    if should_compile_translation_files():
        compile_translation_files()

    return default.build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )
