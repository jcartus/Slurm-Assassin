#!/usr/bin/env python3
"""This module contains a class that can monitor an aims calculations on the 
VSC and kill them it no progress is made.

When executed as a script, the assassin will assume the start command to be 
"mpirun aims.x" and also assume the names of the output files as given 
by the default arguments of the assassin's constructor. Email notifications
are disabled by default as well.

Author:
    - Johannes Cartus, TU Graz, 07.06.2019
"""

import subprocess as sp
import os, sys
from datetime import datetime
import time
import smtplib
from email.message import EmailMessage

import argparse

class DeadCalculation(RuntimeError):
    pass

class CalculationTimeout(DeadCalculation):
    pass

class CalculationCrashed(DeadCalculation):
    pass 

class Logger(object):
    """This class handles the logging (writes log messages to a log file)"""

    name_of_logfile = "assassin.log"

    # log message prefix that help identify the gravity of the log
    _markers = [
        "[ ] ",
        "[#] ",
        "[w] ",
        "[X] "
    ]
    
    @classmethod
    def log(cls, msg, level=0):
        """Write message to log file. There are several levels available 
        to distinct between more or less important log messages:
        
        level should be bettween 0 and 3:
            - 0 ordinary info
            - 1 important info
            - 2 warning
            - 3 error
        """

        timestamp = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

        try:
            marker = cls._markers[level]
        except IndexError:
            raise ValueError("Unknown error level: " + str(level))

        
        with open(cls.name_of_logfile, "a") as f:
            f.write(
                marker + timestamp + ": " + msg + os.linesep
            )

class EMailHandler(object):
    """This class serves as an interface from the assassin to mailing.
    
    Attributes:
     - sender_address: the addres that will be listed as sender for mails sent.
     - recipient_address: the mail address the mail should be sent to.
     - subject_prefix: a string that is added at the front of the subject line
       to help the receiver to identify the purpose of the mail.
    """

    _default_logger = Logger

    def __init__(self, 
        sender_address, 
        recipient_address,
        subject_prefix=None,
        logger=None
    ):

        self.sender_address = sender_address
        self.recipient_address = recipient_address
        self.subject_prefix = "" if subject_prefix is None else subject_prefix

        # if no logger is specified use the default
        self._logger = self._default_logger if logger is None else logger
            
    def _log(self, msg, level=0):
        self._logger.log(msg=msg, level=level)

    def send_email(self, subject, message):
        """Send an email notification to user."""
        msg = EmailMessage()
        msg.set_content(message)
        msg['From'] = self.sender_address
        msg['To'] = self.recipient_address
        msg['Subject'] = self.subject_prefix + subject

        self._log("Sending mail to " + self.recipient_address + ": " + subject)
       
        s = smtplib.SMTP('localhost')
        s.send_message(msg)
        s.quit()
    

