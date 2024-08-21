"""
Filetranslate
-----------

Tool for translating games.
Works with multiple games that use text scripts via regular expressions and supports machine translation.
Produces delimiter separated text databases for ease of translation modifications and updates.
Uses git if availible and enabled for collaborative translation and to backup the translation progress.

Link
`````
 `github <https://github.com/UserUnknownFactor/filetranslate>`_


"""
from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f: long_description = f.read()
with open(path.join(this_directory, 'requirements.txt'), encoding='utf-8') as f: requirements = f.read().splitlines()

setup(
    name='filetranslate',
    version='0.9.10',
    url='https://github.com/UserUnknownFactor/filetranslate',
    license='MIT',
    author='UserUnknownFactor',
    author_email='noreply@example.com',
    description='Tool for translating game files (primarily from Japanese to English)',
    long_description=long_description,
    install_requires=requirements,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Other Audience',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Games/Entertainment',
    ],
    packages = find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': ['filetranslate=filetranslate.filetranslate:main', 'ft=filetranslate.filetranslate:main']
    }
)
