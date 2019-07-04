"""This file contains some (unit) tests for the slurm assassing.

Author: Johannes Cartus, TU Graz, 04.07.2019
"""
import numpy as np
import unittest

from collections import defaultdict

from assassin import SlurmAssassin, Logger, EMailHandler
from assassin import CalculationCrashed, CalculationTimeout



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
            
SlurmAssassin._logger = LoggerMock



class TestCodeFailuresAreRecognized(unittest.TestCase):

    def test_calculation_raises_exception(self):
        
        LoggerMock.reset_counter()

        assassin = SlurmAssassin(
            timeout=15,
            polling_period=5
        )

        assassin.start_calculation_process(
            ["python3", "utilities/dummy_raises_exception.py"]
        )

        # should detect the broken calculation by raising an exception
        self.assertRaises(RuntimeError, assassin._lurk)

            
        LoggerMock.assert_expected_counts_errors(0)



if __name__ == '__main__':
    unittest.main()
