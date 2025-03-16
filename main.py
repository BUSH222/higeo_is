from flask import Flask, render_template, request, abort, jsonify
from flask_login import login_required
from helper.db.initialise_database import engine, Organization, Person, Document
from helper.db.initialise_database import DocumentAuthorship, OrganizationMembership
from helper.login.login import app_login, login_manager
from sqlalchemy import select, func, extract, and_, inspect
from sqlalchemy.orm import Session
# from secrets import token_urlsafe
import urllib.parse
import requests
from datetime import datetime
from dateutil.parser import parse


app = Flask(__name__)
app.register_blueprint(app_login)
app.config['SECRET_KEY'] = '123'  # token_urlsafe(16)

login_manager.init_app(app)
login_manager.login_view = 'app_login.login'


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
    page = {'heading': f'{obj.__name__}', 'title': f'View {obj.__name__.lower()}',
            'id': viewid, 'type': viewtype}
    return render_template('view.html', data=data, page=page)


@app.route('/search')
def search():  # universal search view for organization, person, document
    page = {'heading': 'Search page', 'title': 'Search'}
    if len(request.args) == 0 or not request.args.get('type'):
        return render_template('search.html', page=page)
    if request.args.get('quicksearch'):
        args = dict(request.args)
        args.pop('quicksearch')
        results = requests.get(request.base_url + '?' + urllib.parse.urlencode(args), verify=False)
        out_res = list(results.json())
        return render_template('search.html', page=page, results=out_res)
    elif request.args.get('content'):
        content = request.args.get('content')
        query = select(Person).filter(Person.bibliography.ilike(f'%{content}%')).order_by(Person.surname)
        results = []
        with Session(engine) as session:
            data = session.execute(query)
            for person_row in data:
                person = person_row[0]
                results.append(['person', person.id, str(person)])
        return jsonify(results)
    elif request.args.get('type') == 'person':
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
        stmt = select(Person).where(final_where_stmt).order_by(Person.surname)
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
        if query is not None:
            stmt = select(obj.id, obj.name).where(func.lower(obj.name).startswith(query.lower())).order_by(obj.name)
        else:
            stmt = select(obj.id, obj.name).order_by(obj.name)
        results = []
        with Session(engine) as session:
            data = session.execute(stmt)
            for row in data:
                results.append([obj_type, row[0], row[1]])
        return jsonify(results)
    else:
        abort(418)


@app.route('/new')
@login_required
def new():  # admin only new record generator
    if len(request.args) != 1 or not request.args.get('type'):
        abort(501)
    obj_type = request.args.get('type')
    title_converter = {'org': 'organization', 'person': 'person', 'doc': 'document'}
    page = {'heading': f'New {title_converter[obj_type]}', 'title': f'New {title_converter[obj_type]}'}
    obj_dict = {'org': Organization, 'person': Person, 'doc': Document}
    obj = obj_dict[obj_type]

    mapper = inspect(obj)
    data_fin = dict()
    for column in mapper.attrs:
        if column.key not in ['organizations', 'documents', 'members', 'authors'] and column.key != 'id':
            data_fin[column.key] = ''
    print(data_fin)
    data2 = {}
    if obj_type == 'person':
        data2 = {'doc': [], 'org': []}
    elif obj_type == 'doc':
        data2 = {'person': []}
    elif obj_type == 'org':
        data2 = {'person': []}

    return render_template('new.html', page=page, data1=data_fin, data2=data2, obj_type=obj_type)


