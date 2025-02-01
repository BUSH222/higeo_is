from flask import Flask, render_template, request, abort
from initialise_database import engine, Organization, Person, Document
from sqlalchemy import select
from sqlalchemy.orm import Session


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/view')
def view():  # universal view for organization, person, document
    if request.args.get('type') not in ['org', 'person', 'doc'] or not request.args.get('id'):
        abort(404)
    viewtype_to_object = {'org': Organization, 'person': Person, 'doc': Document}
    viewtype = request.args.get('type')
    viewid = int(request.args.get('id'))
    obj = viewtype_to_object[viewtype]
    stmt = select(obj).where(obj.id == viewid)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        data = data.values_ru()
        print(data)

    page = {'heading': f'{obj.__name__}', 'title': f'View {obj.__name__.lower()}'}

    return render_template('view.html', data=data, page=page,)


@app.route('/search')
def search():  # universal search view for organization, person, document
    page = {'heading': 'Search page', 'title': 'Search'}
    return render_template('search.html', page=page)


@app.route('/new')
def new():  # admin only new record generator
    page = {'heading': 'New document', 'title': 'Search'}
    data = {'person': 'person',
            'source': 'source',
            'doc_name': 'doc_name',
            'year': 'year',
            'comment': 'comment',
            'file': 'file',
            'links': 'links'
            }
    return render_template('new.html', page=page, data=data)


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='localhost', port=5000, debug=True)
