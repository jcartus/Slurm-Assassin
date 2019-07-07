# Slurm-Assassin

A python script that runs a command in a slurm environment and monitors the outcome (e.g. by checking output files and polling the child process for an error code). Used to detect and kill zombie jobs, that use up cpu time but are not calculating anything anymore.


Status
------

Below you find the status on [Travis-CI](https://travis-ci.org/jcartus/Slurm-Assassin) for the relevant branches.

| Branch   |      Status   | 
|:--------:|:-------------:|
| master   | [![Build Status](https://travis-ci.org/jcartus/Slurm-Assassin.svg?branch=master)](https://travis-ci.org/jcartus/Slurm-Assassin) |
