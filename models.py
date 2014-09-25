'''Database model object'''
# Standard Library
import datetime
# Third Party
import flask.ext.security
import sqlalchemy
import sqlalchemy.ext.hybrid
from sqlalchemy.ext.associationproxy import association_proxy
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
    email = db.Column(db.String, unique=True, nullable=True)
    phone = db.Column(db.String)
    timezone = db.Column(db.String)
    check_hour = db.Column(db.Integer)
    check_minute = db.Column(db.Integer)
    utc_hour = db.Column(db.Integer)
    secret = db.Column(db.String)
    email_hotp = db.Column(db.Integer, default=0)
    phone_hotp = db.Column(db.Integer, default=0)
    totp_enabled = db.Column(db.Boolean)
    confirmed_at = db.Column(db.DateTime)
    email_confirmed_at = db.Column(db.DateTime)
    phone_confirmed_at = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    current_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String)
    current_login_ip = db.Column(db.String)
    login_count = db.Column(db.Integer)
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))
    method_id = db.Column(db.Integer, db.ForeignKey('method.id'))
    method = db.relationship('Method', foreign_keys=[method_id])
    actions = db.relationship('Action', secondary=users_actions)
    _weekdays = db.relationship('Weekday', backref='user')
    messages = db.relationship('Message')
    active_index = db.Index(email_confirmed_at, phone_confirmed_at)

    def __repr__(self):
        return self.email or self.phone

    @sqlalchemy.ext.hybrid.hybrid_property
    def suggested_methods(self):
        methods = []
        for method in self.authored_methods:
            if method.status.name == 'Proposed':
                methods.append(method)
        return methods

    @sqlalchemy.ext.hybrid.hybrid_property
    def weekdays(self):
        return [x.utc_weekday for x in self._weekdays]


class Weekday(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    utc_weekday = db.Column(db.Integer)


class Status(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)

    def __repr__(self):
        return self.name


class Method(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'))
    status = db.relationship('Status', backref='methods')
    sections = db.relationship('Section', backref='method',
                               cascade='all, delete-orphan')
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True,
                                                    name='fk_author_id'))
    author = db.relationship('User', foreign_keys=[author_id],
                             backref='authored_methods')

    def __repr__(self):
        return self.name


class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    method_id = db.Column(db.Integer, db.ForeignKey('method.id'))
    name = db.Column(db.String)
    actions = db.relationship('SectionActions', backref='sections')

    def __repr__(self):
        return self.name

    @sqlalchemy.ext.hybrid.hybrid_property
    def approved_actions(self):
        actions = []
        approved = Status.query.filter_by(name='Approved').first()
        for assoc in self.actions:
            if assoc.status == approved and assoc.action.status == approved:
                actions.append(assoc.action)
        return actions


class SectionActions(db.Model):
    __tablename__ = 'section_actions'
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'),
                           primary_key=True)
    section = db.relationship('Section', backref=db.backref('section_actions'))
    action_id = db.Column(db.Integer, db.ForeignKey('action.id'),
                          primary_key=True)
    action = db.relationship('Action', backref=db.backref('section_actions'))
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'))
    status = db.relationship('Status', backref='section_actions')
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True,
                                                    name='fk_author_id'))
    author = db.relationship('User', foreign_keys=[author_id],
                             backref='authored_accociations')


class Action(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String)
    status_id = db.Column(db.Integer, db.ForeignKey('status.id'))
    status = db.relationship('Status', backref='actions')
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True,
                                                    name='fk_author_id'))
    author = db.relationship('User', foreign_keys=[author_id],
                             backref='authored_actions')
    sections = association_proxy('section_actions', 'section')

    def __repr__(self):
        return self.label


def approved_methods():
    return Method.query.filter(Status.name == 'Approved')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sender = db.relationship('User', foreign_keys=[sender_id])
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    parent_id = db.Column(db.Integer, db.ForeignKey('message.id'))
    children = db.relationship('Message',
                               cascade='all, delete-orphan',
                               backref=db.backref('parent', remote_side=id))