@app.route('/edit')
@login_required
def edit():  # admin only record editor, same template
    page = {'heading': 'Edit document', 'title': 'Edit document'}
    if len(request.args) != 2 or not request.args.get('type') or not request.args.get('id'):
        abort(501)
    obj_type = request.args.get('type')
    obj_id = request.args.get('id')
    obj = {'org': Organization, 'person': Person, 'doc': Document}[obj_type]

    stmt = select(obj).where(obj.id == obj_id)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        mapper = inspect(obj)
        data_fin = dict()
        for column in mapper.attrs:
            if not isinstance(getattr(data, column.key), list):
                data_fin[column.key] = getattr(data, column.key)
    data_fin2 = {}
    for k, v in data_fin.items():
        if isinstance(v, list):
            continue
        elif v is None:
            data_fin2[k] = ''
        elif k.endswith('date'):
            data_fin2[k] = parse(str(v)).date()
        else:
            data_fin2[k] = str(v)

    data2 = {}
    with Session(engine) as session:
        obj_real = session.query(obj).filter(obj.id == obj_id).one_or_none()
        assert obj_real is not None
        if obj_type == 'person':
            data2 = {"org": [], "doc": []}
            for doc_authorship in obj_real.documents:  # doc_authorship is DocumentAuthorship
                doc = doc_authorship.document
                data2['doc'].append({'type': 'doc', 'id': doc.id, 'name': doc.name})
            for org_membership in obj_real.organizations:
                org = org_membership.organization
                data2['org'].append({'type': 'org', 'id': org.id, 'name': org.name})
        elif obj_type == 'org':
            data2 = {'person': []}
            for obj_person in obj_real.members:
                person = obj_person.person
                data2['person'].append({'type': 'person', 'id': person.id, 'name': str(person)})
        elif obj_type == 'doc':
            data2 = {'person': []}
            for obj_person in obj_real.authors:
                person = obj_person.person
                data2['person'].append({'type': 'person', 'id': person.id, 'name': str(person)})

    return render_template('new.html', page=page, data1=data_fin2, data2=data2, obj_type=obj_type)


@app.route('/save', methods=['POST'])
@login_required
def save():
    formdata = request.form.to_dict()
    if 'connection' in formdata.keys():
        formdata.pop('connection')
    formdata = {key: (value if value != '' else None) for key, value in formdata.items()}
    connections = request.form.getlist('connection')
    obj_type = request.args.get('type')
    obj = {'org': Organization, 'person': Person, 'doc': Document}[obj_type]
    if formdata.get('id'):
        obj_id = formdata.pop('id')
        stmt = select(obj).where(obj.id == obj_id)
        with Session(engine) as session:
            data = session.execute(stmt).scalar_one_or_none()
            for key, value in formdata.items():
                if value == '' or value == 'None':
                    value = None
                if key.endswith('date') and value is not None:
                    value = datetime.strptime(value, '%Y-%m-%d')
                setattr(data, key, value)
            session.commit()
    else:
        data = obj(**formdata)
        with Session(engine) as session:
            session.add(data)
            session.commit()
            obj_id = data.id

    with Session(engine) as session:
        if obj_type == 'person':
            session.query(DocumentAuthorship).filter(DocumentAuthorship.person_id == obj_id).delete()
            session.query(OrganizationMembership).filter(OrganizationMembership.person_id == obj_id).delete()
        elif obj_type == 'org':
            session.query(OrganizationMembership).filter(OrganizationMembership.organization_id == obj_id).delete()
        elif obj_type == 'doc':
            session.query(DocumentAuthorship).filter(DocumentAuthorship.document_id == obj_id).delete()
        session.commit()
        for connection in connections:
            connection_type, connection_id = connection.split(':')
            if obj == Person:
                if connection_type == 'doc':
                    session.add(DocumentAuthorship(document_id=connection_id, person_id=obj_id))
                    session.commit()
                elif connection_type == 'org':
                    session.add(OrganizationMembership(organization_id=connection_id, person_id=obj_id))
                    session.commit()
            elif obj == Organization:
                session.add(OrganizationMembership(organization_id=obj_id, person_id=connection_id))
                session.commit()
            elif obj == Document:
                session.add(DocumentAuthorship(document_id=obj_id, person_id=connection_id))
                session.commit()
    return render_template('redirect.html', url='/search')


@app.route('/delete')
@login_required
def delete():
    if len(request.args) != 2 or not request.args.get('type') or not request.args.get('id'):
        abort(501)
    obj_type = request.args.get('type')
    obj_id = request.args.get('id')
    obj = {'org': Organization, 'person': Person, 'doc': Document}[obj_type]
    stmt = select(obj).where(obj.id == obj_id)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        if data:
            if obj_type == 'person':
                session.query(DocumentAuthorship).filter(DocumentAuthorship.person_id == obj_id).delete()
                session.query(OrganizationMembership).filter(OrganizationMembership.person_id == obj_id).delete()
            elif obj_type == 'org':
                session.query(OrganizationMembership).filter(OrganizationMembership.organization_id == obj_id).delete()
            elif obj_type == 'doc':
                session.query(DocumentAuthorship).filter(DocumentAuthorship.document_id == obj_id).delete()
            session.delete(data)
            session.commit()
        else:
            abort(404)

    return render_template('redirect.html', url='/search')


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='localhost', port=5000, debug=True, ssl_context='adhoc')
