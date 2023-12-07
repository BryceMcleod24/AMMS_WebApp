from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from werkzeug.utils import secure_filename
from firebase_admin import storage

# Initialize Firebase Admin with the service account and specify the storageBucket
app = Flask(__name__)
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'amms-db.appspot.com'
})

# Initialize Firestore and Storage clients
db = firestore.client()
bucket = storage.bucket()

@app.route('/')
def home():
    return render_template('home.html')
    # return render_template('submit_request.html')
    # return render_template('browse_request.html')
    # return render_template('create_tenant.html')

@app.route('/tenant')
def tenant():
    return render_template('submit_request.html')

@app.route('/staff')
def staff():
    return render_template('view_request.html')  # or any other page accessible by staff

@app.route('/manager')
def manager():
    # return render_template('create_tenant.html')  # or any other page accessible by manager
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
        if not data.get('tenant_id') or not data.get('apartment'):
            return "Error: Missing required fields", 400

        photo = request.files['photo']

        if photo:
            # Ensure the filename is safe, e.g., "my_picture.jpg"
            filename = secure_filename(photo.filename)

            # Create a Cloud Storage bucket reference
            bucket = storage.bucket()

            # Create a new blob (file) in the bucket
            blob = bucket.blob(filename)

            # Upload the file
            blob.upload_from_file(photo)

            # Get the URL of the uploaded file
            photo_url = blob.public_url
        else:
            photo_url = None

        # Store other data along with photo URL in Firestore
        db.collection('maintenance_requests').add({
            'tenant_id': data.get('tenant_id'),
            'apartment': data.get('apartment'),
            'area': data.get('area'),
            'description': data.get('description'),
            'photo_url': photo_url,
            'status': 'pending'  # Default status
        })
        return redirect(url_for('submit_request'))
    return render_template('submit_request.html')


# Route to View Requests
@app.route('/view_request')
def view_request():
    docs = db.collection('maintenance_requests').stream()
    requests = [doc.to_dict() for doc in docs]
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

# Route to Manage Tenant Accounts
@app.route('/manage_tenants', methods=['GET', 'POST'])
def manage_tenants():
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id')
        new_apartment_number = request.form.get('new_apartment_number')

        if tenant_id and new_apartment_number:
            # Update the apartment number of the specified tenant
            db.collection('tenant_accounts').document(tenant_id).update({'apartment_number': new_apartment_number})

    # Fetch all tenants from Firestore
    tenants_query = db.collection('tenant_accounts').stream()
    tenants = [tenant.to_dict() for tenant in tenants_query]
    return render_template('manage_tenants.html', tenants=tenants)

@app.route('/delete_tenant/<tenant_id>', methods=['POST'])
def delete_tenant(tenant_id):
    # Deleting the tenant from Firestore
    db.collection('tenant_accounts').document(tenant_id).delete()
    return redirect(url_for('manage_tenants'))

@app.route('/browse_request')
def browse_request():
    queries = request.args
    req_query = db.collection('maintenance_requests')

    # Check if each filter parameter is provided and not empty before applying it
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

    # Make sure to retrieve all fields of each request
    requests = [doc.to_dict() for doc in req_query.stream()]
    return render_template('browse_request.html', requests=requests)

# @app.route('/update_request_status/<request_id>', methods=['POST'])
# def update_request_status(request_id):
#     # Function implementation
#     new_status = request.form.get('new_status')
#     db.collection('maintenance_requests').document(request_id).update({'status': new_status})
#     return redirect(url_for('browse_request'))

@app.route('/update_status', methods=['POST'])
def update_status():
    request_id = request.form.get('request_id')
    new_status = request.form.get('new_status')

    if not request_id:
        return "Error: No request ID provided", 400

    request_ref = db.collection('maintenance_requests').document(request_id)
    if not request_ref.get().exists:
        return "Maintenance request not found", 404

    request_ref.update({'status': new_status})
    return redirect(url_for('browse_request'))

if __name__ == '__main__':
    app.run(debug=True)
