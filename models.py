'''Database model object'''
# Third Party
import flask.ext.security
import sqlalchemy.ext.hybrid
# Local
from main import db

# Users and Roles
roles_users = db.Table('roles_users',
                       db.Column('user_id', db.Integer,
                                 db.ForeignKey('user.id')),
                       db.Column('role_id', db.Integer,
                                 db.ForeignKey('role.id')))
users_actions = db.Table('users_actions',
                         db.Column('user_id', db.Integer,
                                   db.ForeignKey('user.id')),
                         db.Column('action_id', db.Integer,
                                   db.ForeignKey('action.id')))
groups_actions = db.Table('groups_actions',
                          db.Column('group_id', db.Integer,
                                    db.ForeignKey('group.id')),
                          db.Column('action_id', db.Integer,
                                    db.ForeignKey('action.id')))
methods_groups = db.Table('methods_groups',
                          db.Column('method_id', db.Integer,
                                    db.ForeignKey('method.id')),
                          db.Column('group_id', db.Integer,
                                    db.ForeignKey('group.id')))


class Role(db.Model, flask.ext.security.RoleMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True)
    description = db.Column(db.String)

    def __repr__(self):
        return self.name


class User(db.Model, flask.ext.security.UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    password = db.Column(db.String, default='')
    active = db.Column(db.Boolean)
    email = db.Column(db.String, unique=True)
    phone = db.Column(db.String)
    secret = db.Column(db.String)
    confirmed_at = db.Column(db.DateTime)
    phone_confirmed_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    current_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String)
    current_login_ip = db.Column(db.String)
    login_count = db.Column(db.Integer)
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    method_id = db.Column(db.Integer, db.ForeignKey('method.id'))
    method = db.relationship('Method')
    actions = db.relationship('Action', secondary=users_actions)
    schedule = db.relationship('Crontab', backref='user')

    def __repr__(self):
        return self.email or self.phone


class Crontab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    day_of_week = db.Column(db.Integer)
    time = db.Column(db.Time)
    timezone = db.Column(db.String)

    def __repr__(self):
        return '{} at {:%I:%M %p} ({})'.format(self.day_label, self.time,
                                               self.timezone)
    @sqlalchemy.ext.hybrid.hybrid_property
    def day_label(self):
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday',
                     'Friday', 'Saturday']
        return day_names[self.day_of_week]


class Action(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String)

    def __repr__(self):
        return self.label


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    actions = db.relationship('Action', secondary=groups_actions)

    def __repr__(self):
        return self.name


class Method(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    groups = db.relationship('Group', secondary=methods_groups)

    def __repr__(self):
        return self.name
