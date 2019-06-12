"""This script will monitor aims calculations on the VSC and kill them if no 
progress is made.
"""

import subprocess as sp
import os
from datetime import datetime
import time
import smtplib
from email.message import EmailMessage


class DeadCalculation(RuntimeError):
    pass

class CalculationTimeout(DeadCalculation):
    pass

class CalculationCrashed(DeadCalculation):
    pass 



class SlurmAssassin(object):

    def __init__(self, 
        timeout=15,
        polling_period=5,
        out_file_name="aims.out",
        err_file_name="aims.err",
        log_file="assassin.log",
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
            log_file: Name of the file the assassin will write log messages to.
            email: The email address, that potential notifications (e.g. if
                a calculation crashes) shall be sent. E.g. 'name@dummy.lol'.
                Mail will have the prefix '[Slurm-Assassin]' and the sender
                address noreply@assassin.vsc.info.
        """

        # store timeout and polling period in seconds 
        self.timeout = timeout * 60

        # interval in which outfiles are checked in seconds
        self.polling_period_outfiles = polling_period * 60

        # intervall in which calculation process is checked in seconds
        self.polling_period_process_handle = 60

        # note names of out and error file
        self.out_file_name = out_file_name
        self.err_file_name = err_file_name

        # name of the file the assassin logs to
        self.log_file = log_file

        # mail address to which notifications should be sent
        self.email_recipient = email
        self.email_sender = "noreply@assassin.vsc.info"
        self.email_subject_prefix = "[Slurm-Assassin] "

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

    @staticmethod
    def get_job_id():
        """Get the id of current slurm job as string"""
        return os.environ["SLURM_JOB_ID"]

    @staticmethod
    def get_job_name():
        """Get the jobname of current slurm job if available"""
        try:
            return os.environ["SLURM_JOB_NAME"]
        except KeyError:
            return "Unknown"

    @staticmethod
    def time_last_modified(file):
        return os.stat(file).st_mtime

    def start_calculation_process(self, command=["mpirun", "aims.x"], *args):
        """Run a subprocess executing the command to be governed by the 
        assassin. This will probably be the aims calculation."""
        
        self.log("Running command: " + " ".join(command), 1)
        self.calculation_process = sp.Popen(command, *args)

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

        timestamp = datetime.now().strftime("%Y-%m-%d, %H:%M:%S")

        if level == 0:
            marker = "[ ] "
        elif level == 1:
            marker = "[#] "
        elif level == 2:
            marker = "[w] "
        elif level == 3:
            marker = "[X] "
        else:
            raise ValueError("Unknown error level: " + str(level))

        
        with open(self.log_file, "a") as f:
            f.write(
                marker + timestamp + ": " + msg + os.linesep
            )

    def send_email(self, subject, message):
        """Send an email notification to user. Sender will always be
        noreply@assassin.vsc.info. The subject will always be prefixed
        with '[Slurm-Assassin]'"""
        msg = EmailMessage()
        msg.set_content(message)
        msg['From'] = self.email_sender
        msg['To'] = self.email_recipient
        msg['Subject'] = self.email_subject_prefix + subject

        self.log("Sending mail to " + self.email_recipient + ": " + subject)

        with smtplib.SMTP('localhost') as s:
            s.send_message(msg)


    def send_email_notifcation_crashed(self):
        """If the user specified a notification email address, 
        send a notification mail that the job crashed."""

        if not self.email_recipient is None:
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

    def send_email_notifcation_timeout(self):
        """If the user specified a notification email address, 
        send a notification mail that the job timed out."""

        if not self.email_recipient is None:
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

        modification_time = self.time_last_modified(self.out_file_name)

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

        with open(self.out_file_name, "r") as f:
            for line in f: # TODO avoid re-reading the whole outfile, maybe used read in chunk by chunk
                if self.end_of_calculation_string in line:
                    is_finished = True
                    break
        
        return is_finished

    def is_calculation_crashed(self):
        """Checks if there is an error message in the error file, that would 
        justify killing the job"""

        #raise NotImplementedError("TODO: parse error file for common errors")
        return False

    def kill_job(self):
        """Cancels the current job via Slurm's scancel."""

        job_id = self.get_job_id()

        self.log("Killing job " + str(job_id))

        # cancell the slurm job the assassin is running in.
        sp.run(["scancel", job_id]) 


    def lurk_and_kill(self):
        """Activates a listener that checks whether the calculation started via
        the start_calculation method is still alive. If it has died the 
        assassin will kill the slurm job (and notify the user if a mail
        address was specified in the constructor)
        
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

        #--- keep listening if calculation is still sane ---
        time_last_poll = self.time_calculation_start

        try:
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
                if abs(time_last_poll - self.time_now()) < \
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

        except CalculationCrashed as ex:
            
            self.log("Calculation crashed!", 3)
            self.send_email_notifcation_crashed()


        except CalculationTimeout as ex:

            self.log("Calculation timed out!", 3)
            self.send_email_notifcation_timeout()

            # stop the calculation process.
            try:
                self.terminate_calculation_process()
            except:
                self.log("Could not stop calculation process!", 3)

        finally:
            
            self.kill_job()
        #---




        