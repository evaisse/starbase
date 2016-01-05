#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STARBASE

Meteor JS servers deployment & management tools

"""
from setuptools import setup

setup(
    name='Starbase',
    version="0.4.1",
    url='https://github.com/evaisse/starbase',
    license='MIT',
    author='Emmanuel VAÏSSE',
    author_email='evaisse@gmail.com',
    description="Meteor JS servers deployment & management tools",
    py_modules=['starbase'],
    install_requires=[
        'docopt',
        'fabric',
        'commentjson',
        'jinja2',
    ],
    entry_points={
        'console_scripts': ['starbase = starbase:main']
    },
    package_data={
        '': ['templates/*'],
    },
    zip_safe=False,
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)