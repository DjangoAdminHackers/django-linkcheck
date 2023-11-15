import os
import subprocess
import sys

from setuptools import find_packages, setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


if 'sdist' in sys.argv[1:]:
    subprocess.run(["django-admin", "compilemessages"], cwd="linkcheck")

setup(
    name='django-linkcheck',
    version='2.2.1',
    description="A Django app that will analyze and report on links in any "
                "model that you register with it.",
    long_description=read('README.rst'),
    author='Andy Baker',
    author_email='andy@andybak.net',
    license='BSD',
    url='https://github.com/DjangoAdminHackers/django-linkcheck',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['django>=3.2', 'requests'],
    extras_require={
        "dev": ["flake8", "isort", "pre-commit"],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Framework :: Django',
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
    ],
)
