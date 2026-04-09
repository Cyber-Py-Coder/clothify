from flask import Flask, render_template,request, session, redirect, url_for, flash
import mysql.connector
import uuid
from datetime import timedelta

app=Flask(__name__)
app.permanent_session_lifetime = timedelta(days=1)

app.secret_key='secret123'
upload_folder = "static/uploads"

mydb=mysql.connector.connect(
    host='clothify-clothify.d.aivencloud.com',
    user='avnadmin',
    password='AVNS_i_QwNQUWmZ0svAl5VPs',
    database='clothify',
    port=24620,
    ssl_ca="ssl/ca.pem",
    ssl_verify_cert=True
)

@app.route('/')
def home():
    if 'shop_name' in session:
        return redirect(url_for('dash'))
    elif "delivery_name" in session:
        return redirect(url_for('delivery_dash'))
    
    if 'customer_name' in session:
        return redirect(url_for('cus_dash'))

    return render_template('home.html') #home template


#---------------------CUSTOMER START-------------------------------------
@app.route('/customer_registration')
def cus_reg():
    return render_template('cust_reg.html') #customer registration template

@app.route('/custo', methods=['get', 'post']) #customer backend registration
def custo():
    name=request.form.get('fullname')
    email=request.form.get('email')
    phone=request.form.get('phone')
    address=request.form.get('address')
    latitude=request.form.get('latitude')
    longitude=request.form.get('longitude')
    password=request.form.get('password')

    cursor=mydb.cursor()
    query='''insert into customers(name, email, address, latitude, longitute, password, phone)
                   values(%s, %s, %s, %s, %s, %s, %s)'''
    values = (name, email, address, latitude, longitude, password, phone)
    cursor.execute(query, values)
    mydb.commit()
    cursor.close()

    return render_template("home.html")

@app.route('/customer_login')
def Cus_login():
    return render_template("customer_login.html") #customer login template

@app.route('/customer_dashboad')
def cus_dash():  #customer dashboard login only if customer log in
    if 'customer_name' not in session:
        return redirect(url_for('Cus_login'))
    return render_template('index.html', name=session['customer_name'])

@app.route('/login_submit', methods=["GET", "POST"])
def submit_login():     #customer login with redirection to index page
    phone=request.form.get('phone')
    password=request.form.get('password')

    cursor = mydb.cursor(dictionary=True)
    query='select id, name from customers where phone=%s and password=%s'
    cursor.execute(query, (phone, password))
    customer=cursor.fetchone()
    cursor.close()
    if customer:
        session.permanent=True
        session['customer_id']=customer['id']
        session['customer_name'] = customer['name']
        return redirect(url_for('cus_dash'))
    
    return render_template("customer_login.html", credential="Wrong Credentials")

#Customer portal inner parts | LOGOUT----------------------------------
@app.route('/customer_logout')
def cust_logout():
    session.pop('customer_name', None)
    session.pop('customer_id', None)
    return redirect(url_for('home'))

@app.route('/jeans')
def jeans():
    if "customer_name" in session:
        cursor=mydb.cursor(dictionary=True)
        query='''select product.id, product_name, shop_name, size, photo, price from product inner join shopkeeper on product.shop_id = shopkeeper.id where product_category="jeans"'''
        cursor.execute(query)
        products=cursor.fetchall()
        cursor.close()
        return render_template('jeans.html', products=products)
    return redirect(url_for('home'))

@app.route('/shirts')
def shirts():
    if "customer_name" in session:
        cursor=mydb.cursor(dictionary=True)
        query = '''
            SELECT product.id, product_name, shop_name, size, photo, price
            FROM product
            INNER JOIN shopkeeper ON product.shop_id = shopkeeper.id
            WHERE product_category = 'Shirts'
            '''
        cursor.execute(query)
        products=cursor.fetchall()
        cursor.close()
        return render_template('shirts.html', products=products)
    return redirect(url_for('home'))

#add to cart------------------------------------

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):

    if 'customer_id' not in session:
        return redirect(url_for('Cus_login'))

    customer_id = session['customer_id']
    cursor = mydb.cursor()

    # Simple insert
    cursor.execute(
        "INSERT INTO cart (customer_id, product_id) VALUES (%s, %s)",
        (customer_id, product_id)
    )

    mydb.commit()
    cursor.close()

    return redirect(request.referrer)  # back to the page

