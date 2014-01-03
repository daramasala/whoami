from contextlib import closing
import sqlite3
from flask import Flask, render_template, request, url_for, session
from werkzeug.utils import redirect

DATABASE = '/tmp/whoami.db'
DEBUG = True
SECRET_KEY = 'top secret'

app = Flask(__name__)
app.config.from_object(__name__)


adjectives = ['Judgemental', 'Accepting',
              'Morose', 'Cheerful',
              'Nervous', 'Relaxed',
              'Childish', 'Mature',
              'Vain', 'Modest']


def connect_db():
    return sqlite3.connect(app.config['DATABASE'])


def init_db():
    with closing(connect_db()) as db:
        with app.open_resource('schema.sql', mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()


@app.route('/')
def main():
    return home()


@app.route('/login')
def login():
    return redirect(url_for('static', filename='login.html'))


@app.route('/logout')
def logout():
    session['user_id'] = None
    return redirect('login')


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


@app.route('/home', methods=['POST', 'GET'])
def home():
    if request.method == 'POST':
        session['user_id'] = int(request.form['user_id'])
    elif not session.get('user_id'):
        return redirect(url_for('login'))
    window = calc_window()
    return render_template('home.html', window=window)


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
