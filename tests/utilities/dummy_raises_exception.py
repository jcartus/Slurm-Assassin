"""This script is a dummy application that raises an exception after a 
random time. An outfile will not be created.

Author: Johannes Cartus, TU Graz, 04.07.2019
"""

import time
import numpy as np

from assassin import Logger


def main():

    Logger.log("Dummy Process (Raise Exception): started")

    wating_time = np.random.rand() * 20
    Logger.log("Dummy Process (Raise Exception):" + \
        " Waiting time is {0} seconds".format(wating_time))

    time.sleep(wating_time)
    Logger.log("Dummy Process (Raise Exception):" + \
        " Wating is over. Now Raising Exception")

    raise RuntimeError("Dummy Process Raised an Exception")
    Logger.log("Dummy Process (Raise Exception):" + \
        " Exception was raised.")

if __name__ == '__main__':
    main()


