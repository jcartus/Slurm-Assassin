"""This script is designed to test if a mail can be sent from a runnign 
slurm job both separately and as part of a unit test.

Author:
    Johannes Cartus, TU Graz, 04.07.2019
"""

from assassin import EMailHandler
from assassin import Logger

Logger.name_of_logfile = "mail_test.log"


def test_sending_a_mail(
    msg="This is a testmessage.", 
    subject="[Slurm-Assassin] test", 
    recipient="slurmassassin@mailinator.com",
    sender="test@assassin.vsc3.ac.at"
):
    """Send a mail to an address just to see if it works. Probably 
    not good for automated tests.
    """

    handler = EMailHandler(
        sender_address=sender,
        recipient_address=recipient,
    )

    handler.send_email(subject, msg)

if __name__ == '__main__':
    test_sending_a_mail()



