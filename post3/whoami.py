from contextlib import closing
import sqlite3
import urllib
from flask import Flask, render_template, request, url_for, session, make_response
import time
from werkzeug.utils import redirect
import facebook

DATABASE = 'db/whoami.db'
DEBUG = True
SECRET_KEY = 'top secret'
APP_SECRET = '8c717bae4e0c9ee44d0ea17232ee461a'
APP_ID = '676631292359762'
CANVAS_PAGE = 'https://apps.facebook.com/d-whoami'

app = Flask(__name__)
app.config.from_object(__name__)


adjectives = ['Judgemental', 'Accepting',
              'Morose', 'Cheerful',
              'Nervous', 'Relaxed',
              'Childish', 'Mature',
              'Vain', 'Modest']


def read_user_token():
    if request.method == "POST" and request.form.get('signed_request'):
        fb_request = facebook.parse_signed_request(request.form['signed_request'], app.config['APP_SECRET'])
        if u'user_id' in fb_request:
            session['user_id'] = fb_request[u'user_id']
            session['oauth_token'] = fb_request[u'oauth_token']
            session['expires'] = fb_request[u'expires']
            return True
        else:
            return False

    if session.get('user_id'):
        expires = int(session[u'expires'])
        now = time.time()
        if expires > now:
            return True

    return False


def build_authenticate_redirect():
    auth_url = 'https://www.facebook.com/dialog/oauth?%s' % (
        urllib.urlencode({'client_id': app.config['APP_ID'], 'redirect_uri': app.config['CANVAS_PAGE'],
                          'scope': 'user_friends'})
    )
    return make_response("<script> top.location.href='" + auth_url + "'</script>")


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.route('/', methods=['POST', 'GET'])
def main():
    return home()


def calc_window():
    user_id = session['user_id']
    with closing(connect_db()) as db:
        cur = db.execute('''
            select adjective, count(adjective)
            from results
            where subject_id=?
            group by adjective
            ''', [user_id])
        adj_counts = {row[0]: row[1] for row in cur.fetchall()}
        cur = db.execute('''
            select distinct adjective
            from results
            where subject_id=? and submitter_id<>subject_id
            group by adjective
            ''', [user_id])
        friend_select = {row[0] for row in cur.fetchall()}
        cur = db.execute('''
            select distinct adjective
            from results
            where subject_id=? and submitter_id=subject_id
            group by adjective
            ''', [user_id])
        player_select = {row[0] for row in cur.fetchall()}
        hidden = player_select - friend_select
        open = player_select & friend_select
        blind = friend_select - player_select
        window = dict()
        count = lambda a: dict(adj=a, count=adj_counts[a])
        window['hidden'] = [count(adj) for adj in hidden]
        window['open'] = [count(adj) for adj in open]
        window['blind'] = [count(adj) for adj in blind]

        return window


def get_user_profile(user_id):
    graph = facebook.GraphAPI(session['oauth_token'])
    result = graph.get_object(user_id, fields='id,name,picture.type(large),first_name,last_name')
    #   {
    #       "id": "704064176",
    #       "name": "Doron Tohar",
    #       "picture": {
    #           "data": {
    #               "url": "https://...",
    #               "is_silhouette": false
    #           }
    #       }
    #   }
    profile = {
        'id': result[u'id'],
        'name': result[u'name'],
        'first_name': result[u'first_name'],
        'last_name': result[u'last_name'],
        'pic_url': result[u'picture'][u'data'][u'url']
    }
    return profile


@app.route('/home')
def home():
    if 'error_reason' in request.args:
        return "Sorry, if you want to play 'Who Am I' you need to authorize it"
    elif request.method == 'POST':
        if not read_user_token():
            return build_authenticate_redirect()
    elif not session.get('user_id'):
        return redirect('https://apps.facebook.com/d_who-am-i')
    window = calc_window()

    profile = get_user_profile(session['user_id'])

    return render_template('home.html', window=window, profile=profile)


def load_results(submitter_id, subject_id):
    with closing(connect_db()) as db:
        cur = db.execute('select adjective from results where submitter_id=? and subject_id=?', [submitter_id, subject_id])
        return [row[0] for row in cur.fetchall()]


@app.route('/self-test')
def self_test():
    selected = load_results(session['user_id'], session['user_id'])
    return render_template('self-test.html', action=url_for('save_self_test'), adjectives=adjectives, selected=selected)


def update_results(submitter_id, subject_id):
    with closing(connect_db()) as db:
        db.execute('delete from results where submitter_id=? and subject_id=?', [submitter_id, subject_id])
        adjs = [adj[2:] for adj in request.form if adj.startswith('a_')]
        for adj in adjs:
            db.execute('insert into results (submitter_id, subject_id, adjective) values (?, ?, ?)',
                       [submitter_id, subject_id, adj])
        db.commit()


def get_friend_ids():
    with closing(connect_db()) as db:
        cur = db.execute('select distinct submitter_id from results')
        return [row[0] for row in cur.fetchall()]


@app.route('/friend-test')
def friend_test():
    friend_ids = get_friend_ids()
    return render_template('friend-test.html', action=url_for('save_friend_test'), adjectives=adjectives, friend_ids=friend_ids)


@app.route('/friend-test', methods=['POST'])
def save_friend_test():
    submitter_id = session['user_id']
    subject_id = request.form['subject_id']
    update_results(submitter_id, subject_id)
    return redirect(url_for('home'))


@app.route('/self-test', methods=['POST'])
def save_self_test():
    submitter_id = session['user_id']
    update_results(submitter_id, submitter_id)
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run()
