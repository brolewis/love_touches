# Standard Library
import argparse
import datetime
# Third Party
import pytz
import sqlalchemy
import sqlalchemy.dialects.postgres
# Local
import main
import tasks


def find_email(check_hour=None, check_minute=None, dry_run=False):
    prop = main.models.User.email_confirmed_at
    for user in _find_user(prop, check_hour=check_hour,
                           check_minute=check_minute):
        if dry_run:
            print user.email
        else:
            tasks.send_email.delay(user.id)


def find_phone(check_hour=None, check_minute=None, dry_run=False):
    prop = main.models.User.phone_confirmed_at
    for user in _find_user(prop, check_hour=check_hour,
                           check_minute=check_minute):
        if dry_run:
            print user.phone
        else:
            tasks.send_sms.delay(user.id)


def _find_user(prop, check_hour=None, check_minute=None):
    if check_hour is None:
        check_hour = main.models.User.check_hour
    if check_minute is None:
        check_minute = main.models.User.check_minute
    utc_now = datetime.datetime.utcnow()
    utc_now = utc_now.replace(tzinfo=pytz.utc)
    session = main.db.create_scoped_session()
    array = sqlalchemy.dialects.postgres.ARRAY(sqlalchemy.Integer,
                                               as_tuple=True)
    weekdays = sqlalchemy.func.array_agg(main.models.Weekday.utc_weekday,
                                         type_=array)
    user_query = session.query(main.models.User.id,
                               main.models.User.timezone, check_hour,
                               weekdays.label('weekdays'))
    join_clause = main.models.Weekday.user_id == main.models.User.id
    user_query = user_query.join(main.models.Weekday, join_clause)
    user_query = user_query.group_by(main.models.User.id)
    minute_query = check_minute == utc_now.minute
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
    parser = argparse.ArgumentPraser('Cron Job for Love Touches')
    parser.add_argument('--dry_run', action='store_true')
    parser.add_argument('--check_hour', type=int)
    parser.add_argument('--check_minute', type=int)
    args = parser.parse_args()
    find_email(check_hour=args.check_hour, check_minute=args.check_minute,
               dry_run=args.dry_run)
    find_phone(check_hour=args.check_hour, check_minute=args.check_minute,
               dry_run=args.dry_run)
