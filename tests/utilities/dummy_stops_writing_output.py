"""This script is run as a dummy process that writes to an outfile
and then stops to write, causing it to be killed by the assassin.
"""
import os
import time
import argparse
from assassin import Logger

def main(outfile="dummy_stop_writing.log"):
    
    logging_prefix = "Dummy (stops writing): "

    Logger.log(logging_prefix + "started")

    with open(outfile, "a") as f:
        for i in range(3):
            Logger.log(logging_prefix + "Loop: " + str(i))
            f.write("Dummy process is Active. Loop " + str(i) + os.linesep)
            f.flush()
            time.sleep(5)

    Logger.log(logging_prefix + "Dummy done with writing, now just waiting")


    time.sleep(50)
    Logger.log(logging_prefix + "Dummy process ran completely through!")

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog="dummy_stops_writing_output.py",
        description= "Dummy process that logs to a file for a while and " + \
            "then just stops."
    )

    parser.add_argument(
        '-o', '--out-file',
        help="The logfile the process should write to.",
        default="dummy_stop_writing.log",
        type=str,
        required=False,
        dest="outfile"
    )

    args = parser.parse_args()

    main(outfile=args.outfile)
