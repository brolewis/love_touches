'''Initial application settings'''
# Standard Library
import os
# Third Party
import flask
import flask_bootstrap
import flask_debugtoolbar
import flask_sqlalchemy
import flask.ext.migrate

# General Setup
app = flask.Flask(__name__)
app.config['DEBUG'] = str(os.getenv('DEBUG', False)).lower() == 'true'
DEV_SECRET_KEY = 'v=&3w2fsnn+all#(av21nbj9w&w5+$yd71tg*(zng_qwrw=)k*'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', DEV_SECRET_KEY)
# SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///love_touches.sqlite'
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask.ext.migrate.Migrate(app, db)
# Bootstrap
flask_bootstrap.Bootstrap(app)
# Flask-Security
import models
app.config['SECURITY_PASSWORD_HASH'] = 'bcrypt'
app.config['SECURITY_PASSWORD_SALT'] = 'Fa_vX`u`>W52|:+6NFCV_-f+sU#BdUGC:s+!*n'
app.config['SECURITY_REMEMBER_SALT'] = 'sCZ;2Hd$n~4;}8<2iG3dqgkr~=HQz b7j-yK@,'
app.config['SECURITY_TRACKABLE'] = True
app.config['SECURITY_CONFIRMABLE'] = True
app.config['SECURITY_CONFIRM_URL'] = '/confirm_email'
app.config['SECURITY_POST_LOGIN_VIEW'] = 'post_login'
user_datastore = flask.ext.security.SQLAlchemyUserDatastore(db, models.User,
                                                            models.Role)
app.security = flask.ext.security.Security(app, user_datastore)
# Debug Toolbar
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
flask_debugtoolbar.DebugToolbarExtension(app)


# Local
# import admin  # flake8: noqa
import views  # flake8: noqa
