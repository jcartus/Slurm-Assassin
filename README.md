# Slurm-Assassin

A python script that runs a command in a slurm environment and monitors the outcome (e.g. by checking output files and polling the child process for an error code). Used to detect and kill zombie jobs, that use up cpu time but are not calculating anything anymore.