@app.route('/cart')
def view_cart():

    # Check if customer logged in
    if 'customer_id' not in session:
        return redirect(url_for('Cus_login'))

    customer_id = session['customer_id']
    cursor = mydb.cursor(dictionary=True)

    # Fetch products in cart
    query = """
    SELECT cart.id AS cart_id, product.product_name, product.price, product.photo
    FROM cart
    JOIN product ON cart.product_id = product.id
    WHERE cart.customer_id = %s
    """
    cursor.execute(query, (customer_id,))
    items = cursor.fetchall()
    cursor.close()

    # Calculate total price
    total = 0
    for item in items:
        total += float(item['price'])  # Convert to float for safety

    # Render cart template with items and total
    return render_template('add_cart.html', items=items, total=total)

@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):

    if 'customer_id' not in session:
        return redirect(url_for('Cus_login'))

    cursor = mydb.cursor()
    # Only delete if belongs to logged in customer
    cursor.execute("DELETE FROM cart WHERE id=%s AND customer_id=%s", 
                   (cart_id, session['customer_id']))
    mydb.commit()
    cursor.close()

    return redirect(url_for('view_cart'))

#by ai-------------- only checkout in customer
@app.route('/checkout')
def checkout():

    if 'customer_id' not in session:
        return redirect(url_for('Cus_login'))

    customer_id = session['customer_id']
    cursor = mydb.cursor(dictionary=True)

    # 1️⃣ Create main order
    cursor.execute("INSERT INTO orders (customer_id) VALUES (%s)", (customer_id,))
    mydb.commit()

    order_id = cursor.lastrowid

    # 2️⃣ Get cart items with shop_id
    query = """
    SELECT cart.product_id, product.price, product.shop_id
    FROM cart
    JOIN product ON cart.product_id = product.id
    WHERE cart.customer_id = %s
    """
    cursor.execute(query, (customer_id,))
    cart_items = cursor.fetchall()

    # 3️⃣ Insert into order_items
    for item in cart_items:
        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, shop_id, quantity, price)
            VALUES (%s, %s, %s, %s, %s)
        """, (order_id, item['product_id'], item['shop_id'], 1, item['price']))

    # 4️⃣ Clear cart
    cursor.execute("DELETE FROM cart WHERE customer_id=%s", (customer_id,))
    mydb.commit()
    cursor.close()

    return "Order Placed Successfully!"

@app.route('/my_orders')
def my_orders():

    if 'customer_id' not in session:
        return redirect(url_for('Cus_login'))

    customer_id = session['customer_id']
    cursor = mydb.cursor(dictionary=True)

    query = """
    SELECT orders.id AS order_id, orders.order_date,
           product.product_name, product.photo,
           order_items.price
    FROM orders
    JOIN order_items ON orders.id = order_items.order_id
    JOIN product ON order_items.product_id = product.id
    WHERE orders.customer_id = %s
    ORDER BY orders.id DESC
    """

    cursor.execute(query, (customer_id,))
    orders = cursor.fetchall()
    cursor.close()

    return render_template('my_orders.html', orders=orders)

#--------------------------DELIVERY START----------------------------------------------

@app.route('/delivery_registration')
def del_reg():
    return render_template('del_reg.html') #delivery registration template

@app.route('/delivery', methods=["GET", "POST"]) #deliver registration backend
def delivero(): 
    name=request.form.get('fullname')
    email=request.form.get('email')
    phone=request.form.get('phone')
    address=request.form.get('address')
    latitude=request.form.get('latitude')
    longitude=request.form.get('longitude')
    password=request.form.get('password')
    bikenumber=request.form.get('bikenumber')

    cursor=mydb.cursor()
    query='''insert into delivery(name, email, address, latitude, longitute, password, phone, bikenumber)
                   values(%s, %s, %s, %s, %s, %s, %s, %s)'''
    values = (name, email, address, latitude, longitude, password, phone, bikenumber)
    cursor.execute(query, values)
    mydb.commit()
    cursor.close()

    return render_template('home.html')

@app.route("/login/delivery")
def deliver_login_page():
    return render_template("delivery_login.html")

@app.route('/delivery_login_submit', methods=['post', 'get'])
def delivery_login_submit():
    if 'delivery_name' in session:
        return redirect(url_for('delivery_dash'))

    phone=request.form.get("phone")
    password=request.form.get("password")
    cursor=mydb.cursor(dictionary=True)
    query='select id, name from delivery where phone=%s and password=%s'
    cursor.execute(query, (phone, password))
    user=cursor.fetchone()
    cursor.close()
    if user:
        session['delivery_id'] = user['id']
        session['delivery_name']= user['name']
        return render_template('delivery_portal.html', name=session['delivery_name'])
    
    return render_template('delivery_login.html', credential="wrong Credential!")

# inside delivery side
@app.route('/delivery_dash')
def delivery_dash():
    if "delivery_name" in session:
        return render_template("delivery_portal.html")
    return redirect(url_for('deliver_login_page'))

#by ai for delivery boy

@app.route('/api/new_orders')
def api_new_orders():
    if 'delivery_id' not in session:
        return {"status": "error", "message": "Not logged in"}, 401

    cursor = mydb.cursor(dictionary=True)
    query = """
    SELECT orders.id AS order_id,
           orders.order_date,
           customers.name AS customer_name,
           customers.phone AS customer_phone,
           shopkeeper.shop_name,
           shopkeeper.phone AS shop_phone,
           product.product_name,
           product.photo,
           order_items.price
    FROM orders
    JOIN order_items ON orders.id = order_items.order_id
    JOIN product ON order_items.product_id = product.id
    JOIN shopkeeper ON order_items.shop_id = shopkeeper.id
    JOIN customers ON orders.customer_id = customers.id
    WHERE orders.delivery_status='Pending'
    
    ORDER BY orders.order_date ASC
    """
    cursor.execute(query)
    orders = cursor.fetchall()
    cursor.close()

    return {"status": "success", "orders": orders}

@app.route('/accept_order/<int:order_id>')
def accept_order(order_id):
    if 'delivery_id' not in session:
        return redirect(url_for('delivery_login'))

    delivery_id = session['delivery_id']
    cursor = mydb.cursor(dictionary=True)

    # Check if order already accepted
    cursor.execute("SELECT delivery_status FROM orders WHERE id=%s", (order_id,))
    order = cursor.fetchone()

    if order['delivery_status'] != 'Pending':
        cursor.close()
        return "Order Already Accepted by another delivery boy."

    cursor.execute("""
        UPDATE orders
        SET delivery_boy_id=%s, delivery_status='Accepted'
        WHERE id=%s
    """, (delivery_id, order_id))
    mydb.commit()
    cursor.close()

    return redirect(url_for('delivery_dash'))

@app.route('/delivery_history')
def delivery_history():
    if 'delivery_id' not in session:
        return redirect(url_for('delivery_login'))

    delivery_id = session['delivery_id']
    cursor = mydb.cursor(dictionary=True)
    query = """
    SELECT orders.id AS order_id,
           orders.order_date,
           orders.delivery_status,
           customers.name AS customer_name,
           customers.phone AS customer_phone,
           shopkeeper.shop_name,
           shopkeeper.phone AS shop_phone,
           product.product_name,
           product.photo,
           order_items.price
    FROM orders
    JOIN order_items ON orders.id = order_items.order_id
    JOIN product ON order_items.product_id = product.id
    JOIN shopkeeper ON order_items.shop_id = shopkeeper.id
    JOIN customers ON orders.customer_id = customers.id
    WHERE orders.delivery_boy_id=%s
    ORDER BY orders.order_date DESC
    """
    cursor.execute(query, (delivery_id,))
    orders = cursor.fetchall()
    cursor.close()

    return render_template('delivery_history.html', orders=orders)

#------------------SHOPKEEPER START-------------------------------------------------------------
@app.route('/shopkeeper_registration')
def shop_reg():
    return render_template('shop_reg.html') #shopkeeper registration template

@app.route('/shop', methods=["GET", "POST"]) #shopkeepr backend registration
def shopo():
    name=request.form.get('fullname')
    email=request.form.get('email')
    phone=request.form.get('phone')
    address=request.form.get('address')
    latitude=request.form.get('latitude')
    longitude=request.form.get('longitude')
    password=request.form.get('password')
    shopname=request.form.get('shopname')

    cursor=mydb.cursor()
    query='''insert into shopkeeper(name, email, address, latitude, longitute, password, phone, shop_name)
                   values(%s, %s, %s, %s, %s, %s, %s, %s)'''
    values = (name, email, address, latitude, longitude, password, phone, shopname)
    cursor.execute(query, values)
    mydb.commit()
    cursor.close()

    return render_template('shopkeeper_portal.html')

@app.route('/shopkeeper_login')
def sho_login(): #shopkeeper's login template
    return render_template('shop_login.html')

@app.route('/shop_login_submit', methods=["POST", "GET"])
def shop_login():  # shopkeeper login portal with portal redirection
    if 'shop_name' in session:
        return redirect(url_for('dash'))
    
    phone = request.form.get('phone')
    password = request.form.get('password')

    cursor = mydb.cursor(dictionary=True)
    query = 'select id, shop_name from shopkeeper where phone=%s and password=%s'
    cursor.execute(query, (phone, password))
    user = cursor.fetchone()
    cursor.close()

    if user:
        # ✅ SESSION ADD HERE
        session['shop_id'] = user['id']
        session['shop_name'] = user['shop_name']

        return render_template('shopkeeper_portal.html', name=user['shop_name'])

    return render_template("shop_login.html", credential="Wrong Credentials")

#inner shop portal routes------------------------------------
@app.route('/product_manage')
def pro_man():
    if 'shop_name' not in session:
        return redirect(url_for('shop_login'))  # login page par bhej do
    
    cursor=mydb.cursor(dictionary=True)
    shop_id= session['shop_id']
    query=('''select * from product where shop_id=%s''')
    cursor.execute(query, (shop_id,))
    products=cursor.fetchall()
    cursor.close()
    return render_template('product_management.html', products=products)

@app.route('/add_product', methods=['POST'])
def add_product():

    if 'shop_id' not in session:
        return redirect(url_for('shop_login'))

    product_name=request.form.get('product_name')
    size=request.form.get('size')
    gender=request.form.get('gender')
    category =request.form.get('category')
    photo=request.files['photo']
    price=request.form.get('price')

    if photo:
        filename= photo.filename
        unique_filename= str(uuid.uuid1())+ "_" +filename
        photo.save(upload_folder+'/'+unique_filename)
        shop_id =session['shop_id'] 
        cursor = mydb.cursor()
        query='''insert into product (shop_id, product_name, size, gender, product_category, photo, price)
            values (%s, %s, %s, %s, %s, %s, %s)'''
        cursor.execute(query, (shop_id, product_name, size, gender, category, unique_filename, price ))
        mydb.commit()
        cursor.close()
        flash("Product add successfully", "success")
    return redirect(url_for('pro_man'))
        

@app.route('/dashboard')
def dash():
    if 'shop_name' not in session:
        return redirect(url_for('shop_login'))
    
    return render_template('shopkeeper_portal.html')

#by ai shop order show

@app.route('/shop_orders')
def shop_orders():

    if 'shop_id' not in session:
        return redirect(url_for('shop_login'))

    shop_id = session['shop_id']
    cursor = mydb.cursor(dictionary=True)

    query = """
    SELECT orders.id AS order_id, 
           orders.order_date,
           customers.name AS customer_name,
           product.product_name,
           product.photo,
           order_items.price
    FROM order_items
    JOIN orders ON order_items.order_id = orders.id
    JOIN product ON order_items.product_id = product.id
    JOIN customers ON orders.customer_id = customers.id
    WHERE order_items.shop_id = %s
    ORDER BY orders.id DESC
    """

    cursor.execute(query, (shop_id,))
    orders = cursor.fetchall()
    cursor.close()

    return render_template('shop_orders.html', orders=orders)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

#----------------------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
