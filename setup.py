  
"""This script installs the assassin as python package

Author:
    - Johannes Cartus, TU Graz, 08.06.2019
"""

from distutils.core import setup

name = 'SlurmAssassin'

setup(
    name=name,
    version='0.0',
    description='A script to start/monitor calculations on a Slurm calculation system',
    author='Johannes Cartus',
    packages=[
        name, 
    ],
    package_dir={
        name: 'src',
    }
)