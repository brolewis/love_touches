#!/usr/bin/env python
# Standard Library
import datetime
import getpass
import os
# Third Party
import flask.ext.migrate
import flask.ext.script
import flask.ext.security
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
    print 'creating admin@love-touches.org'
    password = flask.ext.security.utils.encrypt_password(getpass.getpass())
    main.user_datastore.create_user(email='admin@love-touches.org',
                                    password=password)
    main.models.db.session.commit()


@MANAGER.command
def create_confirmed_user():
    main.models.db.create_all()
    print 'creating lewis@love-touches.org'
    password = flask.ext.security.utils.encrypt_password(getpass.getpass())
    main.user_datastore.create_user(email='lewis@love-touches.org',
                                    password=password, active=True,
                                    confirmed_at=datetime.datetime.now())
    main.models.db.session.commit()


@MANAGER.command
def create_defaults():
    '''Create default data.'''
    main.models.db.create_all()
    groups = {
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
    print 'Creating method'
    approved = main.models.APPROVED
    for name in ('Five Love Languages',):
        method = main.models.Method.query.filter_by(name=name).first()
        if not method:
            method = main.models.Method(name=name, status=approved)
            main.models.db.session.add(method)
    print 'Creating groups'
    for group_name in groups:
        group = main.models.Group.query.filter_by(name=group_name).first()
        if not group:
            group = main.models.Group(name=group_name, status=approved)
            main.models.db.session.add(group)
        if group not in method.groups:
            method.groups.append(group)
        for label in groups[group_name]:
            action = main.models.Action.query.filter_by(label=label).first()
            if not action:
                action = main.models.Action(label=label, status=approved)
                main.models.db.session.add(action)
            if action not in group.actions:
                group.actions.append(action)
    main.models.db.session.commit()


@MANAGER.shell
def _make_shell_context():
    return dict(app=main.app, db=main.models.db, models=main.models,
                session=main.models.db.session)


PORT = int(os.getenv('PORT') or 5000)
SERVER = flask.ext.script.Server(host='0.0.0.0', port=PORT)
MANAGER.add_command('runserver', SERVER)
MANAGER.run()
