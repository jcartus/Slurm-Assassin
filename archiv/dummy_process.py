"""This script is run as a dummy process"""

import time
from datetime import datetime


def make_log_string(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

    return timestamp + ": " + msg

def main():
    print("Dummy Process Started")
    with open("dummy_process.out", "a") as f:
        for i in range(2):
            print("Dummy loop: " + str(i))
            f.write(make_log_string("Dummy process is Active. Loop " + str(i)))
            f.flush()
            time.sleep(5)

    print("Loop done, warting for timeout")
    time.sleep(360)

    print("Dummy Process ran completely through!, Finished")

if __name__ == '__main__':
    main()
