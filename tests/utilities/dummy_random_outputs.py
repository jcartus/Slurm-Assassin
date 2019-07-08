"""This script is run as a dummy process that writes to many output files 
of a random name and then stops to write, causing it to be killed by the 
assassin.
"""
import os
import time
import argparse
from assassin import Logger

def main(outfolder="dummy_random_output"):
    
    logging_prefix = "Dummy (random outputs): "

    Logger.log(logging_prefix + "started")

    for i in range(3):

        new_folder = os.path.join(outfolder, str(i))
        try:
            Logger.log(logging_prefix + "Creating directory: " + new_folder)
            os.makedirs(new_folder)
            
        except OSError:
            Logger.log(logging_prefix + "Directory already exists: " + new_folder)

        outfile = os.path.join(new_folder, "dummy.out")

        with open(outfile, "a") as f:
            for j in range(4):
                Logger.log(logging_prefix + "Loop: " + str(j))
                f.write("Dummy process is Active. Loop " + str(j) + os.linesep)
                f.flush()
                time.sleep(1)
        
        time.sleep(3)

    Logger.log(logging_prefix + "Dummy done with writing, now just waiting")


    time.sleep(30)
    Logger.log(logging_prefix + "Dummy process ran completely through!")

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog="dummy_stops_writing_output.py",
        description= "Dummy process that logs to a file for a while and " + \
            "then just stops."
    )

    parser.add_argument(
        '-o', '--out-folder',
        help="The folder the process should write to.",
        default="dummy_random_output",
        type=str,
        required=False,
        dest="outfolder"
    )

    args = parser.parse_args()

    main(outfolder=args.outfolder)
