# Standard Library
import os
# Third Party
import flask
import flask.ext.security
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


def get_actions_for_method(method_name, header='', back=''):
    current_user = flask.ext.security.current_user
    actions = [x.id for x in getattr(current_user, 'actions', [])]
    if not actions:
        actions = flask.session.get('actions', [])
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=str(method_name)).first()
        for group in method.groups:
            action_dict = {x.id: x.label for x in group.approved_actions}
            result[group.name] = action_dict
    else:
        all_actions = models.Action.query.all()
        result = {'': {x.id: x.label for x in all_actions}}
    return flask.render_template('snippets/actions.html', result=result,
                                 method_name=method_name, actions=actions,
                                 header=header, back=back)


def get_redirect(endpoint):
    urls = [flask.ext.security.utils.get_url(flask.request.args.get('next')),
            flask.ext.security.utils.get_url(flask.request.form.get('next')),
            flask.ext.security.utils.get_url(endpoint)]
    for url in urls:
        if flask.ext.security.utils.validate_redirect_url(url):
            return url
