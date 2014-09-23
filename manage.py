#!/usr/bin/env python
# Standard Library
import datetime
import getpass
import os
import random
# Third Party
import flask.ext.migrate
import flask.ext.script
import flask.ext.security
import pyotp
import pytz
# Local
import main

MANAGER = flask.ext.script.Manager(main.app)
MANAGER.add_command('db', flask.ext.migrate.MigrateCommand)


@MANAGER.command
def dropdb():
    '''Drops all database tables'''
    print 'Database: %s' % main.models.db.engine.url
    main.models.db.drop_all()
    print 'All tables dropped'


@MANAGER.command
def create_admin():
    '''Create new admin user.'''
    main.models.db.create_all()
    print 'creating "admin" role'
    admin_role = main.user_datastore.find_or_create_role('admin')
    print 'creating admin@love-touches.org'
    now = datetime.datetime.utcnow()
    password = flask.ext.security.utils.encrypt_password(getpass.getpass())
    admin = main.user_datastore.create_user(email='admin@love-touches.org',
                                            password=password, active=True,
                                            confirmed_at=now)
    main.user_datastore.add_role_to_user(admin, admin_role)
    main.models.db.session.commit()


@MANAGER.command
def create_confirmed_user():
    main.models.db.create_all()
    print 'creating lewis@love-touches.org'
    password = flask.ext.security.utils.encrypt_password(getpass.getpass())
    main.user_datastore.create_user(email='lewis@love-touches.org',
                                    password=password, active=True,
                                    confirmed_at=datetime.datetime.utcnow(),
                                    secret=pyotp.random_base32(),
                                    method_id=1)
    main.models.db.session.commit()


@MANAGER.command
def create_defaults():
    '''Create default data.'''
    main.models.db.create_all()
    sections = {
        'Words of Affirmation': ['Compliment looks', 'Leave a love note',
                                 'Be encouraging about a project',
                                 'Compliment something they say'],
        'Acts of Service': ['Cook dinner', 'Do some vacuuming', 'Dust',
                            "Do next day's chore(s)"],
        'Receiving Gifts': ['Give flowers', 'Give candy',
                            'Give a homemade card'],
        'Quality Time': ['Talk aout something God is doing', 'Go on a walk',
                         'Discuss the news', 'Game night'],
        'Physical Touch': ['Back rub with oil', 'Back rub before bed',
                           'Slow dance hug', 'Passionate kiss goodbye',
                           'Multiple kisses on body', 'Kiss on the neck',
                           'Multiple kisses on face,'],
    }
    print 'Creating statuses'
    for name in ('Proposed', 'Rejected', 'Approved'):
        status = main.models.Status.query.filter_by(name=name).first()
        if not status:
            status = main.models.Status(name=name)
            main.models.db.session.add(status)
    print 'Creating method'
    for name in ('Five Love Languages',):
        method = main.models.Method.query.filter_by(name=name).first()
        if not method:
            method = main.models.Method(name=name, status=status)
            main.models.db.session.add(method)
    print 'Creating sections'
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


def create_crontabs():
    engine = main.db.engine
    names = set(open('/usr/share/dict/words').read().lower().splitlines())
    names = list(names)
    utc_now = datetime.datetime.utcnow()
    users = []
    for user_id in xrange(1, 100001):
        name = random.choice(names)
        names.remove(name)
        email = '{}@love-touches.org'.format(name)
        users.append({'email': email, 'active': True, 'method_id': 1,
                      'email_confirmed_at': utc_now, 'id': user_id})
    engine.execute(main.models.User.__table__.insert(), users)
    for user_id in xrange(1, 100001):
        crontabs = []
        for _ in xrange(10):
            time = datetime.time(random.randint(0, 23), random.randint(0, 59))
            weekday = random.randint(0, 6)
            timezone = random.choice(pytz.common_timezones)
            crontabs.append({'time': time, 'weekday': weekday,
                            'timezone': timezone, 'user_id': user_id})
        engine.execute(main.models.Crontab.__table__.insert(), crontabs)


@MANAGER.shell
def _make_shell_context():
    return dict(app=main.app, db=main.models.db, models=main.models,
                session=main.models.db.session)


PORT = int(os.getenv('PORT') or 5000)
SERVER = flask.ext.script.Server(host='0.0.0.0', port=PORT)
MANAGER.add_command('runserver', SERVER)
MANAGER.run()
