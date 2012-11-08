from setuptools import setup
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()

version = '1.0'

install_requires = [
  'pep8',
  ]

classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Education",
  "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python",
  "Topic :: Utilities",
  ]

setup(
  name = 'assignmentprint',
  py_modules = ['assignmentprint'],
  version = version,
  description="Pretty printer for student-submitted assignments.",
  long_description=README + '\n\n' + NEWS,
  classifiers=classifiers,
  keywords='prettyprint',
  author='Marco Lui',
  author_email='saffsd@gmail.com',
  url='https://github.com/saffsd/assignmentprint',
  license='GPLv3',
  install_requires=install_requires,
  )