class SlurmAssassin(object):

    _logger = Logger

    def __init__(self, 
        timeout=15,
        polling_period=5,
        out_file_name="aims.out",
        err_file_name="aims.err",
        email=None
    ):
        """Args:
            timeout: time after which a non-responsive calculation is assumed 
                to be dead (in minutes!).
            polling_period: period in which sanity of calculation is checked
                (also in minutes).
            out_file_name: name of file to which the calculation must keep
                writing to be regarded as sane. If "Have a nice day" apears
                in this file, the calculation is assumed to have finished.
                The phrase that is checked for can be altered in the 
                attribute end_of_calculation_string
            err_file_name: Optionall an error file can be given. This 
                file will be periodically checked for vsc error messages. 
                If critical messages are found, the calculation is aborted 
                (even is time out is not reached yet).
            email: The email address, that potential notifications (e.g. if
                a calculation crashes) shall be sent. E.g. 'name@dummy.lol'.
                Mail will have the prefix '[Slurm-Assassin]' and the sender
                address noreply@assassin.vsc.info.
        """

        # store timeout and polling period in seconds 
        self.timeout = timeout * 60

        # period in which outfiles are checked in seconds
        self.polling_period_outfiles = polling_period * 60

        # period in which calculation process is checked in seconds
        self.polling_period_process_handle = 30

        #--- note names of out and error file ---
        if isinstance(out_file_name, list):
            self.out_file_name = out_file_name
        else:
            self.out_file_name = [out_file_name]

        self.err_file_name = err_file_name
        #---

        # mail address to which notifications should be sent
        if not email is None:
            self._email_handler = EMailHandler(
                sender_address="noreply@assassin.vsc.info",
                recipient_address=email,
                subject_prefix="[Slurm-Assassin] "
            )
        else:
            self._email_handler = None

        # start time of job
        self.time_calculation_start = self.time_now()

        # the time the output files were last updated
        self.time_last_update_out = self.time_calculation_start
        self.time_last_update_err = self.time_calculation_start

        # initialize handle for aims
        self.calculation_process = None

        # if this string apears in out file the calculation must be finished
        self.end_of_calculation_string = "Have a nice day"

    @staticmethod
    def time_now():
        """Current time in s"""
        return datetime.now().timestamp()

    def get_job_id(self):
        """Get the id of current slurm job as string"""
        try:    
            return os.environ["SLURM_JOB_ID"]
        except Exception as ex:
            self.send_email_notification_assassin_error(ex)
            raise ex

    @staticmethod
    def get_job_name():
        """Get the jobname of current slurm job if available"""
        try:
            return os.environ["SLURM_JOB_NAME"]
        except KeyError:
            return "Unknown"

    def time_last_modified(self, file):
        """Gets the time of last modification (in seconds since ??)"""

        try: 
            return os.stat(file).st_mtime

        except FileNotFoundError:
            
            # if the missing file was the main file, we have a problem!
            if file == self.out_file_name[0]:
                msg = "Main outfile " + file + " not found!"
                self.log(msg, 3)
                raise CalculationCrashed(msg)

            else:
                self.log("Outfile " + file + " not found!", 2)
                return 0

    def start_calculation_process(self, 
        command=["mpirun", "aims.x"], 
        *args, 
        **kwargs
    ):
        """Run a subprocess executing the command to be governed by the 
        assassin. This will probably be the aims calculation."""
        
        self.log("Running command: " + " ".join(command), 1)
        self.calculation_process = sp.Popen(command, *args, **kwargs)

    def terminate_calculation_process(self):
        """Stop the goverened subprocess."""
        self.log("Attempting to terminating child process.")
        self.calculation_process.terminate()
        self.log("Finished terminating child process.")

    def log(self, msg, level=0):
        """Write message to log file. There are several levels available 
        to distinct between more or less important log messages:
        
        level should be bettween 0 and 3:
            - 0 ordinary info
            - 1 important info
            - 2 warning
            - 3 error
        """

        self._logger.log(msg=msg, level=level)

    def send_email(self, subject, message):
        self._email_handler.send_email(subject=subject, message=message)

    def send_email_notification_assassin_error(self, exception=None):
        """Used to send to user an error warning, in case e.g. an exception
        that cannot be handled occurres"""

        if not self._email_handler is None:
            msg = "Dear VSC3 user, " + os.linesep
            msg += "while tending to your calculation '" +  \
                self.get_job_name() + "' (job id: " + self.get_job_id() + \
                    ") an unexpected error occurred. Please manually check " + \
                        "the situation on vsc immediately!!!"  + os.linesep
            
            if not exception is None:
                msg += "The following error occurred: " + str(exception) + \
                    os.linesep

            msg += os.linesep + "Best Regards," + os.linesep
            msg += "Your favorite Slurm-Assassin"


            self.send_email(
                subject="Unexpected Assassin-Error, USER ACTION REQUIRED!",
                message=msg
            )


    def send_email_notification_crashed(self):
        """If the user specified a notification email address, 
        send a notification mail that the job crashed."""

        if not self._email_handler is None:
            msg = "Dear VSC3 user, " + os.linesep
            msg += "your calculation '" +  self.get_job_name() + \
                        "' has crashed. The corresponding job '" + \
                            self.get_job_id() + "' was thus cancelled." + \
                                os.linesep
            msg += os.linesep + "Best Regards," + os.linesep
            msg += "Your favorite Slurm-Assassin"


            self.send_email(
                subject="Calculation Crashed",
                message=msg
            )

    def send_email_notification_timeout(self):
        """If the user specified a notification email address, 
        send a notification mail that the job timed out."""

        if not self._email_handler is None:
            msg = "Dear VSC3 user, " + os.linesep
            msg += "your calculation '" +  self.get_job_name() + \
                        "' has timed out, because the was no update in any " + \
                            "of the outfiles for " + str(self.timeout / 60.0) + \
                                " minutes. The corresponding job '" + \
                                    self.get_job_id() + \
                                        "' was thus cancelled." + os.linesep
            msg += os.linesep + "Best Regards," + os.linesep
            msg += "Your favorite Slurm-Assassin"


            self.send_email(
                subject="Calculation Crashed",
                message=msg
            )


    def is_timeout_reached(self):
        """Checks the outfile(s) for changes. Returns whether there 
        the time that passed since the last change exceeds the timeout."""

        timeout_reached = False

        #--- find time of most recent file change ---
        modification_time = max(
            [ self.time_last_modified(f) for f in self.out_file_name]
        )
        #---

        # if there was a modification, store new modification time
        if modification_time > self.time_last_update_out:
            self.time_last_update_out = modification_time

        # else check if calculation timed out
        elif abs(modification_time - self.time_now()) > self.timeout:
            timeout_reached = True

        # otherwise no action necessary
        else:
            pass

        return timeout_reached

    def is_calculation_finished(self):
        """Check if the end_calculation_string appeared in the outfile"""

        is_finished = False

        try:
            with open(self.out_file_name[0], "r") as f:
                for line in f: # TODO avoid re-reading the whole outfile, maybe used read in chunk by chunk
                    if self.end_of_calculation_string in line:
                        is_finished = True
                        break

        except FileNotFoundError:
            msg = "Main outfile " + self.out_file_name[0] + " not found!"
            self.log(msg, 3)
            raise CalculationCrashed(msg)


        return is_finished

    def is_calculation_crashed(self):
        """Checks if there is an error message in the error file, that would 
        justify killing the job"""

        #raise NotImplementedError("TODO: parse error file for common errors")
        return False

    def kill_job(self):
        """Cancels the current job via Slurm's scancel."""

        job_id = self.get_job_id()

        self.log("Killing job " + str(job_id), 1)

        # cancell the slurm job the assassin is running in.
        sp.run(["scancel", job_id]) 

    def _lurk(self):
        """This function encapsulates the monitoring process. It is used 
        by lurk an kill and only a separate function for testing reasons."""

        time_last_poll = self.time_calculation_start

        while True:
            
            time.sleep(self.polling_period_process_handle)
            
            #--- check process handle if calculation has ended ---
            # check process handle 
            return_code = self.calculation_process.poll()
            
            # calculation process has terminated :D
            if not return_code is None:
                
                # calculation exited normally
                if return_code == 0:
                    
                    self.log("Calculation finished (by process handle).", 1)
                    break # quit the while-loop
                
                # there was an error
                else:
                    raise CalculationCrashed(
                        "Calculation finished with return code " + \
                            str(return_code) + "."
                    )
            #---


            #--- Handle file polling ---

            # check file polling interval. 
            if abs(time_last_poll - self.time_now()) > \
                self.polling_period_outfiles:
                
                self.log("Polling outfiles.")

                #--- check outfiles---
                if self.is_calculation_finished():
                    
                    self.log("Calculation finished (by outfile).", 1)
                    break # quit the while-loop, calculation was successful

                elif self.is_calculation_crashed():
                    
                    raise CalculationCrashed(
                        "Calculation crash was detected via error file."
                    )

                else:
                    
                    self.log("Outfiles are ok.")

                    # if nothing meaningful was found in outfiles, 
                    # see if timeout is reached
                    if self.is_timeout_reached():

                        raise CalculationTimeout(
                            "Timeout of {0} minutes was exceeded.".format(
                                self.timeout / 60.0
                            )
                        )
                #---

                # update last poll time
                time_last_poll = self.time_now()
            #---

        self.log("Calculation finished normally", 1)

    def lurk_and_kill(self):
        """Activates a listener that checks whether the calculation started via
        the start_calculation method is still alive. If it has died the 
        assassin will kill the slurm job (and notify the user if a mail
        address was specified in the constructor). At the end (when 
        calculation finished or was killed) python will be ended via sys.exit.
        
        A calculation will be regarded finished if:
         - The child process containing the calculation terminates with return 
           code 0.
         - The output file contains the line "Have a nice day". This may be
           altered using the attribute 'end_of_calculation_string'

        A calculation will be regarded crashed/undead/a zombie if:
         - The child process containing the calculation terminates with a return
           code other than 0.
         - The outfile(s) are not updated for longer than the specified 
           timeout period (set in constructor).
         - A specific keyword is found in the error file (yet to be 
           implemented).
        """

        try:
            
            #keep listening if calculation is still sane
            self._lurk()

        except CalculationCrashed as ex:
            
            self.log("Calculation crashed!" + str(ex), 3)
            self.send_email_notification_crashed()

            self.kill_job()


        except CalculationTimeout as ex:

            self.log("Calculation timed out!" + str(ex), 3)
            self.send_email_notification_timeout()

            # stop the calculation process.
            try:
                self.terminate_calculation_process()
            except Exception as ex:
                self.log("Could not stop calculation process!", 3)
                self.send_email_notification_assassin_error(ex)
            
            self.kill_job()

        except Exception as ex:
            
            self.log("An unexpected error occurred: " + str(ex))
            self.send_email_notification_assassin_error(ex)

            self.kill_job()

        finally:
            
            # end whichever python program the assassin was run in.
            sys.exit()



