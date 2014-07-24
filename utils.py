# Standard Library
import os
# Third Party
import phonenumbers
import pyotp
import telapi.rest
# Local
import models


def format_phone(dct):
    if dct.get('country_code') and dct.get('phone'):
        num_obj = phonenumbers.parse('+{country_code} {phone}'.format(**dct))
        number = phonenumbers.format_number_for_mobile_dialing(num_obj, 'us',
                                                               True)
        return number
    else:
        return ''


def send_code(user):
    user.secret = pyotp.random_base32()
    models.db.session.add(user)
    models.db.session.commit()
    hotp = pyotp.HOTP(user.secret)
    message = 'Your Love Touches verification code is: {}'
    message = message.format(hotp.at(0))
    client = telapi.rest.Client(os.getenv('ACCOUNT_SID'),
                                os.getenv('AUTH_TOKEN'))
    account = client.accounts[client.account_sid]
    from_number = account.incoming_phone_numbers[0].phone_number
    account.sms_messages.create(to_number=user.phone, from_number=from_number,
                                body=message)
