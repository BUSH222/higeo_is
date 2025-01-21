from flask import Flask, render_template


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/view_org')
def view_organization():
    data = {'org_name': 'org_name',
            'description': 'description',
            'associated_people': 'associated_people',
            'additional_info': 'additional_info'}
    return render_template('view_organization.html', data=data)


@app.route('/view_doc')
def view_document():
    data = {'person': 'person',
            'source': 'source',
            'doc_name': 'doc_name',
            'year': 'year',
            'comment': 'comment',
            'file': 'file',
            'links': 'links'
            }
    return render_template('view_document.html', data=data)


if __name__ == '__main__':
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='localhost', port=5000, debug=True)
