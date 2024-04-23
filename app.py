import os
import uuid
import zlib
import hashlib
import pyrebase
import PyPDF2
import firebase_admin
from flask import make_response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from firebase_admin import db
from firebase_admin import auth
from firebase_admin import credentials
from flask import Flask, render_template, request, make_response, session, url_for, redirect

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'

firebaseConfig={'apiKey': "AIzaSyCMQqO6cGLz-0fwmvzRvcoLOk68Bc3_uEc",
  'authDomain': "final-project-efb5b.firebaseapp.com",
  'databaseURL': "https://final-project-efb5b-default-rtdb.firebaseio.com",
  'projectId': "final-project-efb5b",
  'storageBucket': "final-project-efb5b.appspot.com",
  'messagingSenderId': "506356440192",
  'appId': "1:506356440192:web:4cfd5501138fe34f83da65"

}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

script_dir = os.path.dirname(os.path.abspath(__file__))
key_file_path = os.path.join(script_dir, 'serviceAccountKey.json')


cred = credentials.Certificate(key_file_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://final-project-efb5b-default-rtdb.firebaseio.com',
})


UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)




@app.route('/')

def index():

    return render_template('index.html')

@app.route('/login',  methods=['GET', 'POST'])

def login():
    return render_template('loginPage.html')

@app.route('/signup', methods=['GET', 'POST'])

def signup():
    return render_template('signUpPage.html')

# User Sign Up Module

@app.route('/createAccount', methods=['GET', 'POST'])

def createAccount():
    if request.method == "POST":
        pwd0 = request.form['password']
        pwd1 = request.form['password2']
        if pwd0 == pwd1:
            try:
                email = request.form['username']
                password = request.form['password']
                new_user = auth.create_user_with_email_and_password(email, password)
                ref = db.reference('/users')
                ref.push({
                    'email': email
                })
                message = 'User registered successfully!'
                return render_template('signUpPage.html',msg=message)
            except:
                existing_account = 'This email exists'
                return render_template('signUpPage.html',exist_message=existing_account)


# User Login Module

@app.route('/userdashboard', methods=['GET', 'POST'])

def userdashboard():
    if request.method == 'POST':
        email = request.form['username']
        password = request.form['password']
        session['email']=email
        data=None
        try:
            auth.sign_in_with_email_and_password(email,password)
            successful = 'User login successful'
            if email == 'admin@gmail.com':
                return redirect(url_for('listUsers'))
            else:
                ref = db.reference('/files')
                data = ref.order_by_child('username').equal_to(email).get()
                if data:
                    return render_template('userDashboard.html',data=data, smessage=successful)
                else:
                #   noData='no data'
                    return render_template('noData.html')
        except Exception as e:
            print(e)
            unsuccessful = 'Please check your credentials'
            return render_template('loginPage.html', umessage = unsuccessful)


#---Segmentation of file into blocks of fixed size---

block_size = 500
def divide_into_blocks(content, block_size):
    print(len(content))
    blocks = []
    for i in range(0, len(content), block_size):
        blocks.append(content[i:i + block_size])
    return blocks


#---Retrieving contents associated with a block id from firebase---

def retrieve_block_contents(block_id):
    try:
        ref = db.reference('/blocks')
        query = ref.order_by_child('block_id').equal_to(block_id).limit_to_first(1).get()
        if query:
            block_key = next(iter(query.keys()))
            block_contents = query[block_key].get('block_contents', '')
            return block_contents
        else:
            return ''
    except Exception as e:
        print("An error occurred while retrieving block contents:", e)
        return ''

#---Module to convert the file contents retrieved into pdf---

def convert_to_pdf(text):
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=letter)

    lines = text.split('\n')
    top_margin = 720
    bottom_margin = 50
    line_height = 18
    c.setFont("Times-Roman", 14)

    # Start writing text
    y = top_margin
    for line in lines:
        if y - bottom_margin < 0:
            c.showPage()
            c.setFont("Times-Roman", 14)
            y = top_margin
        c.drawString(70, y, line)
        y -= line_height

    c.save()
    buffer.seek(0)
    return buffer


#---Download file by user---

@app.route('/download/<fileName>', methods=['GET','POST'])
def download(fileName):
    try:
        ref= db.reference('/files')
        query = ref.order_by_child('file_name').equal_to(fileName).get()
        if query:
            file_key = next(iter(query.keys()))
            file_as_blocks = query[file_key].get('file_as_blocks', None)
            print(file_as_blocks)
            if file_as_blocks:
                file_contents_for_display = ''
                for value in file_as_blocks:
                    block_contents = retrieve_block_contents(value)
                    file_contents_for_display += block_contents
                #print(file_contents_for_display)
                bytes_utf8_check = file_contents_for_display.encode('utf-8')
                checksum_verify = zlib.adler32(bytes_utf8_check)
                print(checksum_verify)
                checksum_stored = query[file_key].get('file_checksum')
                print(checksum_stored)
                if checksum_verify == checksum_stored:
                    pdf_buffer = convert_to_pdf(file_contents_for_display)
                    response = make_response(pdf_buffer.getvalue())
                    response.headers['Content-Disposition'] = f'attachment; filename={fileName}'
                    response.headers['Content-type'] = 'application/pdf'
                    return response
                else:
                    return 'Error in downloading file : corrupted'
    except Exception as e:
        print("An error occurred:", e)
        return "An error occurred while processing the request", 500


