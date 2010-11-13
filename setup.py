import os
from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def package_data(package):
    package_data = []
    for dirpath, dirnames, filenames in os.walk(
            os.path.join(os.path.dirname(__file__), package)):
        for i, dirname in enumerate(dirnames):
            if dirname.startswith('.'): del dirnames[i]
        if '__init__.py' in filenames:
            continue
        elif filenames:
            for f in filenames:
                package_data.append(
                    os.path.join(dirpath[len(package)+len(os.sep):], f))
    return {package: package_data}

setup(
    name='django-linkcheck',
    version='0.5.1',
    description="A Django app that will analyze and report on links in any "
                "model that you register with it.",
    long_description=read('README.rst'),
    author='Andy Baker',
    author_email='andy@andybak.net',
    license='BSD',
    url='http://github.com/andybak/django-linkcheck/',
    packages=[
        'linkcheck',
        'linkcheck.management',
        'linkcheck.management.commands',
    ],
    package_data=package_data('linkcheck'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
)
