# Standard Library
import os
# Third Party
import flask
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


def _get_actions_for_method(method_name, actions, link, signup=False, back=''):
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=method_name).first()
        for group in method.groups:
            result[group.name] = {x.id: x.label for x in group.actions}
    else:
        actions = models.Action.query.all()
        result = {'All': {x.id: x.label for x in actions}}
    return flask.render_template('snippets/actions.html', result=result,
                                 method_name=method_name, actions=actions,
                                 link=link, signup=signup, back=back)