#---Delete file by user---

@app.route('/delete/<name>', methods=['GET','POST'])
def delete(name):
    try:
        ref = db.reference('/files')
        query = ref.order_by_child('file_name').equal_to(name).get()

        if query:
            for key in query:
                ref.child(key).delete()
                print(f"Data associated with file name {name} deleted successfully.")
        else:
            print(f"No data found for file name {name}.")
        return redirect('/stayDashboard')
    except Exception as e:
        print("An error occurred:", e)

#---For rendering file uploading page---

@app.route('/uploadPage', methods=['GET'])

def uploadPage():
    return render_template('uploadFile.html')

#---Retrieve files uploaded by user and display as table---

@app.route('/stayDashboard')
def stayDashboard():
    email=session.get('email',None)
    ref = db.reference('/files')
    data = ref.order_by_child('username').equal_to(email).get()
    if data:
        return render_template('userDashboard.html', data=data)
    else:
        return render_template('noData.html')


#---Module where file upload and processing occurs---

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
    print('File uploaded successfully')

    directory_path = 'uploads'
    try:
        files = os.listdir(directory_path)
        if len(files) == 1:
            file_name = files[0]
            file_path = os.path.join(directory_path, file_name)
            file_as_blocks = {}

            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                print(len(reader.pages))
                end_page = len(reader.pages)
                text=''
                for page_num in range(1, end_page + 1):
                    page = reader.pages[page_num - 1]
                    text += page.extract_text()
                file_size = os.path.getsize(file_path)
                file_size_kb = round(file_size / 1024, 2)
                bytes_utf8 = text.encode('utf-8')
                checksum = zlib.adler32(bytes_utf8)
                print(text)
                print("File name", file_name)
                print("File checksum", checksum)
                print("File size", file_size_kb, "KB")

                blocks = divide_into_blocks(text, block_size)
                print("Number of blocks:", len(blocks))
                for i, block in enumerate(blocks):
                    print("Block", i+1, "size:", len(block), "bytes")
                    #print("Content:")
                    print(block)
                    print(len(block))
                    bytes=block.encode('utf-8')
                    #print(len(bytes))
                    md5_hash = hashlib.md5(bytes).hexdigest()
                    print("MD5 Hash:", md5_hash)
                    ref = db.reference('/blocks')
                    query = ref.order_by_child('md5_hash').equal_to(md5_hash).get()   #---Checking whether duplicate blocks exist---
                    if query:
                        for key, value in query.items():
                            if 'block_id' in value:
                                id = value['block_id']
                                block_id = id
                            else:
                                return None
                    else:
                        block_id = str(uuid.uuid4())      #---Generate id for block---
                        print(block_id)
                        ref = db.reference('/blocks')
                        ref.push({

                            'block_id': block_id,
                            'block_size': len(block),
                            'md5_hash': md5_hash,
                            'block_contents': block
                        })
                    file_as_blocks[i]=block_id     #---File represented as a dictionary of block ids---
            print(file_as_blocks)
            email=session.get('email',None)
            ref = db.reference('/files')
            ref.push({
                'username': email,
                'file_name': file_name,
                'file_size': file_size_kb,
                'file_checksum':checksum,
                'file_as_blocks': file_as_blocks
            })
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            print("No file")
    except FileNotFoundError:
        print(f"Directory '{directory_path}' not found")
    return render_template('uploadFile.html')


@app.route('/status')
def status():
    ref = db.reference('/files')
    data = ref.get()

    total_size = 0
    count = 0
    if data:
        for key, value in data.items():
            count = count+1
            file_size = value.get('file_size', 0)
            total_size += file_size
    ref_blocks = db.reference('/blocks')
    data_blocks = ref_blocks.get()

    size_block = 0
    if data_blocks:
        for key, value in data_blocks.items():
            size = value.get('block_size', 0)
            size_block += size
    total_block_size = total_size- (size_block/1024)
    rounded_size = round(total_block_size, 2)
    return render_template('status.html',size=total_size, count=count, total_block_size=rounded_size)


@app.route('/listUsers')
def listUsers():
    ref = db.reference('/users')
    user_data = ref.get()
    if user_data:
        return render_template('adminDashboard.html', user_data=user_data)



@app.route('/logout')
def logout():
    return redirect(url_for('index'))


@app.route('/gotoAdminDashboard')
def gotoAdminDashboard():
    return redirect(url_for('listUsers'))

if __name__ == '__main__':
    app.run(debug=True)