from flask import Flask, render_template, request, abort, jsonify
from initialise_database import engine, Organization, Person, Document
from sqlalchemy import select, func, extract, and_
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
    if len(request.args) == 0 or not request.args.get('type'):
        return render_template('search.html', page=page)
    if request.args.get('type') == 'person':
        if len(set(request.args.keys()).intersection({'firstName', 'lastName', 'patronymic'})) == 0:
            query = request.args.get('fullName')
            where_stmt = []
            if query is not None:
                query_list = query.split()
                if len(query_list) == 1:
                    where_stmt.append(func.lower(Person.surname).startswith(query_list[0].lower()))
                elif len(query_list) == 2:
                    where_stmt.append(func.lower(Person.surname) == query_list[0].lower()
                                      & func.lower(Person.name) == query_list[1].lower())
                elif len(query_list) == 3:
                    where_stmt.append(func.lower(Person.surname) == query_list[0].lower()
                                      & func.lower(Person.name) == query_list[1].lower()
                                      & func.lower(Person.patronymic) == query_list[2].lower())
            year_query = request.args.get('birthYear')
            if year_query is not None:
                where_stmt.append(extract('year', Person.birth_date) == int(year_query))
        else:
            firstname = request.args.get('firstName')
            lastname = request.args.get('lastName')
            patronymic = request.args.get('patronymic')
            year_query = request.args.get('birthYear')
            where_stmt = []
            if firstname is not None:
                where_stmt.append(func.lower(Person.name).startswith(firstname.lower()))
            if lastname is not None:
                where_stmt.append(func.lower(Person.surname).startswith(lastname.lower()))
            if patronymic is not None:
                where_stmt.append(func.lower(Person.patronymic).startswith(patronymic.lower()))
            if year_query is not None:
                where_stmt.append(extract('year', Person.birth_date) == int(year_query))

        final_where_stmt = and_(*where_stmt) if where_stmt else True
        stmt = select(Person).where(final_where_stmt)
        results = []
        with Session(engine) as session:
            data = session.execute(stmt)
            for person_row in data:
                person = person_row[0]
                results.append(['person', person.id, str(person)])
        return jsonify(results)
    elif request.args.get('type') in ['org', 'doc']:  # Name only search
        obj_type = request.args.get('type')
        obj = {'org': Organization, 'doc': Document}[obj_type]
        query = request.args.get('name')
        print(query)
        if query is not None:
            stmt = select(obj.id, obj.name).where(func.lower(obj.name).startswith(query.lower()))
        else:
            stmt = select(obj.id, obj.name)
        results = []
        with Session(engine) as session:
            data = session.execute(stmt)
            for row in data:
                results.append([obj_type, row[0], row[1]])
        return jsonify(results)
    else:
        abort(418)


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
