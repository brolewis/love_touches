# Standard Library
import datetime
# Third Party
import pytz
# Local
import main
import tasks


def find_email():
    for user in _find_user(main.models.User.email_confirmed_at):
        tasks.send_email.delay(user.id)


def find_phone():
    for user in _find_user(main.models.User.phone_confirmed_at):
        tasks.send_sms(user.id)
        break


def _find_user(prop):
    utc_now = datetime.datetime.utcnow()
    utc_now = utc_now.replace(tzinfo=pytz.utc)
    session = main.db.create_scoped_session()
    user_query = session.query(main.models.User)
    user_query = user_query.filter_by(check_minute=utc_now.minute)
    between = main.models.User.utc_hour.between(utc_now.hour - 1,
                                                utc_now.hour + 1)
    user_query = user_query.filter(between)
    user_query = user_query.filter(prop != None)  # noqa
    for user in user_query:
        check_dt = utc_now.astimezone(pytz.timezone(user.timezone))
        if user.check_hour == check_dt.hour:
            if check_dt.weekday() in user.weekdays:
                yield user


if __name__ == '__main__':
    find_email()
    find_phone()
