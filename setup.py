import os
from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='django-linkcheck',
    version='1.8.1',
    description="A Django app that will analyze and report on links in any "
                "model that you register with it.",
    long_description=read('README.rst'),
    author='Andy Baker',
    author_email='andy@andybak.net',
    license='BSD',
    url='https://github.com/DjangoAdminHackers/django-linkcheck',
    packages=[
        'linkcheck',
        'linkcheck.management',
        'linkcheck.management.commands',
        'linkcheck.migrations',
        'linkcheck.tests',
        'linkcheck.tests.sampleapp',
    ],
    package_data={
        'linkcheck': [
            'templates/linkcheck/*.html',
            'templates/linkcheck/*.xhtml',
            'tests/media/*',
        ]
    },
    install_requires=['requests'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Framework :: Django',
    ],
)
