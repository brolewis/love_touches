#!/usr/bin/env python
# Standard Library
import datetime
import getpass
import os
import random

# Third Party
import flask_migrate
import flask_script
import flask_security
import pyotp
import pytz
import sqlalchemy.sql

# Local
import main

MANAGER = flask_script.Manager(main.app)
MANAGER.add_command("db", flask_migrate.MigrateCommand)


@MANAGER.command
def dropdb():
    """Drop all database tables."""
    print(f"Database: {main.models.db.engine.url}")
    main.models.db.drop_all()
    print("All tables dropped")


@MANAGER.command
def create_admin():
    """Create new admin user."""
    main.models.db.create_all()
    print('creating "admin" role')
    admin_role = main.user_datastore.find_or_create_role("admin")
    print("creating admin@love-touches.org")
    now = datetime.datetime.utcnow()
    password = flask_security.utils.encrypt_password(getpass.getpass())
    admin = main.user_datastore.create_user(
        email="admin@love-touches.org", password=password, active=True, confirmed_at=now
    )
    main.user_datastore.add_role_to_user(admin, admin_role)
    main.models.db.session.commit()


@MANAGER.command
def create_confirmed_user():
    main.models.db.create_all()
    print("creating lewis@love-touches.org")
    password = flask_security.utils.encrypt_password(getpass.getpass())
    main.user_datastore.create_user(
        email="lewis@love-touches.org",
        password=password,
        active=True,
        confirmed_at=datetime.datetime.utcnow(),
        secret=pyotp.random_base32(),
        method_id=1,
    )
    main.models.db.session.commit()


@MANAGER.command
def create_defaults():
    """Create default data."""
    main.models.db.create_all()
    sections = {
        "Words of Affirmation": [
            "Compliment looks",
            "Leave a love note",
            "Be encouraging about a project",
            "Compliment something they say",
        ],
        "Acts of Service": [
            "Cook dinner",
            "Do some vacuuming",
            "Dust",
            "Do next day's chore(s)",
        ],
        "Receiving Gifts": ["Give flowers", "Give candy", "Give a homemade card"],
        "Quality Time": [
            "Talk aout something God is doing",
            "Go on a walk",
            "Discuss the news",
            "Game night",
        ],
        "Physical Touch": [
            "Back rub with oil",
            "Back rub before bed",
            "Slow dance hug",
            "Passionate kiss goodbye",
            "Multiple kisses on body",
            "Kiss on the neck",
            "Multiple kisses on face,",
        ],
    }
    print("Creating statuses")
    for name in ("Proposed", "Rejected", "Approved"):
        status = main.models.Status.query.filter_by(name=name).first()
        if not status:
            status = main.models.Status(name=name)
            main.models.db.session.add(status)
    print("Creating method")
    for name in ("Five Love Languages",):
        method = main.models.Method.query.filter_by(name=name).first()
        if not method:
            method = main.models.Method(name=name, status=status)
            main.models.db.session.add(method)
    print("Creating sections")
    for name in sections:
        section = main.models.Section.query.filter_by(name=name).first()
        if not section:
            section = main.models.Section(name=name)
        if section not in method.sections:
            method.sections.append(section)
        for label in sections[name]:
            assoc = main.models.SectionActions(status=status)
            assoc.action = main.models.Action(label=label, status=status)
            section.actions.append(assoc)
        main.models.db.session.add(section)
    main.models.db.session.commit()


@MANAGER.command
def create_dummy_data(max_id):
    engine = main.db.engine
    names = set(open("/usr/share/dict/words").read().lower().splitlines())
    names = list(names)
    utc_now = datetime.datetime.utcnow()
    email_users = []
    phone_users = []
    query = main.db.create_scoped_session().query
    min_id = query(sqlalchemy.sql.func.max(main.models.User.id)).first()[0]
    schedules = []
    actions = []
    for user_id in range((min_id or 0) + 1, (min_id or 0) + int(max_id) + 1):
        name = "{}{}".format(random.choice(names), user_id)
        active = bool(random.randint(0, 5))
        check_hour = random.randint(0, 23)
        check_minute = random.randint(0, 59)
        timezone = random.choice(pytz.common_timezones)
        tz = pytz.timezone(timezone)
        check_dt = datetime.datetime.now().replace(hour=check_hour, minute=check_minute)
        utc_hour = tz.localize(check_dt).utctimetuple()[3]
        days_of_week = []
        weekdays = range(0, 7)
        for _ in range(random.randint(2, 7)):
            days_of_week.append(random.choice(weekdays))
            weekdays.remove(days_of_week[-1])
        for local_weekday in days_of_week:
            days = (local_weekday - check_dt.weekday()) % 7
            weekday_dt = check_dt + datetime.timedelta(days=days)
            utc_weekday = tz.localize(weekday_dt).weekday()
            schedules.append({"utc_weekday": utc_weekday, "user_id": user_id})
        possible_actions = range(1, 23)
        action_ids = []
        for _ in range(3, random.randint(5, 10)):
            action_ids.append(random.choice(possible_actions))
            possible_actions.remove(action_ids[-1])
        for action_id in action_ids:
            actions.append({"user_id": user_id, "action_id": action_id})
        user = {
            "active": active,
            "method_id": 1,
            "id": user_id,
            "check_hour": check_hour,
            "check_minute": check_minute,
            "timezone": timezone,
            "utc_hour": utc_hour,
        }
        if random.randint(0, 1):
            user["email"] = "{}@love-touches.org".format(name)
            user["email_confirmed_at"] = utc_now
            email_users.append(user)
        else:
            user["phone"] = "+1 {}-{}-{}".format(
                random.randint(100, 999),
                random.randint(100, 999),
                random.randint(1000, 9999),
            )
            user["phone_confirmed_at"] = utc_now
            phone_users.append(user)
    if email_users:
        engine.execute(main.models.User.__table__.insert(), email_users)
    if phone_users:
        engine.execute(main.models.User.__table__.insert(), phone_users)
    engine.execute(main.models.Weekday.__table__.insert(), schedules)
    engine.execute(main.models.users_actions.insert(), actions)


@MANAGER.shell
def _make_shell_context():
    return {
        "app": main.app,
        "db": main.models.db,
        "models": main.models,
        "session": main.models.db.session,
    }


PORT = int(os.getenv("PORT") or 5000)
SERVER = flask_script.Server(host="0.0.0.0", port=PORT)
MANAGER.add_command("runserver", SERVER)
MANAGER.run()
