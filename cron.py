# Standard Library
import datetime
# Third Party
import pytz
import sqlalchemy
import sqlalchemy.dialects.postgres
# Local
import main
import tasks


def find_email():
    for user in _find_user(main.models.User.email_confirmed_at):
        tasks.send_email.delay(user.id)


def find_phone():
    for user in _find_user(main.models.User.phone_confirmed_at):
        tasks.send_sms.delay(user.id)


def _find_user(prop):
    utc_now = datetime.datetime.utcnow()
    utc_now = utc_now.replace(tzinfo=pytz.utc)
    session = main.db.create_scoped_session()
    array = sqlalchemy.dialects.postgres.ARRAY(sqlalchemy.Integer,
                                               as_tuple=True)
    weekdays = sqlalchemy.func.array_agg(main.models.Weekday.utc_weekday,
                                         type_=array)
    user_query = session.query(main.models.User.id,
                               main.models.User.timezone,
                               main.models.User.check_hour,
                               weekdays.label('weekdays'))
    join_clause = main.models.Weekday.user_id == main.models.User.id
    user_query = user_query.join(main.models.Weekday, join_clause)
    user_query = user_query.group_by(main.models.User.id)
    minute_query = main.models.User.check_minute == utc_now.minute
    user_query = user_query.filter(minute_query)
    hour_list = [utc_now.hour, (utc_now - datetime.timedelta(hours=1)).hour,
                 (utc_now + datetime.timedelta(hours=1)).hour]
    user_query = user_query.filter(main.models.User.utc_hour.in_(hour_list))
    user_query = user_query.filter(prop != None)  # noqa
    for user in user_query:
        check_dt = utc_now.astimezone(pytz.timezone(user.timezone))
        if user.check_hour == check_dt.hour:
            if check_dt.weekday() in user.weekdays:
                yield user


if __name__ == '__main__':
    find_email()
    find_phone()
