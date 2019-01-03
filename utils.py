# Standard Library
import datetime
import os

# Third Party
import flask
import flask_security
import phonenumbers
import pyotp
import pytz
import twilio.rest

# Local
import models


def add_schedule(user, dct):
    user.timezone = dct["timezone"]
    user.check_hour = dct["hour"] + 12 if dct["am_pm"] == "pm" else dct["hour"]
    user.check_minute = dct["minute"]
    tz = pytz.timezone(dct["timezone"])
    check_dt = datetime.datetime.now().replace(hour=dct["hour"], minute=dct["minute"])
    user.utc_hour = tz.localize(check_dt).utctimetuple()[3]
    weekdays = []
    for local_weekday in dct["days_of_week"]:
        days = (local_weekday - check_dt.weekday()) % 7
        weekday_dt = check_dt + datetime.timedelta(days=days)
        utc_weekday = tz.localize(weekday_dt).weekday()
        weekdays.append(models.Weekday(utc_weekday=utc_weekday))
    user._weekdays = weekdays


def format_phone(dct):
    num_obj = None
    if dct.get("country_code") and dct.get("phone"):
        num_obj = phonenumbers.parse("+{country_code} {phone}".format(**dct))
    elif dct.get("From"):
        num_obj = phonenumbers.parse(dct.get("From"))
    if num_obj:
        number = phonenumbers.format_number_for_mobile_dialing(num_obj, "us", True)
        return number
    else:
        return ""


def send_code(user):
    user.phone_hotp = max(user.email_hotp, user.phone_hotp) + 1
    models.db.session.add(user)
    models.db.session.commit()
    message = "Your Love Touches verification code is: {}"
    message = message.format(pyotp.HOTP(user.secret).at(user.phone_hotp))
    client = twilio.rest.Client(os.getenv("ACCOUNT_SID"), os.getenv("AUTH_TOKEN"))
    from_number = client.incoming_phone_numbers.list()[0].phone_number
    client.messages.create(body=message, from_=from_number, to=user.phone)


def send_sms(to_number, message):
    client = twilio.rest.Client(os.getenv("ACCOUNT_SID"), os.getenv("AUTH_TOKEN"))
    from_number = client.incoming_phone_numbers.list()[0].phone_number
    client.messages.create(body=message, from_=from_number, to=to_number)


def get_actions_for_method(method_name, header="", back=""):
    current_user = flask_security.current_user
    actions = [x.id for x in getattr(current_user, "actions", [])]
    if not actions:
        actions = flask.session.get("actions", [])
    if method_name:
        result = {}
        method = models.Method.query.filter_by(name=str(method_name)).first()
        for section in method.sections:
            action_dict = {x.id: x.label for x in section.approved_actions}
            result[section.name] = action_dict
    else:
        approved_status = models.Status.name == "Approved"
        all_actions = models.Action.query.filter(approved_status)
        result = {"": {x.id: x.label for x in all_actions}}
    return flask.render_template(
        "snippets/actions.html",
        result=result,
        method_name=method_name,
        actions=actions,
        header=header,
        back=back,
    )


def get_redirect(endpoint):
    urls = [
        flask_security.utils.get_url(flask.request.args.get("next")),
        flask_security.utils.get_url(flask.request.form.get("next")),
        flask_security.utils.get_url(endpoint),
    ]
    for url in urls:
        if flask_security.utils.validate_redirect_url(url):
            return url


def unsubscribe_test(message):
    message = message.lower()
    for keyword in ("unsubscribe", "quit", "cancel", "remove", "delete", "stop"):
        if keyword in message:
            return True
    return False
