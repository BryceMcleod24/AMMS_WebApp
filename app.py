from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.utils import secure_filename
from firebase_admin import storage
from datetime import datetime
import uuid

app = Flask(__name__)
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'amms-db.appspot.com'
})

db = firestore.client()
bucket = storage.bucket()

@app.route('/')
def home():
    return render_template('home.html')
    # return render_template('browse_request.html')

@app.route('/tenant')
def tenant():
    return render_template('submit_request.html')

@app.route('/staff')
def staff():
    return render_template('browse_request.html')  # or any other page accessible by staff

@app.route('/manager')
def manager():
    return render_template('manager_options.html')

@app.route('/manager_options')
def manager_options():
    tenants_query = db.collection('tenant_accounts').stream()
    tenants = [tenant.to_dict() for tenant in tenants_query]
    return render_template('manager_options.html', tenants=tenants)

@app.route('/submit_request', methods=['GET', 'POST'])
def submit_request():
    if request.method == 'POST':
        data = request.form
        photo = request.files['photo']
        photo_url = None

        if photo:
            filename = secure_filename(photo.filename)
            blob = bucket.blob(filename)
            blob.upload_from_file(photo)
            photo_url = blob.public_url

        request_id = str(uuid.uuid4())  # Generate unique request ID
        current_time = datetime.now()  # Record current date and time

        db.collection('maintenance_requests').add({
            'request_id': request_id,
            'apartment': data.get('apartment'),
            'area': data.get('area'),
            'description': data.get('description'),
            'photo_url': photo_url,
            'status': 'pending',
            'request_date': current_time
        })
        return redirect(url_for('submit_request'))
    return render_template('submit_request.html')

@app.route('/view_request')
def view_request():
    requests_query = db.collection('maintenance_requests').stream()
    requests = [req.to_dict() for req in requests_query]
    return render_template('view_request.html', requests=requests)

@app.route('/create_tenant', methods=['GET'])
def create_tenant_form():
    return render_template('create_tenant.html')

@app.route('/create_tenant', methods=['POST'])
def create_tenant():
    tenant_data = request.form
    new_tenant_id = db.collection('tenant_accounts').document().id  # Generate new tenant ID
    db.collection('tenant_accounts').document(new_tenant_id).set({
        'tenant_id': new_tenant_id,
        'name': tenant_data['name'],
        'phone': tenant_data['phone'],
        'email': tenant_data['email'],
        'check_in': tenant_data['check_in'],
        'check_out': tenant_data['check_out'],
        'apartment_number': tenant_data['apartment_number']
    })
    return redirect(url_for('home'))  # Redirect to the home page after submission

@app.route('/manage_tenants', methods=['GET', 'POST'])
def manage_tenants():
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id')
        new_apartment_number = request.form.get('new_apartment_number')

        if tenant_id and new_apartment_number:
            db.collection('tenant_accounts').document(tenant_id).update({'apartment_number': new_apartment_number})

    tenants_query = db.collection('tenant_accounts').stream()
    tenants = [tenant.to_dict() for tenant in tenants_query]
    return render_template('manage_tenants.html', tenants=tenants)

@app.route('/delete_tenant/<tenant_id>', methods=['POST'])
def delete_tenant(tenant_id):
    db.collection('tenant_accounts').document(tenant_id).delete()
    return redirect(url_for('manage_tenants'))

@app.route('/browse_request')
def browse_request():
    queries = request.args
    req_query = db.collection('maintenance_requests')

    if 'apartment_number' in queries and queries['apartment_number']:
        req_query = req_query.where('apartment_number', '==', queries['apartment_number'])
    if 'area' in queries and queries['area']:
        req_query = req_query.where('area', '==', queries['area'])
    if 'status' in queries and queries['status']:
        req_query = req_query.where('status', '==', queries['status'])
    if 'start_date' in queries and queries['start_date'] and 'end_date' in queries and queries['end_date']:
        start_date = datetime.strptime(queries['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(queries['end_date'], '%Y-%m-%d')
        req_query = req_query.where('request_date', '>=', start_date).where('request_date', '<=', end_date)

    requests = [doc.to_dict() for doc in req_query.stream()]
    return render_template('browse_request.html', requests=requests)

@app.route('/update_status', methods=['POST'])
def update_status():
    request_id = request.form.get('request_id')
    new_status = request.form.get('new_status')

    if not request_id:
        return "Invalid request ID", 400

    request_ref = db.collection('maintenance_requests').document(request_id)
    request_doc = request_ref.get()

    if not request_doc.exists:
        return "Maintenance request not found", 404

    request_ref.update({'status': new_status})
    return redirect(url_for('browse_request'))

@app.route('/update_request_status', methods=['POST'])
def update_request_status():
    try:
        request_id = request.form['request_id']
        new_status = request.form['new_status']

        request_ref = db.collection('maintenance_requests').document(request_id)
        request_doc = request_ref.get()

        if request_doc.exists:
            request_ref.update({'status': new_status})
            return redirect(url_for('staff'))  # Redirect to the staff page or any other appropriate page
        else:
            return "Maintenance request not found", 404
    except Exception as e:
        return str(e), 500


if __name__ == '__main__':
    app.run(debug=True)
