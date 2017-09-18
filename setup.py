from setuptools import setup, find_packages

setup(
    name='pyaconv',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'pyaconv=pyaconv.__main__:main'
        ]
    }
)
