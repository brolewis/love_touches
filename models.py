'''Database model object'''
# Third Party
import flask.ext.security
import sqlalchemy.ext.hybrid
from sqlalchemy.ext.associationproxy import association_proxy
# Local
from main import db

APPROVED = 1
REJECTED = -1
PROPOSED = 0


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
    secret = db.Column(db.String)
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
    schedule = db.relationship('Crontab', backref='user')

    def __repr__(self):
        return self.email or self.phone

    @sqlalchemy.ext.hybrid.hybrid_property
    def suggested_methods(self):
        return [x for x in self.authored_methods if x.status == PROPOSED]


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


class Method(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    status = db.Column(db.Integer, default=PROPOSED)
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
        for assoc in self.actions:
            if assoc.status == APPROVED and assoc.action.status == APPROVED:
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
    status = db.Column(db.Integer, default=PROPOSED)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True,
                                                    name='fk_author_id'))
    author = db.relationship('User', foreign_keys=[author_id],
                             backref='authored_accociations')


class Action(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String)
    status = db.Column(db.Integer, default=PROPOSED)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id', use_alter=True,
                                                    name='fk_author_id'))
    author = db.relationship('User', foreign_keys=[author_id],
                             backref='authored_actions')
    sections = association_proxy('section_actions', 'section')

    def __repr__(self):
        return self.label

approved_methods = Method.query.filter_by(status=APPROVED)
