import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='cfdiclient',
    version='1.4.1',
    author='Luis Iturrios',
    author_email='luisiturrios1@gmail.com',
    description='Cliente Python Web Service del SAT para la descarga masiva de CFDIs',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/luisiturrios1/python-cfdiclient',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 2.7',
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
    install_requires = [
        'lxml>=4.2.5',
        'requests>=2.21.0',
        'pycryptodome>=3.7.2',
        'pyOpenSSL>=18.0.0'
    ]
)
