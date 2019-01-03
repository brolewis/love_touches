# Standard Library
import argparse
import datetime
import os

# Third Party
import pytz
import raven
import sqlalchemy

# Local
import main
import tasks


def find_email(hour=None, minute=None, dry_run=False, local=False):
    if dry_run:
        session = main.db.create_scoped_session()
    prop = main.models.User.email_confirmed_at
    for user in _find_user(prop, hour=hour, minute=minute):
        if dry_run:
            user = session.query(main.models.User).get(user.id)
            print(user.email)
        else:
            if local:
                tasks.send_email(user.id)
            else:
                tasks.send_email.delay(user.id)


def find_phone(hour=None, minute=None, dry_run=False, local=False):
    if dry_run:
        session = main.db.create_scoped_session()
    prop = main.models.User.phone_confirmed_at
    for user in _find_user(prop, hour=hour, minute=minute):
        if dry_run:
            user = session.query(main.models.User).get(user.id)
            print(user.phone)
        else:
            if local:
                tasks.send_sms(user.id)
            else:
                tasks.send_sms.delay(user.id)


def _find_user(prop, hour=None, minute=None):
    utc_now = datetime.datetime.utcnow()
    utc_now = utc_now.replace(tzinfo=pytz.utc)
    if hour is not None:
        utc_now = utc_now.replace(hour=hour)
    if minute is not None:
        utc_now = utc_now.replace(minute=minute)
    session = main.db.create_scoped_session()
    weekdays = sqlalchemy.func.array_agg(main.models.Weekday.utc_weekday)
    user_query = session.query(
        main.models.User.id,
        main.models.User.timezone,
        main.models.User.check_hour,
        weekdays.label("weekdays"),
    )
    join_clause = main.models.Weekday.user_id == main.models.User.id
    user_query = user_query.join(main.models.Weekday, join_clause)
    user_query = user_query.group_by(main.models.User.id)
    minute_query = main.models.User.check_minute == utc_now.minute
    user_query = user_query.filter(minute_query)
    hour_list = [
        utc_now.hour,
        (utc_now - datetime.timedelta(hours=1)).hour,
        (utc_now + datetime.timedelta(hours=1)).hour,
    ]
    user_query = user_query.filter(main.models.User.utc_hour.in_(hour_list))
    user_query = user_query.filter(prop != None)  # noqa
    for user in user_query:
        check_dt = utc_now.astimezone(pytz.timezone(user.timezone))
        if user.check_hour == check_dt.hour:
            if check_dt.weekday() in user.weekdays:
                yield user


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Cron Job for Love Touches")
    parser.add_argument("--dry_run", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--hour", type=int)
    parser.add_argument("--minute", type=int)
    args = parser.parse_args()
    try:
        find_email(
            hour=args.hour, minute=args.minute, dry_run=args.dry_run, local=args.local
        )
        find_phone(
            hour=args.hour, minute=args.minute, dry_run=args.dry_run, local=args.local
        )
    except Exception:
        if "SENTRY_DSN" in os.environ:
            client = raven.Client(os.environ["SENTRY_DSN"])
            client.captureException()
        else:
            raise
