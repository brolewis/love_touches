# Third Party
import flask.ext.admin
import flask.ext.admin.contrib.sqla
import flask.ext.admin.helpers
import flask.ext.admin.model
import flask.ext.principal
import sqlalchemy
import wtforms
# Local
import forms
import main
import models


class AuthBaseView(flask.ext.admin.BaseView):
    def is_accessible(self):
        user = flask.ext.login.current_user
        return user.is_authenticated() and user.has_role('admin')

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return flask.current_app.login_manager.unauthorized()


class AuthIndexView(flask.ext.admin.AdminIndexView, AuthBaseView):
    pass


class AuthModelView(flask.ext.admin.contrib.sqla.ModelView, AuthBaseView):
    pass


class LogoutView(AuthBaseView):
    @flask.ext.admin.expose('/')
    def logout(self):
        return flask.redirect(flask.url_for('security.logout'))


class UserModelView(AuthModelView):
    can_create = False
    form_columns = ('roles', 'active', 'email', 'phone', 'secret')
    column_list = ('active', 'email', 'phone', 'method', 'confirmed_at',
                   'email_confirmed_at', 'phone_confirmed_at')
    column_searchable_list = ('email', 'phone')
    column_filters = ('active', 'email', 'phone')

    def scaffold_form(self):
        form_class = super(UserModelView, self).scaffold_form()
        form_class.password2 = wtforms.PasswordField('New Password')
        return form_class

    def on_model_change(self, form, model):
        if len(model.password2):
            passwd = form.password2.data
            model.password = flask.ext.security.utils.encrypt_password(passwd)


class ProposedModelView(AuthModelView):
    proposed = models.Status.query.filter_by(name='Proposed')

    def get_query(self):
        status = self.model.status == self.proposed.first()
        return self.session.query(self.model).filter(status)

    def get_count_query(self):
        count = sqlalchemy.func.count('*')
        status = models.Method.status == self.proposed.first()
        return self.session.query(count).select_from(self.model).filter(status)


class MethodModelView(ProposedModelView):
    column_list = ('name', 'status', 'sections', 'author')


class ActionModelView(ProposedModelView):
    column_list = ('label', 'status', 'author')


class ApproveMethod(AuthBaseView):
    @flask.ext.admin.expose('/')
    def index(self):
        pass


class UnansweredFeedbackView(AuthModelView):
    column_list = ('sender', 'message', 'created_at')
    list_template = 'admin/feedback_list.html'

    @flask.ext.admin.expose('/reply/', methods=['GET', 'POST'])
    def reply_view(self):
        return_url = flask.ext.admin.helpers.get_redirect_target()
        if not return_url:
            return_url = flask.url_for('.index_view')
        id = flask.request.args.get('id')
        if id is None:
            return flask.redirect(return_url)
        parent = self.get_one(id)
        if parent is None:
            return flask.redirect(return_url)
        form = forms.FeedbackForm()
        if form.validate_on_submit():
            message = models.Message(sender=flask.ext.security.current_user,
                                     message=form.message.data, parent=parent)
            models.db.session.add(message)
            models.db.session.commit()
            return flask.redirect(return_url)
        return self.render('admin/feedback_reply.html', form=form,
                           parent=parent, return_url=return_url)

    def get_query(self):
        user = flask.ext.security.current_user
        query = self.session.query(self.model)
        query = query.filter(self.model.sender != user)
        return query.filter(~self.model.children.any())

    def get_count_query(self):
        user = flask.ext.security.current_user
        count = sqlalchemy.func.count('*')
        query = self.session.query(count).select_from(self.model)
        query = query.filter(self.model.sender != user)
        return query.filter(~self.model.children.any())


admin = flask.ext.admin.Admin(main.app, 'Love Touches',
                              index_view=AuthIndexView())
admin.add_view(UserModelView(models.User, models.db.session, 'Users'))
admin.add_view(MethodModelView(models.Method, models.db.session,
                               'Proposed Methods'))
admin.add_view(ActionModelView(models.Action, models.db.session,
                               'Proposed Actions'))
admin.add_view(UnansweredFeedbackView(models.Message, models.db.session,
                                      'Unanswered Feedback'))
# Logout
admin.add_view(LogoutView(name='Logout'))
