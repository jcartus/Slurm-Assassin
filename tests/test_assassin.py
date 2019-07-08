"""This file contains some (unit) tests for the slurm assassing.

Author: Johannes Cartus, TU Graz, 04.07.2019
"""
import numpy as np
import unittest
import os

from collections import defaultdict

from SlurmAssassin import SlurmAssassin, Logger, EMailHandler
from SlurmAssassin import CalculationCrashed, CalculationTimeout


utilities_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "utilities"
)

class LoggerMock(Logger):     
    # count logging by differt level
    log_counter = np.zeros(4)
    log_errors = defaultdict(int)

    @classmethod
    def advance_counter(cls, level, message):
        cls.log_counter[level] += 1

        # in case it is an error, store the error
        if level==3:
            cls.log_errors[message] += 1

    @classmethod
    def log(cls, msg, level=0):
        if level in list(range(4)):
            cls.advance_counter(level, msg)
        else:
            raise ValueError("Unknown log level: " + str(level))

    @classmethod
    def reset_counter(cls):
        cls.log_counter = np.zeros(4)
        cls.log_errors = defaultdict(int)

    @classmethod
    def assert_expected_counts(cls, expected):
        """Check if as much was logged as you think it was"""
        np.testing.assert_array_equal(
            cls.log_counter,
            expected
        )

    @classmethod
    def assert_expected_counts_errors(cls, expected):
        """Check if as much errors were logged as you think there were"""
        np.testing.assert_array_equal(
            cls.log_counter[3],
            expected
        )



class EMailHandlerMock(EMailHandler): 
    # count logging by differt level

    _default_logger = LoggerMock

    mail_category_tokens = {
        "crashed": "Calculation Crashed",
        "timeout": "Calculation Time Out",
        "assassin_error": "Unexpected Assassin-Error"
    }

    def __init__(self, *args, **kwargs):

        super(EMailHandlerMock, self).__init__(*args, **kwargs)
        
        self.initialize_counters()

    def initialize_counters(self):
        self.counter_errors = defaultdict(int)
        self.counter_overall = 0

    def send_email(self, subject, message):
        """Instead of sending, just count."""

        self.counter_overall += 1

        for key, token in self.mail_category_tokens.items():
            
            if token in subject:
                self.counter_errors[key] += 1

    def assert_expected_counts_error_category(self, category, expected):
        """Comapre number of registered error messages of a specific 
        category with expectations"""
        if not category in self.mail_category_tokens.keys():
            raise ValueError("Unknown E-Mail-Kategory: " + str(category))
        else:
            assert expected == self.counter_errors[category], \
                "Expected {0} in category {1}, but got {2}.".format(
                    expected, 
                    category,
                    self.counter_errors[category]
                ) + " Overall results: " + str(self.counter_errors)

    def assert_expected_counts_errors(self, expected):
        """Compare logged number of error-mail with a dict of expectations"""
        for key, value in expected.items():
            self.assert_expected_counts_error_category(key, value)



# make sure the assassin uses the mocks for logger and mailing
SlurmAssassin._logger = LoggerMock
SlurmAssassin._default_email_handler = EMailHandlerMock


            
class FakeAssassin(SlurmAssassin):
    """This class fakes/stubs some of the methods of the slurm assassin for 
    testing """

    def get_job_id(self):
        return 75129





class TestCodeFailuresAreRecognized(unittest.TestCase):

    def setUp(self):

        self.fnull = open(os.devnull, "w")
        LoggerMock.reset_counter()

    def tearDown(self):
        
        self.fnull.close()

    def test_calculation_raises_exception(self):
        
        

        assassin = SlurmAssassin(
            timeout=15,
            polling_period=5
        )

        assassin.start_calculation_process(
            [
                "python3", 
                os.path.join(utilities_path, "dummy_raises_exception.py")
            ],
            stdout=self.fnull,
            stderr=self.fnull
        )

        # should detect the broken calculation by raising an exception
        self.assertRaises(CalculationCrashed, assassin._lurk)
        assassin.terminate_calculation_process()
            
        LoggerMock.assert_expected_counts_errors(0)

    def test_calculation_stops_writing(self):


        LoggerMock.reset_counter()


        logfile = os.path.join(utilities_path, "dummy_stop_writing.log")

        assassin = SlurmAssassin(
            timeout=20 / 60, 
            polling_period=7 / 60,
            out_file_name=logfile
        )

        assassin.start_calculation_process(
            [
                "python3", 
                os.path.join(utilities_path, "dummy_stops_writing_output.py"), 
                "-o",
                logfile
            ],
            stdout=self.fnull,
            stderr=self.fnull
        )

        # should detect the broken calculation by raising an exception
        self.assertRaises(CalculationTimeout, assassin._lurk)

        assassin.terminate_calculation_process()
            
        LoggerMock.assert_expected_counts_errors(0)

        try:
            os.remove(logfile)
        except FileNotFoundError:
            pass







class TestNotifyOnlyMode(unittest.TestCase):
    """Tests if the assassin works correctly in notify-only mode"""

    def setUp(self):

        self.fnull = open(os.devnull, "w")  
        LoggerMock.reset_counter()

    def tearDown(self):
        
        self.fnull.close()

    def test_calculation_stops_writing(self):


        
        
        logfile = os.path.join(utilities_path, "dummy_stop_writing.log")

        assassin = FakeAssassin(
            timeout=20 / 60, 
            polling_period=10 / 60,
            out_file_name=logfile,
            email="test@test.test"
        )

        assassin.start_calculation_process(
            [
                "python3", 
                os.path.join(utilities_path, "dummy_stops_writing_output.py"), 
                "-o",
                logfile
            ],
            stdout=self.fnull,
            stderr=self.fnull
        )

        # should detect the broken calculation by raising an exception
        try:
            assassin.lurk_and_notify()

            # fail if system exit is not given
            self.fail("Assassin did not trigger system exit!")
        except SystemExit:
            pass
        
        #--- check if process has terminated ---
        # (it should finish normally)
        return_code = assassin._calculation_process.poll()
        self.assertIsNotNone(return_code, msg="Process is still running!")
        self.assertEqual(
                return_code, 
                0,
                msg="Process did not finish normally. Exit Code: " + \
                    str(return_code)
            )
        #---

        #--- check if emails / log errors were send ---
        expected = 26
        #LoggerMock.assert_expected_counts_errors(expected * 2)
        assassin._email_handler.assert_expected_counts_error_category(
            "timeout",
            expected
        )
        #---

        try:
            os.remove(logfile)
        except FileNotFoundError:
            pass

if __name__ == '__main__':
    unittest.main()
