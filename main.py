from flask import Flask, render_template, request, abort, jsonify
from flask_login import login_required
from helper import SECRET_KEY
from helper.db.initialise_database import engine, Organization, Person, Document
from helper.db.initialise_database import DocumentAuthorship, OrganizationMembership
from helper.login.login import app_login, login_manager
from sqlalchemy import select, func, extract, and_, inspect
from sqlalchemy.orm import Session
import urllib.parse
import requests
from datetime import datetime
from dateutil.parser import parse


app = Flask(__name__)
app.register_blueprint(app_login)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SESSION_COOKIE_DOMAIN'] = False

login_manager.init_app(app)
login_manager.login_view = 'app_login.login'


@app.route('/')
def index():
    """
    Renders the 'Index' page.

    This route handles the display of the 'Index' page, which provides an overview of the
    information system. The page includes a brief description of the system's purpose and
    its main functionalities.

    Returns:
    - Renders the 'index.html' template.
    """
    return render_template('index.html')


@app.route('/about')
def about():
    """
    Renders the 'About' page.

    This route handles the display of the 'About' page, which provides information about the
    information system. The page includes details about the  system's purpose, instructions for searching,
    publications about the system, and information about the software development and content support.

    Returns:
    - Renders the 'about.html' template.
    """
    return render_template('about.html')


@app.route('/view')
def view():
    """
    Universal view for organization, person, and document.

    This route handles the display of detailed information for an organization, person, or document
    based on the query parameters provided in the request. It expects 'type' and 'id' parameters
    in the request arguments.

    Query Parameters:
    - type (str): The type of object to view ('org', 'person', 'doc').
    - id (int): The ID of the object to view.

    Returns:
    - Renders the 'view.html' template with the data and page context if the object is found.
    - Aborts with a 404 status code if the 'type' is not one of the expected values or if the 'id' is missing.
    """
    if request.args.get('type') not in ['org', 'person', 'doc'] or not request.args.get('id'):
        abort(404)
    viewtype_to_object = {'org': Organization, 'person': Person, 'doc': Document}
    viewtype_to_str = {'org': 'Организация', 'person': 'Персоналия', 'doc': 'Документ'}
    viewtype = request.args.get('type')
    viewid = int(request.args.get('id'))
    obj = viewtype_to_object[viewtype]
    stmt = select(obj).where(obj.id == viewid)
    with Session(engine) as session:
        data = session.execute(stmt).scalar_one_or_none()
        data = data.values_ru()
    page = {'heading': f'{viewtype_to_str[viewtype]}', 'title': f'View {obj.__name__.lower()}',
            'id': viewid, 'type': viewtype}
    if "Фотография" in data:
        data["Фотография"] = f'<img src="{data["Фотография"]}" alt="Фотография" />'
    return render_template('view.html', data=data, page=page)


@app.route('/search')
def search():
    """
    Universal search view for organization, person, and document.

    This route handles the search functionality for organizations, persons, and documents based on the
    query parameters provided in the request. It supports various search types including quick search,
    content search, and specific attribute search.

    Query Parameters:
    - type (str): The type of object to search ('org', 'person', 'doc').
    - quicksearch (str): A quick search term.
    - content (str): A term to search within the bibliography content.
    - fullName (str): The full name of the person to search.
    - firstName (str): The first name of the person to search.
    - lastName (str): The last name of the person to search.
    - patronymic (str): The patronymic of the person to search.
    - birthYear (int): The birth year of the person to search.
    - name (str): The name of the organization or document to search.

    Returns:
    - Renders the 'search.html' template with the search results if any.
    - Returns a JSON response with the search results if applicable.
    - Aborts with a 404 status code if the search type is not recognized.
    """
    page = {'heading': 'Поиск', 'title': 'Search'}
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
        query = select(Person).filter(Person.bibliography.ilike(f'%{content}%')).order_by(Person.surname.collate('C'))
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
                    where_stmt.append((func.lower(Person.surname) == query_list[0].lower())
                                      & (func.lower(Person.name) == query_list[1].lower()))
                elif len(query_list) == 3:
                    where_stmt.append((func.lower(Person.surname) == query_list[0].lower())
                                      & (func.lower(Person.name) == query_list[1].lower())
                                      & (func.lower(Person.patronymic) == query_list[2].lower()))
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
        stmt = select(Person).where(final_where_stmt).order_by(Person.surname.collate('C'))
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
            stmt = select(obj.id, obj.name)\
                .where(func.lower(obj.name)
                       .startswith(query.lower())).order_by(func.lower(obj.name))
        else:
            stmt = select(obj.id, obj.name).order_by(func.lower(obj.name).collate('C'))
        results = []
        with Session(engine) as session:
            data = session.execute(stmt)
            for row in data:
                results.append([obj_type, row[0], row[1]])
        return jsonify(results)
    else:
        abort(404)


@app.route('/new')
@login_required
def new():
    """
    Renders the 'New' page for creating a new organization, person, or document.

    This route handles the display of the 'New' page, which allows users to create a new entry
    for an organization, person, or document based on the query parameters provided in the request.
    It expects a 'type' parameter in the request arguments.

    Query Parameters:
    - type (str): The type of object to create ('org', 'person', 'doc').

    Returns:
    - Renders the 'new.html' template with the necessary data for creating the specified object type.
    - Aborts with a 501 status code if the 'type' parameter is missing or invalid.
    """
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
def edit():
    """
    Renders the 'Edit' page for editing an existing organization, person, or document.
    Admin only

    This route handles the display of the 'Edit' page, which allows users to edit an existing entry
    for an organization, person, or document based on the query parameters provided in the request.
    It expects 'type' and 'id' parameters in the request arguments.

    Query Parameters:
    - type (str): The type of object to edit ('org', 'person', 'doc').
    - id (int): The ID of the object to edit.

    Returns:
    - Renders the 'new.html' template with the necessary data for editing the specified object type.
    - Aborts with a 501 status code if the 'type' or 'id' parameter is missing or invalid.
    """
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
    """
    Saves a new or edited organization, person, or document.

    This route handles the saving of a new or edited entry for an organization, person, or document
    based on the form data provided in the request. It expects a 'type' parameter in the request arguments
    and form data in the request body.

    Query Parameters:
    - type (str): The type of object to save ('org', 'person', 'doc').

    Form Data:
    - Various fields corresponding to the attributes of the specified object type.
    - connection (list): A list of connections to other objects.

    Returns:
    - Renders the 'redirect.html' template to redirect to the search page after saving. [TO BE REMOVED]
    """
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
    """
    Deletes an existing organization, person, or document.

    This route handles the deletion of an existing entry for an organization, person, or document
    based on the query parameters provided in the request. It expects 'type' and 'id' parameters
    in the request arguments.

    Query Parameters:
    - type (str): The type of object to delete ('org', 'person', 'doc').
    - id (int): The ID of the object to delete.

    Returns:
    - Renders the 'redirect.html' template to redirect to the search page after deletion.
    - Aborts with a 501 status code if the 'type' or 'id' parameter is missing or invalid.
    - Aborts with a 404 status code if the object to delete is not found.
    """
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
