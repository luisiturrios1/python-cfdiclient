import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='cfdiclient',
    version='0.0.1',
    author='Luis Iturrios',
    author_email='iturrios3063@gmail.com',
    description='Cliente Python Web Service del SAT para la descarga masiva de xml',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/luisiturrios/python-cfdiclient',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)