def main(args):
    assassin = SlurmAssassin(
        timeout=args.timeout,
        polling_period=args.polling_period,
        out_file_name=args.outfiles,
        email=args.email
    )

    if isinstance(args.command, list):
        command = args.command
    else: 
        command = args.command.split()
    assassin.start_calculation_process(command=command)

    assassin.lurk_and_kill()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        prog="assassin.py",
        description= \
"""If you want to do calculations on VSC and feel like you should
check on the from time to time, than the assassin is for you!
It runs a command of your choice (see below), checks
periodically whether it is still running and kills the calculation
if it runs into any trouble. If you specify a mail address you 
will also get notified.
""",
        epilog="Have fun on vsc,\nyour favorite Slurm-Assassin"
    )

    parser.add_argument(
        '-c', '--command',
        nargs='+',
        default=["mpirun", "aims.x"],
        help= \
            "The command you want to run. Example (and default) mpirun aims.x.",
        metavar='cmd',
        type=str,
        required=False,
        dest="command"
    )

    
    parser.add_argument(
        '-e', '--email',
        help="An email address the assassin may send notifications to " + \
            "(e.g. in case the calculation dies and is cancelled).",
        metavar="your@mail.address",
        #required=False,
        type=str,
        default=None,
        dest="email",
    )

    parser.add_argument(
        '-o', '--out-files',
        help=\
"""A (list of) file(s) produced by the calculation started by the specified 
command, from which 
the assassin may infer that the calculation is still running as long as they 
keep being updated. You may specify multiple files, e.g. in case a cube file 
or something similar is generated during the calculation. In this case any 
change in ANY of the files will surfice for the calculation not to be killed.
The first output file in the list (if more than one are specified) should be 
the main output file.
It must always be produced. If the (first) output 
file is not found the assassin will assume the calculation to be crashed and 
kill the job. The first/main output file will also be checked for phrases that 
indicate the calculation to be finished (E.g. 'Have a nice day').""",
        default="aims.out",
        type=str,
        nargs="+",
        required=False,
        dest="outfiles"
    )

    parser.add_argument(
        '-p', '--polling',
        help="The polling period, i.e. the time period in which the out " + \
            "files are checked for changes, in minutes. Default is 5 min.",
        default=5,
        type=float,
        required=False,
        dest="polling_period"
    )

    parser.add_argument(
        '-T', '--time-out',
        help="The time-out time in minuted. " + \
            "If none of the specified outfiles shows any change for longer" + \
                " than the timeout period the assassin will kill the " + \
                    "slurm-job. The default is 15 min.",
        default=15,
        type=float,
        required=False,
        dest="timeout"
    )
    
    
    args = parser.parse_args()
    main(args)
       
