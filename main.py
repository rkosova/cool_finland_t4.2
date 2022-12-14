import sqlite3
from datetime import date, timedelta, datetime
from flask import Flask, render_template, request, url_for, flash, redirect, session, g, jsonify
from forms import RegistrationForm, LoginForm
from functools import wraps
import os
import json
from passlib.hash import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_val(email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    users = conn.execute('select * from "users"').fetchall()
    conn.close()
    
    for user in users:
        if user["email"] == email:
            if bcrypt.verify(password, user["password"]):
                return True              

    return False

@app.route('/data')
def return_data():
    conn = get_db_connection()
    cur = conn.cursor()
    SQL = "select weight_amount, start from deliveries;"
    cur.execute(SQL)
    result_list = cur.fetchall()
    deliveries_list = cur.description
    cur.close()
    conn.close()
        # main part
    column_list = []
    for i in deliveries_list:
        column_list.append(i[0])

    global jsonData_list
    jsonData_list = []
    for row in result_list:
        data_dict = {}
        for i in range(len(column_list)):
            data_dict[column_list[i]] = row[i]
        data_dict['title'] = "Reserved amount: " + str(data_dict['weight_amount'])
        del data_dict['weight_amount']
        jsonData_list.append(data_dict)
    json_object = json.dumps(jsonData_list, indent=4)
    with open("deliveries.json", "w") as outfile:
        outfile.write(json_object)
    with open("deliveries.json", "r") as input_data:
        return input_data.read()

@app.route("/admin")
def admin():
    conn = get_db_connection()
    cur = conn.cursor()
    users = conn.execute('select * from "users"').fetchall()
    conn.close()
    return render_template("admin.html", users=users)


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if request.method == 'GET':
        return render_template('register.html', form=form, method=request.method)
    else:
        valid = form.validate_on_submit()
        if valid:
            email = form.email.data
            passw = form.passw.data
            comp = form.comp.data
            rep_name = form.rep_name.data
            rep_lname = form.rep_lname.data
            rep_pnum = form.rep_pnum.data

            hasher = bcrypt.using(rounds=13)
            h_passw = hasher.hash(passw)


            conn = get_db_connection()
            cur = conn.cursor()

            print(f"{email} {passw} {h_passw} {comp} {rep_name} {rep_lname} {rep_pnum}")

            conn.execute(
                'insert into "users" (email, password, comp_name, rep_name, rep_lname, rep_pnumber, priority) values (?, ?, ?, ?, ?, ?, ?)'
                , (email, h_passw, comp, rep_name, rep_lname, rep_pnum, False))

            conn.commit()
            conn.close()
            return render_template('index.html', form=form, valid=valid, method=request.method)

        else:
           return render_template('register.html', form=form, valid=not valid, method=request.method)



@app.route("/login", methods=['GET', 'POST'])
def login():

    form = LoginForm()
    if request.method == 'POST':
        session.pop('user', None)
        form_valid = form.validate_on_submit()
        if form_valid:
            email = form.email.data
            passw = form.passw.data
            rm = form.rem.data
            print("Form is valid")
            print(f"{email} {passw} {rm}")
            logged = login_val(email, passw)
            print(logged)
            conn = get_db_connection()
            s = (email)
            user = conn.execute("select * from users where email =?", (s,))
            if user is not None:
                data =user.fetchone()
                password = data['password']
                print(data['password'])
                if bcrypt.verify(passw, password):
                    print("Correct password")
                    app.logger.info('Password Matched')
                    session['logged_in'] = True 
                    session['user'] = data['email']
                    session['user_id'] = data['id']
                    session['company_name'] = data['comp_name']
                    flash('You are now logged in','success')
                    return render_template("index.html")
                # Close Connection
                user.close()
        else:
            return render_template("login.html", form=form, error=2)
    elif request.method == 'GET':
        return render_template('login.html', form=form)


@app.route('/protected')
def protected():
    if g.user:
        return render_template("protected.html", user=session['user'])
    else: 
        return redirect(url_for("index.html"))
@app.route('/')
def index():
    return render_template("index.html")

@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']

@app.route('/dropsession')
def dropsession():
    session.pop("logged_out", None)
    session.clear()
    render_template('layout.html')
    return redirect('/')

@app.route('/schedule', methods=['GET', 'POST'])
def weightschedule():
    if g.user:
        global enable
        enable = "enable"

        global disabled
        disabled = "disabled"

        global con
        con = sqlite3.connect('database.db',check_same_thread=False)

        global cur
        cur = con.cursor()

        global today
        today = date.today()

        global weight

        global dates
        dates = cur.execute("select weight_amount, start from deliveries;").fetchall()
        global all_Dates
        all_Dates = list
        all_Dates = []
        for i in range(21):
            free = today + timedelta(days=i)
            day_Free = free.strftime('%Y-%m-%d')
            all_Dates.append(day_Free)

        global occupied
        occupied = []
        for occ in dates:
            occupied.append(occ[1])

        if request.method == "POST":
            global c_name
            global v_type
            weight = request.form.get('weight')
            c_name = request.form.get('c_name')
            v_type = request.form.get('v_type')
            
            return redirect(url_for('dayschedule'))
        else:
            return render_template('schedule.html', disabled_switch=disabled, today=today, all_Dates=all_Dates,
                                occupied=occupied)
    else: 
            return redirect('/')

def weightrequire(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            weight
        except NameError:
            return redirect('/schedule')
        return f(*args, **kwargs)

    return decorated_function

@app.route("/schedule/date", methods=['GET', 'POST'])
@weightrequire
def dayschedule():
    global weight
    print("occupied dates:")
    print(occupied)
    weight_Amount = []
    for i in dates:
        if int(i[0]) + int(weight) > 40:
            weight_Amount.append(i[1])
    weight_amount_set = set(weight_Amount)
    occupied_set = set(occupied)

    occupied_w_weight = list(weight_amount_set - occupied_set)
    combined = weight_Amount + occupied_w_weight
    free_dates = set(all_Dates).difference(set(combined))
    sortFreeDates = sorted(free_dates)


    insert = """INSERT INTO deliveries(customer_id,company,v_type,weight_amount,start) VALUES (?,?,?,?,?);"""

    if request.method == "POST":
        userDate = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
        inputDate = datetime.date(userDate)
        data_tuple = (session['user_id'],session['company_name'],v_type, int(weight), inputDate)
        cur.execute(insert, data_tuple)
        con.commit()
        print("Done")
        cur.close()
        del  weight
        return redirect('/')
    else:
        return render_template('schedule_day.html', enable_switch=disabled, disabled_switch=enable, dates=dates,
                               today=today, occupied=occupied, all_Dates=all_Dates, sortFreeDates=sortFreeDates)


if __name__ == '__main__':
    app.run(debug=True)
